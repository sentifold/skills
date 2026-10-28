---
name: github-create-pr
description: "Create or update GitHub pull requests from the complete branch diff, including stacked PRs and submodule changes. Use when the user asks to open, publish, or update a PR with the correct repository, base, title, body, and actual validation evidence."
---

# Create or update a GitHub PR

Work in the target checkout. `PROJECT_ROOT` is the caller-supplied target
checkout or `git rev-parse --show-toplevel` from the working directory, never
the installed skill's location. Read the checkout's governing
`AGENTS.md`/`CLAUDE.md`, its PR template, applicable CI instructions, and the
optional profile at `PROJECT_ROOT/.agents/project-workflow.md`, interpreted
under the shared [project contract](../review-agent/references/project-contract.md).
The profile supplies the repository slug, default base, branch naming, title
format, publishing helper and its quirks, required checks, draft policy, and
the Change Map area list. Without a profile, derive those facts from the
project's own instructions, CI, and PR history; never import another
repository's helper, base name, title format, branch names, or checks.

Creating/updating a PR is the scope; merging, deployment, and team messages
require their own user authorization.

Before creating or updating a PR from a branch with file modifications, run the
formatter the project requires for the touched file types; if it changes
files, review and keep the intended formatting edits, then rerun until clean.
Publish new branches under the project's branch naming conventions.

## Resolve repository, branch and base

Inspect `git status`, current branch, remotes, and any existing PR. Establish
the GitHub owner/repository from the target remote or the user's explicit
target and keep it in `$REPO`. Do not assume an organization, fork owner, or
upstream remote from the installed skill's location. For a fork, distinguish
the destination repository from the head's owner/branch: `gh pr create` then
needs `--head <fork-owner>:<branch>` against `--repo <destination>`.

Verify the default branch instead of guessing it:

```bash
gh repo view "$REPO" --json defaultBranchRef --jq .defaultBranchRef.name
git symbolic-ref --short refs/remotes/<remote>/HEAD   # git remote set-head <remote> --auto if unset
```

Always determine the correct base branch before creating a PR, in this order:

1. If the user specifies a target branch, use it. When updating an existing
   PR, keep the base it already has unless the user retargets it.
2. If the branch is part of a stacked chain, the base branch is the previous
   branch in the chain, not automatically the default branch. The parent is
   recorded in `branch.<name>.gh-merge-base`, in the host's native stack
   metadata (GitHub: the PR payload's `.stack`), or in the profile's stack
   conventions.
3. If the repo configures `branch.<name>.gh-merge-base`, use that as the
   default base.
4. Only fall back to the target repository's verified default branch when
   none of the above apply. If local remote refs are stale, refresh within the
   authorized workflow before claiming an accurate diff.

No base name is universal: do not assume a branch is the base unless it is
actually the repo default or the user asked for it. Do not treat the current
feature branch's tracking upstream as the PR base, and do not guess `HEAD~1`
when metadata is missing. Resolve the relevant local refs and their merge
base; if the target remains ambiguous, gather the candidates and ask for that
decision.

## Bare `gh` calls can resolve against the wrong repo

A clone with more than one remote (an `origin` plus an `upstream` or fork
parent) and no `gh repo set-default` lets a bare `gh pr view 49`,
`gh pr edit 49`, or `gh pr ready 49` silently resolve number 49 against the
**other** repository — editing or reading a foreign PR. Always pass
`--repo "$REPO"` (or `-R`) on every `gh pr`/`gh issue` command that takes a
bare number. A helper that pins `GH_REPO` to one remote is unaffected only
when that remote is the destination; read which remote it pins, since a fork
clone whose `origin` is the fork must target the parent instead.

`gh pr edit --body`/`--body-file` additionally fails on repositories where it
reads `repository.pullRequest.projectCards` over GraphQL, which GitHub has
retired: the command prints a Projects-classic deprecation notice, **exits
without editing anything, and still reports no error loud enough to notice**
(a body edit silently kept the old text through two attempts). Edit a body
through REST instead, which has no projects field. Write a JSON file
containing the intended `title`, `body` and (only when retargeting) `base`,
then:

```bash
gh api --method PATCH "repos/$REPO/pulls/$PR_NUMBER" --input "$JSON_FILE"
```

`gh pr ready`, `gh pr view`, and a helper **when it creates** a PR are
unaffected — `gh pr create` reads no projects field. A helper's **update**
path may not be: helpers like `create-pr.sh` run `gh pr edit` when a PR is
already open, so `--pr <n> --body-file` hits exactly the failure above and
leaves the body untouched while printing the same deprecation notice. The
profile says whether the project's helper behaves this way; when it does,
update an existing body with the REST call above, not through the helper.

## Create / Update a PR

Prefer a consumer-provided helper such as `./scripts/create-pr.sh` or
`./Scripts/create-pr.sh` when the project provides one. Read its usage and
implementation first: verify it targets the intended repo, base and
readiness, and does not merge, notify, or publish unrelated artifacts. Invoke
it from that repository root. If it cannot preserve the authorized scope, use
`gh` directly rather than inheriting its unrelated side effects. Always pass
`--base` explicitly; a helper's own fallback (often the tracking upstream,
then a hard-coded branch) is not the base selection above.

