#!/usr/bin/env bash
set -euo pipefail

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI is required." >&2
  exit 1
fi

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 owner/repo [env-file]" >&2
  exit 1
fi

REPO_SLUG="$1"
ENV_FILE="${2:-.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Env file not found: $ENV_FILE" >&2
  exit 1
fi

echo "Checking GitHub authentication..."
gh auth status >/dev/null

echo "Enabling GitHub Actions for $REPO_SLUG..."
gh api \
  --method PUT \
  -H "Accept: application/vnd.github+json" \
  "/repos/$REPO_SLUG/actions/permissions" \
  -f enabled=true \
  -f allowed_actions=all >/dev/null

echo "Setting workflow permissions to read/write..."
gh api \
  --method PUT \
  -H "Accept: application/vnd.github+json" \
  "/repos/$REPO_SLUG/actions/permissions/workflow" \
  -f default_workflow_permissions=write \
  -F can_approve_pull_request_reviews=false >/dev/null

echo "Uploading selected secrets from $ENV_FILE..."
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  [[ "$line" =~ ^# ]] && continue
  if [[ "$line" != *=* ]]; then
    continue
  fi

  key="${line%%=*}"
  value="${line#*=}"

  case "$key" in
    GEMINI_API_KEY|YT_API_KEY|YOUTUBE_API_KEY|ASSEMBLYAI_API_KEY|MAILAROO_API_KEY|MAILAROO_TO_EMAIL|MAILAROO_FROM_EMAIL|MAILAROO_FROM_NAME|MAILAROO_TO_NAME|MAILAROO_API_URL|QDRANT_URL|QDRANT_API_KEY|QDRANT_COLLECTION|QDRANT_DISTANCE|QDRANT_BATCH_SIZE|QDRANT_RECREATE_COLLECTION|QDRANT_EMBEDDING_MODEL|QDRANT_EMBED_MAX_CHARS)
      if [[ -n "$value" ]]; then
        printf "%s" "$value" | gh secret set "$key" --repo "$REPO_SLUG" --body-file - >/dev/null
        echo "  set $key"
      fi
      ;;
  esac
done < "$ENV_FILE"

echo "GitHub Actions bootstrap complete for $REPO_SLUG"
