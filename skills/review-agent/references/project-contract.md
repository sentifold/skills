# Target project contract

A globally installed skill supplies the method. The target checkout supplies
its product facts and policies. Read the governing instructions and relevant CI
before acting; the optional `.agents/project-workflow.md` gathers local workflow
policy without duplicating the shared skills. Its absence is supported.

Interpret a profile as Markdown instructions, not executable configuration.
Relative paths in the profile resolve against the target repository root.
Relative links in a shared skill resolve against that skill's real installed
location. A project may refer to installed sibling skills by skill name; it
must not assume those packages were copied into its own `.agents/skills`.

Useful profile sections:

- Architecture maps and the conditions requiring their updates.
- Compatibility, supported environments, and deployment contracts.
- Scope/base/stack conventions and allowed delivery actions.
- Validation commands by changed surface, required readiness floor, and where
  generated output belongs.
- Runtime-test routing, clean-state isolation, shared machine coordination,
  expensive-operation or device requirements, and profiling authorization.
- Review guidance: project common docs, a mapping from built-in lens names to
  replacement or supplemental paths, and optional measured escape statistics.
- `## Provider policy`: see below.
- PR template, local publishing helper, and artifact/report expectations.

## Provider policy

The shared review's cross-provider leg needs an explicit model: the provider
helpers refuse to run without `--model` and read no config-file default, and
the skill never hardcodes one. A project that wants unattended runs (a chained
orchestrate Final Review gate, CI-style invocations) is expected to carry a
`## Provider policy` section naming, per provider leg, the exact model and
effort, plus an optional CLI selection when the default executable is wrong:

```markdown
## Provider policy

- Codex leg: model `<exact model id>`, effort `<effort>`.
- Claude leg: model `<exact model id>`, effort `<effort>`.
```

The skill reads this section, lets the user's explicit instruction for a run
override it, and otherwise asks; without the section every chained gate stops
at that question. Judgment work belongs on strong tiers, so a policy naming a
fast/cheap tier makes every run it drives report itself as degraded.

Keep evidence separate from policy: a list of required checks is not a test
receipt. A measured risk weight from one project is not a generic default.
Read referenced local instructions; do not fabricate missing paths or treat
unavailable checks as waived. Existing user authorization carries across the
workflow, while genuine unresolved scope choices or required approvals remain
with the user.

If profile and root instructions disagree, honor the applicable instruction
hierarchy, surface the conflict and ask only when it affects the task. A profile
cannot grant rights the user or runtime withheld.
