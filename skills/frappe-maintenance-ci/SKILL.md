---
name: frappe-maintenance-ci
description: >-
  Central CI/CD, lint and git hook config for Aakvatech-Limited apps that are
  listed in frappe-maintenance configs/central-ci-apps.json (now av_tools).
  Load this skill before you commit in such an app, touch its CI, pre-commit,
  ruff, commitlint or semgrep files, set up its git hooks, or when the user
  asks to move an app to central CI. For apps not in that list, use
  pre-commit-enforcement instead.
---

# Central CI for Aakvatech apps

frappe-maintenance (`Aakvatech-Limited/frappe-maintenance`) is the only place to change CI, lint and hook config for the apps in `configs/central-ci-apps.json`. The apps receive the files from the Mass PR campaign `configs/sync-app-ci.json`.

## Is the app on central CI?

```bash
python3 -c "import json,sys; print(sys.argv[1] in json.load(open('configs/central-ci-apps.json'))['repositories'])" av_tools
```

Run it from the frappe-maintenance clone. `False` means: stop and use `pre-commit-enforcement`.

## Rules

- Never edit a managed file in the app. The managed files are the `files` targets in `configs/sync-app-ci.json`: `.pre-commit-config.yaml`, `ruff.toml`, `commitlint.config.js`, `scripts/setup-git-hooks.sh`, `.editorconfig`, `.eslintrc` and `.github/workflows/*.yml`. The pre-commit CI check fails when they differ from frappe-maintenance.
- To change a rule, edit the template in `frappe-maintenance/templates/`, open a PR there, publish `stable`, then run the campaign.
- Ruff style comes from `ruff.toml`. `[tool.ruff]` in the app `pyproject.toml` has no effect. Do not add it.
- Do not commit or push to `version-N` branches (version-15, 16, 17, 18). The local hooks block it. Use `version-N-hotfix` and PRs.
- Commit messages follow `commitlint.config.js` (conventional, lower-case subject).
- Raw SQL (`frappe.db.sql`, `frappe.db.multisql`) fails the required no-raw-sql check, also for existing calls. Use `frappe.qb`.

## Developer setup (once per clone)

```bash
cd apps/<app>
bash scripts/setup-git-hooks.sh
```

This installs the pre-commit, commit-msg and pre-push hooks. VS Code Source Control uses them. Use `bash`, because a file written by the campaign is not executable.

## Required checks

A PR cannot merge until these pass (when the ruleset is applied): semantic commits, pre-commit, Semgrep, no-raw-sql, linter. The names are in `configs/required-checks.json`. Releases with the `promote/<branch>` label run the same checks on the bump commit, then push it directly. No PR is created.

## Move an app to central CI

1. Fix what the full checks will report in the app first: raw SQL calls, and files that fail `pre-commit run --all-files` with `templates/pre-commit-config.yaml`. Merge these fixes as normal PRs.
2. Add the app to `configs/central-ci-apps.json` in a frappe-maintenance PR. Merge it and publish `stable` (**Publish stable workflows**).
3. Run **Mass PR Across Organization** with `config_path=configs/sync-app-ci.json`, `repository=<app>`, `dry_run=true`. Read the log, then run it with `dry_run=false`.
4. Merge the sync PRs on each branch (default, `version-N`, `version-N-hotfix`).
5. Open a test PR in the app and note the exact check names. If they differ from `configs/required-checks.json`, fix that file first.
6. If the token has Administration: write, run **Apply Required Check Rulesets** with `repository=<app>`, first with `dry_run=true`.
7. Each developer runs `bash scripts/setup-git-hooks.sh` in the app.
