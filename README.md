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

Because the caller workflow points to `Aakvatech-Limited/frappe-maintenance/.github/workflows/custom-app-compliance-reusable.yml@main`, future rule changes in the central repository are picked up automatically by all repositories that already have the caller workflow.
