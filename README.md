# Frappe Maintenance Automation

Central automation for Frappe packaging modernization and configuration-driven mass pull requests across `Aakvatech-Limited` repositories.

## Generic Mass PR Engine

The workflow **Mass PR Across Organization** runs `scripts/mass_pr.py` using a JSON configuration file. Future organization-wide changes normally require only:

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

The custom app compliance system verifies that every managed Frappe application contains at least one of each required operational UI/reporting artifact:

- Workspace
- Report
- Dashboard
- Dashboard Chart
- Number Card

The centrally maintained rules live in `configs/custom-app-compliance.json`, and the scanner lives in `scripts/check_custom_app_compliance.py`.

Each Frappe application receives only the lightweight caller workflow from `templates/workflows/custom-app-compliance.yml`. That workflow calls the reusable workflow in this repository, so new compliance rules can normally be introduced centrally without rewriting the compliance logic in every application repository.

### Pull request behavior

On every pull request open, update, reopen, or transition to ready-for-review, the workflow scans the full PR head.

If any required artifact is missing:

- the workflow fails,
- the job summary identifies each missing requirement,
- the pull request receives the label `custom-app-compliance-failed`.

When the PR becomes compliant, the label is removed automatically.

To find outstanding custom-app compliance issues across the organization, search GitHub pull requests for:

```
org:Aakvatech-Limited is:pr is:open label:custom-app-compliance-failed
```

### Monthly reconciliation

The caller workflow runs on the first day of every month and reconciles all open pull requests in that repository. This catches old PRs, rule changes, and compliance drift. It also supports manual execution with `workflow_dispatch`.

The current schedule is `17 2 1 * *` (02:17 UTC on the first day of each month).

### Organization rollout

Use the existing **Mass PR Across Organization** workflow with:

```
configs/custom-app-compliance-workflow.json
```

Run in dry-run mode first, then run with writes enabled. Eligible repositories are detected by the presence of exactly one `*/hooks.py`.

Because the compliance criteria are configuration-driven, future requirements can be added to `configs/custom-app-compliance.json` and immediately consumed by all repositories already using the centrally managed reusable workflow.
