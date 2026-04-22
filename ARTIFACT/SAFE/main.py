import csv
import json
import yaml
import sys
import os
from pathlib import Path
from datetime import datetime

from core.logger import system_logger, error_logger, save_finding_json
from core.auditor import SecurityAuditorAgent
from tools.artifact_resolver import resolve_artifact_path
from llm.cost_tracker import cost_tracker

# ─── CSV output columns ───────────────────────────────────────────────────────
CSV_FIELDS = [
    "finding_uid",
    "artifact_id",
    "tool",
    "finding_id",
    "severity_raw",
    "file",
    "line",
    "package",
    "version",
    "security_label",
    "code_purpose",
    "execution_context",
    "required_conditions_for_exploit",
    "input_controlled_by_attacker",
    "reachable_in_artifact_execution",
    "evidence_snippet",
    "reasoning",
    "recommendation",
    "finding_cost_usd",
    "finding_prompt_tokens",
    "finding_completion_tokens",
]


def _print_cost_banner(finding_uid: str, finding_num: int, total_findings: int, model: str):
    """Print a visible live cost progress banner to stdout."""
    fc = cost_tracker.get_finding_cost(finding_uid)
    gc = cost_tracker.get_global_totals()

    finding_cost   = fc.get("total_cost_usd", 0.0)
    finding_prompt = fc.get("total_prompt_tokens", 0)
    finding_comp   = fc.get("total_completion_tokens", 0)

    global_cost    = gc.get("total_cost_usd", 0.0)
    global_prompt  = gc.get("total_prompt_tokens", 0)
    global_comp    = gc.get("total_completion_tokens", 0)

    bar_filled = int((finding_num / total_findings) * 30)
    bar = "█" * bar_filled + "░" * (30 - bar_filled)

    print("\n" + "─" * 65)
    print(f"  ✅  Finding {finding_num}/{total_findings}  [{bar}]")
    print(f"  UID    : {finding_uid}")
    print(f"  Model  : {model}")
    print(f"  ┌─ This Finding ─────────────────────────────────")
    print(f"  │   Prompt tokens    : {finding_prompt:>10,}")
    print(f"  │   Completion tokens: {finding_comp:>10,}")
    print(f"  │   Cost             : ${finding_cost:>10.6f}")
    print(f"  ├─ Cumulative Total ─────────────────────────────")
    print(f"  │   Prompt tokens    : {global_prompt:>10,}")
    print(f"  │   Completion tokens: {global_comp:>10,}")
    print(f"  │   Total cost       : ${global_cost:>10.6f}")
    print("  └─────────────────────────────────────────────────")
    print("─" * 65 + "\n")