For a new local branch, publish it and set its upstream before invoking the
helper; a helper's new-PR path may not push the branch:

```bash
git push -u origin <current-branch>
```

When updating an existing PR, helpers like `create-pr.sh` push the **current
checked-out branch** before editing the PR title/body: with a configured
upstream they push `HEAD` to that remote branch, otherwise they run
`git push`. This also applies with `--pr <number-or-url>`: that option
selects the PR to edit, not the branch to push. Run such a helper from the
intended PR head branch; the profile says which helper behaves this way.

```bash
./scripts/create-pr.sh "<title>" --base <target-branch> --body "<body>"
./Scripts/create-pr.sh "<title>" --base <target-branch> --body "<body>"
```

For a long or multi-line body, write it to a file and pass `--body-file`
instead of shell-interpolating `--body "$(cat file)"`, which is fragile with
backticks, `$`, quotes, and newlines. A helper's `--body-file` usually goes
through the same normalization and environment-supplied appendix handling as
`--body` (its `--help` names any appendix variable); the two options are
mutually exclusive.

```bash
./Scripts/create-pr.sh "<title>" --base <target-branch> --body-file <path>
```

Without a helper, write the body as exact UTF-8 Markdown in a local temporary
file, use real newlines, quote path/argument variables, and create or update
with supported `gh` options:

```bash
gh pr create --repo "$REPO" --head "$HEAD_BRANCH" --base "$BASE_BRANCH" \
  --title "$TITLE" --body-file "$BODY_FILE"
gh pr edit "$PR_NUMBER" --repo "$REPO" --base "$BASE_BRANCH" \
  --title "$TITLE" --body-file "$BODY_FILE"
```

Add `--draft` for a draft creation when the user's intent or project policy
calls for it. A helper's update path typically cannot flip draft state; use
`gh pr ready "$PR_NUMBER" --repo "$REPO"` once the project's readiness floor
is met. Push only the intended branch to the intended remote; never
force-push unrelated changes. If a supported `gh` version has an update
limitation, use the GitHub API with structured JSON or a file payload after
checking its exact schema (the REST `PATCH` above); do not improvise
shell-escaped multiline prose.

On Windows PowerShell, invoke a bash helper through Git for Windows Bash. Do
not rely on bare `bash`: it may resolve to a WSL app-execution alias even when
no WSL distribution is installed.

```powershell
$gitRoot = Split-Path (Split-Path (Get-Command git.exe).Source -Parent) -Parent
$gitBash = Join-Path $gitRoot "bin\bash.exe"
& $gitBash ./Scripts/create-pr.sh "<title>" --base <target-branch> --body "<body>"
```

If a PR already exists for the current branch, prefer pushing updates instead
of opening a duplicate; identify the exact PR number/URL before editing
metadata.

Read the resulting PR back and verify URL, repo, base, head, draft state,
title, and rendered body match the intended change. Attach every created PR
to the current task when the host provides an attachment tool. Return its
link and material validation/limitations. An update success message alone
does not prove the right PR or base was selected.

## PR Title and Body Must Reflect the Full Change Set

