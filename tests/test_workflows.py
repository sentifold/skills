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
WORKFLOWS = ("orchestrate", "review-agent", "github-create-pr", "claude-stock-code-review")


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

    def test_installed_symlink_helper_uses_consumer_not_package_checkout(self):
        installed = self.repo.parent / "installed skill"
        installed.symlink_to(SCOPE.parent.parent, target_is_directory=True)
        result = self.scope(script=installed / "scripts/resolve_scope.py", cwd=ROOT)
        self.assertEqual(Path(result["repository_root"]), self.repo)
        self.assertEqual(result["changed_paths"], ["feature.txt"])


class WorkflowPackageTests(unittest.TestCase):
    def test_packaged_markdown_references_resolve_independently_of_cwd(self):
        count = 0
        for name in WORKFLOWS:
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
        for name in WORKFLOWS:
            text = (ROOT / "skills" / name / "SKILL.md").read_text()
            self.assertTrue(text.startswith("---\n"), name)
            frontmatter = text.split("---", 2)[1]
            self.assertIn("name: " + name + "\n", frontmatter)
            self.assertIn("description:", frontmatter)
            ui = (ROOT / "skills" / name / "agents/openai.yaml").read_text()
            self.assertIn("$" + name, ui)
            if name in ("orchestrate", "review-agent"):
                self.assertIn("disable-model-invocation: true", frontmatter)
                self.assertIn("allow_implicit_invocation: false", ui)

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
