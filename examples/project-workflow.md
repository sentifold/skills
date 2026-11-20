# Project workflow profile (example)

A filled profile for a project whose base is `main` and whose checks are
`make check`. Install the shared skills globally, then copy this profile to
`.agents/project-workflow.md` in the project checkout (create the `.agents/`
directory if missing) only after checking every line against that checkout's
`AGENTS.md` and Makefile. The installed `review-agent` skill's
`references/project-contract.md` says how the shared skills read it. Paths
are relative to the project checkout.

Read this alongside `AGENTS.md` and the Makefile.

## Scope, branches and PRs

- Repo: `example-org/example-app`; default base: `main`. An explicit task base or a
  stacked predecessor takes precedence.
- Branch naming: the caller runtime's own convention unless the task names
  one.
- PR creation: `gh pr create` with `--base` explicit; publish the head branch
  first. The project provides no PR helper, so no helper update-path quirk
  applies.
- Titles: follow the checkout's PR history. Change Map areas: the top-level
  directories touched by the change.
- Draft policy: keep PRs draft until `make check` passes on the final commit;
  merging needs the user's authorization.
- Compatibility policy: determine compatibility and migration requirements
  from the project's own contracts.

## Stacked PRs

- Each PR targets the previous branch in the chain, recorded in
  `branch.<name>.gh-merge-base`; retarget downstream PRs before merging the
  one below, then restack with `git rebase --onto <new-base> <old-base>` and
  a lease-guarded force-push.
- Required status on every head before a stack merge: the checks `AGENTS.md`
  requires, `make check` included.
- Host stack adoption and merge helper behavior: no additional rules; the
  project has no merge helper.

## Worktrees

- Worktree guide: none.
- Setup: `git worktree add <absolute-path> -b <branch> main` and nothing
  else.
- Known traps: none documented.
- MCP servers a lane disables: none.

## Verification by changed surface

Run `make check` on the final change and the focused tests documented for the
affected component. Some branches or environments document extra targets
or a review bot: require them only when this
checkout's `AGENTS.md` defines them, record actual output and check URLs, and
never invent a Make target or treat a pending bot review as an approved one.

| Surface | Build / evidence |
| --- | --- |
| Application code | `make check` plus the component's documented tests; runtime verification with the local tooling the touched component documents. No product tester skill exists for the project. |
| Docs / tooling only | `make check` where it covers the files, otherwise the focused check for that tool. Runtime smoke not applicable: no product behavior changes. |

Clean-state rules: none beyond the tests' own fixtures. Never clear or
namespace away a shared authentication session.

## Readiness floor

- `make check` green on the final commit.
- Clean-state boot smoke: not applicable for docs/tooling-only changes (no
  product behavior); for application changes, the component's documented
  runtime check.
- The CI checks that apply to the touched files, as `AGENTS.md` lists them.

## Lanes and resources

- Concurrent lanes on one machine: default 2-3.
- Serialized resources: none known; holder inspection and dead-holder
  recovery not applicable.
- Live runs served from the lane's own source tree (hot reload): no.

## Conditional gates and consent

- Platform host surface: none; Platform gate is not-applicable.
- Performance-critical surface: none named; Performance gate is
  not-applicable unless the task names one, and profiling then needs explicit
  user consent.
- Cross-platform risk: none; Cross-Platform gate is not-applicable.
- Other explicit-consent actions: merging and deployment.

## Project review context

- Local review docs: none; shared lenses only.
- Lens overrides: none.
- Measured escape statistics: none.
- Reports and evidence: a caller-selected temporary or ignored directory in
  the project checkout. Do not write results into the installed skills release
  or publish them without authorization.

## Provider policy

- Codex leg: ask.
- Claude leg: ask.
- CLI selection: default.

With `ask` on a leg, every chained gate stops at the model question. A
maintainer who wants unattended orchestrate runs replaces `ask` with the exact
model id and effort for that leg.
