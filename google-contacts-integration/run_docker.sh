#!/usr/bin/env bash
# Helper to build and run the contacts sync docker image
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
IMAGE_NAME="agropride-contacts-sync"
DOCKERFILE_PATH="$SCRIPT_DIR/Dockerfile"

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Options:
  build                 Build the docker image (default action if none specified)
  run                   Run the container (will build first if image not found)
  --env-file PATH       Path to an env file to pass to the container
  --credentials PATH    Path to credentials.json to mount into container
  --token PATH          Path to sync_token.txt to mount into container
  --db-id ID            Notion CRM_DATABASE_ID to pass as env var
  --help                Show this help

Examples:
  # Build image
  $(basename "$0") build

  # Run with mounted credentials and env file
  $(basename "$0") run --env-file .env --credentials google-contacts-integration/credentials.json --token google-contacts-integration/sync_token.txt

EOF
}

if [[ ${#@} -eq 0 ]]; then
  ACTION=build
else
  ACTION="${1:-}"; shift || true
fi

ENV_FILE=""
CREDENTIALS_PATH=""
TOKEN_PATH=""
DB_ID=""

while [[ ${#@} -gt 0 ]]; do
  case "$1" in
    --env-file)
      ENV_FILE="$2"; shift 2;;
    --credentials)
      CREDENTIALS_PATH="$2"; shift 2;;
    --token)
      TOKEN_PATH="$2"; shift 2;;
    --db-id)
      DB_ID="$2"; shift 2;;
    --help|-h)
      usage; exit 0;;
    run|build)
      ACTION="$1"; shift;;
    *)
      echo "Unknown arg: $1"; usage; exit 1;;
  esac
done

build_image() {
  echo "Building image ${IMAGE_NAME}..."
  docker build -t ${IMAGE_NAME} -f "$DOCKERFILE_PATH" "$REPO_ROOT"
}

run_container() {
  # Build if image missing
  if ! docker image inspect ${IMAGE_NAME} >/dev/null 2>&1; then
    build_image
  fi

  DOCKER_RUN_ARGS=(--rm -it)

  if [[ -n "$ENV_FILE" ]]; then
    # Docker --env-file doesn't support 'export' keyword, so strip it
    TMP_ENV=$(mktemp)
    sed 's/^export //' "$ENV_FILE" > "$TMP_ENV"
    DOCKER_RUN_ARGS+=(--env-file "$TMP_ENV")
    trap "rm -f $TMP_ENV" EXIT
  fi

  if [[ -n "$CREDENTIALS_PATH" ]]; then
    # mount into container path expected by the app
    abs_creds="$(cd "$(dirname "$CREDENTIALS_PATH")" && pwd)/$(basename "$CREDENTIALS_PATH")"
    DOCKER_RUN_ARGS+=(-v "$abs_creds:/app/google-contacts-integration/credentials.json:ro")
  fi

  if [[ -n "$TOKEN_PATH" ]]; then
    abs_token="$(cd "$(dirname "$TOKEN_PATH")" && pwd)/$(basename "$TOKEN_PATH")"
    DOCKER_RUN_ARGS+=(-v "$abs_token:/app/google-contacts-integration/sync_token.txt")
  fi

  if [[ -n "$DB_ID" ]]; then
    DOCKER_RUN_ARGS+=(-e CRM_DATABASE_ID="$DB_ID")
  fi

  echo "Running container..."
  docker run "${DOCKER_RUN_ARGS[@]}" ${IMAGE_NAME}
}

case "$ACTION" in
  build)
    build_image;;
  run)
    run_container;;
  *)
    echo "Unknown action: $ACTION"; usage; exit 1;;
esac
