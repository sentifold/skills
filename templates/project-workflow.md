# <Project> workflow profile

Copy this file to `.agents/project-workflow.md` in the project checkout and
replace every `<placeholder>`. The shared Sentifold skills (`orchestrate`,
`review-agent`, `github-create-pr`) read it as Markdown instructions under the
project contract in the installed `review-agent` skill
(`references/project-contract.md`); it carries this project's facts and
policy, never the shared method. Every path
below is relative to the project checkout, not to the installed skills. Name
only commands, helpers, executors and paths that exist in this checkout; never
import another project's commands, branch names, environment variables or
report paths. Delete a bullet that does not apply instead of leaving a guess.

Read this alongside `<governing instructions: AGENTS.md / CLAUDE.md, CI docs,
architecture map>`.

## Scope, branches and PRs

Name the repository, the default base, branch naming, the PR helper and title
format, and the stacked-PR rules.

- Repo: `<owner/name>`; default base: `<branch>`. An explicit task base or a
  stacked predecessor takes precedence.
- Branch naming: `<convention, or "caller runtime's own convention">`.
- PR creation: `<helper path and how to call it, or "gh pr create">`; publish
  the head branch first; pass `--base` explicitly. Note any helper quirk on
  the update path (`<quirk, or none>`).
- Titles: `<format>`. Change Map areas: `<area list or the architecture map
  that defines them>`.
- Draft policy: keep PRs draft until `<required checks>` pass; merging needs
  the user's authorization.
- Compatibility policy: `<what must stay compatible, or "early-stage, no
  compatibility layer required">`.

## Stacked PRs

State how a dependent chain is based, restacked and merged in this
repository.

- Each PR targets the previous branch in the chain, recorded in
  `branch.<name>.gh-merge-base`; retarget downstream PRs before merging the
  one below, then restack with `git rebase --onto <new-base> <old-base>` and
  a lease-guarded force-push.
- Required status on every head before a stack merge: `<status name, or
  "the required checks above">`.
- Host stack adoption and merge helper behavior: `<what the host or the
  project's merge helper does with an adopted stack, or "no additional
  rules">`.

## Worktrees

Name the worktree guide and the provisioning a fresh lane worktree needs.

- Worktree guide: `<path, or "none">`.
- Setup: `git worktree add <absolute-path> -b <branch> <base>` plus
  `<env seeding hook, LFS or submodule hydration, dependency install, or
  "nothing else">`.
- Known traps: `<long hydration needing a background call, shared files to
  preserve, or "none">`.

## Verification by changed surface

List the checks and the live-test executor per surface. A row with no runtime
behavior records `not-applicable:` for the runtime smoke with its reason.

Run `<required check command>` on the final change, plus the focused tests
documented for the affected component.

| Surface | Build / evidence |
| --- | --- |
| `<surface 1>` | `<commands, executor or tester skill, evidence to capture>` |
| `<surface 2>` | `<...>` |
| Docs / tooling only | `<focused checks>`. Runtime smoke not applicable; record the reason. |

Clean-state rules: `<what persisted state to clear before a live run, what
never to clear (shared auth), the isolation for auth-flow tests>`.

## Readiness floor

State what every PR must pass at its final commit before it leaves draft.

- `<green build / required check command>`.
- `<clean-state boot smoke, or "not applicable for docs/tooling-only changes,
  reason recorded">`.
- `<CI checks for the touched files>`.

## Lanes and resources

Name the machine-wide resources parallel lanes contend for and how to
inspect and clear a dead holder.

- Concurrent lanes on one machine: `<count or "default 2-3">`.
- Serialized resources: `<build-cache lease, dependency lock, device,
  shared auth mutation, or "none">`; holder inspection: `<command or
  "not applicable">`; dead-holder recovery: `<steps, or "not applicable">`.
- Live runs served from the lane's own source tree (hot reload): `<yes, so
  the simplification pass must not overlap the live test; or "no">`.

## Conditional gates and consent

State which orchestrate gates can apply here and what each one needs.

- Platform host surface: `<host, executor and simulator route, or "none;
  Platform gate is not-applicable">`.
- Performance-critical surface: `<paths and profiling route; profiling needs
  explicit user consent, or "none; Performance gate is not-applicable">`.
- Cross-platform risk: `<tooling and reachable targets, or "none;
  Cross-Platform gate is not-applicable">`.
- Other explicit-consent actions: `<release, deploy, publication, or "none">`.

## Project review context

Point the shared review at local guidance and say where evidence goes.

- Local review docs: `<paths, or "none; shared lenses only">`.
- Lens overrides: `<built-in lens name -> project-relative replacement or
  supplement path, with reason; or "none">`.
- Measured escape statistics: `<path, or "none">`.
- Reports and evidence: `<ignored directory for review reports, logs,
  screenshots>`; publish only when the task authorizes it.

## Provider policy

Name the exact model and effort per cross-provider leg; the helpers refuse to
run without one, and an unattended orchestrate run stops here without it.

- Codex leg: model `<exact model id>`, effort `<effort>`.
- Claude leg: model `<exact model id>`, effort `<effort>`.
- CLI selection: `<value the helper's --cli accepts, or "default">`.
