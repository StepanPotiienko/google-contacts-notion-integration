"""Check if the Google OAuth refresh token is valid; re-authorize if it is not.

Usage:
    python google-contacts-integration/check_refresh_token.py

The script reads credentials from environment variables (or a .env file at the
repo root).  If the token is still valid it exits with code 0.  If it is
expired / revoked it opens a browser for re-authorization, writes the new
refresh token back to the .env file, and (optionally) updates the GitHub
Actions secret GOOGLE_REFRESH_TOKEN via the `gh` CLI.

Required env vars:
    GOOGLE_CLIENT_ID
    GOOGLE_CLIENT_SECRET
    GOOGLE_REFRESH_TOKEN

Optional env vars:
    GITHUB_REPO   – e.g. "StepanPotiienko/google-contacts-notion-integration"
                    If set and `gh` is on PATH the secret is updated automatically.
"""

import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPES = ["https://www.googleapis.com/auth/contacts.readonly"]
DOTENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def _load_env():
    load_dotenv(DOTENV_PATH)
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN")

    missing = [k for k, v in {
        "GOOGLE_CLIENT_ID": client_id,
        "GOOGLE_CLIENT_SECRET": client_secret,
        "GOOGLE_REFRESH_TOKEN": refresh_token,
    }.items() if not v]

    if missing:
        raise SystemExit(f"Missing required environment variable(s): {', '.join(missing)}")

    return client_id, client_secret, refresh_token


def check_token(client_id: str, client_secret: str, refresh_token: str) -> bool:
    """Return True if the refresh token can obtain a valid access token."""
    resp = requests.post(TOKEN_URI, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }, timeout=10)

    data = resp.json()
    if "access_token" in data:
        print("Token is valid.")
        return True

    error = data.get("error", "unknown")
    print(f"Token check failed: {error} – {data.get('error_description', '')}")
    return False


def reauthorize(client_id: str, client_secret: str) -> str:
    """Run the local OAuth2 flow and return the new refresh token."""
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": TOKEN_URI,
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

    if not creds.refresh_token:
        raise RuntimeError("OAuth flow completed but no refresh token was returned.")

    return creds.refresh_token


def update_dotenv(new_token: str):
    """Write GOOGLE_REFRESH_TOKEN into the .env file, creating it if absent."""
    key = "GOOGLE_REFRESH_TOKEN"
    line = f'{key}="{new_token}"\n'

    if DOTENV_PATH.exists():
        content = DOTENV_PATH.read_text(encoding="utf-8")
        pattern = re.compile(rf'^{key}\s*=.*$', re.MULTILINE)
        if pattern.search(content):
            updated = pattern.sub(line.rstrip(), content)
            DOTENV_PATH.write_text(updated, encoding="utf-8")
            print(f".env updated: replaced existing {key}.")
            return
        # Key not present — append it
        if not content.endswith("\n"):
            content += "\n"
        DOTENV_PATH.write_text(content + line, encoding="utf-8")
        print(f".env updated: appended {key}.")
    else:
        DOTENV_PATH.write_text(line, encoding="utf-8")
        print(f".env created with {key}.")


def update_github_secret(new_token: str):
    """Update the GitHub Actions secret via the gh CLI if GITHUB_REPO is set."""
    import shutil
    import subprocess

    repo = os.environ.get("GITHUB_REPO")
    if not repo:
        print("GITHUB_REPO not set — skipping GitHub secret update.")
        return

    if not shutil.which("gh"):
        print("gh CLI not found — skipping GitHub secret update.")
        return

    result = subprocess.run(
        ["gh", "secret", "set", "GOOGLE_REFRESH_TOKEN", "--body", new_token, "--repo", repo],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(f"GitHub secret GOOGLE_REFRESH_TOKEN updated for {repo}.")
    else:
        print(f"Failed to update GitHub secret: {result.stderr.strip()}")


def main():
    client_id, client_secret, refresh_token = _load_env()

    if check_token(client_id, client_secret, refresh_token):
        sys.exit(0)

    print("\nRefresh token is invalid or expired. Starting re-authorization...")
    new_token = reauthorize(client_id, client_secret)
    print("New refresh token obtained.")

    update_dotenv(new_token)
    update_github_secret(new_token)

    print("\nDone. Re-run the sync workflow to resume contact syncing.")


if __name__ == "__main__":
    main()
