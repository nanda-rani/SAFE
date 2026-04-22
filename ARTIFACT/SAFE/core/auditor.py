import json
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.prebuilt import create_react_agent
from typing import Dict, Any

from tools.repo_parser import get_repo_tree, find_important_files
from tools.file_reader import read_file, read_snippet
from tools.code_search import search_repo
from tools.dependency_analyzer import extract_dependency_files, detect_entrypoints, search_package_usage
from tools.ast_parser import extract_enclosing_function

from llm.provider import get_llm
from llm.cost_tracker import cost_tracker
from core.logger import setup_finding_logger, system_logger, save_guardrail_log
from core.validator import validate_and_parse_output
from core.schemas import AnalysisResult, RepoUnderstanding
# from core.guardrails import apply_guardrails

# Core tools used for detailed finding analysis
ANALYSIS_TOOLS = [
    get_repo_tree,
    find_important_files,
    read_file,
    read_snippet,
    search_repo,
    extract_dependency_files,
    detect_entrypoints,
    search_package_usage,
    extract_enclosing_function
]

# Tools for repo understanding (limited scope to prevent hyper-focus on specific lines)
UNDERSTANDING_TOOLS = [
    get_repo_tree,
    find_important_files,
    read_file,
    extract_dependency_files,
    detect_entrypoints
]

REPO_UNDERSTANDING_PROMPT = """You are a Contextual Security Auditor tasked with understanding a repository BEFORE performing finding analysis.

Target Repository path: {repo_path}

MANDATORY EXECUTION ORDER — follow exactly:
Step 1 [REQUIRED FIRST]: Call get_repo_tree(repo_path='{repo_path}') before anything else.
         This gives you the verified directory layout you MUST use for all subsequent steps.
Step 2: Call find_important_files(repo_path='{repo_path}') to obtain ABSOLUTE paths to README, requirements, etc.
Step 3: Call read_file() on the absolute paths returned above (do NOT invent paths).
Step 4: Call detect_entrypoints(repo_path='{repo_path}') to get ABSOLUTE entrypoint paths.
Step 5: Call extract_dependency_files(repo_path='{repo_path}') for dependency context.

PATH RULES (CRITICAL):
- All tools return ABSOLUTE paths — always use those exact strings when calling read_file or read_snippet.
- NEVER construct or guess paths. Only use paths that tools have explicitly returned.
- If a file cannot be opened, note it as inaccessible — do NOT assume it doesn't exist.

OUTPUT: Your final output MUST be exactly this JSON, NOT wrapped in ```json blocks:
{{
  "project_type": "...",
  "entrypoints": ["..."],
  "execution_mode": "...",
  "external_exposure": "...",
  "input_sources": ["..."],
  "trust_boundary": "...",
  "repo_summary": "..."
}}
"""

