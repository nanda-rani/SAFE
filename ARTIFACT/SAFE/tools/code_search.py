import os
from pathlib import Path
from langchain_core.tools import tool

IGNORE_DIRS = {".git", "__pycache__", ".venv", "env", "node_modules", "build", "dist"}


@tool
def search_repo(repo_path: str, query: str) -> str:
    """
    Search for a literal string across all text files in the repository.
    Always walks from the verified repo_path root — never constructs file paths from
    external input.  Returns absolute paths and line numbers so results can be
    passed directly to read_snippet or read_file.
    Limited to 50 matches.
    """
    root = Path(repo_path).resolve()
    if not root.exists() or not root.is_dir():
        return f"Error: repo_path '{repo_path}' does not exist or is not a directory."

    results = []
    for dirpath, dirnames, filenames in os.walk(str(root)):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for filename in filenames:
            abs_path = Path(dirpath) / filename
            if not abs_path.is_file():
                continue
            try:
                with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, 1):
                        if query in line:
                            # Return absolute path so downstream tools work directly
                            results.append(
                                f"{abs_path}:{line_num} | {line.strip()}"
                            )
                            if len(results) >= 50:
                                results.append("... [truncated at 50 results]")
                                return "\n".join(results)
            except Exception:
                pass

    if results:
        return "\n".join(results)
    return f"No matches found for '{query}' in '{root}'"