Before choosing the PR title and description, inspect the full branch diff
against the selected base branch, not just the latest commit or the current
conversation.

Minimum review:

```bash
git diff --stat "$BASE"...HEAD
git diff --name-status "$BASE"...HEAD
git log --oneline "$BASE"..HEAD
```

For a large branch, capture the full patch to a file **once** and read slices
from it, instead of re-running `git diff` or paging the whole patch into
context on every step:

```bash
git diff "$BASE"...HEAD > "$DIFF_FILE"
grep -nE '^\+\+\+ |^@@' "$DIFF_FILE"   # file + hunk map; read specific hunks on demand
```

Then inspect the changed code and docs enough to describe the final behavior
and its important risks. Identify uncommitted changes separately: they will
not be in the PR until intentionally committed and pushed. Preserve unrelated
work.

Use session context only as a helper for intent and rationale. Choose the PR
title and body from the actual code and docs present in the branch. Rewrite
outdated titles/bodies after scope changes instead of appending a
conversation log.

Run applicable project checks, or reuse current evidence tied to the same
revision. Report actual commands and results; label unavailable checks and
limitations plainly. Do not claim a live test from a build or a green CI
result that was never observed. Follow project policy for draft versus ready
state.

### Oversized diff confirmation

Before creating a ready PR, flipping a draft to ready, or merging, inspect
both line counts and large files:

```bash
git diff --numstat "$BASE"...HEAD | sort -nr
git ls-tree -rl HEAD | sort -nr -k4 | head -20
```

Treat the change as oversized when it adds more than 10,000 lines total, or
adds or replaces a generated fixture, oracle, snapshot, or asset larger than
1 MiB. Show the user the total additions/deletions, the largest paths and why
they are needed, plus any compact alternative. Get explicit confirmation
after showing those numbers before opening a ready PR or running the
project's merge helper or any other merge command. A broad instruction to
implement or land a phase is not size confirmation. Reverts whose purpose is
to remove oversized data do not require this confirmation.

## PR Title

Use the title format the project prescribes (profile or PR history); a
common shape names the tracking context, the kind of work, and the concrete
outcome:

```text
[<issue key or chore area>] <kind>: <concise outcome>
```

Rules:
- If the branch, commits, PR body, or user request references a tracker
  issue, use the exact issue key in the prefix. Do not invent or guess a key.
- If there is no tracked issue, use a short chore area in the prefix, such as
  `[build]`, `[docs]`, or `[tooling]`; avoid vague prefixes like `[misc]`.
- Pick one work kind that describes the main change from the project's kind
  vocabulary (for example `feat`, `bugfix`, `refactor`, `docs`, `test`,
  `chore`, or `infra`).
- The outcome should be short, concrete, and reviewer-facing. Prefer
  "move create-pr skill to canonical discovery" over "updates" or "fix stuff".
- Keep the title aligned with the full branch diff, not just the most recent
  prompt.

When the branch has a measurable outcome (time saved, crash eliminated, size
reduced), put the number in the title after an em dash, as in
`[build] perf: stop full-tree hashing of patched deps — fresh-worktree dep
sync 13 min -> seconds`. A concrete before/after beats an abstract verb
phrase.

The title and body should answer:
- what changed across the whole branch
- which workflow or behavior improved
- which subsystems were touched
- which checks validated the change
- any follow-up or known limitation reviewers should know

Bad pattern:
- title/body describe only the last tweak from the current session
- docs-only framing hides code, infra, or workflow changes from the same branch

Good pattern:
- reviewers can predict the touched areas from the PR text
- testing notes match the actual commands or checks run
- the body explains the full branch, not just the latest prompt

## Write for a Reader Outside the Project

The PR body's audience is someone with zero context — they did not see the
session, the tracker issue, or the codebase. They open the PR and must
understand, in plain words, what was done, why, what got fixed, and how.

Rules that follow from that:

- Top-level story first, mechanics second. No filler, no restating the diff.
- Simplest words that are still precise. Prefer "an integrity check re-hashed a
  huge dependency file by file on every build" over "fingerprint verification
  exhibited superlinear IO amplification".