def load_config(path="config.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def read_csv(path):
    findings = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            findings.append(row)
    return findings


def save_final_csv(all_results: list, output_path: str):
    """Writes all finding results to a single consolidated CSV."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_results)
    print(f"\n  📄  Final results CSV saved → {output_path}\n")


def main():
    system_logger.info("Starting Contextual Security Auditor")
    print("\n" + "═" * 65)
    print("   CONTEXTUAL SECURITY AUDITOR")
    print(f"   Started : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 65)

    try:
        config = load_config()
    except Exception as e:
        error_logger.error(f"Failed to load config: {e}")
        sys.exit(1)

    model_string = config.get("model", "gpt-4o")
    print(f"   Model   : {model_string}")
    system_logger.info(f"Using model: {model_string}")

    try:
        agent = SecurityAuditorAgent(model_string)
    except Exception as e:
        error_logger.error(f"Failed to initialize agent (check API keys): {e}")
        sys.exit(1)

    csv_path     = config.get("input_csv", "TEMP.csv")
    artifact_root = config.get("artifact_root", "ARTIFACT")
    output_csv   = config.get("output_csv", "outputs/final_results.csv")

    if not Path(csv_path).exists():
        error_logger.error(f"CSV missing at {csv_path}")
        sys.exit(1)

    findings = read_csv(csv_path)
    total = len(findings)
    print(f"   Findings: {total} loaded from {csv_path}")
    print("═" * 65 + "\n")
    system_logger.info(f"Loaded {total} findings from {csv_path}")

    repo_understanding_cache: dict = {}
    all_results: list = []

    for idx, row in enumerate(findings, start=1):
        artifact_id = row.get("artifact_id", "")
        uid = f"{row.get('finding_id', 'unknown')}_{artifact_id}"
        print(f"⏳  [{idx}/{total}] Processing: {uid}")
        system_logger.info(f"Processing finding: {uid}")

        # Resolve artifact path
        repo_path = resolve_artifact_path(artifact_id, artifact_root)
        if not repo_path:
            error_logger.error(f"Skipping {uid} due to missing artifact path")
            print(f"   ⚠️  Skipped — artifact path not resolved for: {artifact_id}\n")
            continue

        # Stage 1: Repo Understanding (cached per artifact)
        if artifact_id not in repo_understanding_cache:
            print(f"   🔍  Building Repository Understanding for {artifact_id}...")
            system_logger.info(f"Building Repository Understanding for {artifact_id}...")
            repo_understanding = agent.build_repo_understanding(repo_path, artifact_id)
            repo_understanding_cache[artifact_id] = repo_understanding
            system_logger.info(f"Cached Repo Understanding for {artifact_id}")
        else:
            repo_understanding = repo_understanding_cache[artifact_id]

        # Stage 2: Finding Analysis
        print(f"   🔬  Analyzing vulnerability in context...")
        system_logger.info(f"Analyzing finding context...")
        result = agent.analyze_finding(
            row, repo_path, repo_understanding,
            max_retries=config.get("max_retries", 3)
        )

        if result:
            save_finding_json(uid, result)
            system_logger.info(f"Saved output for {uid}")

            # Build a flat row to write into CSV
            fc = cost_tracker.get_finding_cost(uid)
            csv_row = {
                "finding_uid":                    uid,
                "artifact_id":                    artifact_id,
                "tool":                           row.get("tool", ""),
                "finding_id":                     row.get("finding_id", ""),
                "severity_raw":                   row.get("severity_raw", ""),
                "file":                           row.get("file", ""),
                "line":                           row.get("line", ""),
                "package":                        row.get("package", ""),
                "version":                        row.get("version", ""),
                "security_label":                 result.get("security_label", ""),
                "code_purpose":                   result.get("code_purpose", ""),
                "execution_context":              result.get("execution_context", ""),
                "required_conditions_for_exploit":result.get("required_conditions_for_exploit", ""),
                "input_controlled_by_attacker":   result.get("input_controlled_by_attacker", ""),
                "reachable_in_artifact_execution":result.get("reachable_in_artifact_execution", ""),
                "evidence_snippet":               result.get("evidence_snippet", ""),
                "reasoning":                      result.get("reasoning", ""),
                "recommendation":                 result.get("recommendation", ""),
                "finding_cost_usd":               round(fc.get("total_cost_usd", 0.0), 6),
                "finding_prompt_tokens":          fc.get("total_prompt_tokens", 0),
                "finding_completion_tokens":      fc.get("total_completion_tokens", 0),
            }
            all_results.append(csv_row)
        else:
            system_logger.warning(f"Failed to get valid output for {uid}")
            print(f"   ❌  Analysis failed for {uid}")

        # Live cost banner after every finding
        _print_cost_banner(uid, idx, total, model_string)

    # Write consolidated CSV
    save_final_csv(all_results, output_csv)

    gc = cost_tracker.get_global_totals()
    print("═" * 65)
    print("   RUN COMPLETE")
    print(f"   Total findings processed : {len(all_results)}/{total}")
    print(f"   Grand total cost (USD)   : ${gc.get('total_cost_usd', 0.0):.6f}")
    print(f"   Grand total tokens       : {gc.get('total_prompt_tokens', 0) + gc.get('total_completion_tokens', 0):,}")
    print(f"   Output CSV               : {output_csv}")
    print("═" * 65 + "\n")
    system_logger.info("Auditor run complete.")


if __name__ == "__main__":
    main()
