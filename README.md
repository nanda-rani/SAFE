# SAFE (Security-Aware Framework for Artifact Evaluation)

SAFE is a system for contextual security auditing of research artifacts. It takes outputs from static analysis tools (e.g., Semgrep, Trivy) and uses a repository-aware LLM agent to determine whether a finding is truly exploitable in real-world usage.

The system uses a ReAct-style agent powered by LangGraph, equipped with filesystem tools to inspect code, trace dependencies, and reason about execution context.

---

## Repository Structure
```bash
SAFE/
│── main.py                       # Entry point
│── config.yaml                   # Configuration file
│── requirements.txt              # Dependencies
│── SAFE_TOOL_OUTPUT.csv          # Tool (Semgrep and Trivy) output for SAFE (its own codebase)
│
├── core/                         # Core reasoning & pipeline logic
│   ├── auditor.py                # Main auditing pipeline
│   ├── validator.py              # Validation logic
│   ├── schemas.py                # Data schemas
│   └── logger.py                 # Logging utilities
│
├── tools/                        # Static & structural analysis tools
│   ├── repo_parser.py            # Repository structure parsing
│   ├── ast_parser.py             # Code-level AST analysis
│   ├── dependency_analyzer.py    # Analyzes dependencies between modules and files
│   ├── file_reader.py            # Handles file loading and content extraction
│   ├── code_search.py.           # Enables keyword and pattern-based code search
│   └── artifact_resolver.py.     # Resolves artifacts and links related components
│
├── llm/                          # LLM interaction layer
│   ├── provider.py               # LLM abstraction
│   └── cost_tracker.py           # Token & cost tracking
│
├── outputs/                      # Generated outputs from SAFE runs
│   ├── final_results.csv         # Final classified findings/results
│   ├── costs/                    # Cost tracking outputs
│   │   └── *.json                # Token usage and cost logs
│   └── logs/                     # Execution logs (generated per run)
│       └── *.log                 # Detailed execution traces
├── ARTIFACT
│   └── SAFE/                     # Self-contained sample artifact used for testing SAFE on its own codebase
```

---

## Setup Instructions

1. Setup Repository
   ```bash
   git clone https://github.com/nanda-rani/SAFE.git
   cd SAFE
   ```

2. **Install Virtual Environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure API Keys**
   You must export the relevant API key for the model you intend to use.
   ```bash
   export OPENAI_API_KEY="sk-..."
   ```

3. **Data Placement**
   - Modify `config.yaml` the CSV file containing findings/flags (`SAFE_TOOL_OUTPUT.csv` for demo) obtained from static analysis tool. `SAFE_TOOL_OUTPUT.csv` is the colelction of flags obtained using static analysis tools (Semgrep and Trivy).
   - Place your analyzed repositories in the `ARTIFACT/` folder. The structure should map `artifact_id` to directories (e.g. `ARTIFACT/<artifact_id>/`). `ARTIFACT` Folder contains SAFE codebase copied in side the folder.

4. **Configuration Settings**
   Edit `config.yaml` to select model string, paths, and maximum retry counts for schema validation.

5. **Run** the auditor after completing setup
   ```bash
   python main.py
   ```
6. **Check logs and outputs**
   ```bash
   cat outputs/logs/system.log
   cat outputs/logs/<finding_uid>.json
   cat outputs/logs/repo_<artifact_id>.log
   ```
---

## Quick Start: Run SAFE on Its Own Codebase

This repository already includes a ready-to-run demo setup so you can test SAFE without preparing any external data.

### Pre-configured setup:
- `SAFE_TOOL_OUTPUT.csv` → Findings generated from SAFE’s own codebase (via Semgrep + Trivy)
- `ARTIFACT/SAFE/` → A copy of the SAFE repository used as the target artifact

### Mapping:
```
artifact_id (CSV) = SAFE
→ ARTIFACT/SAFE/
```

### Run:

```bash
python main.py
```

---

## Run SAFE on Your Own Artifact

### Step 1: Prepare Artifact

```bash
ARTIFACT/
└── my_project/
```

### Step 2: Generate Findings

#### Option A: Semgrep

```bash
semgrep scan --config auto --json > semgrep.json
```

#### Option B: Trivy

```bash
trivy fs --format json --output trivy.json .
```

### Convert Outputs to SAFE CSV

Example Entry:

artifact_id,tool,finding_id,category,severity_raw,file,line,message,package,version,cwe,cvss,scanner_applicable
my_project,semgrep,python.lang.security.eval,code,HIGH,app.py,10,Use of eval,,,"CWE-95",,true

### Step 3: Configure SAFE

Edit config.yaml:

input_csv: my_project_findings.csv  
artifact_root: ARTIFACT/

### Step 4: Run

```bash
python main.py
```

### Step 5: Outputs

- outputs/final_results.csv  
- outputs/logs/  
- outputs/costs/  


## Core Mapping Rule

artifact_id → ARTIFACT/<artifact_id>/

---

## How Analysis Works

1. **Initialization:** The script reads findings from `SAFE_TOOL_OUTPUT.csv`.
2. **Artifact Resolution:** For each row, the script resolves the `artifact_id` against the `ARTIFACT/` root to pinpoint the local Git repository matching the finding.
3. **Agent Delegation:** The specific finding metadata (file, message, priority, line code) is passed to the LangGraph ReAct agent.
4. **Tool Use:** The Agent dynamically executes local python functions exposed to it (`get_repo_tree`, `read_snippet`, `search_package_usage`, etc.) inspecting the filesystem for evidence.
5. **JSON Emittance:** The Agent concludes its analysis loop by emitting a final strict JSON evaluation mapping the artifact into standard Taxonomy boundaries (e.g. `CONTEXTUAL_RISK` vs `FALSE_POSITIVE`).
6. **Validation:** Pydantic logic strictly enforces that the final payload complies. If not, the LangGraph loop repeats requesting the LLM to fix formatting.

## Logging and Cost Tracking

All outputs from the framework are routed into the `outputs/` directory dynamically creating logs and saving costs at both the global and finding level dynamically using concurrent file locks.

- **`outputs/logs/system.log`**: Standard operational log encompassing tool run initialization, finding traversal, schema retries, etc.
- **`outputs/logs/error.log`**: Isolates stack-traces and validation aborts.
- **`outputs/logs/<finding_uid>.log`**: Highly detailed debug log tracing the exact LangGraph inputs, raw node chains, precise tool parameters, and tool return data generated specifically for a singular finding.
- **`outputs/logs/<finding_uid>.json`**: The final valid structured Pydantic payload returned upon successfully analyzing a finding.
- **`outputs/costs/global_costs.json`**: An appending aggregator showing combined total dollars dynamically calculated per the requested LLM.
- **`outputs/costs/<finding_uid>_cost.json`**: The isolated calculated USD dollar cost strictly applied measuring the prompt/completion token usage to investigate the singular finding.


## Troubleshooting

- **Missing Artifact**: If the log states "Skipping due to missing artifact path", ensure the ID column in your CSV correlates locally to a folder exactly inside `ARTIFACT/`.
- **API Timeout/Limits**: Switch model down (e.g., to `gpt-4o-mini`) via `config.yaml` if you are hitting aggressive tier limits on concurrent tools querying models.
- **Missing API keys**: Running the system fails out immediately. Set your standard keys via `export` before invoking.
