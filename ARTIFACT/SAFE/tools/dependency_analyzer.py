import os
from pathlib import Path
from langchain_core.tools import tool

IGNORE_DIRS = {".git", "__pycache__", ".venv", "env", "node_modules", "build", "dist"}
DEPENDENCY_FILES = {"requirements.txt", "pyproject.toml", "setup.py", "environment.yml", "Pipfile"}
ENTRYPOINT_KEYWORDS = {
    "if __name__ == '__main__':",
    "@app.",
    "def main(",
    "FastAPI(",
    "Flask(",
    "setup(",
}


@tool
def extract_dependency_files(repo_path: str) -> str:
    """
    Finds and reads the content of dependency files (requirements.txt, pyproject.toml, etc.).
    Returns ABSOLUTE paths alongside content so they can be opened directly.
    """
    root = Path(repo_path).resolve()
    if not root.exists() or not root.is_dir():
        return f"Error: repo_path '{repo_path}' does not exist or is not a directory."

    found_content = []
    for dirpath, dirnames, filenames in os.walk(str(root)):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for file in filenames:
            if file in DEPENDENCY_FILES:
                abs_path = Path(dirpath) / file
                try:
                    with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                    content = "".join(lines[:100])
                    if len(lines) > 100:
                        content += "\n...[TRUNCATED]"
                    found_content.append(f"--- {abs_path} ---\n{content}")
                except Exception as exc:
                    found_content.append(f"--- {abs_path} --- [READ ERROR: {exc}]")

    if found_content:
        return "\n\n".join(found_content)
    return "No dependency definition files found in the repository."


@tool
def detect_entrypoints(repo_path: str) -> str:
    """
    Scans the repository and identifies likely execution entrypoints.
    Returns ABSOLUTE paths so they can be opened directly.
    """
    root = Path(repo_path).resolve()
    if not root.exists() or not root.is_dir():
        return f"Error: repo_path '{repo_path}' does not exist."

    results = []
    for dirpath, dirnames, filenames in os.walk(str(root)):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for file in filenames:
            if not file.endswith(".py"):
                continue
            abs_path = Path(dirpath) / file
            try:
                with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                if any(kw in content for kw in ENTRYPOINT_KEYWORDS):
                    results.append(str(abs_path))
            except Exception:
                pass

    if results:
        return "Possible entrypoints (absolute paths):\n" + "\n".join(results)
    return "No obvious entrypoint files detected."


@tool
def search_package_usage(repo_path: str, package_name: str) -> str:
    """
    Searches the repository for imports of a specific package.
    Scans all .py files using os.walk on the real filesystem.
    Returns ABSOLUTE file paths and matching line numbers so they can be verified directly.
    """
    root = Path(repo_path).resolve()
    if not root.exists() or not root.is_dir():
        return f"Error: repo_path '{repo_path}' does not exist or is not a directory."

    import_patterns = [
        f"import {package_name}",
        f"from {package_name}",
        f"import {package_name}.",
    ]
    results = []

    for dirpath, dirnames, filenames in os.walk(str(root)):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for file in filenames:
            if not file.endswith(".py"):
                continue
            abs_path = Path(dirpath) / file
            # Guard: skip files that don't exist (shouldn't happen but be safe)
            if not abs_path.is_file():
                continue
            try:
                with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, 1):
                        if any(pat in line for pat in import_patterns):
                            results.append(
                                f"{abs_path}:{line_num} | {line.strip()}"
                            )
                            if len(results) >= 50:
                                results.append("... [truncated at 50 results]")
                                return (
                                    f"Package '{package_name}' found in:\n"
                                    + "\n".join(results)
                                )
            except Exception:
                pass

    if results:
        return f"Package '{package_name}' found in:\n" + "\n".join(results)
    return f"Package '{package_name}' is NOT imported anywhere in the repository."
