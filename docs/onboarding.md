# Sentifold skills onboarding

Goal: `/orchestrate` in Claude Code and `$orchestrate` in Codex work in a
participant's own project, including its checks and an independent review,
without a gamejam checkout.

1. **Access and version.** The participant checks access to the private
   `sentifold/skills`, Python 3.11+, Bash and the CLI of each runtime they use.
   They use a reviewed commit; for gamejam that is `.agents/shared-skills.lock.json`.
   Authentication stays personal.
2. **Sources.** Run `install.py plan --runtime both` (or one runtime) and read the
   real source/destination paths. With dotfiles in place, transfer ownership of
   the shared packages only, as the README describes. Folders with personal
   edits are preserved; `--adopt NAME` is for explicitly chosen links.
3. **Install.** Run `apply`, then `doctor` with the same home/runtime roots.
   `doctor` checks the legacy duplicates in `~/.codex/skills` and, for Codex,
   `features.multi_agent` / `agents.max_depth` in `config.toml`; copies of the
   shared packages inside a project are checked by that project's test (in
   gamejam, `Scripts/tests/test_shared_skills_setup.py`). Installer state lives in
   `~/.local/share/sentifold-skills-state/` (the receipt and, during `apply`, the
   journal); an interrupted `apply` is recovered by the next `plan`/`apply`.
   The installer never changes model, auth, MCP or approval settings.
4. **New session.** Open the project and confirm that orchestrate and
   review-agent are discovered. Before implementing anything the agent must
   name the right project, base branch and checks. For the sleash pilot:
   sleash, main, make check; extra targets and the bot only per the current
   contract of that branch.
5. **CLI check.** Select an available model explicitly. The helper records the
   actual CLI path/version and run ID. If the PATH binary does not support the
   selected model, check the installation; switching binaries is explicit. For
   the app distribution the `codex-code-mode-host` companion must ship with the
   same CLI. Neither the model nor a personal routing wrapper is replaced
   automatically.
6. **A real task.** Complete a small fix with a verifiable result, the real
   project checks and a review in both runtimes in use. Test the second
   provider separately. An unavailable CLI/auth, an early child finish and a
   missing SendMessage must produce recovery or an honest INCOMPLETE, never a
   hang or a fake successful review.
7. **Update and rollback.** Install a newer version from another checkout, then
   return to the previous one through its `install.py apply` (for gamejam,
   `Scripts/setup-shared-skills.py --revision <old-commit> apply`). Run the usual
   dotfiles sync and `doctor` again: the old sources must not take the links
   back; if they do, `plan` names the entry and the action (restore, delete the
   recreated legacy link, or repeat `--adopt NAME`).
8. **Feedback.** The shared workflow is fixed by a PR to skills; product gates by
   a PR to the project; machine setup in its own configuration. Never edit the
   installed release in the middle of a product task.

## Connect a project

The procedure for any consumer without a gamejam checkout. Every path below is
inside the project checkout.

1. **Install the pinned release per the README.** From a `sentifold/skills`
   checkout at a reviewed commit: `python3 install.py plan --runtime both`, then
   `apply` and `doctor` with the same `--home`/`--runtime`. A project with a pin
   file (step 5) runs its own bootstrap instead.
2. **Create the profile.** Copy `templates/project-workflow.md` from the release
   to the project's `.agents/project-workflow.md` (create `.agents/` if missing;
   sleash currently has no `.agents/`, `.claude/` or `.codex/`) and replace every
   `<placeholder>` with facts of that checkout: the base is `develop` in gamejam
   and cloud, `main` in sleash, captain and codex-multi-auth, `master` in
   teamclaude; checks are `make check` in sleash per its `AGENTS.md`, and in
   cloud `make check` plus a final `make e2e` for the user-facing changes it
   lists. Delete an item that does not apply instead of leaving a guess; a
   profile never imports another project's commands. A filled example:
   `examples/sleash.project-workflow.md`; the reference with product gates is
   `.agents/project-workflow.md` in gamejam.
3. **Codex: allow nested agents.** The review-agent topology
   (caller → `review-orchestrator` → `review-lens`) needs
   `[features] multi_agent = true` and `[agents] max_depth = 2` in
   `config.toml`: the user-level `~/.codex/config.toml` (checked by `doctor`) or
   the project's `.codex/config.toml` (not read by `doctor`). Claude Code needs
   no configuration.
4. **Smoke.** Open a new session in the project and run `/orchestrate`
   (Claude Code) or `$orchestrate` (Codex) on a tiny documentation change.
   Expected: the agent reads the profile and names the project's base and
   checks; it records `not-applicable:` with a reason for the runtime smoke;
   Final Review runs both provider legs or ends honestly with
   `REVIEW INCOMPLETE` and a reason. If `## Provider policy` is left as `ask`,
   the run stops at the model question; that is expected. Answer explicitly or
   fill the section with models.
5. **Pin file (optional).** A project that needs a fixed revision repeats the
   gamejam scheme: `.agents/shared-skills.lock.json` with `version`, `repository`,
   `revision` (full commit) and `packages`, plus a bootstrap
   `Scripts/setup-shared-skills.py {plan,apply,doctor,uninstall,run}` with
   `--revision <commit>` and `--cache-dir`, which clones the release into
   `$XDG_CACHE_HOME/sentifold-skills/<revision>` (default
   `~/.cache/sentifold-skills/<revision>`), verifies it and runs `install.py`
   with the lock's `--package` list. Other projects may copy this scheme or rely
   on the installed release.
6. **Update and rollback.** A new revision: `install.py apply` from the new
   checkout with the same roots (or a PR with the new `revision` in the lock,
   then the bootstrap `apply`). Rollback: `install.py apply` from the previous
   checkout; for pinned projects the bootstrap `--revision <previous-commit>
   apply`. Then `doctor` and the smoke from step 4.
7. **Where fixes go.** The shared workflow, scripts and template: a PR to
   `sentifold/skills`. A project's base, checks, executors and report paths: a
   PR to its `.agents/project-workflow.md`.

For the pilot, record: participant, project, runtime and CLI version, skills
commit, check commands, a link to the real task/PR, the second-provider result,
and update/rollback. An empty item means an unverified part, not a PASS.

First the sleash pilot and one more participant in gamejam, then the remaining
active projects. These PRs provide the set and the procedure; they do not prove
that the whole team has installed it. Do not message participants without the
user's explicit instruction.
