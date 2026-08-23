# AI Agent Guide — {{REPO_NAME}}

This repository is `{{FULL_REPO}}`, currently operating on branch `{{BRANCH}}`.

This guide is vendor-neutral and is intended for AI coding agents such as Claude, ChatGPT, Codex, GitHub Copilot, Cursor, and similar tools. Follow the repository's existing architecture and conventions before introducing new patterns.

## Primary Objective

Make the smallest correct change that solves the stated problem without creating unnecessary architectural, behavioral, or migration risk.

For this repository:

- Treat `{{REPO_NAME}}` as the repository/application context.
- Preserve existing Frappe/ERPNext conventions and project structure.
- Prefer existing framework APIs, utilities, and local patterns over custom abstractions.
- Do not change unrelated behavior while implementing a focused request.
- Do not assume this repository has the same architecture as another Aakvatech or Frappe application.

## Before Changing Code

Inspect the repository before editing.

1. Identify the Frappe app package from the repository structure, normally the directory containing `hooks.py`.
2. Read the relevant `hooks.py`, DocType controllers, API modules, patches, reports, tests, and configuration associated with the requested change.
3. Check `pyproject.toml`, `setup.py`, `requirements.txt`, `package.json`, CI workflows, and lint/test configuration when relevant.
4. Search for existing implementations before adding new helpers, APIs, DocTypes, utilities, or patterns.
5. Determine the supported Frappe/ERPNext version from the branch and repository metadata. Do not infer compatibility from unrelated repository names or local directory names.
6. If the task is a bug fix, identify the root cause before modifying behavior.

If repository-specific documentation such as `README.md`, `CONTRIBUTING.md`, `SPEC.md`, `AGENTS.md`, or module documentation exists, read the relevant parts before changing that area.

## Frappe and ERPNext Conventions

- Use supported Frappe APIs instead of direct database manipulation unless direct SQL is clearly required and justified.
- Respect DocType lifecycle methods such as `validate`, `before_save`, `on_submit`, `on_cancel`, and related hooks.
- Preserve document permissions, workflow behavior, naming rules, and transaction boundaries.
- Use `frappe.db.get_value`, `frappe.db.get_all`, `frappe.get_all`, Query Builder, or ORM patterns consistently with surrounding code.
- Avoid bypassing validations or permissions unless the existing design explicitly requires it.
- Be careful with submitted documents (`docstatus = 1`) and cancelled documents (`docstatus = 2`).
- Treat patches and migrations as production-sensitive. They must be safe for existing data and repeatable where practical.
- Do not introduce schema assumptions without checking the relevant DocType definitions or migration history.
- For integrations, preserve idempotency and avoid duplicate external or ERPNext transactions.
- For background jobs and schedulers, assume retries can happen and design operations safely.

## Code Design

- Choose clear code over clever code.
- Prefer explicit behavior over hidden side effects.
- Keep functions focused and reasonably small.
- Keep cyclomatic complexity low where practical.
- Reuse existing repository patterns before creating new abstractions.
- Avoid unnecessary helper functions for trivial one-use expressions.
- Avoid abbreviations unless they are established domain terms.
- Keep one authoritative owner for mutable state that could otherwise drift out of sync.
- Keep temporary state local to the operation that needs it.
- Fail close to the actual error instead of hiding corrupt or partial state behind broad fallbacks.
- Retry only operations that are safe to repeat.
- Do not silently swallow exceptions.
- Preserve backward compatibility unless the requested change explicitly allows breaking behavior.

## Python

- Follow the Python style already established in the repository.
- Prefer descriptive names.
- Keep comments short and useful; do not restate obvious code.
- Use docstrings when they add information about behavior, constraints, or non-obvious intent.
- Do not add imports, dependencies, decorators, or abstractions that are not needed.
- Avoid mutable global state.
- Do not import the application package from packaging build metadata in a way that breaks isolated PEP 517 builds.
- When modern packaging is present, treat `pyproject.toml` as the primary packaging metadata source unless repository conventions clearly say otherwise.

## JavaScript and Client Scripts

- Follow existing Frappe client-side conventions in the repository.
- Use supported form, list, report, and dialog APIs.
- Avoid DOM manipulation when a Frappe API exists for the same behavior.
- Keep client logic focused on UI/client concerns; move authoritative business rules to the server when appropriate.
- Do not rely on client-side validation alone for controls that must be enforced securely.

## Database and Data Safety

- Never delete or rewrite production data casually.
- Before bulk updates, understand affected rows and document states.
- Prefer bounded, explainable migrations.
- For expensive queries, inspect existing indexes and query patterns before proposing schema changes.
- Do not add indexes to framework-owned DocTypes casually; consider whether the change belongs upstream or in application-owned schema.
- Avoid N+1 queries in loops when records can be fetched in batches.
- For SQL, parameterize values instead of interpolating untrusted input.

## Security and Permissions

- Preserve Frappe's permission model.
- Do not expose whitelisted methods unnecessarily.
- Validate inputs on server-side APIs.
- Do not log passwords, tokens, API secrets, session identifiers, or confidential customer information.
- Never commit credentials or generated secrets.
- Treat guest-accessible endpoints as public attack surfaces.
- For file access, verify permissions and avoid exposing private files unintentionally.

## Testing and Validation

Validate changes using the repository's own tooling.

- Run the narrowest relevant tests first.
- Run broader tests when the change affects shared behavior.
- Use the repository's configured formatter, linter, and test commands rather than assuming one universal command.
- For Frappe changes, test relevant document lifecycle paths including draft, submit, cancel, amend, and permissions when applicable.
- For bug fixes, add or update a regression test when the repository has an established test framework for that area.
- For migrations and patches, consider both fresh installations and upgrades from existing data.
- Do not report tests as passing unless they were actually executed successfully.

## Git and Scope Discipline

- Do not modify unrelated files.
- Do not revert or overwrite unrelated work already present in the working tree.
- Keep generated files out of commits unless the repository intentionally tracks them.
- Do not create planning documents, temporary debug files, or scratch artifacts in the repository unless specifically requested.
- Keep commits and pull requests focused on one logical change.
- Explain important behavior changes, compatibility concerns, migrations, and operational impact in the commit or pull request description.

## Documentation

Update documentation when a change affects:

- installation or upgrade steps,
- configuration,
- permissions or roles,
- public APIs,
- scheduled jobs,
- integrations,
- user-visible workflows,
- migration requirements,
- operational procedures.

Keep documentation concise and close to the source of truth.

## Repository-Specific Decisions

This file intentionally does not prescribe module names, controller locations, application architecture, test commands, or UI frameworks beyond standard Frappe/ERPNext practices.

When repository-specific conventions conflict with generic guidance here, prefer the established repository convention unless it is unsafe, obsolete, or directly responsible for the issue being fixed.

When uncertain, inspect the surrounding code and make the least disruptive change consistent with the current design.
