import enum
from typing import List
from pydantic import BaseModel, Field

class SecurityLabel(str, enum.Enum):
    TRUE_SECURITY_RISK = "TRUE_SECURITY_RISK"
    CONTEXTUAL_RISK = "CONTEXTUAL_RISK"
    HARDENING_RECOMMENDATION = "HARDENING_RECOMMENDATION"
    BENIGN_RESEARCH_USAGE = "BENIGN_RESEARCH_USAGE"
    FALSE_POSITIVE = "FALSE_POSITIVE"

class RepoUnderstanding(BaseModel):
    project_type: str = Field(description="training pipeline / CLI tool / web service / demo / library")
    entrypoints: List[str] = Field(description="List of detected entrypoint files")
    execution_mode: str = Field(description="local / server / batch")
    external_exposure: str = Field(description="yes/no")
    input_sources: List[str] = Field(description="List of identified input sources (e.g. sys.argv, argparse)")
    trust_boundary: str = Field(description="user-controlled, researcher-controlled, external input, etc.")
    repo_summary: str = Field(description="project purpose and usage instructions")

class AnalysisResult(BaseModel):
    security_label: SecurityLabel = Field(
        description="Must be one of: TRUE_SECURITY_RISK, CONTEXTUAL_RISK, HARDENING_RECOMMENDATION, BENIGN_RESEARCH_USAGE, FALSE_POSITIVE"
    )
    code_purpose: str = Field(description="what this code is doing")
    execution_context: str = Field(description="how/where this code runs in the artifact")
    required_conditions_for_exploit: str = Field(description="conditions needed for exploitation")
    input_controlled_by_attacker: str = Field(description="yes/no/uncertain + brief justification")
    reachable_in_artifact_execution: str = Field(description="yes/no/uncertain + brief justification")
    evidence_snippet: str = Field(description="exact relevant code lines or summary")
    reasoning: str = Field(description="step-by-step explanation grounded in evidence")
    recommendation: str = Field(description="practical fix or mitigation if needed")
