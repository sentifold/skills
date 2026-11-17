# Sentifold skills

Shared engineering workflows for Sentifold projects, usable from Claude Code and
Codex without a gamejam checkout. Project commands, product knowledge and release
policy stay in each consuming repo's `AGENTS.md` and optional
`.agents/project-workflow.md`.

| Package | Runtime | Entry |
| --- | --- | --- |
| `orchestrate` | Claude Code, Codex | Explicit workflow invocation |
| `orchestrate-linked-sessions` | Claude Code (desktop app) | Explicit workflow invocation; `orchestrate` with every lane as a linked session |
| `delegate` | Claude Code | Explicit workflow invocation; one medium task as one PR, in two layers: the session specs and reviews, Codex writes |
| `review-agent` | Claude Code, Codex | Explicit layered review, or the named final gate of `orchestrate` or `delegate` |
| `github-create-pr` | Claude Code, Codex | Create/update a PR when requested |
| `codex` | Claude Code | Explicit second-provider task or authorized workflow leg |
| `claude` | Codex | Explicit second-provider task or authorized workflow leg |
| `claude-stock-code-review` | Claude Code | Internal first-review dependency; separate from the stock command |

`catalog.json` is the installable set. `agents/` supplies the review orchestrator
and lens agents for both runtimes. Domain skills stay in gamejam. `history-search`, rebase,
Linear and Mermaid are outside this release; `pr-arch-review` is retired.

## Install

Requirements: Python **3.11+**, Git, Bash, access to this private repo, and the
CLI for each runtime you use. Provider helpers support macOS/Linux/WSL through
POSIX process groups and native Windows (Git Bash) through Job Objects.
POSIX hosts need `ps -axo pid=,pgid=,stat=` and `ps -o stat= -p <pid>` support.
On Windows, `python3` must resolve to a real interpreter, not the Microsoft
Store alias. Authentication and model availability remain personal runtime settings.

Check out a reviewed commit or release, keeping the whole checkout at a stable
path. The provider scripts depend on the repository's `lib/`; copying individual
skill directories is insufficient.

```sh
git clone https://github.com/sentifold/skills.git "$HOME/.local/share/sentifold-skills-source"
cd "$HOME/.local/share/sentifold-skills-source"
# Check out the release the team agreed on (a tag or main).
python3 install.py plan --runtime both
python3 install.py apply --runtime both
python3 install.py doctor --runtime both
```

The installer prints every planned change as `link -> target`, with
`(was -> <previous target>)` for a symlink it adopts, retargets or removes, and
writes only the selected packages, agent files and its ownership receipt. It
does not change model, authentication, MCP, approval, network or nesting
configuration.

- Codex skills: `<home>/.agents/skills/` (`--home`, default `$HOME`;
  `CODEX_HOME` does not move it); agents: `$CODEX_HOME/agents/`
  (default `~/.codex/agents/`).
- Claude skills and agents: `$CLAUDE_CONFIG_DIR/skills/` and `agents/`
  (default `~/.claude/`).
- Ownership receipt: `<home>/.local/share/sentifold-skills-state/receipt.json`,
  keyed by resolved destination path, so a symlinked home or `/var` versus
  `/private/var` spelling is one installation. This directory holds only the
  installer's own state; the source checkout lives elsewhere.
- `--runtime codex` or `claude` installs only that runtime's complete set.
- `--package NAME` (repeatable) installs that package plus everything its
  `requires` closure names for each selected runtime, and the agents whose
  requirements are then met; the selection is the desired state, so a package
  left out of a later `apply` is removed. Default: every catalog package.
- `--home`, `--codex-home`, `--claude-config-dir` support explicit roots and
  isolated test installations; see `python3 install.py --help`.

`apply` takes `install.lock` in the state directory and writes a journal of the
planned changes there before touching any destination. If the process is killed
mid-way, the next `plan` reads that journal, owns again every change it finds
written (including adopted links and their recorded original targets), reports
any destination that changed since, and `apply` or `uninstall` completes the
recovery and clears the lock. A journal whose process is still running is never
taken over.

