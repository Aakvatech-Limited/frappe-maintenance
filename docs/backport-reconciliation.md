# Backport reconciliation

Runs daily or via workflow_dispatch. Configure BACKPORT_MONITOR_TOKEN with read access to monitored repositories' pull requests and write access to frappe-maintenance Issues. Create the backport-exception label in frappe-maintenance.

For a pilot, run manually with repository=av_tools and dry_run=true, review backport-reconciliation.json, then rerun with dry_run=false. The issue register contains one exception per source PR and target branch. Linked merged backport PRs count as completed; open backport PRs remain pending; missing linkage is unverified, not proven cherry-pick failure.

Current limitations: sliding lookback based on PR updated_at; search by standard backport PR title and `Backport of #NN` body; manually cherry-picked fixes cannot be verified automatically. This is a conservative exception register, not a complete commit-level branch-equivalence audit. A configured token is required even for dry runs.
