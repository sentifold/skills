#!/usr/bin/env python3
"""Install a complete local Sentifold skills checkout without editing user config.

Python 3.11+, standard library only. Run plan before apply. Applying another
checkout updates the owned files and links; applying the previous checkout rolls
back that update. No downloads, authentication or model requests are performed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from threading import current_thread, main_thread


ROOT = Path(__file__).resolve().parent
RUNTIMES = {"codex", "claude"}
NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\Z")


class InstallError(Exception):
    pass


@dataclass(frozen=True)
class State:
    kind: str
    value: str | bytes = ""
    mode: int = 0o644

    def fingerprint(self) -> dict:
        result = {"kind": self.kind}
        if self.kind == "symlink":
            result["target"] = self.value
        elif self.kind == "file":
            result.update(sha256=hashlib.sha256(self.value).hexdigest(), mode=self.mode)
        return result


ABSENT = State("absent")


def snapshot(path: Path) -> State:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return ABSENT
    if stat.S_ISLNK(info.st_mode):
        return State("symlink", os.readlink(path))
    if stat.S_ISREG(info.st_mode):
        return State("file", path.read_bytes(), stat.S_IMODE(info.st_mode))
    return State("other")


def absolute(path: str | Path) -> Path:
    return Path(os.path.abspath(Path(path).expanduser()))


@dataclass(frozen=True)
class Locations:
    home: Path
    codex: Path
    claude: Path

    @property
    def state_dir(self) -> Path:
        return self.home / ".local/share/sentifold-skills"

    @property
    def receipt(self) -> Path:
        return self.state_dir / "receipt.json"

    def skills(self, runtime: str) -> Path:
        return self.home / ".agents/skills" if runtime == "codex" else self.claude / "skills"

    def agents(self, runtime: str) -> Path:
        return (self.codex if runtime == "codex" else self.claude) / "agents"


@dataclass(frozen=True)
class Change:
    path: Path
    before: State
    after: State
    label: str


@dataclass
class Plan:
    changes: list[Change]
    expected: dict[Path, State]
    destination_ids: dict[Path, Path]
    locations: Locations
    selected: set[str]


def load_catalog(root: Path) -> dict:
    try:
        catalog = json.loads((root / "catalog.json").read_text())
        if catalog["schema_version"] != 1:
            raise ValueError("unsupported schema_version")
        packages = catalog["packages"]
        names = [p["name"] for p in packages]
        if len(names) != len(set(names)) or any(not NAME.fullmatch(n) for n in names):
            raise ValueError("invalid or duplicate package name")
        available = {r: {p["name"] for p in packages if r in p["runtimes"]} for r in RUNTIMES}
        for package in packages:
            if not package["runtimes"] or not set(package["runtimes"]) <= RUNTIMES:
                raise ValueError(f"invalid runtimes: {package['name']}")
            resources = package.get("required_files", [])
            if not isinstance(resources, list) or any(
                not isinstance(resource, str) or not resource or Path(resource).is_absolute()
                or ".." in Path(resource).parts for resource in resources
            ):
                raise ValueError(f"invalid required_files: {package['name']}")
            for runtime, requires in package.get("requires", {}).items():
                if runtime not in package["runtimes"] or not set(requires) <= available[runtime]:
                    raise ValueError(f"unavailable dependency: {package['name']} / {runtime}")
        seen = set()
        for agent in catalog["agents"]:
            runtime, name = agent["runtime"], agent["name"]
            if runtime not in RUNTIMES or not NAME.fullmatch(name) or (runtime, name) in seen:
                raise ValueError("invalid or duplicate agent")
            seen.add((runtime, name))
            suffix = "toml" if runtime == "codex" else "md"
            if agent["source"] != f"agents/{runtime}/{name}.{suffix}":
                raise ValueError(f"invalid agent source: {name}")
            if not set(agent["requires"]) <= available[runtime]:
                raise ValueError(f"unavailable agent dependency: {name}")
        return catalog
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise InstallError(f"Invalid catalog in {root}: {exc}") from exc


def load_receipt(path: Path) -> tuple[dict, State]:
    state = snapshot(path)
    if state.kind == "absent":
        return {"schema_version": 1, "entries": {}}, state
    if state.kind != "file":
        raise InstallError(f"Receipt must be an ordinary file: {path}")
    try:
        receipt = json.loads(state.value)
        if receipt["schema_version"] != 1 or not isinstance(receipt["entries"], dict):
            raise ValueError("unsupported receipt")
        for path_text, entry in receipt["entries"].items():
            dest = Path(path_text)
            if not dest.is_absolute() or entry["runtime"] not in RUNTIMES:
                raise ValueError("invalid destination or runtime")
            if not NAME.fullmatch(entry["name"]) or entry["kind"] not in {"file", "symlink", "absent"}:
                raise ValueError("invalid owned entry")
            if entry["kind"] == "file" and (not re.fullmatch(r"[a-f0-9]{64}", entry["sha256"]) or not isinstance(entry["mode"], int)):
                raise ValueError("invalid file fingerprint")
            if entry["kind"] == "symlink" and not isinstance(entry["target"], str):
                raise ValueError("invalid link target")
            if entry.get("restore") is not None and not isinstance(entry["restore"], str):
                raise ValueError("invalid original symlink target")
        return receipt, state
    except (ValueError, KeyError, TypeError) as exc:
        raise InstallError(f"Invalid receipt {path}: {exc}") from exc


def owned_matches(entry: dict, state: State) -> bool:
    return all(entry.get(key) == value for key, value in state.fingerprint().items()) and entry["kind"] == state.kind


def rendered_agent(root: Path, agent: dict) -> bytes:
    source = root / agent["source"]
    try:
        template = source.read_text()
        if "{{SKILLS_ROOT}}" not in template:
            raise ValueError("missing {{SKILLS_ROOT}} reference")
        for reference in re.findall(r"\{\{SKILLS_ROOT\}\}/([a-zA-Z0-9_./-]+)", template):
            relative = Path(reference.rstrip("."))
            if ".." in relative.parts or not (root / "skills" / relative).exists():
                raise ValueError(f"missing or invalid package reference: {reference}")
        rendered = template.replace("{{SKILLS_ROOT}}", (root / "skills").as_posix())
        if re.search(r"\{\{[^}]+\}\}", rendered):
            raise ValueError("unresolved template placeholder")
        if agent["runtime"] == "codex":
            parsed = tomllib.loads(rendered)
            if parsed.get("name") != agent["name"] or not parsed.get("developer_instructions"):
                raise ValueError("agent needs matching name and developer_instructions")
        return rendered.encode()
    except (OSError, ValueError) as exc:
        raise InstallError(f"Invalid agent template {source}: {exc}") from exc


def validate_parent(path: Path) -> None:
    for parent in path.parents:
        if parent.exists():
            if not parent.is_dir():
                raise InstallError(f"Destination parent is not a directory: {parent}")
        elif parent.is_symlink():
            raise InstallError(f"Destination parent is a broken symlink: {parent}")


def destination_identity(path: Path) -> Path:
    # The parent may alias another runtime directory. The leaf is what we own;
    # resolving a skill symlink itself would incorrectly identify its source.
    return path.parent.resolve() / path.name


def prepare(root: Path, locations: Locations, selected: set[str], adopt: set[str] | None = None,
            uninstall: bool = False) -> Plan:
    """Read and validate the entire transaction before changing any destination."""
    root = root.resolve()
    adopt = adopt or set()
    receipt, receipt_state = load_receipt(locations.receipt)
    old = receipt["entries"]
    desired: dict[Path, tuple[str, str, State]] = {}
    owners: dict[Path, tuple[Path, str, str]] = {}
    destination_ids: dict[Path, Path] = {}

    def claim_destination(dest: Path, runtime: str, name: str) -> None:
        identity = destination_identity(dest)
        owner = (dest, runtime, name)
        previous = owners.get(identity)
        if previous is not None and previous != owner:
            raise InstallError(f"Runtime destinations overlap: {previous[0]} ({previous[1]}) and "
                               f"{dest} ({runtime}); choose separate runtime roots without aliases")
        owners[identity] = owner
        destination_ids[dest] = identity

    # Retained runtime entries and old roots being removed are part of the same
    # transaction boundary, even when only one runtime was selected.
    for path, entry in old.items():
        claim_destination(Path(path), entry["runtime"], entry["name"])
    claim_destination(locations.receipt, "state", "receipt")

    def add_destination(dest: Path, runtime: str, name: str, state: State) -> None:
        if dest in desired:
            raise InstallError(f"Runtime destinations overlap: {dest}; choose separate runtime roots")
        claim_destination(dest, runtime, name)
        desired[dest] = (runtime, name, state)

    if not uninstall:
        catalog = load_catalog(root)
        known = {p["name"] for p in catalog["packages"]} | {a["name"] for a in catalog["agents"]}
        if adopt - known:
            raise InstallError(f"Unknown --adopt names: {', '.join(sorted(adopt - known))}")
        for package in catalog["packages"]:
            for runtime in set(package["runtimes"]) & selected:
                source = root / "skills" / package["name"]
                if not (source / "SKILL.md").is_file():
                    raise InstallError(f"Missing required package: {source / 'SKILL.md'}")
                for resource in package.get("required_files", []):
                    path = root / resource
                    if not path.is_file() or not path.resolve().is_relative_to(root):
                        raise InstallError(f"Missing or unconfined required file: {path}")
                dest = locations.skills(runtime) / package["name"]
                add_destination(dest, runtime, package["name"], State("symlink", str(source)))
        for agent in catalog["agents"]:
            runtime = agent["runtime"]
            if runtime in selected:
                dest = locations.agents(runtime) / Path(agent["source"]).name
                add_destination(dest, runtime, agent["name"], State("file", rendered_agent(root, agent)))
        if "codex" in selected:
            for legacy_dir in {locations.codex / "skills", locations.home / ".codex/skills"}:
                for package in catalog["packages"]:
                    if "codex" not in package["runtimes"]:
                        continue
                    dest = legacy_dir / package["name"]
                    canonical = locations.skills("codex") / package["name"]
                    if destination_identity(dest) == destination_identity(canonical):
                        # A directory alias is one discovery location, not a duplicate.
                        continue
                    if snapshot(dest).kind != "absent" or str(dest) in old:
                        add_destination(dest, "codex", package["name"], ABSENT)

    relevant = {Path(p) for p, entry in old.items() if entry["runtime"] in selected} | desired.keys()
    expected = {locations.receipt: receipt_state}
    next_entries = {p: entry for p, entry in old.items() if entry["runtime"] not in selected}
    changes = []
    errors = []
    for dest in sorted(relevant):
        validate_parent(dest)
        current = snapshot(dest)
        expected[dest] = current
        entry = old.get(str(dest))
        if entry is not None and not owned_matches(entry, current):
            errors.append(f"Owned destination was changed; preserve or restore it before proceeding: {dest}")
            continue
        if dest not in desired:
            restore = entry.get("restore")
            after = State("symlink", restore) if restore is not None else ABSENT
            if current != after:
                changes.append(Change(dest, current, after, "restore adopted link" if restore is not None else "remove owned entry"))
            continue
        runtime, name, after = desired[dest]
        restore = entry.get("restore") if entry else None
        if entry is None and current.kind != "absent":
            if current.kind != "symlink" or name not in adopt:
                advice = f"; --adopt {name} may take over this symlink" if current.kind == "symlink" else "; ordinary files/directories cannot be adopted"
                errors.append(f"Unowned destination conflict: {dest}{advice}")
                continue
            restore = str(current.value)
        next_entries[str(dest)] = {"runtime": runtime, "name": name, **after.fingerprint(), "restore": restore}
        if current != after:
            label = "remove legacy duplicate" if after.kind == "absent" else ("adopt symlink" if entry is None and restore is not None else "install/update")
            changes.append(Change(dest, current, after, label))
    if errors:
        raise InstallError("\n".join(errors))
    validate_parent(locations.receipt)
    if next_entries:
        next_receipt = {"schema_version": 1, "entries": next_entries}
        receipt_after = State("file", (json.dumps(next_receipt, indent=2, sort_keys=True) + "\n").encode(), 0o600)
    else:
        receipt_after = ABSENT
    if receipt_state != receipt_after:
        changes.append(Change(locations.receipt, receipt_state, receipt_after, "write ownership receipt" if next_entries else "remove ownership receipt"))
    return Plan(changes, expected, destination_ids, locations, selected)


def make_parents(path: Path, created: list[Path]) -> None:
    missing = []
    parent = path.parent
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    for directory in reversed(missing):
        directory.mkdir()
        created.append(directory)


def write_state(path: Path, state: State) -> None:
    if state.kind == "absent":
        path.unlink(missing_ok=True)
        return
    fd, temp_name = tempfile.mkstemp(prefix=".sentifold-", dir=path.parent)
    temporary = Path(temp_name)
    try:
        if state.kind == "symlink":
            os.close(fd)
            temporary.unlink()
            temporary.symlink_to(state.value, target_is_directory=path.suffix not in {".toml", ".md"})
        else:
            with os.fdopen(fd, "wb") as stream:
                stream.write(state.value)
            temporary.chmod(state.mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def apply(plan: Plan) -> None:
    if not plan.changes:
        return
    created: list[Path] = []
    applied: list[Change] = []
    lock = plan.locations.state_dir / "install.lock"
    acquired = False
    try:
        make_parents(lock, created)
        try:
            lock.mkdir()
            acquired = True
        except FileExistsError as exc:
            raise InstallError(f"Another install may be running: {lock}. Inspect its owner before removing a stale lock.") from exc
        for dest, identity in plan.destination_ids.items():
            if destination_identity(dest) != identity:
                raise InstallError(f"Destination parent changed after preflight: {dest}")
        for dest, expected in plan.expected.items():
            if snapshot(dest) != expected:
                raise InstallError(f"Destination changed after preflight: {dest}")
        for change in plan.changes:
            make_parents(change.path, created)
            # Track before writing: interruption may arrive immediately after replace.
            applied.append(change)
            write_state(change.path, change.after)
    except BaseException as exc:
        failures = []
        # A second Ctrl-C must not abandon recovery halfway through its changes.
        handler = signal.signal(signal.SIGINT, signal.SIG_IGN) if current_thread() is main_thread() else None
        try:
            for change in reversed(applied):
                try:
                    if snapshot(change.path) != change.before:
                        write_state(change.path, change.before)
                except BaseException as rollback_error:
                    failures.append(f"{change.path}: {rollback_error}")
        finally:
            if handler is not None:
                signal.signal(signal.SIGINT, handler)
        detail = f"; rollback needs attention: {'; '.join(failures)}" if failures else "; changes rolled back"
        raise InstallError(f"Install failed: {str(exc) or type(exc).__name__}{detail}") from exc
    finally:
        if acquired:
            lock.rmdir()
        for directory in reversed(created):
            try:
                directory.rmdir()
            except OSError:
                pass


def cli_warnings(selected: set[str]) -> list[str]:
    warnings = []
    # Either runtime's cross-provider review needs both provider CLIs.
    for name in ("git", "gh", "codex", "claude"):
        binary = shutil.which(name)
        if binary is None:
            warnings.append(f"{name}: CLI missing from PATH; install it separately before using the affected workflow")
            continue
        try:
            result = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=5)
            version = (result.stdout or result.stderr).strip().splitlines()
            if result.returncode or not version:
                warnings.append(f"{name}: version unavailable (exit {result.returncode})")
            else:
                print(f"CLI {name}: {version[0]}")
        except (OSError, subprocess.TimeoutExpired) as exc:
            warnings.append(f"{name}: version probe failed: {exc}")
    if "codex" in selected:
        warnings.append("Codex: config was preserved; confirm nested agents are available (the review topology needs depth 2), or use the documented parent-coordination fallback")
    warnings.append("CLI versions alone do not prove agent discovery, authorization or model availability. Run the documented explicit smoke in a new session; no model fallback is selected here")
    return warnings


def source_revision(root: Path) -> str | None:
    if not (root / ".git").exists():
        return None
    try:
        revision = subprocess.check_output(["git", "rev-parse", "--verify", "HEAD"], cwd=root,
                                           text=True, stderr=subprocess.DEVNULL, timeout=5).strip()
        return revision if re.fullmatch(r"[a-f0-9]{40,64}", revision) else None
    except (OSError, subprocess.SubprocessError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["plan", "apply", "doctor", "uninstall"])
    parser.add_argument("--runtime", choices=["both", "codex", "claude"], default="both")
    parser.add_argument("--home", type=Path, default=Path.home(), help="ownership/discovery home (use a temporary directory for a dry fixture)")
    parser.add_argument("--codex-home", type=Path, help="agent directory root; defaults to CODEX_HOME or <home>/.codex")
    parser.add_argument("--claude-config-dir", type=Path, help="Claude directory root; defaults to CLAUDE_CONFIG_DIR or <home>/.claude")
    parser.add_argument("--adopt", action="append", default=[], metavar="NAME", help="take over only symlinks for this named package/agent; uninstall restores their original targets")
    args = parser.parse_args(argv)
    if args.adopt and args.command not in {"plan", "apply"}:
        parser.error("--adopt is only valid with plan or apply")
    home = absolute(args.home)
    locations = Locations(home, absolute(args.codex_home or os.environ.get("CODEX_HOME") or home / ".codex"),
                          absolute(args.claude_config_dir or os.environ.get("CLAUDE_CONFIG_DIR") or home / ".claude"))
    selected = RUNTIMES.copy() if args.runtime == "both" else {args.runtime}
    try:
        plan = prepare(ROOT, locations, selected, set(args.adopt), uninstall=args.command == "uninstall")
        revision = source_revision(ROOT)
        print(f"Source: {ROOT}{f' (Git {revision})' if revision else ''}\nHome: {home}\nRuntimes: {', '.join(sorted(selected))}")
        for change in plan.changes:
            origin = f"{change.after.value} -> " if change.after.kind == "symlink" else ""
            print(f"{change.label}: {origin}{change.path}")
        if not plan.changes:
            print("No changes needed.")
        if args.command in {"apply", "uninstall"}:
            apply(plan)
            print("Installation updated." if args.command == "apply" else "Owned installation removed; adopted symlinks restored.")
        elif args.command == "doctor":
            for warning in cli_warnings(selected):
                print(f"WARNING: {warning}")
            if plan.changes:
                print("ERROR: installation differs from this checkout; inspect plan before apply.")
                return 1
            print("Installed links and rendered agents match the checked dependency closure.")
        return 0
    except (InstallError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
