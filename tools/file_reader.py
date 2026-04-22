import traceback
from pathlib import Path
from langchain_core.tools import tool
from tools.path_utils import normalize_path


@tool
def read_file(path: str, repo_path: str = "") -> str:
    """
    Read the content of a file (up to 2000 lines).

    Always pass repo_path so the normaliser can strip duplicated artifact-id
    prefixes (e.g. A012/A012/…) before touching the filesystem.
    Never call this with an unresolved or guessed path.
    """
    if not repo_path:
        p = Path(path)
        if not p.exists() or not p.is_file():
            return (
                f"EVIDENCE_MISSING: File '{path}' could not be accessed and no "
                "repo_path was provided for resolution. "
                "Analysis is INCOMPLETE for this file — classify as CONTEXTUAL_RISK."
            )
    else:
        try:
            p = normalize_path(repo_path, path)
        except FileNotFoundError as e:
            return (
                f"EVIDENCE_MISSING: {e} "
                "Analysis is INCOMPLETE for this file — classify as CONTEXTUAL_RISK, "
                "do NOT assume FALSE_POSITIVE."
            )

    if not p.is_file():
        return (
            f"EVIDENCE_MISSING: Resolved path '{p}' is not a regular file. "
            "Analysis is INCOMPLETE — classify as CONTEXTUAL_RISK."
        )

    try:
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            lines = []
            for i, line in enumerate(f):
                if i >= 2000:
                    lines.append("\n...[TRUNCATED at 2000 lines]")
                    break
                lines.append(line.rstrip("\n"))
        return "\n".join(lines)
    except Exception as e:
        return (
            f"EVIDENCE_MISSING: Could not read '{p}': {e}. "
            "Analysis is INCOMPLETE — classify as CONTEXTUAL_RISK."
        )


@tool
def read_snippet(path: str, line_number: int, context_window: int = 50, repo_path: str = "") -> str:
    """
    Read ±context_window lines around line_number.

    Always pass repo_path so the normaliser can strip duplicated artifact-id
    prefixes (e.g. A012/A012/…) before accessing the filesystem.
    Target line is marked with '>>' and output includes line numbers.
    """
    if not repo_path:
        p = Path(path)
        if not p.exists() or not p.is_file():
            return (
                f"EVIDENCE_MISSING: File '{path}' could not be accessed and no "
                "repo_path was provided for resolution. "
                "Analysis is INCOMPLETE — classify as CONTEXTUAL_RISK."
            )
    else:
        try:
            p = normalize_path(repo_path, path)
        except FileNotFoundError as e:
            return (
                f"EVIDENCE_MISSING: {e} "
                "Analysis is INCOMPLETE for this file — classify as CONTEXTUAL_RISK, "
                "do NOT assume FALSE_POSITIVE."
            )

    if not p.is_file():
        return (
            f"EVIDENCE_MISSING: Resolved path '{p}' is not a regular file. "
            "Analysis is INCOMPLETE — classify as CONTEXTUAL_RISK."
        )

    try:
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        start = max(0, line_number - context_window - 1)
        end = min(len(lines), line_number + context_window)

        snippet = []
        for i in range(start, end):
            indicator = ">>" if i + 1 == line_number else "  "
            snippet.append(f"{indicator} {i + 1:4d} | {lines[i].rstrip()}")

        return f"[Resolved: {p}]\n" + "\n".join(snippet)
    except Exception as e:
        return (
            f"EVIDENCE_MISSING: Error reading snippet from '{p}': {e}\n"
            f"{traceback.format_exc()}"
        )