Skills are symlinks; agent definitions are rendered real files pointing at the
same checkout. Keep that checkout. Do not edit an installed release while an
agent is using it. Codex's supported user skill root and agent-file format are
specified in [skill discovery](https://learn.chatgpt.com/docs/build-skills) and
[custom agents](https://learn.chatgpt.com/docs/agent-configuration/subagents).

## Existing installations and dotfiles

Run `plan` before `apply`. Unowned folders/files and modified managed files are
conflicts, not overwrite targets. Move or reconcile those files yourself. For an
existing symlink whose ownership you deliberately transfer, repeat
`--adopt NAME` for that package on `plan` and `apply`. Original targets are saved
for uninstall, including legacy duplicates in `~/.codex/skills`. A directory
there is reported as a legacy duplicate to move aside; the installer never
removes ordinary files or directories.

If another link manager later retargets an owned symlink or recreates a removed
legacy link, `plan` names the entry and the fix: restore it, delete the
recreated legacy link, or pass `--adopt NAME` again to take it over with the new
target recorded. `uninstall` proceeds when the disk already holds an entry's
restore target.

If dotfiles or another sync tool owns a package, remove **that package only**
from its link plan before adoption. In the earlier Sentifold dotfiles setup,
`link-agent-skills` links `github-create-pr` from dotfiles and `codex`/`claude`
from `gamejam-agent-skills`; those three ownership rules must be retired for a
machine adopting this release. Keep all unrelated personal skills, including the
four deferred packages. A later dotfiles sync followed by `doctor` must leave
these links intact. This repo does not silently edit another dotfiles repository.

Do not keep project-local copies of the six shared packages or review agents in
a migrated project: they shadow the installed version. Migrate a consumer only
with its project profile and an install pointer in its README in the same change.

## Use in a project

Start a new session in the target project after installing. Read its `AGENTS.md`
and CI instructions first. Invoke `/orchestrate` in Claude Code or `$orchestrate`
in Codex with a concrete task; its reviews run light unless you name `heavy`
(`/orchestrate heavy <task>`). In the Claude desktop app,
`/orchestrate-linked-sessions` runs the same loop with every lane as a linked
session of its own. For one medium task that is one PR, `/delegate <task>` in
Claude Code runs a single lane in two layers: the session writes the spec and
reviews, Codex writes the code. The shared workflow discovers the project's base,
checks and optional `.agents/project-workflow.md`; it never assumes `develop`,
a native game runtime, or permission to merge/deploy.

[Project contract](skills/review-agent/references/project-contract.md) explains
local checks and review overlays. [Sleash example](examples/sleash.project-workflow.md)
shows a `main`/`make check` consumer. Gamejam retains native/browser/iOS testing,
profiling consent, platform policy and measured review priorities in its profile.

**Connect a project:** copy [templates/project-workflow.md](templates/project-workflow.md)
to the project's `.agents/project-workflow.md`, fill every placeholder from
that checkout's own instructions, and follow the numbered procedure in
[docs/onboarding.md](docs/onboarding.md#connect-a-project)
(install, profile, Codex `agents.max_depth = 2`, smoke run, optional pin file,
update/rollback).

Nested agents and resume tools vary by client. The parent records scope, child
IDs, deadlines and completed evidence. If nesting or SendMessage is unavailable,
it coordinates sibling agents and collects results itself; incomplete coverage
is reported as incomplete. Missing second-provider authentication never becomes
a claimed cross-provider pass.

Provider helpers require explicit `--model`. Read the corresponding SKILL.md
before use. CLI paths may be selected explicitly; no automatic switch to an app
binary or another model bypasses a user's wrapper. Logs contain version/run IDs,
not credentials. `doctor` checks installation and CLI versions; it does not prove
a model can run or that a user's inherited configuration isolates network/auth.
For Codex it reads `config.toml` and warns only when `features.multi_agent` or
`agents.max_depth` (2 for the heavy review topology) is missing or too low.

## Update, rollback and uninstall

Run tests in a new checkout, then run its installer with the same home/runtime
roots. Owned links and rendered agents switch together. To roll back, run the
previous checkout's `install.py apply` with those same arguments. Keep both
checkouts until the new release has passed the project's smoke task. Projects
do not pin a revision: the team moves to a release together.

`python3 install.py uninstall` removes only unchanged owned objects and restores
adopted symlinks. Modified files block the transaction. No automatic updates run
at shell or agent startup.

## Team onboarding

Use the [onboarding checklist](docs/onboarding.md) for a first installation,
Mikhail's sleash pilot, model compatibility checks and the update/rollback drill.
A successful `doctor` is installation evidence; a real project task in a new
session is workflow evidence. Do not mark a participant onboarded from a clone
or a menu entry alone.

## Development

```sh
python3 -m unittest discover -s tests -v
```

Tests use temporary homes/repos and fake CLIs; they neither publish PRs nor call
models. CI runs them on Linux with Python 3.11, 3.12 and 3.14, and on macOS
with Python 3.14. Keep behavior tests for installer conflicts, crash recovery and
provider exit/cancel/result handling when changing them.
Use independent task fixtures for workflow changes, then pilot the supported
clients before rolling the version out to the team.

Fix common workflow behavior here; fix product commands and policy in its project;
fix personal machine setup in its owner's configuration. Preserve the source
notices in [PROVENANCE.md](PROVENANCE.md) and package licenses. Do not commit
credentials, transcripts or private machine paths.
