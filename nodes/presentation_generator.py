"""
Node 9: Presentation Generator
LLM node — generates structured slide deck payload.
"""

import json
from state import AnalysisState
from config import get_llm, wait_for_quota
from logger import trace, log


PRESENTATION_PROMPT = """\
You are a Senior Strategy Consultant (McKinsey/BCG style). Transform the analysis below into a C-level executive presentation.

Business Context: {business_context}
{metadata_section}

Validated Insights:
{insights_text}

Strategic Recommendations:
{recommendations_text}

{benchmark_section}

Available Charts: {charts}

YOUR TASK:
Create a focused, high-impact storage that tells a clear story.
1. **Curate Ruthlessly**: Do NOT use all charts. Select only the top 3-5 most impactful charts that support your narrative.
2. **"So What?"**: Every slide must have a strategic takeaway (not just "Data shows X").
3. **Structure**:
   - Title Slide
   - Executive Summary (3 bullet points max, hit the bottom line hard)
   - 3-5 Data Story Slides (One chart per slide. Headline + 3 Insight bullets)
   - Strategic Recommendations (Prioritized, actionable)

OUTPUT FORMAT (JSON ONLY):
{{
  "title": "Compelling Presentation Title",
  "slides": [
    {{
      "type": "title",
      "title": "Presentation Title",
      "subtitle": "Subtitle"
    }},
    {{
      "type": "summary",
      "title": "Executive Summary",
      "content": ["bullet 1", "bullet 2", "bullet 3"]
    }},
    {{
      "type": "chart",
      "title": "Actionable Slide Headline (e.g. 'Churn is driven by Support Latency')",
      "content": ["Insight A", "Insight B", "Insight C"],
      "chart_reference": "EXACT_PATH_FROM_AVAILABLE_CHARTS_LIST_OR_NULL"
    }},
    {{
      "type": "recommendations",
      "title": "Strategic Recommendations",
      "content": ["Rec 1", "Rec 2"]
    }}
  ]
}}
"""


def presentation_generator_node(state: AnalysisState) -> dict:
    """Generate an executive-ready presentation payload."""
    trace.record("presentation_generator", "start")

    insights = state.get("validated_insights", [])
    recommendations = state.get("recommendations", [])
    benchmark = state.get("benchmark_results")
    charts = state.get("generated_charts", [])
    business_context = state.get("business_context", "Generic")
    metadata = state.get("parsed_metadata") or {}

    metadata_section = ""
    if metadata:
        parts = []
        for key in ["industry", "business_model", "company_stage", "region", "primary_goal"]:
            if metadata.get(key):
                parts.append(f"{key.replace('_', ' ').title()}: {metadata[key]}")
        metadata_section = "\n".join(parts)

    insights_text = json.dumps(insights, indent=2, default=str)
    recommendations_text = json.dumps(recommendations, indent=2, default=str)

    benchmark_section = ""
    if benchmark and not benchmark.get("error"):
        benchmark_section = f"Industry Benchmarks:\n{json.dumps(benchmark, indent=2, default=str)}"

    prompt = PRESENTATION_PROMPT.format(
        business_context=business_context,
        metadata_section=metadata_section,
        insights_text=insights_text,
        recommendations_text=recommendations_text,
        benchmark_section=benchmark_section,
        charts=json.dumps(charts, indent=2), # Pass charts as flexible string list
    )

    wait_for_quota()
    # High temperature for creativity in storytelling, but grounded in data
    llm = get_llm(temperature=0.2) 
    response = llm.invoke(prompt)
    
    content = response.content
    if isinstance(content, list):
        # Handle list of content blocks (e.g. from Gemini multimodal)
        log.warning(f"LLM returned list content: {content}")
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
        parts = content.split("```")
        if len(parts) > 1:
            content = parts[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

    try:
        presentation = json.loads(content)
    except json.JSONDecodeError:
        log.error("Failed to parse presentation JSON.")
        presentation = {
             "title": "Analysis Report",
             "slides": []
        }

    log.info("Presentation generated: %d slides.", len(presentation.get("slides", [])))
    trace.record("presentation_generator", "complete", {
        "slide_count": len(presentation.get("slides", [])),
        "title": presentation.get("title"),
    })
    return {"presentation_payload": presentation}
