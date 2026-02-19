"""
Node 6: Insight Validator
Hybrid node — deterministic statistical checks + LLM insight generation.
"""

import json
from state import AnalysisState
from config import get_llm, wait_for_quota, MIN_SAMPLE_SIZE, CORRELATION_THRESHOLD
from logger import trace, log


INSIGHT_PROMPT = """\
You are a Senior Data Strategist (McKinsey/BCG style). Your goal is to synthesize raw analysis into high-impact business intelligence.

Business Context: {business_context}
{metadata_section}

Analysis Outputs:
{results_text}

CRITICAL INSTRUCTIONS:
1. **No Observations, Only Insights**: Do not just say "X went up". Explain *why* it matters and what it implies for the business goals.
2. **The "So What?" Test**: Every insight must answer: "How does this help us improve revenue, reduce cost, or mitigate risk?"
3. **Be Specific**: precise numbers are mandatory. "Significant growth" is a failure. "23% YoY growth driven by Enterprise segment" is a success.
4. **Curate ruthlessly**: Discard obvious or low-value findings. Only keep the top 5-7 most critical strategic points.
5. **Confidence**: Be honest. If data is thin, flag it.

Return ONLY a JSON array:
[
  {{
    "title": "Actionable Headline (e.g., 'Churn Spike in Q3 requires targeted retention')",
    "description": "2-3 concise sentences explaining the finding and its strategic implication.",
    "metric_value": "Key Stat (e.g., '15% vs 5%')",
    "confidence": "high|medium|low",
    "supporting_data": "Reference to specific step/chart"
  }}
]
"""


def insight_validator_node(state: AnalysisState) -> dict:
    """Validate execution results and generate business insights."""
    trace.record("insight_validator", "start")

    results = state.get("execution_results", {})
    summary = state.get("dataframe_summary", {})
    business_context = state.get("business_context", "Generic")
    metadata = state.get("parsed_metadata") or {}

    # ── Deterministic validation checks ───────────────────────────────────────
    validation_flags: list[str] = []
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

    trace.record("insight_validator", "validation_flags", validation_flags)

    # ── Build results text for LLM ────────────────────────────────────────────
    results_parts = []
    for step_id, r in results.items():
        if r.get("error"):
            continue  # Skip failed steps
        section = f"### Step {step_id}: {r.get('title', 'Analysis')}\n"
        if r.get("stdout"):
            section += f"Output:\n{r['stdout'][:1000]}\n"
        if r.get("result"):
            section += f"Result: {str(r['result'])[:1000]}\n"
        results_parts.append(section)

    if not results_parts:
        log.warning("No successful execution results to validate.")
        return {
            "validated_insights": [{
                "title": "Insufficient Data",
                "description": "Analysis steps did not produce usable results.",
                "confidence": "low",
            }]
        }

    results_text = "\n".join(results_parts)

    metadata_section = ""
    if metadata:
        metadata_section = f"Company info: {json.dumps(metadata, default=str)}"

    # ── LLM insight generation ────────────────────────────────────────────────
    prompt = INSIGHT_PROMPT.format(
        business_context=business_context,
        metadata_section=metadata_section,
        results_text=results_text,
    )

    wait_for_quota()
    llm = get_llm(temperature=0.1)
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
        insights = json.loads(content)
    except json.JSONDecodeError:
        log.error("Failed to parse insights JSON.")
        insights = [{
            "title": "Analysis Complete",
            "description": content[:500],
            "confidence": "medium",
        }]

    # Append validation flags as a meta-insight
    if validation_flags:
        insights.append({
            "title": "Data Quality Notes",
            "description": " | ".join(validation_flags),
            "confidence": "low",
            "supporting_data": "Automated validation checks",
        })

    log.info("Generated %d insights.", len(insights))
    trace.record("insight_validator", "insights_generated", insights)
    return {"validated_insights": insights}
