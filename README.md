# Frappe Maintenance Automation

Central GitHub Actions implementations for `Aakvatech-Limited` Frappe apps. App repositories keep small caller workflows; approved implementation changes are published here and adopted on their next triggered run. Mass PRs are used for initial onboarding and caller interface changes.

## Shared workflows and stable publication

All nine templates in `templates/workflows/` are callers. The implementations live in `.github/workflows/*-reusable.yml` and declare `workflow_call`. Existing workflow names, triggers, internal job names, release labels and branch checks are retained. Failed-run labeling now explicitly watches all workflow names except itself, as required by GitHub's `workflow_run` configuration.

| Caller | Central implementation | Trigger |
| --- | --- | --- |
| `linter.yml` | `linter-reusable.yml` | PR / manual |
| `pre-commit.yml` | `pre-commit-reusable.yml` | PR / manual |
| `no-raw-sql.yml` | `no-raw-sql-reusable.yml` | PR / push / manual |
| `semantic-commits.yml` | `semantic-commits-reusable.yml` | PR |
| `backport.yml` | `backport-reusable.yml` | PR closed / labeled |
| `tag-and-promote-from-pr-label.yml` | `tag-and-promote-from-pr-label-reusable.yml` | PR closed / labeled |
| `label-failed-prs.yml` | `label-failed-prs-reusable.yml` | Workflow completed / manual |
| `custom-app-compliance.yml` | `custom-app-compliance-reusable.yml` | Manual |
| `modernize-frappe.yml` | `modernize-frappe-reusable.yml` | Manual |

Callers retain triggers and minimum token permissions. The central jobs receive the app's event context and `GITHUB_TOKEN` automatically; no organization token or `secrets: inherit` is needed for these calls. Backport/modernization still require the app's Actions setting to allow GitHub Actions to create pull requests. Required branch protections still apply to release commits. Organization Actions policy must allow the central workflows and their actions.

Concurrency is defined only in the implementation. Caller and callee share `github.workflow`, so repeating cancellation groups in both can cancel the calling run.

### One-time rollout

1. Merge the central reusable workflow PR into `main`.
2. In a pilot app (for example `av_tools`), temporarily point callers to `@main` and run the relevant checks. For compliance and modernization, also pass `with: {maintenance-ref: main}` so scripts follow the pilot workflow version. Release/backport behavior should be exercised on a controlled test repository before organization-wide use.
3. In this repository, run **Publish stable workflows** from `main` and enter the full SHA of the approved, merged commit. It validates that exact commit again, requires it to be an ancestor of `main`, and creates or fast-forwards `stable`. It never force-pushes. Publication does not trigger builds in application repositories.
4. Run **Mass PR Across Organization** with `configs/migrate-reusable-workflows.json`, `repository=av_tools`, `dry_run=true`. Then use `dry_run=false` to open the pilot migration PR.
5. Merge the pilot callers and verify the app's Actions runs. The migration retains workflow and internal job names, but reusable calls add an outer job (`shared`), so required status-check contexts can change. Update required checks to the exact names shown on the pilot PR before expanding rollout.
6. Run the same campaign for the remaining eligible apps. It targets each default branch plus `version-N` and `version-N-hotfix` branches. Review and merge those initial PRs.

Do not merge `@stable` callers before the channel exists. The workflow campaign preflight blocks rollout if `stable` or any referenced central workflow is missing. The older default-branch-only sync config remains available and now also distributes callers exclusively.

### Routine changes

Open one PR here, pass **Validate shared workflows**, merge to `main`, test the pilot against `@main`, then publish the approved commit to `stable`. Migrated apps use the updated implementation on their next event. Changes to triggers, permissions, required inputs, workflow paths, or the selected channel still require caller PRs; preserve backward-compatible inputs whenever possible.

Production compliance and modernization callers explicitly set `maintenance-ref: stable`. The input defaults to `main` for compatibility with previously installed `@main` callers and supports pilots and fixed-ref callers; use the same ref as the reusable workflow. No scripts are fetched from `main` by production callers. A moving channel intentionally tracks approved changes rather than guaranteeing immutable run reproduction; a fixed SHA caller plus matching `maintenance-ref` provides that when needed.

Restrict writes to `main` and `stable` through repository rulesets. Allow the publication workflow's approved actor to update `stable`; if the ruleset blocks `GITHUB_TOKEN`, configure that policy before publishing. GitHub workflow YAML cannot itself configure repository protection.

To roll back, revert the faulty central change on `main`, validate and publish the resulting new commit. This keeps `stable` updates fast-forward-only.

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

### Required path modes

- `at_least_one_each`: every configured glob must match at least one repository path.
- `exactly_one_each`: every configured glob must match exactly one repository path.
- `any`: at least one configured glob must match.

### Default and maintained branches

`include_default_branch: true` includes the repository default branch regardless of its name, in addition to branches matched by `branch_include_regex`. Exclusions always take precedence. `default_branch_only: true` still limits a campaign to the default branch.

Workflow campaigns declare `required_workflow_source`; the engine checks that the central ref and referenced workflows exist before creating any application branches or PRs.

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

The caller uses `custom-app-compliance-reusable.yml@stable`. Future rules are adopted after the approved central commit is published to `stable`.
