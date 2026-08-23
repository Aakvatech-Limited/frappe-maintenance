# Frappe Maintenance Automation

Central automation for Frappe packaging modernization and configuration-driven mass pull requests across `Aakvatech-Limited` repositories.

## Generic Mass PR Engine

The workflow **Mass PR Across Organization** runs `scripts/mass_pr.py` using a JSON configuration file. Future organization-wide changes normally require only:

1. Add one or more template files under `templates/`.
2. Add a JSON file under `configs/`.
3. Run **Mass PR Across Organization** and select the config path.
4. Run first with `dry_run=true`.
5. Re-run with `dry_run=false` to create branches, commits, and PRs.

No new bootstrap script is required for each campaign.

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
