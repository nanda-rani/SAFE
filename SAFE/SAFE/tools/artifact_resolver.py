import os
from pathlib import Path
from core.logger import system_logger


def resolve_artifact_path(artifact_id: str, artifact_root: str = "ARTIFACT") -> str:
    """
    Resolve the absolute filesystem path of a repository for a given artifact_id.

    Returns the resolved absolute path string, or '' if not found.
    Always returns Path.resolve() so callers get a stable absolute path
    that never needs further joining with the artifact_id again.
    """
    root_path = Path(artifact_root).resolve()
    if not root_path.exists() or not root_path.is_dir():
        system_logger.error(f"Artifact root '{artifact_root}' does not exist.")
        return ""

    # Exact match
    target_path = root_path / artifact_id
    if target_path.exists() and target_path.is_dir():
        resolved = target_path.resolve()
        system_logger.info(f"Resolved artifact '{artifact_id}' → '{resolved}'")
        return str(resolved)

    # Fuzzy match: artifact_id appears anywhere in the dir name
    for entry in sorted(root_path.iterdir()):
        if entry.is_dir() and artifact_id in entry.name:
            resolved = entry.resolve()
            system_logger.info(
                f"Fuzzy-matched artifact '{artifact_id}' to dir '{entry.name}' → '{resolved}'"
            )
            return str(resolved)

    system_logger.warning(f"Failed to resolve artifact '{artifact_id}' in '{root_path}'")
    return ""
