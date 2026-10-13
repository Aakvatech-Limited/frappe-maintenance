# Per-target backport attempt reporting

The shared backport workflow retains its existing labels and GitHub backport action.
After an attempt it writes `backport-results.json` and uploads an artifact named
`backport-results` (90-day retention). Its Actions job summary includes one
row per requested `backport-to-<branch>` target.

Statuses are attempt outcomes, **not proof the target branch contains the change**:

- `cherry_pick_failed`: action explicitly reported failure for this target.
- `pr_created`: action succeeded and its created PR was resolved to this target.
- `attempt_succeeded_no_pr`: action succeeded but no created PR was identified.
- `action_failed`: the action failed without a target-specific result.
- `unknown`: no authoritative action output was available.

The artifact includes repository, source PR and merge SHA, run URL, action
outcome, raw target outputs, created PR numbers and per-target statuses.
The original source PR gets an updatable bot comment when a target fails or
its outcome cannot be determined.

This records attempts only. Closing unresolved issues, verifying merged
backports or manual cherry-picks, and organization-wide daily reconciliation
will be part of PR 2.

## Review / acceptance

Test on a merged PR with two `backport-to-*` labels, with one branch
cherry-picking cleanly and the other conflicting. Verify the JSON artifact,
job summary and source-PR exception comment agree on both targets. Check
relabeled retry behavior does not create duplicate comments. Test a
successful backport PR creation separately from its subsequent merge.