ANALYSIS_PROMPT = """You are a meticulous Contextual Security Auditor specialising in research artifact analysis.
Your goal is to investigate a security finding using ONLY code and repository evidence — no assumptions, no hallucinations.

═══════════════════════════════════════════════════════════
DEFAULT REPOSITORY ASSUMPTION (apply unless evidence contradicts)
═══════════════════════════════════════════════════════════
• This repository is a RESEARCH ARTIFACT run locally by a researcher.
• All datasets, configs, and scripts are researcher-managed unless evidence shows otherwise.
• Do NOT assume internet-facing deployment, public API exposure, or attacker-controlled inputs
  unless the code or README explicitly supports this.

═══════════════════════════════════════════════════════════
REPOSITORY CONTEXT (pre-built whole-repo understanding)
═══════════════════════════════════════════════════════════
{repo_understanding}

═══════════════════════════════════════════════════════════
FINDING DETAILS
═══════════════════════════════════════════════════════════
Tool      : {tool}
Finding ID: {finding_id}
Severity  : {severity}
Message   : {message}
File      : {file}
Line      : {line}
Package   : {package}  Version: {version}
Repo path : {repo_path}

═══════════════════════════════════════════════════════════
PATH PASSING RULES (CRITICAL)
═══════════════════════════════════════════════════════════
The 'File' field is the relative path as it appears in the CSV: '{file}'
The repo root is: '{repo_path}'

DO NOT manually concatenate them. Pass path and repo_path SEPARATELY:
  read_snippet(path='{file}', repo_path='{repo_path}', line_number={line})
  extract_enclosing_function(path='{file}', line_number={line}, repo_path='{repo_path}')
  read_file(path='{file}', repo_path='{repo_path}')
The tools normalise and validate the path internally.

═══════════════════════════════════════════════════════════
MANDATORY ANALYSIS SEQUENCE
═══════════════════════════════════════════════════════════
Step 1 [FIRST]: get_repo_tree(repo_path='{repo_path}') — confirm the verified file layout.
Step 2: read_snippet(path='{file}', repo_path='{repo_path}', line_number={line}, context_window=50)
Step 3: extract_enclosing_function(path='{file}', line_number={line}, repo_path='{repo_path}')
Step 4: search_repo(repo_path='{repo_path}', query=<function_name_from_step3>) — find all callers.
Step 5: Trace callers: are any reachable from the entrypoints in the Repository Context?
Step 6 (Trivy only): search_package_usage(repo_path='{repo_path}', package_name='{package}')
Step 7: For any caller found, trace where its inputs originate. Is that input attacker-controlled?

═══════════════════════════════════════════════════════════
EVIDENCE-BASED REASONING CHECKLIST
(answer each internally before producing the JSON)
═══════════════════════════════════════════════════════════
① What exact code pattern or dependency was flagged?
② Is the flagged behaviour actually present in the code read by your tools?
③ What is this code doing in the context of the repository?
④ Is this code reachable from the observed entrypoints during realistic execution?
⑤ Where does the relevant input originate?
⑥ Is that input attacker-controlled, researcher-controlled, internal, or unknown?
⑦ What realistic security impact would follow in this research-artifact context?
⑧ Is your conclusion based on observed evidence, or on assumption?

If any required information is missing or cannot be verified from tool outputs:
• Do NOT assume exploitability
• Do NOT assume attacker control
• Do NOT infer execution paths

Instead:
• Explicitly state what is unknown
• Base the final classification only on confirmed evidence
• Prefer conservative conclusions when evidence is incomplete

═══════════════════════════════════════════════════════════
ANTI-HALLUCINATION RULES (STRICTLY ENFORCED)
═══════════════════════════════════════════════════════════
• Do NOT invent files, APIs, inputs, or execution flows not seen in tool outputs.
• Do NOT assume a web server, public endpoint, or attacker exists unless the repo shows it.
• Do NOT confuse "this primitive is dangerous" with "this is actually exploitable here".
• Base every claim in reasoning on a specific tool output, file, or line of code observed.


═══════════════════════════════════════════════════════════
CLASSIFICATION RULES
═══════════════════════════════════════════════════════════
CONTEXTUAL_RISK         → Vulnerability plausible but attacker control, reachability,
                          or exploitation conditions are uncertain or unconfirmed.
HARDENING_RECOMMENDATION → Risky practice present but realistic exploitability is low
                          in this research-artifact context.
BENIGN_RESEARCH_USAGE   → Code is intentionally demonstrating or studying a risk.
FALSE_POSITIVE          → ONLY if the flagged condition is provably absent in the actual code.


═══════════════════════════════════════════════════════════
FINAL OUTPUT
═══════════════════════════════════════════════════════════
Output ONLY the JSON object — no markdown, no preamble, no trailing text:
{{
  "security_label": "<CONTEXTUAL_RISK|HARDENING_RECOMMENDATION|BENIGN_RESEARCH_USAGE|FALSE_POSITIVE>",
  "code_purpose": "...",
  "execution_context": "...",
  "required_conditions_for_exploit": "...",
  "input_controlled_by_attacker": "yes/no/uncertain + justification grounded in observed code",
  "reachable_in_artifact_execution": "yes/no/uncertain + justification grounded in observed code",
  "evidence_snippet": "exact lines from read_snippet output or EVIDENCE_MISSING message",
  "reasoning": "step-by-step answer to the 8-point checklist, citing specific evidence",
  "recommendation": "practical fix or mitigation, or 'N/A' if no action required"
}}
"""

