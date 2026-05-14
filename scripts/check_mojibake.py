#!/usr/bin/env python3
"""Standalone script wrapper.

For installation:  pip install -e .
Then use:          check-mojibake --root ./src
Or:                python -m check_mojibake --root ./src

This file directly executes the canonical implementation from src/check_mojibake/core.py
using runpy to avoid filename conflicts with the package name.
"""
import runpy
import sys
from pathlib import Path

# Add src/ to the path for package imports (used by core.py internals).
_src = str(Path(__file__).resolve().parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

# Execute core.py directly to avoid "check_mojibake" module name collision.
_core = Path(__file__).resolve().parent.parent / "src" / "check_mojibake" / "core.py"
runpy.run_path(str(_core), run_name="__main__")
