#!/usr/bin/env bash
set -euo pipefail

CONFIG_PATH="${CONFIG_PATH:-configs/frappe-maintenance.json}"
REPOSITORY="${REPOSITORY:-}"

args=("$CONFIG_PATH")
if [[ -n "$REPOSITORY" ]]; then
  args+=("--repository" "$REPOSITORY")
fi
if [[ "${DRY_RUN:-false}" == "true" ]]; then
  args+=("--dry-run")
fi

exec python3 scripts/mass_pr.py "${args[@]}"
