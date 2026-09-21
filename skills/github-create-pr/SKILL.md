---
name: github-create-pr
description: "Create or update GitHub pull requests from the full branch diff, including stacks and submodule dependencies. Use when the user requests a PR with the correct repository, base, title, body, and actual validation evidence."
---

# Create or update a GitHub PR

Work in the target checkout. Read its governing `AGENTS.md`/`CLAUDE.md`, optional
`.agents/project-workflow.md`, PR template, and applicable CI instructions.
Creating/updating a PR is the scope; merging, deployment, and team messages
require their own user authorization.

## Resolve repository, branch and base

Inspect `git status`, current branch, remotes, and any existing PR. Establish the
GitHub owner/repository from the target remote or the user's explicit target.
Use an explicit `--repo "$REPO"` in gh operations when repository context could
be ambiguous, especially across worktrees or repositories. Do not assume an
organization, fork owner, or upstream remote from the installed skill's location.
For a fork, distinguish the destination repository from the head's owner/branch.

Choose the base in this order:

1. The user's explicit target (or existing PR base when updating that PR).
2. The known parent branch of a stack.
3. `branch.<current-branch>.gh-merge-base`.
4. The target repository's verified default branch, from gh metadata or its
   remote HEAD. If local remote refs are stale, refresh within the authorized
   workflow before claiming an accurate diff.

No base name is universal. Do not treat the current feature branch's tracking
upstream as the PR base, and do not guess `HEAD~1` when metadata is missing.
Resolve the relevant local refs and their merge base; if the target remains
ambiguous, gather the candidates and ask for that decision.

## Inspect the complete change

Read the whole branch diff against the chosen base, not just the latest commit
or the current conversation. Start with:

```bash
git diff --stat "$BASE"...HEAD
git diff --name-status "$BASE"...HEAD
git log --oneline "$BASE"..HEAD
```

Then inspect the changed code and docs enough to describe the final behavior and
its important risks. Identify uncommitted changes separately: they will not be
in the PR until intentionally committed and pushed. Preserve unrelated work.
Check for an existing PR for this head and update it rather than opening a
duplicate; identify the exact PR number/URL before editing metadata.

Choose title and body from the final change. Lead with the concrete problem and
resulting behavior; include only details a reviewer needs to assess it. Follow
the repository template where present. For a small PR, a short explanation plus
Testing is sufficient. For larger changes, group by behavior and boundaries.
Rewrite outdated titles/bodies after scope changes instead of appending a
conversation log.

Run applicable project checks, or reuse current evidence tied to the same
revision. Report actual commands and results; label unavailable checks and
limitations plainly. Do not claim a live test from a build or a green CI result
that was never observed. Follow project policy for draft versus ready state.

## Publish within the user's requested scope

Prefer a consumer-provided helper such as `scripts/create-pr.sh` when present.
Read its usage and implementation first: verify it targets the intended repo,
base and readiness, and does not merge, notify, or publish unrelated artifacts.
Invoke it from that repository root. If it cannot preserve the authorized scope,
use gh directly rather than inheriting its unrelated side effects.

Write the body as exact UTF-8 Markdown in a local temporary file. Use real
newlines and quote path/argument variables; avoid shell interpolation of prose
or `--body "$(cat ...)"`. Create or update with supported gh options:

```bash
gh pr create --repo "$REPO" --head "$HEAD_BRANCH" --base "$BASE_BRANCH" \
  --title "$TITLE" --body-file "$BODY_FILE"
gh pr edit "$PR_NUMBER" --repo "$REPO" --base "$BASE_BRANCH" \
  --title "$TITLE" --body-file "$BODY_FILE"
```

Add `--draft` for a draft creation when the user's intent or project policy calls
for it. Push only the intended branch to the intended remote; never force-push
unrelated changes. If a supported gh version has an update limitation, use the
GitHub API with structured JSON or a file payload after checking its exact
schema; do not improvise shell-escaped multiline prose. For example, an update
blocked by the legacy `projectCards` GraphQL field can use the REST pull-request
endpoint. Write a JSON file containing the intended `title`, `body` and `base`,
then run `gh api --method PATCH "repos/$REPO/pulls/$PR_NUMBER" --input "$JSON_FILE"`.
Keep the repository and PR identity explicit and verify the resulting fields.

Read the resulting PR back and verify URL, repo, base, head, draft state, title,
and rendered body match the intended change. Attach every created PR to the
current task when the host provides an attachment tool. Return its link and
material validation/limitations. An update success message alone does not prove
the right PR or base was selected.

## Dependent changes

For a stack, each PR targets its recorded parent. Show both each incremental
diff and the combined target diff. Use the repository's actual stack mechanism;
do not assume provider-native stacking or automatic retargeting exists.

If the user later authorizes merging a manually managed stack, protect the
remaining PRs according to the hosting workflow: retarget when needed, merge
through GitHub, restack descendants onto the new parent, and push rewritten
branches with lease protection. A squash changes commit identity, so verify
child diffs afterwards. Creating a stack never implicitly authorizes its merge.

For a submodule/provider change, prepare the dependency PR first, then the
consumer PR or pointer update to an intended accessible revision. Explain the
merge/deployment order and validate compatible versions. Do not imply the two
repositories will publish atomically or that a private local SHA is fetchable.
