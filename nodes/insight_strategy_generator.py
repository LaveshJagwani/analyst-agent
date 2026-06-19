"""
Node 6: Combined Insight & Strategy Generator
LLM node — parses code execution results to extract validated business insights
and formulate strategic recommendations in a single LLM call.
"""

import json
from state import AnalysisState
from config import get_llm, wait_for_quota, MIN_SAMPLE_SIZE
from logger import trace, log


INSIGHT_STRATEGY_PROMPT = """\
You are an Elite Data Analyst and Strategic Business Advisor (ex-McKinsey/BCG Director).
Your goal is to analyze the execution outputs from a completed data analysis pipeline, synthesize the findings into high-impact business insights, and formulate actionable recommendations.

---
### Business Context & Goals:
- Domain/Context: {business_context}
- Target Industry: {industry}
- Company Stage & Business Model: {stage} | {business_model}
- Primary Business Goal: {primary_goal}
- Focus KPIs: {kpis}

---
### Dataset Profile & Stats:
- Columns: {columns}
- Row count: {row_count}

---
### Analysis Sandbox Outputs:
{results_text}

---
### INSTRUCTIONS:

1. **VALIDATED INSIGHTS**:
   - Extract the top 4-6 most critical business insights.
   - Do not make generic observations (e.g. "churn went up"). Be specific and use precise numbers.
   - Every insight must pass the "So What?" test: how does it help improve revenue, reduce cost, or mitigate risk?
   - Link each insight to the step/chart that supports it.

2. **STRATEGIC RECOMMENDATIONS**:
   - Formulate 3-4 high-impact actionable business recommendations.
   - Adapt your tone and focus to the company stage:
     - Seed/Early -> focus on experimentation, quick wins, learning.
     - Growth -> focus on scaling, optimization, operational efficiency.
     - Mature -> focus on retention, diversification, risk mitigation.
   - Quantify expected impact, note critical risks/mitigations, and give a concrete next step.

Return ONLY a JSON object with these two fields (no markdown wrappers, no explanations):
{{
  "validated_insights": [
    {{
      "title": "Actionable Headline (e.g., 'Retention drop in Q3 requires targeted email campaign')",
      "description": "2-3 concise sentences explaining the finding and its strategic implications.",
      "metric_value": "Key Stat (e.g., '12.4% Churn vs 3.2% Average')",
      "confidence": "high" | "medium" | "low",
      "supporting_data": "Reference to specific step/chart"
    }}
  ],
  "recommendations": [
    {{
      "action": "Concrete recommended action",
      "rationale": "Why we should do this (tied to insights data)",
      "expected_impact": "Quantified projection of ROI/revenue/retention improvement",
      "risk": "What could go wrong & how to mitigate it",
      "suggested_next_step": "First concrete immediate step to take (1-10 days)"
    }}
  ]
}}
"""


def insight_strategy_generator_node(state: AnalysisState) -> dict:
    """Validate execution results, generate insights, and formulate strategy recommendations in one call."""
    trace.record("insight_strategy_generator", "start")

    results = state.get("execution_results", {})
    summary = state.get("dataframe_summary", {})
    business_context = state.get("business_context", "Generic")
    metadata = state.get("parsed_metadata") or {}

    # Deterministic validation flags
    validation_flags = []
    row_count = summary.get("row_count", 0)

    if row_count < MIN_SAMPLE_SIZE:
        validation_flags.append(
            f"⚠️ Small sample size ({row_count} rows). Findings may not be statistically significant."
        )

    warnings = summary.get("warnings", [])
    validation_flags.extend(warnings)

    # Check for execution errors
    error_steps = [sid for sid, r in results.items() if r.get("error")]
    if error_steps:
        validation_flags.append(
            f"⚠️ {len(error_steps)} analysis step(s) had execution errors."
        )

    trace.record("insight_strategy_generator", "validation_flags", validation_flags)

    # Build results text for LLM
    results_parts = []
    for step_id, r in results.items():
        if r.get("error"):
            continue  # Skip failed steps
        section = f"### Step {step_id}: {r.get('title', 'Analysis')}\n"
        if r.get("stdout"):
            section += f"Output/Log:\n{r['stdout'][:1000]}\n"
        if r.get("result"):
            section += f"Result Value: {str(r['result'])[:1000]}\n"
        results_parts.append(section)

    if not results_parts:
        error_msg = "Analysis steps did not produce usable results."
        if error_steps:
            error_msg = f"Analysis failed: {len(error_steps)} step(s) encountered execution errors."
        
        log.error("Analysis steps failed: %s", validation_flags)
        return {
            "validated_insights": [{
                "title": "Insufficient Data",
                "description": error_msg,
                "confidence": "low",
            }],
            "recommendations": [{
                "action": "Verify pipeline code",
                "rationale": "No execution results were obtained.",
                "expected_impact": "N/A",
                "risk": "Low",
                "suggested_next_step": "Run the data validation check script."
            }]
        }

    results_text = "\n".join(results_parts)

    # Context variables
    industry = metadata.get("industry", "Generic")
    stage = metadata.get("company_stage", "Not specified")
    business_model = metadata.get("business_model", "Not specified")
    primary_goal = metadata.get("primary_goal", "Maximize business value")
    kpis = ", ".join(metadata.get("important_kpis", ["Revenue", "Growth"]))

    prompt = INSIGHT_STRATEGY_PROMPT.format(
        business_context=business_context,
        industry=industry,
        stage=stage,
        business_model=business_model,
        primary_goal=primary_goal,
        kpis=kpis,
        columns=list(state.get("schema", {}).get("columns", {}).keys()),
        row_count=row_count,
        results_text=results_text,
    )

    wait_for_quota()
    llm = get_llm(temperature=0.2)
    response = llm.invoke(prompt)

    content = response.content
    if isinstance(content, list):
        content = "".join([part.get("text", "") if isinstance(part, dict) else str(part) for part in content])

    content = content.strip()
    if "```" in content:
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    try:
        data = json.loads(content)
        insights = data.get("validated_insights", [])
        recommendations = data.get("recommendations", [])
    except Exception as exc:
        log.error("Failed to parse combined insights/recommendations JSON: %s. Using fallback.", exc)
        insights = [{
            "title": "Analysis Complete",
            "description": "Synthesizer failed to extract structured JSON insights. Review raw steps.",
            "confidence": "medium",
        }]
        recommendations = [{
            "action": "Review steps manually",
            "rationale": "JSON parsing failure fallback.",
            "expected_impact": "N/A",
            "risk": "Low",
            "suggested_next_step": "Review results tab stdout."
        }]

    # Append data quality checks as a meta-insight if present
    if validation_flags:
        insights.append({
            "title": "Data Quality Notes",
            "description": " | ".join(validation_flags),
            "confidence": "low",
            "supporting_data": "Automated validation checks",
        })

    log.info("Generated %d insights and %d strategic recommendations.", len(insights), len(recommendations))
    trace.record("insight_strategy_generator", "complete", {
        "insights_count": len(insights),
        "recommendations_count": len(recommendations)
    })

    return {
        "validated_insights": insights,
        "recommendations": recommendations
    }
