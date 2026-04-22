import ast
from pathlib import Path
from langchain_core.tools import tool
from tools.path_utils import normalize_path


@tool
def extract_enclosing_function(path: str, line_number: int, repo_path: str = "") -> str:
    """
    Parse a Python file with AST and identify the function/class enclosing the given line.
    Returns the function name and full body so caller can search for its usages.

    Always supply repo_path so duplicated artifact-id prefixes are stripped correctly.
    """
    if not repo_path:
        p = Path(path)
        if not p.exists() or not p.is_file():
            return (
                f"EVIDENCE_MISSING: File '{path}' not found and repo_path not provided. "
                "Cannot extract enclosing function — analysis is INCOMPLETE."
            )
    else:
        try:
            p = normalize_path(repo_path, path)
        except FileNotFoundError as e:
            return (
                f"EVIDENCE_MISSING: {e} "
                "Cannot extract enclosing function — analysis is INCOMPLETE, "
                "classify as CONTEXTUAL_RISK."
            )

    if not p.is_file():
        return f"EVIDENCE_MISSING: Resolved path '{p}' is not a file."

    try:
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()
    except Exception as e:
        return f"EVIDENCE_MISSING: Cannot read '{p}': {e}"

    try:
        tree = ast.parse(code, filename=str(p))
    except SyntaxError as e:
        return f"SyntaxError — cannot parse '{p}': {e}. File may not be valid Python."

    matches = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                if node.lineno <= line_number <= node.end_lineno:
                    matches.append(node)

    if not matches:
        return (
            f"No enclosing function/class found at line {line_number} in '{p}'. "
            "The line may be at module level."
        )

    # Innermost = tightest line range
    best = min(matches, key=lambda n: n.end_lineno - n.lineno)
    code_lines = code.split("\n")
    body = "\n".join(code_lines[best.lineno - 1 : best.end_lineno])

    return (
        f"[Resolved: {p}]\n"
        f"Enclosing {best.__class__.__name__}: '{best.name}'\n"
        f"Range: lines {best.lineno}–{best.end_lineno}\n"
        f"--- Body ---\n{body}"
    )