- Bold the few numbers and outcomes that carry the story (**782s → 0.16s**),
  and nothing else.
- Explain repo-specific context inline in one short paragraph (a `Background`
  section) instead of assuming it. If understanding the fix requires knowing
  how dep caching works, say how dep caching works — in three sentences.
- Add a schematic only when it compresses the story, and keep it to a
  minimal plain-text diagram in a fenced `text` block (see Diagram section).
- Anchor in concrete user or developer impact: "fresh worktree no longer sits
  13 minutes in dependency sync", not "improves sync performance".

## Body Shape

Follow the repository's PR template where present. Otherwise two shapes.
Pick by weight, not by mood.

**Narrative shape** — default for any substantive PR (a real bug, a perf win,
a behavior change, anything with a story):

```md
## TL;DR
One short paragraph: symptom, cause, what this PR does, headline number or
outcome in bold. A reader who stops here still got the point.

## Background: <the one thing you must know>
Only if needed. 2–4 sentences of repo context that make the rest legible.

## The problem
What was wrong, how it manifested, why it happened. Narrative, not bullets,
if the causality matters.

## The fix
What the change does and why it is safe/correct, in plain words.
Before/after plain-text schematic here if it helps.

## Migration
Only if reviewers or users must do (or explicitly need NOT do) anything.

## Changes
- `path/to/area` — what changed here and by what mechanism
- ...

## Testing
- ...
```

Section titles are content-bearing, not fixed labels — `## Background: how
dependency caching works here` beats bare `## Background`. Drop any section
with nothing to say; never pad.

**Compact shape** — for small or mechanical PRs (docs fix, rename, config
knob, single obvious bugfix) where a story would be padding:

```md
## Why
- ...

## Summary
- ...

## Change Map
- `path/to/area` — what changed here and how (mechanism, not restated summary)

## Testing
- ...
```

## Change Map / Changes

The per-area breakdown appears as `## Changes` in the narrative shape and
`## Change Map` in the compact shape — same content, same rules. Add it for
any change that touches more than one area of the repo. It is a technical,
per-area breakdown so a reviewer can predict the blast radius before opening
the diff — the code counterpart to the user-facing story above it.

"Area" is whatever unit best explains the change, not just code modules. The
profile supplies the project's area list; without one, use the project's
architecture map or top-level layout. Typical areas:

- an engine, service, or product module, named by path and one-line purpose
- UI code or generated API bindings
- scripting, shaders, or data files plus their schema
- build files and the build-tool graph
- scripts and wrappers (helper scripts, build/run entrypoints, env hooks)
- CI, pre-commit, or checks
- docs and repo skills
- tests, at any layer

Derive it from the actual branch diff, not session memory:

```bash
git diff --name-status "$BASE"...HEAD
git diff --stat "$BASE"...HEAD
```

Group the changed files by area, then write one bullet per area. Each bullet
names the area by path and says what changed there *and by what mechanism* —
not a restatement of the summary.

- Order bullets by significance: the area carrying the core change first,
  incidental/test/doc areas last.
- State the mechanism or interface touched: new function, changed signature,
  new dependency edge, schema field, config knob, build target, script flag,
  hook, migration.
- Note cross-area effects explicitly: "A now depends on B", "callers of X must
  pass Y", "ABI/struct layout changed", "consumers must regenerate bindings".
- Keep each bullet to one line; if an area needs a paragraph, it probably wants
  a small plain-text schematic or a PR split.
- Skip the section entirely for a genuinely single-area or trivial change —
  do not pad it.

Example (a change that spans code, build, generated output, script, and docs):

```md
## Change Map
- `src/config` — added `PR_MAP` knob; parsed in `Config::load`, defaulted off
- `src/editor/pr` — new `buildChangeMap()`; consumes Config, emits the body section
- `ui/graphql` — regenerated bindings after schema field `prBody` added
- `scripts/create-pr.sh` — new `--change-map` flag threaded into body assembly
- `build/tests` — new coverage target for the map builder
- `docs/architecture/overview.md` — documented the new editor/pr entry point
```

## View PR

```bash
gh pr list --repo "$REPO" --head "$(git branch --show-current)"
gh pr view "$PR_NUMBER" --repo "$REPO" --web
```

