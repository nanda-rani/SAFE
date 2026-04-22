import os
from pathlib import Path
from langchain_core.tools import tool

IGNORE_DIRS = {".git", "__pycache__", ".venv", "env", "node_modules", "build", "dist", ".idea", ".vscode"}
IMPORTANT_FILENAMES = {
    "README.md", "README.rst", "requirements.txt", "pyproject.toml",
    "setup.py", "environment.yml", "Dockerfile", "docker-compose.yml", "Pipfile",
}


@tool
def get_repo_tree(repo_path: str, max_depth: int = 4, max_files: int = 300) -> str:
    """
    Returns a tree structure of the repository up to max_depth, skipping common irrelevant dirs.
    ALWAYS call this first to understand the repository layout before reading or searching files.
    """
    root = Path(repo_path).resolve()
    if not root.exists() or not root.is_dir():
        return f"Error: Path '{repo_path}' does not exist or is not a directory."

    tree_lines = []
    file_count = 0

    def walk(directory: Path, prefix: str = "", current_depth: int = 0):
        nonlocal file_count
        if current_depth > max_depth or file_count >= max_files:
            return
        try:
            entries = sorted(directory.iterdir(), key=lambda x: (not x.is_dir(), x.name))
        except PermissionError:
            return

        filtered = [e for e in entries if e.name not in IGNORE_DIRS and not e.name.startswith(".git")]
        for i, entry in enumerate(filtered):
            if file_count >= max_files:
                tree_lines.append(prefix + "└── ... (max files reached)")
                break
            is_last = i == len(filtered) - 1
            connector = "└── " if is_last else "├── "
            tree_lines.append(f"{prefix}{connector}{entry.name}")
            if entry.is_dir():
                file_count += 1
                child_prefix = prefix + ("    " if is_last else "│   ")
                walk(entry, child_prefix, current_depth + 1)
            else:
                file_count += 1

    tree_lines.append(f"{root.name}/  [absolute: {root}]")
    walk(root)
    return "\n".join(tree_lines)


@tool
def find_important_files(repo_path: str) -> str:
    """
    Finds README, build files, and dependency manifests.
    Returns ABSOLUTE paths so you can pass them directly to read_file.
    """
    root = Path(repo_path).resolve()
    if not root.exists() or not root.is_dir():
        return f"Error: Path '{repo_path}' does not exist or is not a directory."

    found_files = []
    for dirpath, dirnames, filenames in os.walk(str(root)):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for file in filenames:
            if file in IMPORTANT_FILENAMES or file in ("main.py", "app.py", "run.py", "train.py", "server.py"):
                abs_path = str(Path(dirpath) / file)
                found_files.append(abs_path)

    if found_files:
        return "Important files (absolute paths):\n" + "\n".join(found_files)
    return "No typical important files (README, requirements, etc.) found."
