# Frappe Maintenance Automation

Central automation for modernizing legacy Frappe app packaging for Pilot/uv compatibility.

The reusable workflow is intended to be called from Frappe app repositories on `version-*` branches. It creates a PR rather than modifying the source branch directly.

Managed changes include:

- `pyproject.toml` project metadata where missing
- `[tool.bench.frappe-dependencies]` version declarations
- legacy `setup.py` compatibility shim
- packaging validation with `uv`

The modernization script is designed to preserve existing `pyproject.toml` content where possible and only add/repair the required sections.
