"""
Node 8: Benchmark Node (Conditional)
Dynamic market research + LLM comparison against live industry data.
"""

import json
from state import AnalysisState
from config import get_llm, wait_for_quota
from tools.market_research import market_research
from logger import trace, log


BENCHMARK_PROMPT = """\
You are an industry benchmarking analyst. Compare this company's performance
against the market research data provided.

Business Context: {business_context}
Company KPIs from analysis:
{company_kpis}

Live Market Research:
{research_data}

For each comparable KPI:
1. State the company value
2. State the industry benchmark (from research)
3. Calculate deviation %
4. Provide a positioning statement (e.g., "above average", "needs improvement")

Also provide:
- Overall market positioning summary
- Key competitive advantages
- Areas needing improvement
- Current market trends that affect this company

Return ONLY a JSON object:
{{
  "comparisons": [
    {{
      "kpi": "...",
      "company_value": "...",
      "benchmark_value": "...",
      "deviation_pct": "...",
      "positioning": "..."
    }}
  ],
  "market_positioning": "...",
  "competitive_advantages": ["..."],
  "improvement_areas": ["..."],
  "market_trends": ["..."]
}}
"""


def should_run_benchmark(state: AnalysisState) -> str:
    """Conditional edge: run benchmark or skip to report generator."""
    if not state.get("benchmark_enabled", False):
        return "skip"
    context = state.get("business_context", "")
    if context in ("Sales", "Marketing", "SaaS", "Finance", "Churn"):
        return "run"
    return "skip"


def benchmark_node(state: AnalysisState) -> dict:
    """Run dynamic market research and compare company KPIs."""
    trace.record("benchmark", "start")

    metadata = state.get("parsed_metadata") or {}
    business_context = state.get("business_context", "Generic")
    insights = state.get("validated_insights", [])
    results = state.get("execution_results", {})

    industry = metadata.get("industry", business_context)
    region = metadata.get("region", "Global")
    stage = metadata.get("company_stage", "Unknown")
    kpis = metadata.get("important_kpis", [])

    # ── Dynamic market research ───────────────────────────────────────────────
    log.info("Running dynamic market research for %s (%s, %s)...", industry, region, stage)

    research_result = market_research.invoke({
        "industry": industry,
        "region": region,
        "company_stage": stage,
        "kpis": kpis,
    })

    trace.record("benchmark", "research_result", research_result)

    if research_result.get("error"):
        log.warning("Market research failed: %s", research_result["error"])
        return {
            "benchmark_results": {
                "error": research_result["error"],
                "note": "Benchmarking skipped due to research failure.",
            }
        }

    # ── Extract company KPIs from results ─────────────────────────────────────
    company_kpis_parts = []
    for insight in insights:
        if insight.get("metric_value"):
            company_kpis_parts.append(
                f"- {insight['title']}: {insight['metric_value']}"
            )
    for step_id, r in results.items():
        if r.get("result") and not r.get("error"):
            company_kpis_parts.append(
                f"- Step {step_id} ({r.get('title', '')}): {str(r['result'])[:300]}"
            )

    company_kpis = "\n".join(company_kpis_parts) if company_kpis_parts else "No specific KPIs extracted."

    research_data = json.dumps(research_result.get("research_findings", []), indent=2, default=str)

    # ── LLM comparison ────────────────────────────────────────────────────────
    prompt = BENCHMARK_PROMPT.format(
        business_context=business_context,
        company_kpis=company_kpis,
        research_data=research_data,
    )

    wait_for_quota()
    llm = get_llm(temperature=0.2)
    response = llm.invoke(prompt)
    content = response.content.strip()

    if "```" in content:
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    try:
        benchmark_results = json.loads(content)
    except json.JSONDecodeError:
        log.error("Failed to parse benchmark JSON.")
        benchmark_results = {
            "market_positioning": content[:500],
            "comparisons": [],
        }

    benchmark_results["sources"] = research_result.get("sources", [])

    log.info("Benchmarking complete.")
    trace.record("benchmark", "complete", benchmark_results)
    return {"benchmark_results": benchmark_results}
