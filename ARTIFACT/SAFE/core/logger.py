import logging
import os
import json
from pathlib import Path

# Setup base logging format
LOG_FORMAT = "%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"

def setup_global_loggers():
    """Sets up the top-level system and error logs."""
    os.makedirs("outputs/logs", exist_ok=True)
    
    # System logger
    sys_logger = logging.getLogger("system")
    sys_logger.setLevel(logging.INFO)
    sys_handler = logging.FileHandler("outputs/logs/system.log")
    sys_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    sys_logger.addHandler(sys_handler)
    
    # Console handler for system logger
    sys_console = logging.StreamHandler()
    sys_console.setFormatter(logging.Formatter(LOG_FORMAT))
    sys_console.setLevel(logging.INFO)
    sys_logger.addHandler(sys_console)

    # Error logger
    err_logger = logging.getLogger("error")
    err_logger.setLevel(logging.ERROR)
    err_handler = logging.FileHandler("outputs/logs/error.log")
    err_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    err_logger.addHandler(err_handler)
    err_logger.addHandler(sys_console)  # also print to console

    return sys_logger, err_logger

def setup_finding_logger(finding_uid: str):
    """Sets up a specific logger for a finding and returns it."""
    os.makedirs("outputs/logs", exist_ok=True)
    finding_logger = logging.getLogger(f"finding_{finding_uid}")
    finding_logger.setLevel(logging.DEBUG)
    
    # Avoid duplicate handlers if called multiple times
    if finding_logger.hasHandlers():
        finding_logger.handlers.clear()
        
    handler = logging.FileHandler(f"outputs/logs/{finding_uid}.log")
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    finding_logger.addHandler(handler)
    
    return finding_logger

def save_finding_json(finding_uid: str, data: dict):
    """Saves the final analysis output for a finding."""
    os.makedirs("outputs/logs", exist_ok=True)
    with open(f"outputs/logs/{finding_uid}.json", "w") as f:
        json.dump(data, f, indent=2)

def save_guardrail_log(finding_uid: str, guardrail_log: dict):
    """
    Saves the structured guardrail decision record for a finding.
    Stored alongside the finding JSON as <finding_uid>_guardrail.json.
    Fields: flag_present, attacker_control, reachability, impact,
            evidence_complete, raw_model_label, final_label_after_guardrails, downgrade_reason.
    """
    os.makedirs("outputs/logs", exist_ok=True)
    with open(f"outputs/logs/{finding_uid}_guardrail.json", "w") as f:
        json.dump(guardrail_log, f, indent=2)

system_logger, error_logger = setup_global_loggers()
