---
name: frappe-maintenance-ci
description: >-
  Central CI/CD, lint and git hook config for Aakvatech-Limited apps that are
  listed in frappe-maintenance configs/central-ci-apps.json (now av_tools).
  Load this skill before you commit in such an app, touch its CI, pre-commit,
  ruff, commitlint or semgrep config, set up its git hooks, add a check or
  workflow for apps, or when the user asks to move an app to central CI. For
  apps not in that list, use pre-commit-enforcement instead.
---

# Central CI for Aakvatech apps

frappe-maintenance (`Aakvatech-Limited/frappe-maintenance`) is the only place for CI, lint and hook config of the apps in `configs/central-ci-apps.json`. Each of these apps commits one CI file only: `.github/workflows/aakvatech-ci.yml`. Everything else is read from frappe-maintenance.

## Is the app on central CI?

```bash
python3 -c "import json,sys; print(sys.argv[1] in json.load(open('configs/central-ci-apps.json'))['repositories'])" av_tools
```

Run it in the frappe-maintenance clone. `False` means: stop and use `pre-commit-enforcement`.

## Rules

- Never add CI, lint or hook files to the app: no other `.github/workflows/*.yml`, `.pre-commit-config.yaml`, `ruff.toml`, `commitlint.config.js`, `.editorconfig`, `.eslintrc`. The pre-commit check fails when the app commits one of them.
- To add or change a check or workflow, change `.github/workflows/router.yml` or a `*-reusable.yml` in a frappe-maintenance PR and merge it to `main`. Apps use it on their next run. Never ask for an app PR for this.
- To change a lint rule, change the file in `frappe-maintenance/templates/` (listed in `configs/app-config-files.json`). Do not use `{{...}}` placeholders there; apps link these files as they are.
- To make a new check mandatory, add its job and status name to `configs/required-checks.json`, then run **Apply Required Check Rulesets** (needs Administration: write on the maintenance token).
- `[tool.ruff]` in the app `pyproject.toml` has no effect; the linked `ruff.toml` wins.
- Do not commit or push to `version-N` branches (version-15, 16, 17, 18). The local hooks block it. Use `version-N-hotfix` and PRs.
- Commit messages follow conventional commits with a lower-case subject.
- Raw SQL (`frappe.db.sql`, `frappe.db.multisql`) fails the required no-raw-sql check, also for existing calls. Use `frappe.qb`.

## Developer setup (once per bench)

Keep a frappe-maintenance clone on `main` and pull it from time to time. Then:

```bash
python3 <frappe-maintenance>/scripts/app_config_links.py install --bench <bench>
```

It links the config files into each onboarded app (hidden in `.git/info/exclude`, never committed) and installs the pre-commit, commit-msg and pre-push hooks. VS Code and ruff use the linked files. Run it again after you clone another onboarded app.

## Required checks

A PR cannot merge until these pass (once the ruleset is applied): semantic commits, pre-commit, Semgrep, no-raw-sql, linter. The status names are in `configs/required-checks.json`. A release with the `promote/<branch>` label runs the same checks on the bump commit on a short-lived branch, then pushes it directly. No PR is created.

## Move an app to central CI (once per app)

1. Fix what the full checks will report in the app first: raw SQL calls, and files that fail `pre-commit run --all-files` with the central config. Merge these as normal PRs.
2. Add the app to `configs/central-ci-apps.json` in a frappe-maintenance PR and merge it.
3. Run **Mass PR Across Organization** with `config_path=configs/onboard-central-ci.json`, `repository=<app>`, `dry_run=true`. Read the log, then run with `dry_run=false`.
4. Merge the PRs on each branch (default, `version-N`, `version-N-hotfix`). This is the only app PR the app ever needs for CI.
5. Open a test PR in the app and note the exact check names. If they differ from `configs/required-checks.json`, fix that file first.
6. If the token has Administration: write, run **Apply Required Check Rulesets** with `repository=<app>`, first with `dry_run=true`.
7. Each developer runs the setup command above.
