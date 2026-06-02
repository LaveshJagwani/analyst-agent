"""
Node 4: Analysis Planner (Exploratory Inception)
LLM node (structured output) — generates a high-fidelity initial exploratory plan.
Creates foundational profiling steps to seed the dynamic signal engine.
"""

import json
from state import AnalysisState
from config import get_llm, wait_for_quota
from logger import trace, log


PLANNER_PROMPT = """\
You are a principal data analyst. Your task is to design an Initial Exploratory Analysis Plan for a new dataset.
This initial plan must focus on discovering baseline insights, column distributions, correlations, and general metrics. 
This baseline will be scanned by our statistical engine to find anomalies, spikes, and high-value correlations for subsequent deep dives.

Business Context: {business_context}
Columns: {columns}
Numeric columns: {numeric_cols}
Categorical columns: {cat_cols}
Date columns: {date_cols}
Row count: {row_count}

{goal_section}
{kpi_section}
{playbook_section}

Generate EXACTLY 3 foundational exploratory steps:
1. Foundational Data Profiling & High-Level Statistics (objective: capture general statistical summaries of numeric/categorical columns).
2. Key Correlation & Distribution Mining (objective: generate correlation matrices and check key target distributions to identify raw data patterns/segments).
3. Primary Business KPI Baseline Trends (objective: aggregate and plot key KPIs mapped to the primary business goal over time or across top categories).

Return ONLY a JSON object in this format (no extra keys, no explanations):
{{
  "steps": [
    {{
      "id": 1,
      "title": "Foundational Profiling & Overview",
      "objective": "...",
      "method": "..."
    }},
    {{
      "id": 2,
      "title": "Correlation & Distribution Matrix",
      "objective": "...",
      "method": "..."
    }},
    {{
      "id": 3,
      "title": "Business KPI Trend Baseline",
      "objective": "...",
      "method": "..."
    }}
  ]
}}
"""


def analysis_planner_node(state: AnalysisState) -> dict:
    """Generate a structured exploratory analysis plan to initialize data profiling."""
    trace.record("analysis_planner", "start")

    schema = state.get("schema", {})
    summary = state.get("dataframe_summary", {})
    metadata = state.get("parsed_metadata") or {}
    business_context = state.get("business_context", "Generic")

    goal_section = ""
    if metadata.get("primary_goal"):
        goal_section = f"Primary business goal: {metadata['primary_goal']}"

    kpi_section = ""
    if metadata.get("important_kpis"):
        kpi_section = f"Key KPIs of interest: {', '.join(metadata['important_kpis'])}"

    playbook_section = ""
    if metadata.get("playbook_rules"):
        playbook_section = "Persistent Business Rules / Guidelines:\n- " + "\n- ".join(metadata["playbook_rules"])

    prompt = PLANNER_PROMPT.format(
        business_context=business_context,
        columns=list(schema.get("columns", {}).keys()),
        numeric_cols=schema.get("numeric_columns", []),
        cat_cols=schema.get("categorical_columns", []),
        date_cols=schema.get("date_columns", []),
        row_count=summary.get("row_count", "unknown"),
        goal_section=goal_section,
        kpi_section=kpi_section,
        playbook_section=playbook_section
    )

    wait_for_quota()
    llm = get_llm(temperature=0.1)
    response = llm.invoke(prompt)
    
    content = response.content
    if isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, str):
                text_parts.append(part)
            elif isinstance(part, dict) and "text" in part:
                text_parts.append(part["text"])
        content = "".join(text_parts)
    
    if not isinstance(content, str):
        content = str(content)
        
    content = content.strip()

    if "```" in content:
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    try:
        plan = json.loads(content)
        steps = plan.get("steps", [])
        if len(steps) != 3:
            raise ValueError("Expected exactly 3 steps.")
    except Exception as exc:
        log.error("Failed to parse initial exploratory plan JSON. Using robust fallback. Error: %s", exc)
        steps = [
            {
                "id": 1,
                "title": "Foundational Profiling & Overview",
                "objective": "Summarize statistical distributions of all columns",
                "method": "Use df.describe(include='all') to capture high-level overview metrics."
            },
            {
                "id": 2,
                "title": "Correlation & Distribution Matrix",
                "objective": "Examine correlation matrix and key feature histograms",
                "method": "Compute df.corr(numeric_only=True) and select top highly-correlated variables."
            },
            {
                "id": 3,
                "title": "Business KPI Trend Baseline",
                "objective": "Plot target column variations across categories or time",
                "method": "Group target columns by key categories and plot a clean bar/line chart."
            }
        ]

    log.info("Initial exploratory plan generated: %d steps", len(steps))
    trace.record("analysis_planner", "plan_generated", steps)

    return {
        "analysis_plan": steps,
        "active_signals": [],
        "history_steps": [],
        "max_steps_budget": 5,  # Maximum deep dives budget
        "current_step_index": 0,
        "execution_results": {},
        "generated_charts": [],
    }
