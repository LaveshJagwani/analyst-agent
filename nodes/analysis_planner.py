"""
Node 4: Analysis Planner
LLM node (structured output) — generates a step-by-step analysis plan.
"""

import json
from state import AnalysisState
from config import get_llm, wait_for_quota
from logger import trace, log


PLANNER_PROMPT = """\
You are a senior data analyst. Create a detailed analysis plan for the dataset below.

Business Context: {business_context}
Columns: {columns}
Numeric columns: {numeric_cols}
Categorical columns: {cat_cols}
Date columns: {date_cols}
Row count: {row_count}
{goal_section}
{kpi_section}

Generate 4–7 analysis steps. Each step should be actionable and produce a concrete
quantitative result or chart. Order from foundational (overview) to advanced (deep dives).

Return ONLY a JSON object:
{{
  "steps": [
    {{
      "id": 1,
      "title": "...",
      "objective": "...",
      "method": "describe the pandas/matplotlib code approach"
    }}
  ]
}}
"""


def analysis_planner_node(state: AnalysisState) -> dict:
    """Generate a structured analysis plan aligned with business goals."""
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
        kpi_section = f"Key KPIs to focus on: {', '.join(metadata['important_kpis'])}"

    prompt = PLANNER_PROMPT.format(
        business_context=business_context,
        columns=list(schema.get("columns", {}).keys()),
        numeric_cols=schema.get("numeric_columns", []),
        cat_cols=schema.get("categorical_columns", []),
        date_cols=schema.get("date_columns", []),
        row_count=summary.get("row_count", "unknown"),
        goal_section=goal_section,
        kpi_section=kpi_section,
    )

    wait_for_quota()
    llm = get_llm(temperature=0.2)
    response = llm.invoke(prompt)
    
    content = response.content
    if isinstance(content, list):
        # Handle list content (common with Gemini)
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

    # Extract JSON
    if "```" in content:
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    try:
        plan = json.loads(content)
        steps = plan.get("steps", [])
    except json.JSONDecodeError:
        log.error("Failed to parse analysis plan JSON. Using fallback plan.")
        steps = [
            {"id": 1, "title": "Dataset Overview", "objective": "Summarize key statistics", "method": "df.describe()"},
            {"id": 2, "title": "Distribution Analysis", "objective": "Examine numeric distributions", "method": "histograms of numeric columns"},
            {"id": 3, "title": "Correlation Analysis", "objective": "Find relationships", "method": "correlation matrix heatmap"},
        ]

    log.info("Analysis plan: %d steps", len(steps))
    trace.record("analysis_planner", "plan_generated", steps)

    return {
        "analysis_plan": steps,
        "current_step_index": 0,
        "execution_results": {},
        "generated_charts": [],
    }
