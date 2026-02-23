"""
Node 9: Presentation Generator
LLM node — generates structured slide deck payload.
"""

import json
from state import AnalysisState
from config import get_llm, wait_for_quota
from logger import trace, log
from design_systems import DESIGN_SYSTEMS


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

4. **Strict Chart-Slide Alignment**: ONLY use a chart if its provided title or context match the slide narrative. Check the chart's metadata carefully.

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

    # Create a mapping of charts to their context from execution results
    execution_results = state.get("execution_results", {})
    chart_metadata = []
    for step_id, res in execution_results.items():
        step_charts = res.get("charts", []) # Now list of dicts: {"path": ..., "title": ...}
        for c_info in step_charts:
            chart_metadata.append({
                "path": c_info.get("path"),
                "title": c_info.get("title"),
                "context": f"Generated from step: {res.get('title')}. Result summary: {str(res.get('result'))[:200]}"
            })

    insights_text = json.dumps(insights, indent=2, default=str)
    recommendations_text = json.dumps(recommendations, indent=2, default=str)

    # Read design spec
    design = state.get("presentation_design") or {}
    design_system_name = design.get("design_system", "modern_blue")
    design_system = DESIGN_SYSTEMS.get(design_system_name, DESIGN_SYSTEMS["modern_blue"])
    layout_map = design.get("layout_map", {})
    visual_rules = design.get("visual_rules", {})

    design_context = f"""
    PRESENTATION DESIGN SPEC:
    - Theme: {design_system_name} ({design_system.get('tone', 'professional')})
    - Visual Rules: Highlight index {visual_rules.get('highlight_color_index')}, Bullet density {visual_rules.get('bullet_density')}
    - Planned Layouts: {json.dumps(layout_map)}
    
    Please adapt your content (tone, bullet length, and structure) to reflect this {design_system.get('tone')} design.
    """

    # Update Task rules to remove slide limits and enforce chart alignment
    updated_presentation_prompt = PRESENTATION_PROMPT.replace(
        "1. **Curate Ruthlessly**: Do NOT use all charts. Select only the top 3-5 most impactful charts that support your narrative.",
        "1. **Use all relevant data**: Include as many story slides as necessary to cover all key insights. Do NOT limit the presentation length."
    ).replace(
        "- 3-5 Data Story Slides (One chart per slide. Headline + 3 Insight bullets)",
        "- Data Story Slides (One chart per slide. Include all relevant insights discovered. Headline + 3 Insight bullets)"
    )

    benchmark_section = ""
    if benchmark and not benchmark.get("error"):
        benchmark_section = f"Industry Benchmarks:\n{json.dumps(benchmark, indent=2, default=str)}"

    prompt = updated_presentation_prompt.format(
        business_context=business_context,
        metadata_section=metadata_section,
        insights_text=insights_text,
        recommendations_text=recommendations_text,
        benchmark_section=benchmark_section,
        charts=json.dumps(chart_metadata, indent=2), # Pass metadata instead of just paths
    )
    
    # Inject design context into the prompt
    prompt = f"{design_context}\n\n{prompt}"

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
    
    # Attach design spec to the payload so the exporter can use it
    presentation["design"] = state.get("presentation_design")

    trace.record("presentation_generator", "complete", {
        "slide_count": len(presentation.get("slides", [])),
        "title": presentation.get("title"),
        "design_system": presentation.get("design", {}).get("design_system")
    })
    return {"presentation_payload": presentation}
