---
name: review-changes
description: Reviews a bounded Git change set by packaging its diff for a read-only reviewer with repository context. Use when asked to review staged, unstaged, commit, branch, or PR changes, including reviews with a named focus such as modularity, correctness, security, or testing.
---

# Review changes

Treat the **diff as scope** and the repository as context. The reviewer evaluates the change, reading surrounding code only to understand its effects.

## 1. Resolve the change set

Honor an explicit Git scope. Otherwise:

1. Use staged changes when `git diff --cached --quiet` reports a diff.
2. Otherwise use tracked unstaged changes when `git diff --quiet` reports a diff.
3. If neither exists, report that there is no reviewable diff and stop.

Before packaging, list `git status --short`. Keep unrelated changes outside the selected scope. If the requested scope, revision, branch, or PR is ambiguous, ask the user rather than guessing.

This step is complete when one exact Git comparison identifies every change under review.

## 2. Package the evidence

Create a unique temporary diff artifact with `mktemp`. Export the selected comparison with `--no-ext-diff --binary`, and separately collect its changed-file list.

Common comparisons:

- Staged: `git diff --cached --no-ext-diff --binary --`
- Tracked unstaged: `git diff --no-ext-diff --binary --`
- Commit: `git show --format=fuller --no-ext-diff --binary <revision> --`
- Range or branch: `git diff --no-ext-diff --binary <base>...<head> --`

Use the repository's PR tooling to resolve a PR to exact base and head revisions, then package that range. Include untracked files only when the user selected an unstaged or all-working-tree scope; represent each as a new-file diff and name it explicitly.

Verify that the artifact is readable and non-empty. Record:

- comparison and scope,
- artifact path,
- changed-file list,
- user-stated intent and review focus,
- available validation results.

This step is complete when the reviewer can read the exact diff without running Git.

## 3. Dispatch the reviewer

Launch the `reviewer` subagent asynchronously. Use the user's requested model and thinking level when specified; otherwise retain the configured reviewer defaults.

Pass a bounded task containing the recorded evidence and these review rules:

> Review the supplied diff as the primary evidence. Read complete changed files, callers, dependencies, interfaces, and tests from the repository when needed for context. Report findings attributable to, exposed by, or materially affected by this change; avoid a general codebase audit. Rank findings by severity, cite exact paths and lines, explain impact, and recommend the smallest practical fix. Note strengths, residual risks, and an overall verdict. Remain read-only.

Keep the workspace stable while the review runs. If the reviewer cannot read the artifact, provide the artifact path and changed-file list immediately rather than waiting for it to ask.

This step is complete when a read-only reviewer is running with the exact diff, repository path, review focus, and validation evidence.

## 4. Deliver the review

When the reviewer finishes, summarize its verdict and findings. Preserve the full report path. Distinguish change-specific findings from pre-existing context.

Apply fixes only when the user requested implementation or approves them. For a staged baseline, leave subsequent fixes unstaged so `git diff` shows the fix layer separately; stage them only on explicit request.

The review is complete when every finding is reported or resolved and the Git state is stated accurately.
