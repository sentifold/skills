#!/usr/bin/env python3
"""Resolve a local review snapshot without fetching or changing the checkout."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys


class ScopeError(Exception):
    """The requested scope cannot be established without guessing."""


def git(repo, *args, optional=False):
    result = subprocess.run(
        ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", *args], cwd=repo,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if result.returncode:
        if optional:
            return None
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise ScopeError(detail or f"git {args[0]} failed")
    return result.stdout


def commit(repo, ref):
    if not ref or ref.startswith("-"):
        raise ScopeError("A revision must be a non-option Git ref or commit ID")
    return git(repo, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}").decode().strip()


def paths(data):
    return [os.fsdecode(item) for item in data.split(b"\0") if item]


def changed_paths(repo, *revisions, cached=False):
    args = ["diff", "--no-ext-diff", "--no-textconv", "--ignore-submodules=none", "--name-only", "-z"]
    if cached:
        args.append("--cached")
    return paths(git(repo, *args, *revisions, "--"))


def diff(repo, *revisions, cached=False):
    args = ["diff", "--no-ext-diff", "--no-textconv", "--ignore-submodules=none", "--binary", "--full-index"]
    if cached:
        args.append("--cached")
    return git(repo, *args, *revisions, "--")


def add_digest(hasher, label, data):
    # Length-delimited fields avoid ambiguous joins of paths and binary contents.
    for value in (os.fsencode(label), data):
        hasher.update(len(value).to_bytes(8, "big"))
        hasher.update(value)


def untracked_digest(repo, name):
    file_path = repo / name
    info = file_path.lstat()
    if stat.S_ISLNK(info.st_mode):
        return "symlink", hashlib.sha256(os.fsencode(os.readlink(file_path))).hexdigest()
    if not stat.S_ISREG(info.st_mode):
        raise ScopeError(f"Cannot snapshot non-regular untracked file: {name}")
    digest = hashlib.sha256()
    with file_path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    kind = "executable" if info.st_mode & 0o111 else "file"
    return kind, digest.hexdigest()


def resolve(repo, base=None, head="HEAD", mode="branch", include_worktree=False,
            exact_base=False, remote="origin"):
    repo = Path(repo).resolve()
    root = Path(os.fsdecode(git(repo, "rev-parse", "--show-toplevel").rstrip(b"\n")))
    head_id = commit(root, head)
    current_head = commit(root, "HEAD")
    include_dirty = mode == "uncommitted" or include_worktree
    if mode == "uncommitted" and (base or exact_base or head != "HEAD"):
        raise ScopeError("uncommitted mode reviews HEAD, index and working tree; omit base/head options")
    if include_dirty and head_id != current_head:
        raise ScopeError("Worktree changes can only be combined with the current HEAD")
    if exact_base and not base:
        raise ScopeError("--exact-base requires an explicit --base")

    base_source = "explicit"
    if mode == "uncommitted":
        base = "HEAD"
        base_source = "uncommitted"
    elif base is None:
        branch = git(root, "symbolic-ref", "--quiet", "--short", "HEAD", optional=True)
        configured = None
        if branch:
            configured = git(root, "config", "--get", "branch." + branch.decode().strip() + ".gh-merge-base", optional=True)
        if configured and configured.strip():
            base = configured.decode().strip()
            base_source = "branch.gh-merge-base"
        else:
            if not remote or remote.startswith("-"):
                raise ScopeError("Invalid remote name")
            default = git(root, "symbolic-ref", "--quiet", f"refs/remotes/{remote}/HEAD", optional=True)
            if not default:
                raise ScopeError("No explicit base, branch gh-merge-base, or remote HEAD; specify --base")
            base = default.decode().strip()
            base_source = "remote HEAD (local ref; not fetched)"
    base_tip = commit(root, base)
    if exact_base or mode == "uncommitted":
        base_id = base_tip
    else:
        bases = git(root, "merge-base", "--all", base_tip, head_id).decode().splitlines()
        if len(bases) != 1:
            raise ScopeError("Scope has multiple merge bases; supply an explicit --base with --exact-base")
        base_id = bases[0]

    staged_paths = changed_paths(root, current_head, cached=True)
    unstaged_paths = changed_paths(root)
    untracked = paths(git(root, "ls-files", "--others", "--exclude-standard", "-z"))
    dirty_paths = sorted(set(staged_paths + unstaged_paths + untracked))
    included_paths = set(changed_paths(root, base_id, head_id))
    digest = hashlib.sha256()
    add_digest(digest, "base", base_id.encode())
    add_digest(digest, "head", head_id.encode())
    add_digest(digest, "mode", mode.encode())
    add_digest(digest, "committed", diff(root, base_id, head_id))
    untracked_files = []
    if include_dirty:
        # A gitlink diff fingerprints its commit, not arbitrary dirt inside it.
        for entry in git(root, "ls-files", "--stage", "-z").split(b"\0"):
            if not entry.startswith(b"160000 "):
                continue
            name = os.fsdecode(entry.split(b"\t", 1)[1])
            submodule = root / name
            if (submodule / ".git").exists() and git(
                submodule, "status", "--porcelain=v1", "-z",
                "--untracked-files=all", "--ignore-submodules=none",
            ):
                raise ScopeError(f"Dirty submodule requires a separate review snapshot: {name}")
        included_paths.update(dirty_paths)
        add_digest(digest, "staged", diff(root, current_head, cached=True))
        add_digest(digest, "unstaged", diff(root))
        for name in sorted(untracked):
            kind, sha = untracked_digest(root, name)
            add_digest(digest, name, (kind + ":" + sha).encode())
            untracked_files.append({"path": name, "kind": kind, "sha256": sha})
    return {
        "repository_root": str(root), "mode": mode,
        "base_ref": base, "base_source": base_source,
        "base_tip": base_tip, "base_commit": base_id, "head_commit": head_id,
        "includes_worktree": include_dirty, "changed_paths": sorted(included_paths),
        "excluded_dirty_paths": [] if include_dirty else dirty_paths,
        "untracked_files": untracked_files, "snapshot_sha256": digest.hexdigest(),
        "snapshot_note": "Fingerprint, not a frozen checkout; stop concurrent writes and recheck after review.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--base")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--mode", choices=("branch", "uncommitted"), default="branch")
    parser.add_argument("--include-worktree", action="store_true")
    parser.add_argument("--exact-base", action="store_true")
    try:
        args = vars(parser.parse_args())
        print(json.dumps(resolve(**args), indent=2))
    except (ScopeError, OSError) as error:
        print(f"resolve-scope: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
