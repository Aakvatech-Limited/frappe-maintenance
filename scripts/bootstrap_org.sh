#!/usr/bin/env bash
set -euo pipefail

ORG="${ORG:-Aakvatech-Limited}"
WORKFLOW_PATH=".github/workflows/modernize-frappe.yml"
CALLER_CONTENT=$(cat <<'YAML'
name: Modernize Frappe Packaging

on:
  workflow_dispatch:

permissions:
  contents: write
  pull-requests: write

jobs:
  modernize:
    uses: Aakvatech-Limited/frappe-maintenance/.github/workflows/modernize-frappe-reusable.yml@main
YAML
)

repos=$(gh repo list "$ORG" --limit 1000 --json name,isArchived,isFork --jq '.[] | select(.isArchived == false and .isFork == false) | .name')

for repo in $repos; do
  full="$ORG/$repo"
  echo "== $full =="

  branches=$(gh api --paginate "repos/$full/branches?per_page=100" --jq '.[].name' 2>/dev/null || true)

  while IFS= read -r branch; do
    [[ -n "$branch" ]] || continue

    if [[ ! "$branch" =~ ^[Vv]ersion-(14|15|16)(-|$) ]] && [[ ! "$branch" =~ ^v(14|15|16)(-|$) ]]; then
      continue
    fi

    tree=$(gh api "repos/$full/git/trees/$branch?recursive=1" --jq '.tree[]?.path' 2>/dev/null || true)
    hooks_count=$(printf '%s\n' "$tree" | grep -E '^[^/]+/hooks\.py$' | wc -l | tr -d ' ')
    if [[ "$hooks_count" != "1" ]]; then
      echo "  skip $branch: expected one */hooks.py, found $hooks_count"
      continue
    fi

    if gh api "repos/$full/contents/$WORKFLOW_PATH?ref=$branch" >/dev/null 2>&1; then
      echo "  $branch: caller workflow already exists"
      continue
    fi

    work_branch="automation/bootstrap-frappe-maintenance-${branch//\//-}"
    base_sha=$(gh api "repos/$full/git/ref/heads/$branch" --jq '.object.sha')

    if ! gh api "repos/$full/git/ref/heads/$work_branch" >/dev/null 2>&1; then
      gh api -X POST "repos/$full/git/refs" \
        -f ref="refs/heads/$work_branch" \
        -f sha="$base_sha" >/dev/null
    fi

    encoded=$(printf '%s' "$CALLER_CONTENT" | base64 -w 0)
    gh api -X PUT "repos/$full/contents/$WORKFLOW_PATH" \
      -f message='chore: add Frappe maintenance workflow' \
      -f content="$encoded" \
      -f branch="$work_branch" >/dev/null

    if ! gh pr list --repo "$full" --head "$work_branch" --state open --json number --jq 'length' | grep -q '^1$'; then
      gh pr create --repo "$full" \
        --base "$branch" \
        --head "$work_branch" \
        --title "chore: add Frappe maintenance workflow" \
        --body "Adds the organization-managed Frappe packaging modernization workflow. It is manually triggered and opens modernization changes as a PR." >/dev/null
    fi

    echo "  $branch: bootstrap PR ready"
  done <<< "$branches"
done
