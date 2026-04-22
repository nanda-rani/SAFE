"""
core/guardrails.py

Post-processing classification layer for the Security Auditor.

After the LLM produces a validated AnalysisResult, this module:
1. Extracts evidence signals from the parsed output fields.
2. Applies hard guardrail rules to decide if the label must be downgraded.
3. Returns the (possibly corrected) result dict and a structured guardrail log.

Guardrail rules (all enforced deterministically in Python, not by the LLM):
  - TRUE_SECURITY_RISK is ONLY allowed when:
      attacker_control == "yes"  AND  reachability == "yes"
  - Otherwise TRUE_SECURITY_RISK → CONTEXTUAL_RISK
  - FALSE_POSITIVE is ONLY allowed when evidence_snippet contains real code evidence
      (i.e., does NOT start with "EVIDENCE_MISSING")
  - Otherwise FALSE_POSITIVE → CONTEXTUAL_RISK
"""

import re
from typing import Dict, Any, Tuple


def _extract_signal(field_value: str) -> str:
    """
    Parse 'yes/no/uncertain ...' style fields to extract the primary signal.
    Returns one of: "yes", "no", "uncertain"
    """
    if not field_value:
        return "uncertain"
    norm = field_value.strip().lower()
    if norm.startswith("yes"):
        return "yes"
    if norm.startswith("no"):
        return "no"
    return "uncertain"


def _evidence_complete(parsed: Dict[str, Any]) -> bool:
    """
    Returns True only when the evidence_snippet is non-empty and does not
    carry an EVIDENCE_MISSING marker from the filesystem tools.
    """
    snippet = parsed.get("evidence_snippet", "")
    if not snippet or snippet.strip().upper().startswith("EVIDENCE_MISSING"):
        return False
    return True


def apply_guardrails(
    parsed: Dict[str, Any],
    finding_uid: str,
    logger,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Apply hard classification guardrails to the validated parsed result.

    Args:
        parsed:       Validated AnalysisResult dict (from validator.validate_and_parse_output).
        finding_uid:  Finding UID string for logging.
        logger:       Finding-specific logger.

    Returns:
        (corrected_parsed_dict, guardrail_log_dict)
    """
    raw_label = parsed.get("security_label", "")

    # Extract evidence signals
    attacker_control = _extract_signal(parsed.get("input_controlled_by_attacker", ""))
    reachability     = _extract_signal(parsed.get("reachable_in_artifact_execution", ""))
    evidence_ok      = _evidence_complete(parsed)

    # Derive impact signal from reasoning
    reasoning_lower = parsed.get("reasoning", "").lower()
    impact_keywords  = ["rce", "remote code", "data leak", "privilege escalation",
                        "arbitrary command", "arbitrary file", "sql injection",
                        "xss", "ssrf", "path traversal", "shell injection"]
    impact_present = any(kw in reasoning_lower for kw in impact_keywords)

    # --- GUARDRAIL 1 --------------------------------------------------------
    # TRUE_SECURITY_RISK requires attacker_control==yes AND reachability==yes
    final_label = raw_label
    downgrade_reason = ""

    if raw_label == "TRUE_SECURITY_RISK":
        if attacker_control != "yes" or reachability != "yes":
            final_label = "CONTEXTUAL_RISK"
            downgrade_reason = (
                f"Downgraded TRUE_SECURITY_RISK → CONTEXTUAL_RISK. "
                f"attacker_control='{attacker_control}', reachability='{reachability}'. "
                "Both must be 'yes' for TRUE_SECURITY_RISK."
            )

    # --- GUARDRAIL 2 --------------------------------------------------------
    # FALSE_POSITIVE requires positive evidence (real code seen)
    if final_label == "FALSE_POSITIVE" and not evidence_ok:
        final_label = "CONTEXTUAL_RISK"
        downgrade_reason = (
            "Downgraded FALSE_POSITIVE → CONTEXTUAL_RISK because evidence_snippet "
            "is empty or contains EVIDENCE_MISSING. Cannot confirm false positive "
            "without reading the actual code."
        )

    # Apply downgrade to result dict if needed
    corrected = dict(parsed)
    if final_label != raw_label:
        corrected["security_label"] = final_label
        corrected["reasoning"] = (
            f"[GUARDRAIL APPLIED: {downgrade_reason}]\n\n"
            + corrected.get("reasoning", "")
        )
        logger.warning(f"[Guardrail] {downgrade_reason}")
    else:
        logger.info(
            f"[Guardrail] Label '{final_label}' passed all guardrail checks. "
            f"attacker_control='{attacker_control}', reachability='{reachability}', "
            f"evidence_complete={evidence_ok}."
        )

    # --- Structured guardrail log -------------------------------------------
    guardrail_log = {
        "finding_uid":              finding_uid,
        "flag_present":             evidence_ok,
        "attacker_control":         attacker_control,
        "reachability":             reachability,
        "impact":                   "yes" if impact_present else "uncertain",
        "evidence_complete":        evidence_ok,
        "raw_model_label":          raw_label,
        "final_label_after_guardrails": final_label,
        "downgrade_reason":         downgrade_reason or "none",
    }

    return corrected, guardrail_log
