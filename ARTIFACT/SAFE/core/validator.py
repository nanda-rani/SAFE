import json
import re
from pydantic import ValidationError
from typing import Dict, Any, Tuple
from core.schemas import AnalysisResult
from core.logger import error_logger


def _extract_json(raw: str) -> str:
    """
    Robustly extract the first complete JSON object from raw text.
    Handles cases where the LLM wraps JSON in markdown fences or prepends explanation text.
    """
    # Strip markdown fences first
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    # If looks like pure JSON already — try as-is
    if cleaned.startswith("{"):
        return cleaned

    # Walk character-by-character to find first balanced { ... }
    depth = 0
    start = -1
    for i, ch in enumerate(cleaned):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start != -1:
                return cleaned[start : i + 1]

    # Fallback: return as-is (will fail json.loads and trigger a retry)
    return cleaned


def validate_and_parse_output(raw_output: str) -> Tuple[bool, Dict[str, Any], str]:
    """
    Validates the LLM output against the AnalysisResult schema.
    Returns: (is_valid, parsed_dict_if_valid, error_reason)
    """
    extracted = _extract_json(raw_output)
    try:
        data = json.loads(extracted)
    except json.JSONDecodeError as e:
        msg = f"Invalid JSON: {e} | Extracted segment: {extracted[:300]}"
        error_logger.warning(msg)
        return False, {}, msg

    try:
        result = AnalysisResult(**data)
        return True, result.model_dump(), ""
    except ValidationError as e:
        msg = f"Schema validation failed: {e}"
        error_logger.warning(msg)
        return False, {}, msg