## Notes

- Always invoke the repo-local helper from the repo root when the repo has one.
- Prefer real Markdown newlines in `--body`.
- If the helper normalizes escaped `\\n` sequences, still prefer passing real
  newlines instead of relying on shell escaping.
- For a long body, write it to a file and use `--body-file <path>` instead of
  `--body "$(cat file)"`.

## PR Chains

Use PR chains to split large change sets into reviewable pieces. Each PR should
target the previous branch in the chain. Show both each incremental diff and
the combined target diff.

```text
default branch <- PR1 (branch-1) <- PR2 (branch-2) <- PR3 (branch-3)
```

**GitHub native stacks (public preview since 2026-07-30) adopt base-chained
PRs automatically and then own the chain mechanics.** Before any
`gh pr edit --base` or `gh pr merge` on a chain member, check whether the host
adopted the chain as a native stack — on GitHub, the PR's REST payload
carries a `.stack` object. On an adopted stack:

- `gh pr edit --base` on a member fails ("part of a stack"); GitHub retargets.
- `gh pr merge` / `--auto` on a member fails ("must be merged sequentially
  using the stack merge API").
- Merge the chain with the async stack API on the TOP PR — it merges
  everything below it sequentially:

```bash
echo '{"merge_method": "merge", "merge_action": "default", "sha": "<top head sha>"}' | \
  gh api --method PUT "repos/$REPO/pulls/<top>/merge-async" --input -
gh api "repos/$REPO/pulls/<top>/merge-async/<uuid>"   # poll until not pending/enqueued
```

- Every required status check (the project's pre-merge status, named in the
  profile) is still required on EVERY head in the stack before merge-async
  succeeds; a status description caps at 140 characters.
- Local restacks after amends stay manual: `git rebase --onto <new-base>
  <old-base-sha>` bottom-up, then `push --force-with-lease` per branch.
- A project merge helper may detect the adopted stack and stop after posting
  its receipt, printing the merge-async commands above rather than attempting
  a per-PR merge it cannot complete; the profile says whether it does.

For a chain the host has NOT adopted as a stack, the manual protocol still
applies once the user authorizes the merge:
1. Retarget the downstream PR first.
2. Merge the current PR.
3. Rebase the downstream branch onto its updated base.
4. Force-push with lease.

A squash changes commit identity, so verify child diffs afterwards. Creating
a stack never implicitly authorizes its merge.

Never:
- merge the current PR before retargeting the downstream PR (manual chains)
- skip restacking after a squash merge
- replace the GitHub merge with a local `git merge --squash` plus manual PR close

## Submodule Changes

If the branch updates a submodule pointer, you usually need two PRs:
1. a PR in the submodule repository
2. a PR in the consumer repository updating the submodule pointer

Prepare the dependency PR first, then the consumer PR or pointer update to an
intended accessible revision. Explain the merge/deployment order and validate
compatible versions. Do not imply the two repositories will publish
atomically or that a private local SHA is fetchable.

## Diagram

Add a diagram only when it makes the change materially easier to understand
than prose or the change map. Use a minimal plain-text schematic inside a
fenced `text` block, usually next to the paragraph it clarifies:

```text
BEFORE                    AFTER
build -> hash 93k files   build -> hash 3-5 files
      -> 782 s                  -> 0.16 s
```

Keep it to one idea, one reading direction, short labels, and at most a handful
of nodes or steps. Use ASCII characters only; do not use Mermaid, diagram
subagents, rendered assets, or decorative box drawing. If the flow cannot stay
small and immediately legible, explain it with prose and change-map bullets
instead.

Do not add diagrams for tiny fixes, docs-only edits without flow changes,
simple style/lint changes, or changes where bullets are clearer.

## Friction

If this skill, the helper it drives, or the docs it relies on create avoidable
friction — a dead link, a stale or wrong step, a broken/renamed command, or
user pushback when they corrected you — don't just work around it. At task
closure, never mid-run, tell the user what you hit; fix shared-skill text in
the skills repository and project helper or profile text in the project,
following that project's own self-improvement policy where it has one. Never
auto-merge.
