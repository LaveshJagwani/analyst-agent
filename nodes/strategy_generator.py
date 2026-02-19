"""
Node 7: Strategy Generator
LLM node — produces actionable recommendations from validated insights.
"""

import json
from state import AnalysisState
from config import get_llm, wait_for_quota
from logger import trace, log


STRATEGY_PROMPT = """\
You are a strategic business advisor. Based on the validated insights below,
generate actionable recommendations.

Business Context: {business_context}
{metadata_section}

Validated Insights:
{insights_text}

For EACH recommendation include:
- action: what to do
- rationale: why (tied to data)
- expected_impact: quantified if possible
- risk: what could go wrong
- suggested_next_step: concrete follow-up

Adapt your tone to the company stage:
- Seed/Early → focus on experimentation, learning, quick wins
- Growth → focus on optimization, scaling, efficiency
- Mature → focus on retention, diversification, risk mitigation

Return ONLY a JSON array:
[
  {{
    "action": "...",
    "rationale": "...",
    "expected_impact": "...",
    "risk": "...",
    "suggested_next_step": "..."
  }}
]
"""


def strategy_generator_node(state: AnalysisState) -> dict:
    """Generate strategic recommendations from validated insights."""
    trace.record("strategy_generator", "start")

    insights = state.get("validated_insights", [])
    business_context = state.get("business_context", "Generic")
    metadata = state.get("parsed_metadata") or {}

    insights_text = json.dumps(insights, indent=2, default=str)

    metadata_section = ""
    if metadata:
        parts = []
        if metadata.get("company_stage"):
            parts.append(f"Company stage: {metadata['company_stage']}")
        if metadata.get("primary_goal"):
            parts.append(f"Primary goal: {metadata['primary_goal']}")
        if metadata.get("industry"):
            parts.append(f"Industry: {metadata['industry']}")
        if metadata.get("region"):
            parts.append(f"Region: {metadata['region']}")
        metadata_section = "\n".join(parts)

    prompt = STRATEGY_PROMPT.format(
        business_context=business_context,
        metadata_section=metadata_section,
        insights_text=insights_text,
    )

    wait_for_quota()
    llm = get_llm(temperature=0.3)
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

    if "```" in content:
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    try:
        recommendations = json.loads(content)
    except json.JSONDecodeError:
        log.error("Failed to parse recommendations JSON.")
        recommendations = [{
            "action": "Review analysis results manually",
            "rationale": "Automated recommendation generation encountered an issue.",
            "expected_impact": "N/A",
            "risk": "Low",
            "suggested_next_step": "Review the validated insights directly.",
        }]

    log.info("Generated %d recommendations.", len(recommendations))
    trace.record("strategy_generator", "recommendations", recommendations)
    return {"recommendations": recommendations}
