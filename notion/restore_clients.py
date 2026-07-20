#!/usr/bin/env python3
"""
Restore trashed CRM pages via Notion internal API (v3).
Uses token_v2 cookie — same session the web app uses for trash view.

Setup:
  1. Open notion.so in Chrome
  2. DevTools → Application → Cookies → notion.so → copy token_v2
  3. SPACE_ID = last hex segment of your workspace URL:
       https://www.notion.so/JD7200-321f1b322cf980379ef4db13337b14c1
                                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  4. Run:
       TOKEN_V2=xxx SPACE_ID=321f1b322cf980379ef4db13337b14c1 python3 restore_crm_trash_v2.py --dry-run
       TOKEN_V2=xxx SPACE_ID=321f1b322cf980379ef4db13337b14c1 python3 restore_crm_trash_v2.py
"""

import os, sys, re, argparse, requests

TOKEN_V2 = os.environ.get("TOKEN_V2", "")
SPACE_ID = os.environ.get("SPACE_ID", "")
DB_ID    = os.environ.get("DB_ID", "300f1b322cf98081937ae3625dfe9f38")

if not TOKEN_V2 or not SPACE_ID:
    print("ERROR: TOKEN_V2 and SPACE_ID required.")
    sys.exit(1)

# Strip URL cruft, keep hex only
m = re.search(r"([0-9a-f]{32})", SPACE_ID.replace("-", ""))
if not m:
    print(f"ERROR: can't parse UUID from SPACE_ID={SPACE_ID!r}")
    sys.exit(1)
SPACE_HEX = m.group(1)

def to_uuid(h: str) -> str:
    h = h.replace("-", "")
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"

SPACE_UUID  = to_uuid(SPACE_HEX)
DB_ID_CLEAN = DB_ID.replace("-", "")

HEADERS = {
    "cookie":       f"token_v2={TOKEN_V2}",
    "content-type": "application/json",
}
BASE = "https://www.notion.so/api/v3"


def fetch_trash() -> list[dict]:
    results, cursor = [], None
    while True:
        body: dict = {
            "query":   "",
            "spaceId": SPACE_UUID,
            "limit":   100,
            "filters": {
                "isDeletedOnly":          True,
                "excludeTemplates":       False,
                "isNavigableOnly":        False,
                "requireEditPermissions": False,
                "ancestors":              [],
                "createdBy":              [],
                "editedBy":               [],
                "lastEditedTime":         {},
                "createdTime":            {},
            },
        }
        if cursor:
            body["startCursor"] = cursor

        resp = requests.post(f"{BASE}/search", headers=HEADERS, json=body)
        if resp.status_code != 200:
            print(f"ERROR /search {resp.status_code}:\n{resp.text[:600]}")
            sys.exit(1)

        data = resp.json()
        results.extend(data.get("results", []))
        if not data.get("hasMore"):
            break
        cursor = data.get("nextCursor")
        print(f"  ... {len(results)} so far")
    return results


def is_crm_page(item: dict) -> bool:
    pid = item.get("parentId", "").replace("-", "")
    if pid == DB_ID_CLEAN:
        return True
    path = item.get("highlight", {}).get("pathText", "")
    return "CRM" in path


def get_title(item: dict) -> str:
    return item.get("title", item.get("id", "?"))


def restore_pages(ids: list[str]) -> bool:
    for i in range(0, len(ids), 100):
        batch = ids[i:i+100]
        resp = requests.post(
            f"{BASE}/restoreBlocks",
            headers=HEADERS,
            json={"blockIds": batch, "spaceId": SPACE_UUID},
        )
        if resp.status_code != 200:
            print(f"ERROR /restoreBlocks {resp.status_code}:\n{resp.text[:400]}")
            return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--all", action="store_true", help="Restore ALL trash, skip CRM filter.")
    args = ap.parse_args()

    print(f"Space UUID : {SPACE_UUID}")
    print(f"DB filter  : {DB_ID_CLEAN}")
    print(f"Mode       : {'DRY RUN' if args.dry_run else 'LIVE'}\n")

    print("Fetching trash...")
    trash = fetch_trash()
    print(f"Total trash items: {len(trash)}\n")

    if not trash:
        print("Trash empty — or token_v2 expired/wrong.")
        return

    print("Sample (first 3):")
    for item in trash[:3]:
        print(f"  {get_title(item)!r:40s} parent={item.get('parentId','')} table={item.get('parentTable','')}")
    print()

    targets = trash if args.all else [t for t in trash if is_crm_page(t)]
    print(f"CRM pages in trash: {len(targets)}")

    if not targets:
        print(
            "\n0 matched. Check sample parentId above vs DB filter.\n"
            "Try --all to dump everything, find correct parentId."
        )
        return

    print("Pages to restore:")
    for t in targets:
        print(f"  {get_title(t)} ({t.get('id','')})")

    if args.dry_run:
        print(f"\nDRY RUN — {len(targets)} pages would be restored.")
        return

    print(f"\nRestoring {len(targets)} pages...")
    if restore_pages([t["id"] for t in targets]):
        print(f"Done. Restored {len(targets)} pages.")
    else:
        print("Failed.")


if __name__ == "__main__":
    main()