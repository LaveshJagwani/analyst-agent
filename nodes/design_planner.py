"""
Design Planner Node — Strategically chooses the visual theme and layout for the presentation.
"""

import json
from config import get_llm
from logger import trace, log
from design_systems import DESIGN_SYSTEMS, SLIDE_TEMPLATES

DESIGN_PLANNER_PROMPT = """
You are a Presentation Design Strategist. Your goal is to choose a visual theme and layout map that best fits the business context and insights of the data analysis.

STRICT CONSTRAINTS:
1. You MUST choose exactly one design system from the list provided.
2. You MUST choose slide templates from the list provided.
3. You MUST NOT invent new colors, hex codes, or layouts.
4. Return ONLY a valid JSON object.

INPUT DATA:
- Business Context: {context}
- Metadata: {metadata}
- Validated Insights: {insights}
- Recommendations: {recommendations}
- Benchmark Results: {benchmark}

AVAILABLE DESIGN SYSTEMS:
{design_systems}

AVAILABLE SLIDE TEMPLATES:
{slide_templates}

EXPECTED JSON FORMAT:
{{
  "design_system": "key_of_system",
  "layout_map": {{
    "executive_summary": "template_name",
    "main_insights": "template_name",
    "deep_dive": "template_name",
    "benchmarks": "template_name",
    "recommendations": "template_name"
  }},
  "visual_rules": {{
    "highlight_color_index": 1,
    "metric_font_scale": 1.3,
    "bullet_density": "medium"
  }}
}}
"""

def design_planner_node(state: dict) -> dict:
    """Analyze the analysis results and plan the presentation design."""
    
    trace.record("design_planner", "Designing presentation theme...")
    
    llm = get_llm(temperature=0.1)
    
    # Prepare prompt inputs
    context = state.get("business_context", "Unknown")
    metadata = json.dumps(state.get("parsed_metadata", {}), indent=2)
    insights = json.dumps(state.get("validated_insights", []), indent=2)
    recommendations = json.dumps(state.get("recommendations", []), indent=2)
    benchmark = json.dumps(state.get("benchmark_results", {}), indent=2)
    
    design_system_keys = list(DESIGN_SYSTEMS.keys())
    
    prompt = DESIGN_PLANNER_PROMPT.format(
        context=context,
        metadata=metadata,
        insights=insights,
        recommendations=recommendations,
        benchmark=benchmark,
        design_systems=json.dumps(DESIGN_SYSTEMS, indent=2),
        slide_templates=json.dumps(SLIDE_TEMPLATES, indent=2)
    )
    
    try:
        response = llm.invoke(prompt)
        content = response.content.strip()
        
        # Clean up Markdown JSON blocks if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:].strip()
            content = content.strip()
            
        design_json = json.loads(content)
        
        # Validation: Ensure it picked a valid system
        if design_json.get("design_system") not in DESIGN_SYSTEMS:
            log.warning("Design planner picked invalid system '%s', falling back.", design_json.get("design_system"))
            design_json["design_system"] = "modern_blue"
            
        trace.record("design_planner", "Design spec finalized", {"design": design_json})
        return {"presentation_design": design_json}
        
    except Exception as e:
        log.error("Design planner failed: %s", str(e))
        # Fallback to default
        fallback_design = {
            "design_system": "modern_blue",
            "layout_map": {
                "executive_summary": "headline_metric",
                "main_insights": "chart_left_text_right",
                "recommendations": "comparison_blocks"
            },
            "visual_rules": {
                "highlight_color_index": 1,
                "metric_font_scale": 1.2,
                "bullet_density": "medium"
            }
        }
        trace.record("design_planner", "Failed to plan design, using fallback", {"error": str(e)})
        return {"presentation_design": fallback_design}