class SecurityAuditorAgent:
    def __init__(self, model_string: str):
        self.model_string = model_string
        self.llm = get_llm(model_string)
        self.repo_agent = create_react_agent(self.llm, UNDERSTANDING_TOOLS)
        self.analysis_agent = create_react_agent(self.llm, ANALYSIS_TOOLS)

    def _invoke_and_track(self, agent, messages: list, logger, finding_uid: str) -> str:
        for event in agent.stream({"messages": messages}):
            for key, value in event.items():
                if key == "agent":
                    for msg in value.get("messages", []):
                        if getattr(msg, "tool_calls", None):
                            for t in msg.tool_calls:
                                logger.debug(f"[Agent] Called tool: {t['name']} with args: {t['args']}")
                elif key == "tools":
                    for msg in value.get("messages", []):
                        logger.debug(f"[Tool] Result ({msg.name}): {str(msg.content)[:200]}...")
                        
        result_state = agent.invoke({"messages": messages})
        
        if hasattr(result_state["messages"][-1], "response_metadata"):
            usage = result_state["messages"][-1].response_metadata.get("token_usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            comp_tokens = usage.get("completion_tokens", 0)
            if prompt_tokens or comp_tokens:
                cost_tracker.record_call(finding_uid, self.model_string, prompt_tokens, comp_tokens)

        return result_state["messages"][-1].content

    def build_repo_understanding(self, repo_path: str, artifact_id: str) -> Dict[str, Any]:
        """
        Builds the whole repository understanding context.
        """
        logger = setup_finding_logger(f"repo_{artifact_id}")
        logger.info(f"Starting Whole Repository Understanding for: {repo_path}")
        
        sys_msg = SystemMessage(content=REPO_UNDERSTANDING_PROMPT.format(repo_path=repo_path))
        messages = [
            sys_msg,
            HumanMessage(content="Please build the repository understanding and output the structured JSON.")
        ]
        
        max_retries = 3
        for attempt in range(max_retries):
            raw_output = self._invoke_and_track(self.repo_agent, messages, logger, f"repo_{artifact_id}")
            logger.debug(f"Raw Output: {raw_output}")
            
            # Simple manual JSON extraction/validation against RepoUnderstanding 
            try:
                cleaned = raw_output.strip()
                if cleaned.startswith("```json"): cleaned = cleaned[7:]
                if cleaned.startswith("```"): cleaned = cleaned[3:]
                if cleaned.endswith("```"): cleaned = cleaned[:-3]
                
                data = json.loads(cleaned.strip())
                validated = RepoUnderstanding(**data)
                logger.info("Successfully built RepoUnderstanding.")
                return validated.model_dump()
            except Exception as e:
                logger.warning(f"Failed to parse RepoUnderstanding JSON: {e}")
                messages.append(HumanMessage(content=f"Your JSON was invalid: {e}. Fix and output pure JSON only."))
                
        logger.error("Failed to build repo understanding after retries.")
        # Return fallback generic baseline if failed deeply
        return {
            "project_type": "unknown", "entrypoints": [], "execution_mode": "unknown",
            "external_exposure": "unknown", "input_sources": [], "trust_boundary": "unknown",
            "repo_summary": "Parsing failed."
        }

    def analyze_finding(self, finding_row: Dict[str, str], repo_path: str, repo_understanding: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
        """
        Runs the ReAct loop for a specific finding combining the repo understanding.
        After LLM validation, applies hard guardrail rules deterministically.
        """
        finding_uid = finding_row.get("finding_id", "unknown_finding") + "_" + finding_row.get("artifact_id", "unknown_artifact")
        f_logger = setup_finding_logger(finding_uid)
        
        f_logger.info(f"Starting analysis for finding {finding_uid} on repo {repo_path}")
        
        repo_json_str = json.dumps(repo_understanding, indent=2)
        sys_msg = SystemMessage(content=ANALYSIS_PROMPT.format(
            repo_understanding=repo_json_str,
            tool=finding_row.get('tool', ''),
            finding_id=finding_row.get('finding_id', ''),
            severity=finding_row.get('severity_raw', ''),
            message=finding_row.get('message', ''),
            file=finding_row.get('file', ''),
            line=finding_row.get('line', ''),
            package=finding_row.get('package', ''),
            version=finding_row.get('version', ''),
            repo_path=repo_path
        ))
        
        messages = [
            sys_msg,
            HumanMessage(content="Follow the ANALYSIS SEQUENCE stringently, use your tools to perform the deep trace, and finally output purely JSON matching the schema.")
        ]
        
        for attempt in range(max_retries):
            f_logger.info(f"Attempt {attempt + 1}/{max_retries} to get a valid JSON response.")
            try:
                final_message = self._invoke_and_track(self.analysis_agent, messages, f_logger, finding_uid)
            except Exception as e:
                f_logger.error(f"Agent execution failed: {str(e)}")
                return {}

            f_logger.debug(f"Raw Final Output: {final_message}")
            
            # Step 1: Schema validation
            is_valid, parsed, err = validate_and_parse_output(final_message)
            if not is_valid:
                f_logger.warning(f"Validation failed: {err}")
                messages.append(HumanMessage(content=f"Your JSON output was invalid. Fix the errors and output JSON only. Errors: {err}"))
                continue

            # Step 2: Guardrail enforcement (deterministic post-processing)
            # corrected, guardrail_log = apply_guardrails(parsed, finding_uid, f_logger)
            # save_guardrail_log(finding_uid, guardrail_log)
            
            # f_logger.info(
            #     f"[Guardrail Result] raw='{guardrail_log['raw_model_label']}' "
            #     f"→ final='{guardrail_log['final_label_after_guardrails']}' "
            #     f"(attacker_control={guardrail_log['attacker_control']}, "
            #     f"reachability={guardrail_log['reachability']}, "
            #     f"evidence_complete={guardrail_log['evidence_complete']})"
            # )
            return parsed
            
        f_logger.error("Max retries exceeded without valid JSON output.")
        return {}
