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

## Failed cherry-pick diagnostics (schema v2)

When the action explicitly reports a failed target, the workflow replays the source
PR's non-merge commits, in order, using `git cherry-pick --no-commit` in a disposable
worktree created at that target branch. This does not push or modify the target
branch. It captures the first failed commit SHA, Git's unmerged paths, porcelain
status entries, and a shortened error message.

These diagnostics appear in the Actions run summary, in each failed target's
`diagnostic` object in `backport-results.json`, and in the updated source-PR
exception comment. JSON schema version is now 2 (existing status fields remain).
If the isolated replay cannot be performed, the diagnostic reports
`diagnostic_error` or `unavailable` without disguising the action's original
failure. A `clean_replay` result means the problem could not be reproduced in
the diagnostic environment; it does **not** mean the original backport succeeded.

The worktree is removed even after errors. GitHub tokens, repository secrets,
and full source files must not be included in diagnostic comments. Commit
and conflict diagnostics are evidence for manual repair, not authorization
to force-push or automatically resolve conflicts.

For validation, test a two-commit source PR where the second commit changes
a file absent on the destination branch, and verify the failed commit, path,
and corresponding `modify/delete` details appear in all three reporting surfaces.
Also test missing target branches, an ordinary edit/edit conflict, and a
successful backport without diagnostics.
