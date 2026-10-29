"""Portable workflow contracts exercised against real temporary Git checkouts."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

import install


ROOT = Path(__file__).resolve().parents[1]
SCOPE = ROOT / "skills/review-agent/scripts/resolve_scope.py"
WORKFLOWS = ("orchestrate", "orchestrate-linked-sessions", "review-agent", "github-create-pr",
             "claude-stock-code-review")
PROFILE_TEMPLATE = ROOT / "templates/project-workflow.md"
PROFILE_SECTIONS = (
    "Scope, branches and PRs",
    "Stacked PRs",
    "Worktrees",
    "Verification by changed surface",
    "Readiness floor",
    "Lanes and resources",
    "Conditional gates and consent",
    "Project review context",
    "Provider policy",
)


class ReviewScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="workflow fixture ")
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name).resolve() / "consumer with spaces"
        self.repo.mkdir()
        env = patch.dict(os.environ, {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull})
        env.start()
        self.addCleanup(env.stop)
        self.git("init", "-q", "-b", "trunk")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "core.hooksPath", str(self.repo / ".empty-hooks"))
        (self.repo / "base.txt").write_text("base\n")
        self.git("add", "base.txt")
        self.git("commit", "-qm", "initial")
        self.initial = self.git("rev-parse", "HEAD").strip()
        self.git("update-ref", "refs/remotes/origin/trunk", self.initial)
        self.git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/trunk")
        self.git("switch", "-qc", "feature")
        (self.repo / "feature.txt").write_text("feature\n")
        self.git("add", "feature.txt")
        self.git("commit", "-qm", "feature")
        self.feature = self.git("rev-parse", "HEAD").strip()

    def git(self, *args):
        result = subprocess.run(["git", *args], cwd=self.repo, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, check=True)
        return result.stdout

    def scope(self, *args, ok=True, script=SCOPE, cwd=None):
        result = subprocess.run([sys.executable, str(script), "--repo", str(self.repo), *args],
                                cwd=cwd or self.repo.parent, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if not ok:
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertEqual(result.stdout, "")
            return result.stderr
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_default_remote_branch_and_cwd_are_not_assumed(self):
        result = self.scope()
        self.assertEqual(Path(result["repository_root"]), self.repo)
        self.assertEqual(result["base_ref"], "refs/remotes/origin/trunk")
        self.assertEqual(result["base_commit"], self.initial)
        self.assertEqual(result["head_commit"], self.feature)
        self.assertEqual(result["changed_paths"], ["feature.txt"])

    def test_stacked_parent_config_overrides_remote_default(self):
        self.git("branch", "stack-parent")
        self.git("config", "branch.feature.gh-merge-base", "stack-parent")
        (self.repo / "child.txt").write_text("child\n")
        self.git("add", "child.txt")
        self.git("commit", "-qm", "child")
        result = self.scope()
        self.assertEqual(result["base_commit"], self.feature)
        self.assertEqual(result["base_source"], "branch.gh-merge-base")
        self.assertEqual(result["changed_paths"], ["child.txt"])
        explicit = self.scope("--base", "trunk")
        self.assertEqual(explicit["changed_paths"], ["child.txt", "feature.txt"])

    def test_missing_base_fails_without_guessing_last_commit(self):
        self.git("symbolic-ref", "--delete", "refs/remotes/origin/HEAD")
        self.assertIn("specify --base", self.scope(ok=False))
        self.assertEqual(self.scope("--base", "trunk")["base_commit"], self.initial)

    def test_exact_two_commit_scope_is_not_replaced_by_merge_base(self):
        self.git("switch", "-q", "trunk")
        (self.repo / "other.txt").write_text("other\n")
        self.git("add", "other.txt")
        self.git("commit", "-qm", "other branch")
        other = self.git("rev-parse", "HEAD").strip()
        self.git("switch", "-q", "feature")
        result = self.scope("--base", other, "--exact-base")
        self.assertEqual(result["base_commit"], other)
        self.assertEqual(result["changed_paths"], ["feature.txt", "other.txt"])
        self.assertEqual(self.scope("--base", other)["base_commit"], self.initial)

    def test_worktree_is_explicit_and_index_is_unchanged(self):
        (self.repo / "base.txt").write_text("staged\n")
        self.git("add", "base.txt")
        (self.repo / "base.txt").write_text("unstaged\n")
        (self.repo / "untracked name.txt").write_text("new\n")
        index = (self.repo / ".git/index").read_bytes()
        result = self.scope()
        self.assertFalse(result["includes_worktree"])
        self.assertEqual(result["changed_paths"], ["feature.txt"])
        self.assertEqual(result["excluded_dirty_paths"], ["base.txt", "untracked name.txt"])
        all_changes = self.scope("--include-worktree")
        self.assertEqual(all_changes["changed_paths"], ["base.txt", "feature.txt", "untracked name.txt"])
        self.assertEqual(all_changes["excluded_dirty_paths"], [])
        dirty = self.scope("--mode", "uncommitted")
        self.assertEqual(dirty["changed_paths"], ["base.txt", "untracked name.txt"])
        self.assertEqual(dirty["base_commit"], self.feature)
        self.assertEqual((self.repo / ".git/index").read_bytes(), index)

    def test_snapshot_detects_staged_unstaged_and_untracked_drift(self):
        (self.repo / "base.txt").write_text("stage one\n")
        self.git("add", "base.txt")
        (self.repo / "base.txt").write_text("working one\n")
        (self.repo / "extra.txt").write_text("first\n")
        first = self.scope("--mode", "uncommitted")["snapshot_sha256"]
        self.assertEqual(first, self.scope("--mode", "uncommitted")["snapshot_sha256"])
        (self.repo / "extra.txt").write_text("second\n")
        second = self.scope("--mode", "uncommitted")["snapshot_sha256"]
        self.assertNotEqual(first, second)
        (self.repo / "base.txt").write_text("working two\n")
        third = self.scope("--mode", "uncommitted")["snapshot_sha256"]
        self.assertNotEqual(second, third)
        self.git("add", "base.txt")
        fourth = self.scope("--mode", "uncommitted")["snapshot_sha256"]
        self.assertNotEqual(third, fourth)

    def test_untracked_symlink_records_target_without_following_it(self):
        missing = self.repo.parent / "missing external file"
        (self.repo / "link").symlink_to(missing)
        result = self.scope("--mode", "uncommitted")
        self.assertEqual(result["untracked_files"][0]["kind"], "symlink")
        self.assertFalse(missing.exists())

    def test_dirty_submodule_cannot_be_certified_by_parent_gitlink(self):
        child = self.repo / "nested"
        child.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "trunk"], cwd=child, check=True)
        for key, value in (("user.name", "Fixture"), ("user.email", "fixture@example.invalid")):
            subprocess.run(["git", "config", key, value], cwd=child, check=True)
        (child / "inside.txt").write_text("child\n")
        subprocess.run(["git", "add", "inside.txt"], cwd=child, check=True)
        subprocess.run(["git", "commit", "-qm", "child"], cwd=child, check=True)
        self.git("add", "nested")
        self.git("commit", "-qm", "gitlink")
        (child / "inside.txt").write_text("dirty child\n")
        self.assertIn("separate review snapshot: nested", self.scope("--include-worktree", ok=False))
        self.assertIn("nested", self.scope()["excluded_dirty_paths"])

    def test_worktree_cannot_be_spliced_onto_an_unrelated_head(self):
        self.assertIn("current HEAD", self.scope("--head", self.initial, "--include-worktree", ok=False))
        self.assertIn("omit base/head", self.scope("--mode", "uncommitted", "--base", "trunk", ok=False))
        self.assertIn("requires an explicit", self.scope("--exact-base", ok=False))

    def test_rename_lists_both_paths_and_digest_ignores_user_diff_config(self):
        self.git("mv", "base.txt", "renamed.txt")
        self.git("commit", "-qm", "rename")
        plain = self.scope()
        self.assertEqual(plain["changed_paths"], ["base.txt", "feature.txt", "renamed.txt"])
        self.git("config", "diff.renames", "true")
        self.git("config", "diff.noprefix", "true")
        self.git("config", "diff.algorithm", "patience")
        self.git("config", "diff.context", "9")
        self.git("config", "diff.mnemonicPrefix", "true")
        configured = self.scope()
        self.assertEqual(configured["changed_paths"], plain["changed_paths"])
        self.assertEqual(configured["snapshot_sha256"], plain["snapshot_sha256"])

    def test_conflicted_index_and_in_progress_merge_are_refused(self):
        self.git("switch", "-q", "trunk")
        (self.repo / "base.txt").write_text("trunk side\n")
        self.git("commit", "-qam", "trunk side")
        self.git("switch", "-q", "feature")
        (self.repo / "base.txt").write_text("feature side\n")
        self.git("commit", "-qam", "feature side")
        merge = subprocess.run(["git", "merge", "trunk"], cwd=self.repo, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True)
        self.assertNotEqual(merge.returncode, 0)
        self.assertIn("merge is in progress", self.scope("--base", "trunk", ok=False))
        self.git("merge", "--abort")
        self.assertEqual(self.scope("--base", "trunk")["changed_paths"], ["base.txt", "feature.txt"])

    def test_stale_local_base_prefers_its_remote_tracking_ref(self):
        self.git("switch", "-q", "trunk")
        (self.repo / "landed.txt").write_text("landed\n")
        self.git("add", "landed.txt")
        self.git("commit", "-qm", "landed upstream")
        landed = self.git("rev-parse", "HEAD").strip()
        self.git("update-ref", "refs/remotes/origin/trunk", landed)
        self.git("reset", "-q", "--hard", self.initial)
        self.git("switch", "-q", "feature")
        result = self.scope("--base", "trunk")
        self.assertEqual(result["base_upstream"], "refs/remotes/origin/trunk")
        self.assertEqual(result["base_local_tip"], self.initial)
        self.assertEqual(result["base_tip"], landed)
        self.assertEqual(result["base_commit"], self.initial)
        self.assertEqual(len(result["warnings"]), 1)
        self.assertIn("behind refs/remotes/origin/trunk by 1", result["warnings"][0])
        exact = self.scope("--base", "trunk", "--exact-base")
        self.assertIsNone(exact["base_upstream"])
        self.assertEqual(exact["base_commit"], self.initial)
        self.assertEqual(exact["warnings"], [])

    def test_head_branch_supplies_its_own_stacked_parent(self):
        self.git("branch", "stack-parent")
        self.git("switch", "-qc", "child")
        (self.repo / "child.txt").write_text("child\n")
        self.git("add", "child.txt")
        self.git("commit", "-qm", "child")
        self.git("config", "branch.child.gh-merge-base", "stack-parent")
        self.git("switch", "-q", "feature")
        self.git("config", "branch.feature.gh-merge-base", "trunk")
        result = self.scope("--head", "child")
        self.assertEqual(result["base_source"], "branch.gh-merge-base")
        self.assertEqual(result["base_ref"], "stack-parent")
        self.assertEqual(result["changed_paths"], ["child.txt"])

    def test_missing_remote_head_error_names_the_repair(self):
        self.git("symbolic-ref", "--delete", "refs/remotes/origin/HEAD")
        self.assertIn("git remote set-head origin -a", self.scope(ok=False))

    def test_installed_symlink_helper_uses_consumer_not_package_checkout(self):
        installed = self.repo.parent / "installed skill"
        installed.symlink_to(SCOPE.parent.parent, target_is_directory=True)
        result = self.scope(script=installed / "scripts/resolve_scope.py", cwd=ROOT)
        self.assertEqual(Path(result["repository_root"]), self.repo)
        self.assertEqual(result["changed_paths"], ["feature.txt"])


class WorkflowPackageTests(unittest.TestCase):
    def test_packaged_markdown_references_resolve_independently_of_cwd(self):
        catalog = json.loads((ROOT / "catalog.json").read_text())
        packages = sorted(path.name for path in (ROOT / "skills").iterdir() if path.is_dir())
        self.assertEqual(packages, sorted(package["name"] for package in catalog["packages"]))
        count = 0
        for name in packages:
            for path in (ROOT / "skills" / name).rglob("*.md"):
                for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", path.read_text()):
                    if "://" in target or target.startswith("#"):
                        continue
                    local = target.split("#", 1)[0]
                    resolved = (path.parent / local).resolve()
                    self.assertTrue(resolved.is_relative_to(ROOT / "skills"), (path, target))
                    self.assertTrue(resolved.is_file(), (path, target))
                    count += 1
        self.assertGreaterEqual(count, 30)

    def test_full_generic_lens_library_has_common_guidance(self):
        references = ROOT / "skills/review-agent/references"
        expected = {
            "review": {"contracts-standards", "correctness-runtime-safety", "design-architecture",
                       "platform-performance", "port-fidelity-followthrough"},
            "linter": {"code-hygiene", "documentation-consistency", "readability", "speculative-complexity-cleanup"},
        }
        for family, names in expected.items():
            actual = {path.stem for path in (references / family).glob("*.md")}
            self.assertEqual(actual, names)
            for name in names:
                doc = (references / family / (name + ".md")).read_text()
                self.assertIn(f"(../{family}-common.md)", doc)
                self.assertIn("Investigation", doc)

    def test_skill_metadata_preserves_explicit_workflow_entrypoints(self):
        catalog = json.loads((ROOT / "catalog.json").read_text())
        codex = {package["name"] for package in catalog["packages"] if "codex" in package["runtimes"]}
        for name in WORKFLOWS:
            text = (ROOT / "skills" / name / "SKILL.md").read_text()
            self.assertTrue(text.startswith("---\n"), name)
            frontmatter = text.split("---", 2)[1]
            self.assertIn("name: " + name + "\n", frontmatter)
            self.assertIn("description:", frontmatter)
            ui_path = ROOT / "skills" / name / "agents/openai.yaml"
            if name in codex:
                self.assertTrue(ui_path.is_file(), name)
            ui = ui_path.read_text() if ui_path.is_file() else ""
            if ui:
                self.assertIn("$" + name, ui)
            if name in ("orchestrate", "orchestrate-linked-sessions", "review-agent"):
                self.assertIn("disable-model-invocation: true", frontmatter)
                if ui:
                    self.assertIn("allow_implicit_invocation: false", ui)

    def test_github_create_pr_skill_is_portable_and_keeps_generic_rules(self):
        text = (ROOT / "skills/github-create-pr/SKILL.md").read_text()
        self.assertNotIn("sentifold/gamejam", text)
        self.assertIsNone(re.search(r"\bdevelop\b", text), "base branch must come from the project")
        self.assertNotIn("verify-local.sh", text)
        self.assertNotIn("Linear", text)
        self.assertIn("PROJECT_ROOT/.agents/project-workflow.md", text)
        self.assertIn("git rev-parse --show-toplevel", text)
        self.assertIn("Without a profile", text)
        self.assertIn("never import another", text)
        self.assertIn("(../review-agent/references/project-contract.md)", text)
        self.assertIn("gh repo view \"$REPO\" --json defaultBranchRef", text)
        self.assertIn("git symbolic-ref --short refs/remotes/<remote>/HEAD", text)
        self.assertIn("--head <fork-owner>:<branch>", text)
        for spelling in ("./scripts/create-pr.sh", "./Scripts/create-pr.sh"):
            self.assertIn(spelling, text)
        self.assertIn("### Oversized diff confirmation", text)
        self.assertIn("more than 10,000 lines", text)
        self.assertIn("larger than\n1 MiB", text)
        self.assertIn("Reverts whose purpose is\nto remove oversized data do not require this confirmation", text)
        self.assertIn("carries a `.stack` object", text)
        self.assertIn("merge-async", text)
        self.assertNotIn("do not assume provider-native stacking", text)
        self.assertIn("`gh api --method PATCH \"repos/$REPO/pulls/$PR_NUMBER\" --input \"$JSON_FILE\"`".strip("`"), text)
        self.assertIn("exits\nwithout editing anything", text)
        self.assertIn("**Narrative shape**", text)
        self.assertIn("**Compact shape**", text)
        self.assertIn("## Change Map / Changes", text)
        self.assertIn("grep -nE '^\\+\\+\\+ |^@@'", text)
        self.assertIn("Use ASCII characters only", text)
        self.assertIn("--pr <number-or-url>", text)

    def test_orchestrate_discovers_the_project_profile_and_defines_its_fallback(self):
        text = (ROOT / "skills/orchestrate/SKILL.md").read_text()
        self.assertIn("`PROJECT_ROOT/.agents/project-workflow.md`", text)
        self.assertIn("`git rev-parse --show-toplevel`", text)
        self.assertIn("per lane worktree", text)
        self.assertIn("per repository", text)
        self.assertIn("Without a profile", text)
        self.assertIn("Never\nimport another repository's commands", text)
        self.assertIn("visible `blocked:` gate, never a pass", text)
        self.assertIn("(../review-agent/references/project-contract.md)", text)
        self.assertIn("(../review-agent/references/lifecycle.md)", text)
        self.assertIn("(../claude-stock-code-review/SKILL.md)", text)

    def test_orchestrate_keeps_its_gate_vocabulary_and_stop_shape(self):
        text = (ROOT / "skills/orchestrate/SKILL.md").read_text()
        for tag in ("`ran:`", "`not-applicable:`", "`blocked:`", "`waived:`", "`degraded:`"):
            self.assertIn(tag, text)
        self.assertIn("`ran: adopted-existing-work`", text)
        self.assertIn("`degraded: no verified report`", text)
        self.assertIn("`REVIEW COMPLETE`", text)
        self.assertIn("`REVIEW INCOMPLETE`", text)
        hard_stop = text.split("```md\nHard Stop\n", 1)[1].split("```", 1)[0]
        for field in ("triggered_gate_or_rule", "current_proof", "smallest_safe_next_step",
                      "other_lanes", "decision_needed"):
            self.assertIn("- " + field + ":", hard_stop)
        self.assertIn("## Stop conditions", text)
        self.assertIn("stops **its lane, not the world**", text)
        self.assertIn("## Parallelization", text)
        self.assertIn("## Gates summary", text)
        self.assertIn("readiness floor is unconditional", text)
        self.assertIn("DO\nNOT commit", text)
        self.assertIn("`@{upstream}...HEAD`", text)
        self.assertIn("`git checkout <base-sha> -- <file>`", text)
        self.assertIn("never through the Skill tool", text)
        self.assertIn("Provider policy", text)

    def test_orchestrate_extra_engines_stay_optional(self):
        text = (ROOT / "skills/orchestrate/SKILL.md").read_text()
        section = text.split("## Extra engines (optional)\n", 1)[1].split("\n## ", 1)[0]
        self.assertIn("When the session has\nneither skill, skip this section and every reference to it", section)
        self.assertIn("`REVIEW INCOMPLETE` still stops and asks", section)
        self.assertIn("`kimi` never reviews its own lane", section)
        self.assertIn("When\n  neither can run, the rule above stands.", section)
        self.assertIn("Record it as\n`blocked: cross-provider unavailable — <reason>`", text)
        self.assertEqual(text.count("(#extra-engines-optional)"), 5)
        for name in ("## Runtime mapping\n", "## Gates summary\n", "## Stop conditions\n"):
            body = text.split(name, 1)[1].split("\n## ", 1)[0]
            if name != "## Stop conditions\n":  # Only the tables must stay as they are.
                body = "\n".join(line for line in body.splitlines() if line.startswith("|"))
            for engine in ("`cursor`", "`kimi`", "extra engine"):
                self.assertNotIn(engine, body, (name, engine))
        catalog = json.loads((ROOT / "catalog.json").read_text())
        names = {package["name"] for package in catalog["packages"]}
        self.assertFalse({"cursor", "kimi"} & names, "extra engines are never a catalog requirement")

    def test_orchestrate_metadata_is_explicit_only_and_portable(self):
        text = (ROOT / "skills/orchestrate/SKILL.md").read_text()
        frontmatter = text.split("---", 2)[1]
        self.assertIn("disable-model-invocation: true", frontmatter)
        self.assertIn("Explicit invocation in any language counts", frontmatter)
        self.assertIn("a generic 'implement this' does not", frontmatter)
        self.assertIn("Do NOT auto-trigger", frontmatter)
        self.assertNotIn("/Users/", text)
        self.assertNotIn("/home/", text)
        self.assertNotIn("$HOME/", text)
        for project_only in ("game_build", "develop`", "sentifold/cloud", "THGAMES_", "games-ts/"):
            self.assertNotIn(project_only, text)
        ui = (ROOT / "skills/orchestrate/agents/openai.yaml").read_text()
        self.assertIn("allow_implicit_invocation: false", ui)
        self.assertIn("$orchestrate", ui)

    def test_profile_template_and_examples_carry_every_contract_section(self):
        profiles = [PROFILE_TEMPLATE, *sorted((ROOT / "examples").glob("*.md"))]
        self.assertGreaterEqual(len(profiles), 2)
        contract = (ROOT / "skills/review-agent/references/project-contract.md").read_text()
        orchestrate = (ROOT / "skills/orchestrate/SKILL.md").read_text()
        self.assertIn("## Provider policy", contract)
        for named in ("Verification by changed surface", "Lanes and resources", "Provider policy"):
            self.assertIn(named, orchestrate)
        for path in profiles:
            text = path.read_text()
            headings = re.findall(r"^## (.+)$", text, re.MULTILINE)
            for section in PROFILE_SECTIONS:
                self.assertIn(section, headings, (path.name, section))
            self.assertIn("relative to", text, path.name)
            self.assertIn("`references/project-contract.md`", text, path.name)
            self.assertNotIn("](../", text, path.name)
            for home in ("/Users/", "/home/", "$HOME/"):
                self.assertNotIn(home, text, path.name)
        template = PROFILE_TEMPLATE.read_text()
        self.assertIn("never\nimport another project's commands", template)
        for project_only in ("game_build", "make check", "sentifold/gamejam", "THGAMES_", "develop`", "main`"):
            self.assertNotIn(project_only, template)
        self.assertIn("<exact model id>", template)
        sleash = (ROOT / "examples/sleash.project-workflow.md").read_text()
        self.assertIn("default base: `main`", sleash)
        self.assertIn("`make check`", sleash)
        self.assertIn("Runtime smoke not applicable", sleash)
        self.assertIn("- Codex leg: ask.", sleash)
        self.assertIn("- Claude leg: ask.", sleash)
        placeholders = set(re.findall(r"`<[^`>]+>`", template))
        self.assertGreaterEqual(len(placeholders), 20)
        self.assertEqual(sorted(placeholder for placeholder in placeholders if placeholder in sleash), [])

    def test_real_agent_templates_install_with_absolute_package_links(self):
        with tempfile.TemporaryDirectory(prefix="workflow install ") as directory:
            fixture = Path(directory).resolve()
            package = fixture / "package with spaces"
            package.mkdir()
            shutil.copyfile(ROOT / "catalog.json", package / "catalog.json")
            shutil.copytree(ROOT / "skills", package / "skills")
            shutil.copytree(ROOT / "agents", package / "agents")
            shutil.copytree(ROOT / "lib", package / "lib")
            home = fixture / "consumer home"
            locations = install.Locations(home, home / ".codex", home / ".claude")
            install.apply(install.prepare(package, locations, {"codex", "claude"}))
            for name in ("review-orchestrator", "review-lens"):
                path = locations.codex / "agents" / (name + ".toml")
                agent = tomllib.loads(path.read_text())
                self.assertEqual(agent["name"], name)
                self.assertNotIn("model", agent)
                self.assertIn(str(package / "skills/review-agent/SKILL.md"), agent["developer_instructions"])
                self.assertNotIn("{{", path.read_text())
            for source in (package / "agents/claude").glob("*.md"):
                # Render each real template even if a runtime's catalog selects only one.
                rendered = install.rendered_agent(package, {"source": str(source.relative_to(package)), "runtime": "claude", "name": source.stem})
                text = rendered.decode()
                self.assertNotIn("{{", text)
                self.assertIn(str(package / "skills/review-agent/SKILL.md"), text)
                self.assertTrue((home / ".claude/skills/review-agent/SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
