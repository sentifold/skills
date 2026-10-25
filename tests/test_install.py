from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import install


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sentifold installer ")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / "source with spaces"
        self.root.mkdir()
        shutil.copyfile(install.ROOT / "catalog.json", self.root / "catalog.json")
        self.catalog = json.loads((self.root / "catalog.json").read_text())
        for package in self.catalog["packages"]:
            directory = self.root / "skills" / package["name"]
            directory.mkdir(parents=True)
            (directory / "SKILL.md").write_text(f"---\nname: {package['name']}\ndescription: fixture\n---\n")
            for resource in package.get("required_files", []):
                path = self.root / resource
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture required resource\n")
        for agent in self.catalog["agents"]:
            path = self.root / agent["source"]
            path.parent.mkdir(parents=True, exist_ok=True)
            if agent["runtime"] == "codex":
                path.write_text(f"name = \"{agent['name']}\"\ndeveloper_instructions = '''Read {{{{SKILLS_ROOT}}}}/review-agent/SKILL.md.'''\n")
            else:
                path.write_text(f"---\nname: {agent['name']}\n---\nRead {{{{SKILLS_ROOT}}}}/review-agent/SKILL.md.\n")
        self.home = self.base / "test home"
        self.locations = install.Locations(self.home, self.home / ".codex", self.home / ".claude")

    def plan(self, **kwargs):
        return install.prepare(kwargs.pop("root", self.root), kwargs.pop("locations", self.locations),
                               kwargs.pop("selected", {"codex", "claude"}), **kwargs)

    def perform(self, **kwargs):
        plan = self.plan(**kwargs)
        install.apply(plan)
        return plan

    def fixture_link(self, relative, target="old relative target"):
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(target)
        return path

    def assert_no_install(self):
        self.assertFalse(self.locations.receipt.exists())
        self.assertFalse((self.home / ".agents/skills/orchestrate").exists())
        self.assertFalse((self.home / ".claude/agents/review-orchestrator.md").exists())

    def test_plan_is_read_only_then_clean_apply_is_complete_and_idempotent(self):
        plan = self.plan()
        self.assertFalse(self.home.exists())
        install.apply(plan)
        for package in self.catalog["packages"]:
            for runtime in package["runtimes"]:
                link = self.locations.skills(runtime) / package["name"]
                self.assertTrue(link.is_symlink())
                self.assertEqual(link.resolve(), self.root / "skills" / package["name"])
        for agent in self.catalog["agents"]:
            path = self.locations.agents(agent["runtime"]) / Path(agent["source"]).name
            self.assertTrue(path.is_file())
            self.assertFalse(path.is_symlink())
            self.assertIn((self.root / "skills").as_posix(), path.read_text())
            self.assertNotIn("{{SKILLS_ROOT}}", path.read_text())
        self.assertEqual(self.plan().changes, [])
        self.assertFalse((self.home / ".codex/skills").exists())

    def test_runtime_filtering_and_later_expansion(self):
        self.perform(selected={"codex"})
        self.assertTrue((self.home / ".agents/skills/claude").is_symlink())
        self.assertFalse((self.home / ".agents/skills/codex").exists())
        self.assertFalse((self.home / ".claude").exists())
        self.perform(selected={"claude"})
        self.assertTrue((self.home / ".claude/skills/codex").is_symlink())
        self.assertTrue((self.home / ".claude/skills/claude-stock-code-review").is_symlink())
        self.assertFalse((self.home / ".claude/skills/claude").exists())
        self.assertEqual(self.plan().changes, [])

    def test_custom_roots_and_configuration_are_preserved(self):
        locations = install.Locations(self.home, self.base / "custom codex", self.base / "custom claude")
        for path, text in [(locations.codex / "config.toml", 'model = "my-model"\n[agents]\nmax_depth = 1\n'),
                           (locations.claude / "settings.json", '{"model":"my-model"}\n')]:
            path.parent.mkdir(parents=True)
            path.write_text(text)
        before = {path: path.read_bytes() for path in (locations.codex / "config.toml", locations.claude / "settings.json")}
        self.perform(locations=locations)
        self.assertTrue((locations.codex / "agents/review-lens.toml").is_file())
        self.assertTrue((locations.claude / "skills/orchestrate").is_symlink())
        self.assertFalse((self.home / ".codex").exists())
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content)

    def test_environment_roots_and_explicit_flags(self):
        environment = {"CODEX_HOME": str(self.base / "environment codex"),
                       "CLAUDE_CONFIG_DIR": str(self.base / "environment claude")}
        with patch.object(install, "ROOT", self.root), patch.dict(os.environ, environment), redirect_stdout(io.StringIO()):
            self.assertEqual(install.main(["apply", "--home", str(self.home)]), 0)
            self.assertTrue((Path(environment["CODEX_HOME"]) / "agents/review-lens.toml").is_file())
            self.assertTrue((Path(environment["CLAUDE_CONFIG_DIR"]) / "skills/orchestrate").is_symlink())
            override = self.base / "explicit codex"
            self.assertEqual(install.main(["apply", "--home", str(self.home), "--codex-home", str(override)]), 0)
            self.assertTrue((override / "agents/review-lens.toml").is_file())
            self.assertFalse((Path(environment["CODEX_HOME"]) / "agents/review-lens.toml").exists())

    def test_unowned_directory_is_never_adopted(self):
        directory = self.home / ".agents/skills/orchestrate"
        directory.mkdir(parents=True)
        file = directory / "personal.txt"
        file.write_text("keep me")
        with self.assertRaisesRegex(install.InstallError, "ordinary files/directories cannot be adopted"):
            self.plan(adopt={"orchestrate"})
        self.assertEqual(file.read_text(), "keep me")
        self.assertFalse(self.locations.receipt.exists())

    def test_unowned_agent_file_is_never_adopted(self):
        path = self.locations.codex / "agents/review-lens.toml"
        path.parent.mkdir(parents=True)
        path.write_text("personal agent")
        with self.assertRaisesRegex(install.InstallError, "Unowned destination conflict"):
            self.plan(adopt={"review-lens"})
        self.assertEqual(path.read_text(), "personal agent")
        self.assert_no_install()

    def test_symlink_requires_named_adoption_and_uninstall_restores_it(self):
        link = self.fixture_link(".agents/skills/orchestrate")
        with self.assertRaisesRegex(install.InstallError, "--adopt orchestrate"):
            self.plan()
        self.perform(adopt={"orchestrate"})
        self.assertEqual(link.resolve(), self.root / "skills/orchestrate")
        self.perform(uninstall=True)
        self.assertTrue(link.is_symlink())
        self.assertEqual(os.readlink(link), "old relative target")
        self.assertFalse(self.locations.receipt.exists())
        self.assertFalse((self.home / ".claude/skills/orchestrate").exists())

    def test_unknown_adoption_name_fails_before_changes(self):
        with self.assertRaisesRegex(install.InstallError, "Unknown --adopt"):
            self.plan(adopt={"typo"})
        self.assertFalse(self.home.exists())

    def test_legacy_duplicate_is_reported_and_named_adoption_restores_on_uninstall(self):
        legacy = self.fixture_link(".codex/skills/orchestrate", "/old/shared/orchestrate")
        with self.assertRaisesRegex(install.InstallError, "Unowned destination conflict"):
            self.plan()
        self.perform(adopt={"orchestrate"})
        self.assertFalse(legacy.is_symlink())
        self.assertEqual(self.plan().changes, [])
        self.perform(uninstall=True)
        self.assertEqual(os.readlink(legacy), "/old/shared/orchestrate")

    def test_custom_codex_root_checks_both_legacy_locations(self):
        locations = install.Locations(self.home, self.base / "custom codex", self.locations.claude)
        conventional = self.fixture_link(".codex/skills/orchestrate")
        custom = locations.codex / "skills/review-agent"
        custom.parent.mkdir(parents=True)
        custom.symlink_to("old review")
        with self.assertRaises(install.InstallError) as error:
            self.plan(locations=locations)
        self.assertIn(str(conventional), str(error.exception))
        self.assertIn(str(custom), str(error.exception))
        self.perform(locations=locations, adopt={"orchestrate", "review-agent"})
        self.assertFalse(conventional.is_symlink())
        self.assertFalse(custom.is_symlink())

    def test_other_runtime_legacy_directory_does_not_block_claude_only(self):
        legacy = self.fixture_link(".codex/skills/orchestrate")
        self.perform(selected={"claude"})
        self.assertTrue(legacy.is_symlink())

    def test_owned_agent_edit_blocks_entire_update_and_uninstall(self):
        self.perform()
        edited = self.locations.codex / "agents/review-lens.toml"
        edited.write_text(edited.read_text() + "# personal change\n")
        before_receipt = self.locations.receipt.read_bytes()
        for uninstall in (False, True):
            with self.assertRaisesRegex(install.InstallError, "Owned file was changed; preserve or restore it before proceeding"):
                self.plan(uninstall=uninstall)
        self.assertIn("personal change", edited.read_text())
        self.assertEqual(self.locations.receipt.read_bytes(), before_receipt)

    def test_retargeted_owned_symlink_needs_adoption_again(self):
        self.perform()
        link = self.home / ".agents/skills/orchestrate"
        link.unlink()
        link.symlink_to("personal replacement")
        with self.assertRaisesRegex(install.InstallError, "Owned symlink was retargeted; restore it or pass --adopt orchestrate to take it over again"):
            self.plan()
        with self.assertRaisesRegex(install.InstallError, "Owned symlink was retargeted; restore it before proceeding"):
            self.plan(uninstall=True)
        self.assertEqual(os.readlink(link), "personal replacement")
        plan = self.perform(adopt={"orchestrate"})
        self.assertEqual([change.label for change in plan.changes], ["adopt symlink", "write ownership receipt"])
        self.assertEqual(link.resolve(), self.root / "skills/orchestrate")
        self.perform(uninstall=True)
        self.assertEqual(os.readlink(link), "personal replacement")

    def test_dotfiles_recreated_links_block_apply_until_adopted_and_never_block_uninstall(self):
        adopted = self.fixture_link(".agents/skills/orchestrate", "dotfiles/orchestrate")
        legacy = self.fixture_link(".codex/skills/orchestrate", "dotfiles/legacy orchestrate")
        self.perform(adopt={"orchestrate"})
        for round in range(2):
            adopted.unlink()
            adopted.symlink_to("dotfiles/orchestrate")
            legacy.symlink_to("dotfiles/legacy orchestrate")
            with self.assertRaises(install.InstallError) as error:
                self.plan()
            self.assertIn(f"Owned symlink was retargeted; restore it or pass --adopt orchestrate to take it over again before proceeding: {adopted}", str(error.exception))
            self.assertIn(f"Owned legacy duplicate was recreated; delete it or restore its recorded target or pass --adopt orchestrate to remove it again before proceeding: {legacy}", str(error.exception))
            if round == 0:
                plan = self.perform(adopt={"orchestrate"})
                self.assertEqual({change.label for change in plan.changes}, {"adopt symlink", "remove legacy duplicate"})
                self.assertEqual(adopted.resolve(), self.root / "skills/orchestrate")
                self.assertFalse(legacy.is_symlink())
        plan = self.perform(uninstall=True)
        self.assertNotIn(adopted, {change.path for change in plan.changes})
        self.assertEqual(os.readlink(adopted), "dotfiles/orchestrate")
        self.assertEqual(os.readlink(legacy), "dotfiles/legacy orchestrate")
        self.assertFalse(self.locations.receipt.exists())

    def test_deleted_owned_link_does_not_block_uninstall(self):
        self.perform()
        (self.home / ".agents/skills/orchestrate").unlink()
        self.perform(uninstall=True)
        self.assertFalse(self.locations.receipt.exists())

    def test_legacy_directory_is_named_as_duplicate_to_move_aside(self):
        directory = self.home / ".codex/skills/orchestrate"
        directory.mkdir(parents=True)
        (directory / "SKILL.md").write_text("old copy")
        with self.assertRaisesRegex(install.InstallError, f"Legacy Codex skill duplicates the shared package; move it aside, ordinary files/directories are never removed: {re.escape(str(directory))}"):
            self.plan()
        self.assertEqual((directory / "SKILL.md").read_text(), "old copy")
        self.assert_no_install()

    def test_update_then_apply_old_checkout_rolls_back_and_keeps_adoption(self):
        adopted = self.fixture_link(".agents/skills/orchestrate", "before installation")
        self.perform(adopt={"orchestrate"})
        original = self.locations.receipt.read_bytes()
        next_root = self.base / "second checkout"
        shutil.copytree(self.root, next_root)
        self.perform(root=next_root)
        self.assertEqual(adopted.resolve(), next_root / "skills/orchestrate")
        self.assertIn(str(next_root / "skills"), (self.locations.codex / "agents/review-lens.toml").read_text())
        self.perform(root=self.root)
        self.assertEqual(self.locations.receipt.read_bytes(), original)
        self.perform(uninstall=True)
        self.assertEqual(os.readlink(adopted), "before installation")

    def test_partial_failure_restores_adopted_links_and_new_files(self):
        adopted = self.fixture_link(".agents/skills/orchestrate", "before installation")
        plan = self.plan(adopt={"orchestrate"})
        real_write = install.write_state
        calls = 0

        def fail_once(path, state):
            nonlocal calls
            calls += 1
            if calls == 6:
                raise OSError("simulated full disk")
            real_write(path, state)

        with patch.object(install, "write_state", fail_once):
            with self.assertRaisesRegex(install.InstallError, "changes rolled back"):
                install.apply(plan)
        self.assertEqual(os.readlink(adopted), "before installation")
        self.assertFalse(self.locations.receipt.exists())
        self.assertFalse((self.home / ".claude/skills/orchestrate").is_symlink())
        self.assertFalse((self.home / ".agents/skills/review-agent").is_symlink())
        self.assertFalse((self.locations.state_dir / "install.lock").exists())

    def test_failed_update_preserves_previous_receipt_and_rendered_files(self):
        self.perform()
        receipt = self.locations.receipt.read_bytes()
        original_agent = (self.locations.codex / "agents/review-lens.toml").read_bytes()
        next_root = self.base / "new checkout"
        shutil.copytree(self.root, next_root)
        real_write = install.write_state

        def fail_receipt_once(path, state):
            if path == self.locations.receipt:
                raise OSError("cannot publish receipt")
            real_write(path, state)

        with patch.object(install, "write_state", fail_receipt_once):
            with self.assertRaises(install.InstallError):
                install.apply(self.plan(root=next_root))
        self.assertEqual(self.locations.receipt.read_bytes(), receipt)
        self.assertEqual((self.locations.codex / "agents/review-lens.toml").read_bytes(), original_agent)
        self.assertEqual((self.home / ".agents/skills/orchestrate").resolve(), self.root / "skills/orchestrate")

    def test_interruption_after_a_write_rolls_back_and_restores_signal_handler(self):
        for error in (KeyboardInterrupt(), SystemExit(2)):
            with self.subTest(error=type(error).__name__):
                adopted = self.fixture_link(".agents/skills/orchestrate", "before installation")
                plan = self.plan(adopt={"orchestrate"})
                real_write = install.write_state
                handler = install.signal.getsignal(install.signal.SIGINT)
                calls = 0

                def interrupt_after_write(path, state):
                    nonlocal calls
                    calls += 1
                    real_write(path, state)
                    if calls == 6:
                        raise error

                with patch.object(install, "write_state", interrupt_after_write):
                    with self.assertRaisesRegex(install.InstallError, "changes rolled back"):
                        install.apply(plan)
                self.assertEqual(os.readlink(adopted), "before installation")
                self.assertFalse(self.locations.receipt.exists())
                self.assertFalse((self.home / ".claude/skills/orchestrate").is_symlink())
                self.assertFalse((self.home / ".agents/skills/review-agent").is_symlink())
                self.assertFalse((self.locations.state_dir / "install.lock").exists())
                self.assertEqual(install.signal.getsignal(install.signal.SIGINT), handler)
                adopted.unlink()

    def test_change_between_plan_and_apply_is_detected_before_writes(self):
        plan = self.plan()
        conflict = self.home / ".claude/skills/orchestrate"
        conflict.parent.mkdir(parents=True)
        conflict.write_text("arrived after plan")
        with self.assertRaisesRegex(install.InstallError, "changed after preflight"):
            install.apply(plan)
        self.assertEqual(conflict.read_text(), "arrived after plan")
        self.assert_no_install()

    def test_missing_package_or_invalid_agent_stops_before_mutation(self):
        package = self.root / "skills/claude/SKILL.md"
        package.unlink()
        with self.assertRaisesRegex(install.InstallError, "Missing required package"):
            self.plan()
        self.assertFalse(self.home.exists())
        package.write_text("restored")
        (self.root / "agents/codex/review-lens.toml").write_text("not an agent")
        with self.assertRaisesRegex(install.InstallError, "Invalid agent template"):
            self.plan()
        self.assertFalse(self.home.exists())

    def test_invalid_dependency_is_rejected(self):
        self.catalog["packages"][0]["requires"]["codex"].append("missing")
        (self.root / "catalog.json").write_text(json.dumps(self.catalog))
        with self.assertRaisesRegex(install.InstallError, "unavailable dependency"):
            self.plan()

    def test_required_provider_library_and_review_resources_are_checked_before_changes(self):
        for resource in ("lib/provider_runtime.py", "skills/review-agent/scripts/resolve_scope.py",
                         "skills/claude/scripts/claude-ephemeral.sh"):
            with self.subTest(resource=resource):
                path = self.root / resource
                contents = path.read_bytes()
                path.unlink()
                with self.assertRaisesRegex(install.InstallError, "Missing or unconfined required file"):
                    self.plan()
                self.assertFalse(self.home.exists())
                path.write_bytes(contents)

    def test_required_resources_cannot_escape_source_checkout(self):
        path = self.root / "lib/provider_runtime.py"
        path.unlink()
        external = self.base / "external provider"
        external.write_text("untrusted external resource")
        path.symlink_to(external)
        with self.assertRaisesRegex(install.InstallError, "unconfined required file"):
            self.plan()
        self.assertFalse(self.home.exists())

    def test_policy_metadata_and_license_are_required_resources(self):
        for resource in ("skills/orchestrate/agents/openai.yaml", "skills/review-agent/agents/openai.yaml",
                         "skills/github-create-pr/agents/openai.yaml", "skills/claude/agents/openai.yaml",
                         "skills/claude-stock-code-review/agents/openai.yaml", "skills/codex/LICENSE.txt"):
            with self.subTest(resource=resource):
                path = self.root / resource
                contents = path.read_bytes()
                path.unlink()
                with self.assertRaisesRegex(install.InstallError, "Missing or unconfined required file"):
                    self.plan()
                self.assertFalse(self.home.exists())
                path.write_bytes(contents)

    def test_invalid_resource_path_is_rejected(self):
        self.catalog["packages"][0]["required_files"] = ["../outside"]
        (self.root / "catalog.json").write_text(json.dumps(self.catalog))
        with self.assertRaisesRegex(install.InstallError, "invalid required_files"):
            self.plan()

    def test_plan_prints_link_then_target_previous_targets_and_source_revision(self):
        self.fixture_link(".agents/skills/orchestrate", "old orchestrate")
        self.fixture_link(".codex/skills/review-agent", "old legacy review")
        environment = {"CODEX_HOME": str(self.locations.codex), "CLAUDE_CONFIG_DIR": str(self.locations.claude)}
        revision = "a" * 40
        with patch.object(install, "ROOT", self.root), patch.dict(os.environ, environment), \
                patch.object(install, "source_revision", return_value=revision), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(install.main(["plan", "--home", str(self.home), "--adopt", "orchestrate", "--adopt", "review-agent"]), 0)
        text = output.getvalue()
        self.assertIn(f"Source: {self.root} (Git {revision})", text)
        self.assertIn("Packages: claude: claude-stock-code-review, codex, github-create-pr, orchestrate, "
                      "orchestrate-linked-sessions, review-agent; "
                      "codex: claude, github-create-pr, orchestrate, review-agent", text)
        self.assertIn(f"install/update: {self.home / '.claude/skills/orchestrate'} -> {self.root / 'skills/orchestrate'}\n", text)
        self.assertIn(f"adopt symlink: {self.home / '.agents/skills/orchestrate'} -> {self.root / 'skills/orchestrate'} (was -> old orchestrate)\n", text)
        self.assertIn(f"remove legacy duplicate: {self.home / '.codex/skills/review-agent'} (was -> old legacy review)\n", text)
        self.assertFalse(self.locations.receipt.exists())

    def test_package_selection_installs_the_dependency_closure_only(self):
        with patch.object(install, "ROOT", self.root), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(install.main(["apply", "--home", str(self.home), "--package", "github-create-pr"]), 0)
        self.assertIn("Packages: claude: github-create-pr; codex: github-create-pr", output.getvalue())
        self.assertTrue((self.home / ".agents/skills/github-create-pr").is_symlink())
        self.assertFalse((self.home / ".agents/skills/orchestrate").exists())
        self.assertFalse((self.home / ".codex/agents").exists())
        self.assertFalse((self.home / ".claude/agents").exists())
        plan = self.perform(packages={"review-agent"})
        self.assertEqual(plan.packages, {"codex": ["claude", "review-agent"], "claude": ["codex", "review-agent"]})
        self.assertEqual(plan.agents, {"codex": ["review-lens", "review-orchestrator"], "claude": ["review-lens", "review-orchestrator"]})
        self.assertFalse((self.home / ".agents/skills/github-create-pr").exists())
        self.assertTrue((self.home / ".agents/skills/claude").is_symlink())
        self.assertTrue((self.home / ".codex/agents/review-orchestrator.toml").is_file())
        plan = self.perform(packages={"claude-stock-code-review"}, selected={"claude"})
        self.assertEqual(plan.packages, {"claude": ["claude-stock-code-review", "codex", "review-agent"]})
        self.assertTrue((self.home / ".agents/skills/review-agent").is_symlink())
        self.assertEqual(self.plan(packages={"review-agent"}, selected={"codex"}).changes, [])
        with self.assertRaisesRegex(install.InstallError, "Unknown --package names: typo"):
            self.plan(packages={"typo"})
        with self.assertRaisesRegex(install.InstallError, "Packages not available for the selected runtimes: claude"):
            self.plan(packages={"claude"}, selected={"claude"})

    def test_symlinked_home_spelling_is_one_installation(self):
        real = self.base / "real home"
        real.mkdir()
        alias = self.base / "home alias"
        alias.symlink_to(real, target_is_directory=True)
        via_alias = install.Locations(alias, alias / ".codex", alias / ".claude")
        via_real = install.Locations(real, real / ".codex", real / ".claude")
        self.perform(locations=via_alias)
        self.assertEqual(self.plan(locations=via_real).changes, [])
        self.assertEqual(self.plan(locations=via_alias).changes, [])
        receipt = json.loads(via_real.receipt.read_text())
        self.assertTrue(all(key.startswith(f"{real}/") for key in receipt["entries"]), list(receipt["entries"]))
        self.perform(locations=via_real, uninstall=True)
        self.assertFalse((real / ".agents/skills/orchestrate").is_symlink())
        self.assertFalse(via_alias.receipt.exists())

    def test_missing_agent_reference_is_rejected(self):
        agent = self.root / "agents/codex/review-lens.toml"
        agent.write_text(agent.read_text().replace("review-agent/SKILL.md", "review-agent/missing.md"))
        with self.assertRaisesRegex(install.InstallError, "missing or invalid package reference"):
            self.plan()
        self.assertFalse(self.home.exists())

    def test_overlapping_runtime_skill_roots_are_rejected(self):
        locations = install.Locations(self.home, self.locations.codex, self.home / ".agents")
        with self.assertRaisesRegex(install.InstallError, "Runtime destinations overlap"):
            self.plan(locations=locations)
        self.assertFalse(self.home.exists())

    def test_symlink_aliased_runtime_roots_are_rejected_before_writes(self):
        shared = self.home / ".agents"
        shared.mkdir(parents=True)
        self.locations.claude.symlink_to(shared, target_is_directory=True)
        with self.assertRaisesRegex(install.InstallError, "Runtime destinations overlap"):
            self.plan()
        self.assert_no_install()
        self.assertTrue(self.locations.claude.is_symlink())

    def test_selected_runtime_cannot_alias_retained_runtime(self):
        self.perform(selected={"codex"})
        before = self.locations.receipt.read_bytes()
        self.locations.claude.symlink_to(self.home / ".agents", target_is_directory=True)
        with self.assertRaisesRegex(install.InstallError, "Runtime destinations overlap"):
            self.plan(selected={"claude"}, adopt={"orchestrate", "review-agent", "github-create-pr"})
        self.assertEqual(self.locations.receipt.read_bytes(), before)
        self.assertEqual(self.plan(selected={"codex"}).changes, [])

    def test_aliased_spelling_of_an_owned_root_is_the_same_installation(self):
        self.perform(selected={"claude"})
        before = self.locations.receipt.read_bytes()
        alias = self.base / "moved claude root"
        alias.symlink_to(self.locations.claude, target_is_directory=True)
        locations = install.Locations(self.home, self.locations.codex, alias)
        self.assertEqual(self.plan(selected={"claude"}, locations=locations).changes, [])
        self.assertEqual(self.locations.receipt.read_bytes(), before)
        self.perform(selected={"claude"}, locations=locations, uninstall=True)
        self.assertFalse((self.locations.claude / "skills/orchestrate").is_symlink())
        self.assertFalse(self.locations.receipt.exists())

    def test_uninstall_detects_aliased_retained_runtime_receipt_entries(self):
        self.perform()
        before = self.locations.receipt.read_bytes()
        shutil.rmtree(self.locations.claude / "skills")
        (self.locations.claude / "skills").symlink_to(self.home / ".agents/skills", target_is_directory=True)
        with self.assertRaisesRegex(install.InstallError, "Runtime destinations overlap"):
            self.plan(selected={"codex"}, uninstall=True)
        self.assertEqual(self.locations.receipt.read_bytes(), before)
        self.assertTrue((self.home / ".agents/skills/orchestrate").is_symlink())

    def test_legacy_directory_alias_is_not_removed_as_duplicate(self):
        for directory in (self.home / ".agents/skills", self.locations.codex):
            directory.mkdir(parents=True)
        (self.locations.codex / "skills").symlink_to(self.home / ".agents/skills", target_is_directory=True)
        self.perform(selected={"codex"})
        self.assertEqual(self.plan(selected={"codex"}).changes, [])
        link = self.home / ".agents/skills/orchestrate"
        self.assertEqual(link.resolve(), self.root / "skills/orchestrate")
        receipt = json.loads(self.locations.receipt.read_text())
        self.assertNotIn(str(self.locations.codex / "skills/orchestrate"), receipt["entries"])
        self.perform(selected={"codex"}, uninstall=True)
        self.assertFalse(link.is_symlink())
        self.assertTrue((self.locations.codex / "skills").is_symlink())

    def test_legacy_alias_to_other_runtime_is_rejected(self):
        self.perform(selected={"claude"})
        self.locations.codex.mkdir()
        (self.locations.codex / "skills").symlink_to(self.locations.claude / "skills", target_is_directory=True)
        before = self.locations.receipt.read_bytes()
        with self.assertRaisesRegex(install.InstallError, "Runtime destinations overlap"):
            self.plan(selected={"codex"}, adopt={"orchestrate", "review-agent", "github-create-pr"})
        self.assertEqual(self.locations.receipt.read_bytes(), before)

    def test_parent_alias_retargeting_after_preflight_is_rejected(self):
        original = self.base / "original agent directory"
        replacement = self.base / "replacement agent directory"
        original.mkdir()
        replacement.mkdir()
        self.home.mkdir()
        alias = self.home / ".agents"
        alias.symlink_to(original, target_is_directory=True)
        plan = self.plan(selected={"codex"})
        alias.unlink()
        alias.symlink_to(replacement, target_is_directory=True)
        with self.assertRaisesRegex(install.InstallError, "Destination parent changed after preflight"):
            install.apply(plan)
        self.assertFalse(self.locations.receipt.exists())
        self.assertEqual(list(original.iterdir()), [])
        self.assertEqual(list(replacement.iterdir()), [])

    def test_receipt_symlink_or_corruption_is_not_overwritten(self):
        receipt = self.locations.receipt
        receipt.parent.mkdir(parents=True)
        receipt.symlink_to(self.base / "personal file")
        with self.assertRaisesRegex(install.InstallError, "Receipt must be an ordinary file"):
            self.plan()
        self.assertTrue(receipt.is_symlink())
        receipt.unlink()
        receipt.write_text("broken JSON")
        with self.assertRaisesRegex(install.InstallError, "Invalid receipt"):
            self.plan()
        self.assertEqual(receipt.read_text(), "broken JSON")

    def test_uninstall_selected_runtime_preserves_other_runtime_and_user_config(self):
        self.perform()
        config = self.locations.codex / "config.toml"
        config.write_text('model = "personal"\n')
        self.perform(selected={"codex"}, uninstall=True)
        self.assertFalse((self.home / ".agents/skills/orchestrate").is_symlink())
        self.assertTrue((self.home / ".claude/skills/orchestrate").is_symlink())
        self.assertEqual(config.read_text(), 'model = "personal"\n')
        self.assertEqual(self.plan(selected={"claude"}).changes, [])
        self.perform(selected={"claude"}, uninstall=True)
        self.assertFalse(self.locations.receipt.exists())
        self.assertEqual(self.plan(uninstall=True).changes, [])

    def test_uninstall_does_not_require_source_packages(self):
        self.perform()
        shutil.rmtree(self.root / "skills")
        (self.root / "catalog.json").unlink()
        self.perform(uninstall=True)
        self.assertFalse(self.locations.receipt.exists())

    def test_install_lock_prevents_concurrent_changes(self):
        plan = self.plan()
        lock = self.locations.state_dir / "install.lock"
        lock.mkdir(parents=True)
        with self.assertRaisesRegex(install.InstallError, "Another install may be running"):
            install.apply(plan)
        self.assertTrue(lock.is_dir())
        self.assert_no_install()

    def test_doctor_reports_missing_cli_without_models_and_checks_install(self):
        environment = {"CODEX_HOME": str(self.locations.codex), "CLAUDE_CONFIG_DIR": str(self.locations.claude)}
        with patch.object(install, "ROOT", self.root), patch.dict(os.environ, environment), \
                patch.object(install.shutil, "which", return_value=None), \
                patch.object(install.subprocess, "run") as run, redirect_stdout(io.StringIO()) as output:
            self.assertEqual(install.main(["doctor", "--home", str(self.home)]), 1)
            self.assertFalse(self.home.exists())
            self.perform()
            self.assertEqual(install.main(["doctor", "--home", str(self.home)]), 0)
            run.assert_not_called()
            self.assertIn("CLI missing from PATH", output.getvalue())
            self.assertIn("config.toml not found", output.getvalue())
            self.assertIn("Verified: installed links and rendered agents match this checkout.", output.getvalue())
            self.assertIn("codex: packages claude, github-create-pr, orchestrate, review-agent; agents review-lens, review-orchestrator; "
                          "no legacy duplicates in the old Codex skill roots", output.getvalue())

    def test_doctor_reads_codex_nesting_configuration(self):
        self.perform()
        config = self.locations.codex / "config.toml"
        cases = [
            ("[features]\nmulti_agent = true\n[agents]\nmax_depth = 2\n", [], "Codex config: multi_agent enabled, agents.max_depth = 2"),
            ("[features]\nmulti_agent = true\n", ["agents.max_depth is not set"], None),
            ("[agents]\nmax_depth = 1\n", ["multi_agent is not enabled", "agents.max_depth = 1"], None),
            ("multi_agent = [broken", ["cannot read"], None),
        ]
        environment = {"CODEX_HOME": str(self.locations.codex), "CLAUDE_CONFIG_DIR": str(self.locations.claude)}
        for text, expected_warnings, expected_status in cases:
            with self.subTest(config=text):
                config.write_text(text)
                with patch.object(install, "ROOT", self.root), patch.dict(os.environ, environment), \
                        patch.object(install.shutil, "which", return_value=None), redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(install.main(["doctor", "--home", str(self.home)]), 0)
                codex_warnings = [line for line in output.getvalue().splitlines() if line.startswith("WARNING: Codex:")]
                self.assertEqual(len(codex_warnings), len(expected_warnings), codex_warnings)
                for warning, fragment in zip(codex_warnings, expected_warnings):
                    self.assertIn(fragment, warning)
                if expected_status:
                    self.assertIn(expected_status, output.getvalue())
        self.assertEqual(config.read_text(), cases[-1][0])

    def crash_apply(self, writes_before_crash, after_last_write=False, adopt=("orchestrate",)):
        driver = f"""
import os, sys
from pathlib import Path
sys.path.insert(0, {str(Path(install.__file__).parent)!r})
import install
real = install.write_state
calls = 0
def crash(path, state):
    global calls
    if path.name == "journal.json":
        return real(path, state)
    calls += 1
    if calls > {writes_before_crash}:
        os._exit(137)
    real(path, state)
    if {after_last_write!r} and calls == {writes_before_crash}:
        os._exit(137)
install.write_state = crash
locations = install.Locations(Path({str(self.home)!r}), Path({str(self.locations.codex)!r}), Path({str(self.locations.claude)!r}))
install.apply(install.prepare(Path({str(self.root)!r}), locations, {{"codex", "claude"}}, adopt=set({list(adopt)!r})))
"""
        result = subprocess.run([sys.executable, "-c", driver], capture_output=True, text=True)
        self.assertEqual(result.returncode, 137, result.stderr)
        journal = json.loads(self.locations.journal.read_text())
        self.assertEqual(len(journal["changes"]), 14)
        self.assertNotIn(str(self.locations.receipt), {change["path"] for change in journal["changes"]})
        return journal

    def test_hard_crash_leaves_a_journal_and_the_next_plan_recovers_written_changes(self):
        adopted = self.fixture_link(".agents/skills/orchestrate", "before installation")
        journal = self.crash_apply(writes_before_crash=5)
        self.assertEqual(adopted.resolve(), self.root / "skills/orchestrate")
        self.assertTrue((self.locations.claude / "agents/review-lens.md").is_file())
        self.assertFalse((self.locations.claude / "agents/review-orchestrator.md").exists())
        self.assertFalse(self.locations.receipt.exists())
        self.assertTrue(self.locations.lock.is_dir())
        self.assertEqual(journal["entries"][str(adopted)]["restore"], "before installation")
        plan = self.plan()
        self.assertEqual(plan.recovered_pid, journal["pid"])
        self.assertIn("5 of 14 journaled changes had been written and are owned again", plan.notes[0])
        self.assertNotIn(adopted, {change.path for change in plan.changes})
        self.assertNotIn(self.locations.claude / "agents/review-lens.md", {change.path for change in plan.changes})
        self.assertIn(self.locations.claude / "agents/review-orchestrator.md", {change.path for change in plan.changes})
        install.apply(plan)
        self.assertFalse(self.locations.lock.exists())
        self.assertEqual(self.plan().changes, [])
        receipt = json.loads(self.locations.receipt.read_text())
        self.assertEqual(receipt["entries"][str(adopted)]["restore"], "before installation")
        self.assertEqual(len(receipt["entries"]), 14)
        self.perform(uninstall=True)
        self.assertEqual(os.readlink(adopted), "before installation")
        self.assertFalse((self.locations.claude / "agents/review-lens.md").exists())

    def test_uninstall_after_a_hard_crash_restores_the_adopted_link_and_removes_written_files(self):
        adopted = self.fixture_link(".agents/skills/orchestrate", "before installation")
        self.crash_apply(writes_before_crash=5)
        plan = self.plan(uninstall=True)
        self.assertIsNotNone(plan.recovered_pid)
        install.apply(plan)
        self.assertEqual(os.readlink(adopted), "before installation")
        self.assertFalse((self.home / ".agents/skills/claude").exists())
        self.assertFalse((self.locations.claude / "agents/review-lens.md").exists())
        self.assertFalse(self.locations.receipt.exists())
        self.assertFalse(self.locations.lock.exists())

    def test_crash_before_any_write_and_after_the_receipt_both_recover_cleanly(self):
        self.crash_apply(writes_before_crash=0)
        self.assertFalse((self.home / ".agents/skills/orchestrate").exists())
        plan = self.plan()
        self.assertIn("0 of 14 journaled changes", plan.notes[0])
        self.assertEqual(len(plan.changes), 15)
        install.apply(plan)
        self.assertFalse(self.locations.lock.exists())
        self.assertEqual(self.plan().changes, [])
        shutil.rmtree(self.home)
        self.crash_apply(writes_before_crash=15, after_last_write=True)
        self.assertTrue(self.locations.receipt.exists())
        plan = self.plan()
        self.assertEqual(plan.changes, [])
        self.assertIsNotNone(plan.recovered_pid)
        with patch.object(install, "ROOT", self.root), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(install.main(["doctor", "--home", str(self.home)]), 1)
        self.assertIn("run apply to complete its recovery", output.getvalue())
        install.apply(plan)
        self.assertFalse(self.locations.lock.exists())
        self.assertEqual(self.plan().changes, [])

    def test_destination_changed_after_a_crash_is_reported_not_owned(self):
        self.crash_apply(writes_before_crash=5)
        link = self.home / ".agents/skills/review-agent"
        link.unlink()
        link.symlink_to("edited after crash")
        with self.assertRaisesRegex(install.InstallError, f"Destination changed after an interrupted install; restore its journaled state before proceeding: {re.escape(str(link))}"):
            self.plan()
        self.assertEqual(os.readlink(link), "edited after crash")

    def test_journal_of_a_running_install_is_never_taken_over(self):
        self.locations.lock.mkdir(parents=True)
        journal = {"schema_version": 1, "pid": os.getppid(), "entries": {}, "changes": []}
        self.locations.journal.write_text(json.dumps(journal))
        with self.assertRaisesRegex(install.InstallError, f"Another install is running \\(pid {os.getppid()}\\)"):
            self.plan()
        self.assertTrue(self.locations.journal.exists())
        self.assert_no_install()

    def test_journal_appearing_after_the_plan_requires_a_new_plan(self):
        plan = self.plan()
        self.crash_apply(writes_before_crash=0)
        with self.assertRaisesRegex(install.InstallError, "left a journal after this plan was prepared; run plan again"):
            install.apply(plan)
        self.assertTrue(self.locations.journal.exists())
        self.assert_no_install()


if __name__ == "__main__":
    unittest.main()
