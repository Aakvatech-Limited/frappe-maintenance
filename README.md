# Frappe Maintenance Automation

Central GitHub Actions implementations for `Aakvatech-Limited` Frappe apps. App repositories keep small caller workflows; a reviewed change merged to `main` here is used by the apps on their next triggered run. Mass PRs are used for initial onboarding and caller interface changes.

## Recent updates: backport visibility and standard configuration (October 2026)

The latest ten commits on `main` (through [8622f45](https://github.com/Aakvatech-Limited/frappe-maintenance/commit/8622f453bf6561e850cfeaf74d9c9dce912f3ae2)) introduce two backport-control enhancements and standardized project configuration. This section documents **current implementation** on `main`.

### Per-target backport attempt reporting (PR [#9](https://github.com/Aakvatech-Limited/frappe-maintenance/pull/9))

The reusable [backport workflow](.github/workflows/backport-reusable.yml) continues to honor `backport-to-<branch>` labels and use `korthout/backport-action@v4`. Each run now also:

- Records one outcome for each requested target, including `cherry_pick_failed`, `pr_created`, `attempt_succeeded_no_pr`, `action_failed` and `unknown`.
- Shows a per-target table in the GitHub Actions run summary.
- Uploads a `backport-results` artifact containing `backport-results.json` (90-day retention).
- Posts or updates a marked exception comment on the original PR for failed or unknown attempts.

**A created backport PR is not evidence that it was merged.** Attempt results do not independently prove that changes reached the destination branch. See [backport reporting details](docs/backport-reporting.md).

### Organization-wide reconciliation and historical exceptions (PR [#10](https://github.com/Aakvatech-Limited/frappe-maintenance/pull/10))

The central [Backport Reconciliation workflow](.github/workflows/backport-reconciliation.yml) runs daily at **05:15 UTC** and supports manual `workflow_dispatch` audits. It scans merged source PRs carrying `backport-to-*` labels and evaluates each requested target branch independently. The audit:

- Creates or updates an exception Issue in **this repository**, keyed by source repository, PR number and target branch.
- Classifies a linked **merged** backport PR as `completed`, an open linked PR as `awaiting_merge`, and absent evidence as `unverified`.
- Closes an existing exception Issue only when linked merged-PR evidence is found.
- Exports the `backport-reconciliation.json` audit artifact.
- Supports a specific `repository`, `days` lookback (1–730), and `dry_run`; manual invocations default to dry-run.

**Initial setup (required):**

1. Create a fine-grained token with pull-request read access to the monitored organization repositories, and Issues read/write access to `frappe-maintenance`. Ensure its repository selection covers every intended repository and complete any required organization approval.
2. In [frappe-maintenance → Settings → Secrets and variables → Actions](https://github.com/Aakvatech-Limited/frappe-maintenance/settings/secrets/actions), add the repository secret `BACKPORT_MONITOR_TOKEN`. Do not commit or paste the token into workflow files.
3. Create the `backport-exception` Issue label in this repository.
4. In [Actions](https://github.com/Aakvatech-Limited/frappe-maintenance/actions), manually run **Backport Reconciliation** with `repository=av_tools`, `days=90`, `dry_run=true`. Review the log and uploaded JSON before allowing writes.
5. Repeat with `dry_run=false` for a pilot, then run without a repository filter to inspect organization coverage. Scheduled runs use the configured token and update Issues automatically.

**Important limits:** This is a conservative exception register, not a full git-content equivalence verifier. A manually cherry-picked fix with no linked backport PR can remain `unverified`. Searches are bounded by update timestamps, configured history window, and pagination; very old backports may be omitted. Missing linked evidence does **not** itself establish that a cherry-pick conflict occurred. See [backport reconciliation details](docs/backport-reconciliation.md).

### Organization-wide EditorConfig and ESLint defaults (PR [#7](https://github.com/Aakvatech-Limited/frappe-maintenance/pull/7))

The `configs/sync-standard-workflows-default-branch.json` campaign now distributes `templates/editorconfig` and `templates/eslintrc` as `.editorconfig` and `.eslintrc` alongside the standard workflow callers. The campaign targets **default branches only**, recognizes eligible Frappe apps using exactly one `*/hooks.py`, and uses `create_or_update` (so existing files may be replaced through reviewable PRs). Inspect app-specific formatting/lint choices before merging.

From **Actions → Mass PR Across Organization**, use `configs/sync-standard-workflows-default-branch.json`, first with `repository=av_tools` and `dry_run=true`; review the pilot PR before organization-wide distribution. This campaign does not automatically rewrite maintained version branches.

### Commit coverage

This README update reviewed the ten latest commits on `main` as of 13 October 2026: [8622f45](https://github.com/Aakvatech-Limited/frappe-maintenance/commit/8622f453bf6561e850cfeaf74d9c9dce912f3ae2), [7d77ac8](https://github.com/Aakvatech-Limited/frappe-maintenance/commit/7d77ac81e0fea1827251c9e8ce315013b54fb58a), [a2f314b](https://github.com/Aakvatech-Limited/frappe-maintenance/commit/a2f314bc91a4815ab6f2df85c37533964179d74b), [1508f01](https://github.com/Aakvatech-Limited/frappe-maintenance/commit/1508f01f1ae817377c492c8811df8168bca168aa), [92e092e](https://github.com/Aakvatech-Limited/frappe-maintenance/commit/92e092e2dbe0c9a2509034ebfa785840cb63d9ce), [2e59e42](https://github.com/Aakvatech-Limited/frappe-maintenance/commit/2e59e4297286a21cb2ee63cfda603473fc733d41), [100b727](https://github.com/Aakvatech-Limited/frappe-maintenance/commit/100b7275262e76bc645fd181ed8f2496efc2e030), [e3c6f3b](https://github.com/Aakvatech-Limited/frappe-maintenance/commit/e3c6f3b1f614be2aeea2942e2f56fb86bee43cf4), [e9540b1](https://github.com/Aakvatech-Limited/frappe-maintenance/commit/e9540b147bfca6246725dcb86214f8713968061d), and [edc373d](https://github.com/Aakvatech-Limited/frappe-maintenance/commit/edc373d46415fff7d3ef69748d83f1894c78dcd1).

## Central CI for apps

Apps in `configs/central-ci-apps.json` keep one file: `.github/workflows/aakvatech-ci.yml` (`templates/workflows/aakvatech-ci.yml`). It calls `.github/workflows/router.yml@main`, which selects the jobs for each event:

| Event | Jobs |
| --- | --- |
| `pull_request`, or manual run with task `checks` | semantic-commits, pre-commit, semgrep, no-raw-sql, linter |
| `pull_request_target` (closed, labeled) | backport, tag-and-promote |
| `workflow_run` of a `pull_request` run | label-failed-prs |
| Manual run with task `compliance` or `modernize` | compliance, modernize |

To add or change a check or workflow, change `router.yml` or a reusable workflow in a PR, get a review and merge it to `main`. Apps use it on their next event; no app PR is needed.

Config files (`configs/app-config-files.json`) are not committed to apps. CI links them from its frappe-maintenance checkout, and fails when an app commits one of them. On a developer machine, link them and install the git hooks once per bench, and keep the frappe-maintenance clone on `main`:

```bash
python3 scripts/app_config_links.py install --bench ~/frappe-bench
```

To move an app once, add it to `configs/central-ci-apps.json`, merge, and run **Mass PR Across Organization** with `configs/onboard-central-ci.json`. The PR adds the trigger and deletes the old workflow and config files.

## Shared workflows

All ten templates in `templates/workflows/` are callers. The implementations live in `.github/workflows/*-reusable.yml` and declare `workflow_call`. Existing workflow names, triggers, internal job names, release labels and branch checks are retained. Failed-run labeling now explicitly watches all workflow names except itself, as required by GitHub's `workflow_run` configuration.

| Caller | Central implementation | Trigger |
| --- | --- | --- |
| `linter.yml` | `linter-reusable.yml` | PR / manual |
| `semgrep.yml` | `semgrep-reusable.yml` | PR / manual |
| `pre-commit.yml` | `pre-commit-reusable.yml` | PR / manual |
| `no-raw-sql.yml` | `no-raw-sql-reusable.yml` | PR / push / manual |
| `semantic-commits.yml` | `semantic-commits-reusable.yml` | PR |
| `backport.yml` | `backport-reusable.yml` | PR closed / labeled |
| `tag-and-promote-from-pr-label.yml` | `tag-and-promote-from-pr-label-reusable.yml` | PR closed / labeled |
| `label-failed-prs.yml` | `label-failed-prs-reusable.yml` | Workflow completed / manual |
| `custom-app-compliance.yml` | `custom-app-compliance-reusable.yml` | Manual |
| `modernize-frappe.yml` | `modernize-frappe-reusable.yml` | Manual |

Callers retain triggers and minimum token permissions. The central jobs receive the app's event context and `GITHUB_TOKEN` automatically; no organization token or `secrets: inherit` is needed for these calls. Backport/modernization still require the app's Actions setting to allow GitHub Actions to create pull requests. Required branch protections still apply to release commits. Organization Actions policy must allow the central workflows and their actions.

### Required checks on release and backport commits

Pushes and pull requests made with `GITHUB_TOKEN` start no workflows. For apps in `configs/central-ci-apps.json`, the workflows start the app trigger (`aakvatech-ci.yml`, task `checks`) with `workflow_dispatch` instead:

| Workflow | Behavior |
| --- | --- |
| Tag and promote | Pushes the bump commit to `release/bump-<tag>`, runs the required checks on it and waits up to 30 minutes. Then it pushes the same commit to the target branch, deletes the temporary branch and creates the tag. If a check fails or the target branch moved, nothing reaches the target branch; rerun the workflow. |
| Backport | Starts the required checks on each created backport PR and does not wait. |

Pre-commit, Semgrep and Semantic Commits accept an optional `base-sha` input, so a started check looks only at the new commits. The release commit subject is `chore(release): bump to version X.Y.Z`. Earlier releases with `Bumped to Version` are still detected. Callers of tag and promote and backport need `actions: write`.

### Required checks ruleset

A PR cannot merge until these checks pass. The list and the check names are in `configs/required-checks.json`:

| Check | Blocks on |
| --- | --- |
| `ci / semantic-commits / Check Commit Messages` | Commit messages that break `commitlint.config.js` |
| `ci / pre-commit / pre-commit` | Hook failures on changed files |
| `ci / semgrep / Semgrep` | New ERROR findings |
| `ci / no-raw-sql / Reject raw database SQL` | Any raw SQL call in the app, including existing calls |
| `ci / linter / Vulnerable Dependency Check` | Known vulnerable dependencies |

**Apply Required Check Rulesets** (`apply-rulesets.yml`) writes ruleset `aakvatech-required-checks` from `configs/rulesets/required-checks.json` to apps in `configs/central-ci-apps.json`. It covers the default branch and `version-*` (including `version-N-hotfix`), accepts results only from GitHub Actions, and removes classic required checks on those branches. It uses `ORG_MAINTENANCE_TOKEN` with Administration: write. Run it with `dry_run=true` first. The check names are not yet confirmed on a real run; compare them with the pilot PR before applying.

Concurrency is defined only in the implementation. Caller and callee share `github.workflow`, so repeating cancellation groups in both can cancel the calling run.

### One-time rollout

1. Merge the central reusable workflow PR into `main`.
2. Release/backport behavior should be exercised on a controlled test repository before organization-wide use.
3. Run **Mass PR Across Organization** with `configs/migrate-reusable-workflows.json`, `repository=av_tools`, `dry_run=true`. Then use `dry_run=false` to open the pilot migration PR.
4. Merge the pilot callers and verify the app's Actions runs. The migration retains workflow and internal job names, but reusable calls add an outer job (`shared`), so required status-check contexts can change. Update required checks to the exact names shown on the pilot PR before expanding rollout.
5. Run the same campaign for the remaining eligible apps. It targets each default branch plus `version-N` and `version-N-hotfix` branches. Review and merge those initial PRs.

The workflow campaign preflight blocks rollout if any referenced central workflow is missing on `main`. The older default-branch-only sync config remains available and now also distributes callers exclusively.

### Routine changes

Open one PR here, pass **Validate shared workflows**, get a review and merge to `main`. Apps use the updated implementation on their next event. For a risky change, test it before merge: point a pilot app caller at the PR branch and set `maintenance-ref` to the same branch. Changes to triggers, permissions, required inputs or workflow paths still require caller PRs; preserve backward-compatible inputs whenever possible.

Callers use `@main` and `maintenance-ref: main`. The `maintenance-ref` input defaults to `main`; use the same ref as the reusable workflow. A fixed SHA caller plus matching `maintenance-ref` gives a run that does not change when `main` moves.

Protect `main` with a repository ruleset that requires a reviewed PR and **Validate shared workflows**. Every merge to `main` goes live for the apps. GitHub workflow YAML cannot itself configure repository protection.

To roll back, merge a revert of the faulty central change to `main`.

### Local validation

```bash
python -m pip install PyYAML==6.0.3
python -m unittest discover -s tests -v
actionlint -shellcheck= -pyflakes= .github/workflows/*.yml templates/workflows/*.yml templates/label-failed-prs.yml templates/modernize-frappe.yml
```

Tests verify caller/callee permission contracts, event triggers, campaign contents, branch selection, embedded Bash/Python/JavaScript syntax, the raw-SQL rejection policy, and release promotion branch guards. GitHub-hosted execution in the pilot is required to verify token permissions, required-check contexts and external actions.

## Generic Mass PR Engine

The workflow **Mass PR Across Organization** runs `scripts/mass_pr.py` using a JSON configuration file. For changes to repository files or initial workflow onboarding:

1. Add one or more template files under `templates/`.
2. Add a JSON file under `configs/`.
3. Run **Mass PR Across Organization** and select the config path.
4. Optionally enter a repository name to process only that repository. Leave it blank to process all eligible repositories.
5. Run first with `dry_run=true`.
6. Re-run with `dry_run=false` to create branches, commits, and PRs.

No new bootstrap script is required for each campaign.

### Repository targeting

The workflow has an optional `repository` input:

- Leave `repository` blank to preserve the existing mass-PR behavior and process all repositories allowed by the selected configuration.
- Enter one exact repository name, for example `av_tools`, to process only that repository.
- Repository include/exclude rules in the selected configuration still apply. Selecting a repository does not bypass campaign eligibility rules.
- An unknown repository name fails fast instead of silently falling back to all repositories.

The same behavior is available from the CLI:

```bash
python3 scripts/mass_pr.py configs/frappe-maintenance.json --repository av_tools --dry-run
```

Omit `--repository` to process all eligible repositories.

### Configuration example

```json
{
  "organization": "Aakvatech-Limited",
  "repository_include_regex": ".*",
  "repository_exclude_regex": "^frappe-maintenance$",
  "branch_include_regex": "^version-15",
  "branch_exclude_regex": "",
  "required_paths": ["*/hooks.py"],
  "required_paths_mode": "exactly_one_each",
  "files": [
    {
      "source": "templates/example.yml",
      "target": ".github/workflows/example.yml",
      "mode": "create_or_update"
    }
  ],
  "work_branch_prefix": "automation/example",
  "commit_message": "chore: add example workflow",
  "pr_title": "chore: add example workflow",
  "pr_body": "Adds the organization-managed example workflow."
}
```

### File modes

- `create_only`: skip repositories where the target already exists.
- `update_only`: skip repositories where the target does not exist.
- `create_or_update`: create missing files and update differing files.
- `delete`: delete an explicitly named file if present; skip it if already absent. No `source` is required. Deletions are committed only on the campaign work branch and reviewed in its PR.

Creation, replacement and deletion entries can be mixed in the same campaign. A deletion-only campaign is also supported. For example, add this entry to `files` to remove an obsolete workflow:

```json
{
  "target": ".github/workflows/obsolete-ci.yml",
  "mode": "delete"
}
```

This is an example path, not an enabled cleanup rule. The workflow migration does not guess which repository-specific files are obsolete.

A complete deletion-only cleanup campaign can look like this:

```json
{
  "organization": "Aakvatech-Limited",
  "repository_include_regex": ".*",
  "repository_exclude_regex": "^frappe-maintenance$",
  "default_branch_only": true,
  "files": [
    {
      "target": ".github/workflows/obsolete-ci.yml",
      "mode": "delete"
    }
  ],
  "work_branch_prefix": "automation/cleanup-obsolete-workflows",
  "commit_message": "chore: remove obsolete workflow",
  "pr_title": "chore: remove obsolete workflow",
  "pr_body": "Removes the explicitly listed obsolete workflow."
}
```

Save the configuration under `configs/`, then select it in **Mass PR Across Organization**. Choose one repository first and inspect with `dry_run=true` before creating its cleanup PR. For a mixed campaign, include normal create/update entries alongside deletion entries in the same `files` list.

Dry runs print `delete <path>` without writing anything. Missing files print a skip message and do not count as changes. The deletion uses the file's current blob SHA and the campaign work branch; a concurrent file change causes the GitHub request to fail. Inspection errors other than HTTP 404 fail the campaign rather than being treated as missing files. Targets must be explicit repository-relative file paths: directories, glob patterns, absolute paths and parent traversal are rejected. A source-readiness preflight, when configured, ignores deletion entries; deletion-only cleanup configs can omit `required_workflow_source`.

### Required path modes

- `at_least_one_each`: every configured glob must match at least one repository path.
- `exactly_one_each`: every configured glob must match exactly one repository path.
- `any`: at least one configured glob must match.

### Default and maintained branches

`include_default_branch: true` includes the repository default branch regardless of its name, in addition to branches matched by `branch_include_regex`. Exclusions always take precedence. `default_branch_only: true` still limits a campaign to the default branch.

Workflow campaigns declare `required_workflow_source`; the engine checks that the central ref and referenced workflows exist before creating any application branches or PRs.

### Focused backport-caller migration (PR 3)

For repositories still containing their own `.github/workflows/backport.yml`,
use `configs/migrate-backport-callers.json` in **Mass PR Across Organization**.
Unlike `configs/migrate-reusable-workflows.json`, this campaign changes **only**
the Backport workflow and leaves every other CI workflow intact.

Start with `repository=av_tools`, `dry_run=true`; verify the resulting target
branches and the `main` reusable workflow source. Repeat with
`dry_run=false` to create reviewable PRs, then remove the repository selector
for other eligible Frappe apps. The campaign includes default branches and
`version-N` / `version-N-hotfix` branches. All app PRs must be reviewed and
merged; running the campaign alone does not deploy its changes.

**Before rollout:** merge the central commit containing backport attempt
reporting to `main`, check repository Actions permission
to call reusable workflows and create PRs, and validate required status-check
contexts in a pilot. Backport reconciler setup remains centralized in
`frappe-maintenance` and does not need a per-app scheduled workflow.

### Existing Frappe maintenance campaign

`configs/frappe-maintenance.json` distributes `templates/modernize-frappe.yml` to eligible Frappe version branches as `.github/workflows/modernize-frappe.yml`.

## Frappe Packaging Modernization

The reusable modernization workflow creates PRs rather than modifying source version branches directly.

Managed changes include:

- `pyproject.toml` project metadata where missing
- `[tool.bench.frappe-dependencies]` version declarations
- legacy `setup.py` compatibility shim
- packaging validation with `uv`

The modernization script is designed to preserve existing `pyproject.toml` content where possible and only add or repair required sections.



## Custom Frappe App Compliance

The custom app compliance system verifies that a managed Frappe application contains at least one of each required operational UI/reporting artifact:

- Workspace
- Report
- Dashboard
- Dashboard Chart
- Number Card

The centrally maintained rules live in `configs/custom-app-compliance.json`, and the scanner lives in `scripts/check_custom_app_compliance.py`.

Each Frappe application receives only the lightweight caller workflow from `templates/workflows/custom-app-compliance.yml`. That workflow calls the reusable workflow in this repository, so future compliance criteria can normally be changed centrally without rewriting every app repository.

### Manual audit behavior

The compliance workflow runs only when a user manually selects **Actions → Custom App Compliance → Run workflow** in the application repository.

There are no pull-request triggers, no schedule, and no compliance labels.

The audit:

- scans the checked-out branch for the configured required artifacts;
- writes a pass/fail matrix to the GitHub Actions job summary;
- fails the workflow when one or more required artifacts are missing;
- uploads a machine-readable `custom-app-compliance-report` JSON artifact.

A green workflow run means all currently configured compliance requirements were found. A failed run shows the missing requirements in the Actions summary.

### Organization rollout

Use the existing **Mass PR Across Organization** workflow in this repository with:

```
configs/custom-app-compliance-workflow.json
```

Recommended rollout:

1. Run the mass-PR workflow with `dry_run=true`.
2. Review which repositories are detected as eligible Frappe apps.
3. Run it again with `dry_run=false`.
4. The automation creates one PR in each eligible repository adding:
   `.github/workflows/custom-app-compliance.yml`
5. Review and merge those PRs.
6. After merge, each repository will show **Custom App Compliance** in its Actions tab and it can be run manually.

Eligible repositories are currently detected by the presence of exactly one `*/hooks.py`.

The caller uses `custom-app-compliance-reusable.yml@main`. Future rules are adopted when the central PR is merged to `main`.

## Frappe Cloud audit evidence in centralized CI

The reusable `semgrep-reusable.yml` runs a differential Semgrep error gate and a **full-repository finding export**. It uploads `semgrep-finding-evidence/semgrep-full.json` (90-day retention) and writes severity totals to the Actions job summary. The export and upload also run when the error gate fails. Unlike a PR-only differential check, the full export includes pre-existing findings, enabling source-to-finding reconciliation after each bulk remediation.

**Rollout:** Merge the central PR to `main`. App repositories calling `@main` use it on their next run. Local copied workflows, such as those in `csf_tz`, do not inherit this improvement until migrated to the reusable caller.

The JSON is a new-scan snapshot, **not** the missing original 497-finding report. Capture the original baseline separately. Missing scanner installations or missing artifacts fail the workflow rather than being treated as zero findings. This automation generates reports; it does not automatically change application code or fix old findings.
