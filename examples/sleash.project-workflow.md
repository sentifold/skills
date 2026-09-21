# Sleash workflow profile (example)

Install the shared Sentifold skills globally; gamejam is not required. Copy this
profile to `.agents/project-workflow.md` only after checking it against this
checkout's `AGENTS.md` and Makefile.

- Repository: `sentifold/sleash`. Default branch: `main`; explicit task or stack
  bases take precedence.
- Read `AGENTS.md` first. Run `make check` on the final change and the focused
  tests documented for the affected component.
- Select runtime/UI verification from the changed sleash surface and its local
  tooling. Native game, iOS PlayerHost and Steam Deck gates do not apply.
- Some branches/environments use `make verify-local` and the GitHub Codex bot.
  Require those only if this checkout's documented workflow defines them; record
  actual output/check URLs. Do not invent a Make target or equate a pending bot
  review with an approved review.
- Determine compatibility/migration requirements from sleash's contracts, not
  gamejam's early-stage policy. Use local review context when present.
- Write reports to a caller-selected temporary or ignored directory. Do not write
  results into the installed skills release or publish them without authorization.
