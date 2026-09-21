# Source provenance

The initial extraction is from `sentifold/gamejam` commit
`f4dbd06ec62f86b39138ad86519a6ce6b37a5971` (22 September 2026).

| Shared content | Original paths |
| --- | --- |
| orchestrate | `.agents/skills/orchestrate/` |
| review-agent and nine lenses | `.agents/skills/review-agent/`, `docs/agent/review-common.md`, `docs/agent/linter-common.md`, `docs/agent/review/`, `docs/agent/linter/` |
| agent definitions | `.codex/agents/review-{orchestrator,lens}.toml`, `.claude/agents/review-orchestrator.md` |
| provider packages | `.claude/skills/codex/`, `.agents/skills/claude/` |
| stock review copy | `.claude/skills/claude-stock-code-review/` (upstream version and attribution retained in its SKILL.md) |
| PR workflow | `.agents/skills/github-create-pr/`; compared with the portable dotfiles version at commit `3cc9a5f8958278f12d6c49cd88d07ff19d79064e` |
| provider test origins | `Scripts/tests/test_cross_provider_helpers.py`, provider-specific cases in `Scripts/tests/test_native_repo_skills.py` |

This extraction adapts those instructions and helpers; it does not import
unrelated gamejam history, secrets, reports, machine configuration or transcripts.
Existing package licenses/notices remain with their packages. This private
repository does not grant a new public redistribution license for imported work.
Project-specific review policy and measured escape statistics remain in gamejam.
