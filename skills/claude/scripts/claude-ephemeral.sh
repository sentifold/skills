#!/usr/bin/env bash
# Copyright (c) 2026 Theta Games. Derived from gamejam f4dbd06ec.
set -euo pipefail
# Resolve the installed package, never change the caller's working directory.
RUNTIME=$(python3 -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve().parents[3] / "lib/provider_runtime.py")' "${BASH_SOURCE[0]}")
exec python3 "$RUNTIME" claude run "$@"
