"""
tools/path_utils.py

Centralised path normalisation for the security auditor.

The root bug: CSV 'file' fields often carry the artifact_id as a leading
component, e.g.  A012/baselines/extract_info.py
When the agent naively joins  repo_path / file  it gets:
  ARTIFACT/A012/A012/baselines/extract_info.py   ← duplicated prefix!

normalize_path() strips every known duplicated-prefix pattern and returns
a verified absolute Path, or raises FileNotFoundError with a clear message
so callers can surface a controlled error without crashing.
"""

import os
from pathlib import Path


def normalize_path(repo_path: str, path: str) -> Path:
    """
    Resolve *path* to a verified absolute path inside *repo_path*.

    Resolution strategy (tried in order):
      1. If *path* is already an absolute path that exists → return it.
      2. If joining repo_path / path yields an existing file → return it.
      3. Strip every leading segment of *path* that equals the last component
         of *repo_path* (handles A012/A012/… duplication) and retry join.
      4. Walk the repo to find a file whose name matches the basename of *path*
         (last-resort fuzzy fallback for deeply nested renames).

    Raises FileNotFoundError if none of the above strategies succeed.
    """
    root = Path(repo_path).resolve()
    p = Path(path)

    # ── Strategy 1: already absolute and exists ──────────────────────────────
    if p.is_absolute():
        if p.exists():
            return p
        # absolute but wrong → fall through to stripping logic on the parts

    # ── Strategy 2: direct join ───────────────────────────────────────────────
    candidate = (root / p).resolve()
    if candidate.exists():
        return candidate

    # ── Strategy 3: strip duplicated repo-name prefixes ──────────────────────
    # Example:
    #   root      = /…/ARTIFACT/A012
    #   path      = A012/baselines/extract_info.py
    #   root.name = "A012"
    # We strip every leading part of `path` that matches root.name or any
    # ancestor directory component of root.
    #
    # We collect ALL names in the root hierarchy so we handle
    # nested duplications like A012/A012/src/foo.py.
    root_parts = set(root.parts)

    parts = list(p.parts)
    # Keep stripping while the first segment is a known repo-path component
    while parts and parts[0] in root_parts:
        stripped = Path(*parts[1:]) if len(parts) > 1 else Path()
        candidate = (root / stripped).resolve()
        if candidate.exists():
            return candidate
        parts = parts[1:]

    # ── Strategy 4: filename-only search (fallback) ───────────────────────────
    target_name = Path(path).name
    ignore = {".git", "__pycache__", ".venv", "env", "node_modules", "build", "dist"}
    for dirpath, dirnames, filenames in os.walk(str(root)):
        dirnames[:] = [d for d in dirnames if d not in ignore]
        if target_name in filenames:
            found = Path(dirpath) / target_name
            return found.resolve()

    raise FileNotFoundError(
        f"Cannot resolve path '{path}' inside repo '{repo_path}'. "
        "Strategies tried: absolute check, direct join, prefix-stripping, "
        "and filename search. File may not exist in this repository."
    )
