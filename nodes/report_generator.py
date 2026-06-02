"""
Node 9b: Executive Written Report Generator
LLM-driven document compiler. Takes all validated insights, recommendations, data health metrics,
and strategic plans, and outputs a highly polished, document-style Markdown business report.
"""

import json
from state import AnalysisState
from config import get_llm, wait_for_quota
from logger import trace, log


REPORT_PROMPT = """\
You are a Principal Consultant (ex-McKinsey/BCG Director). Your goal is to write a comprehensive, professional, executive-ready written business report based on a raw analytical dataset profile, data health scorecard, validated insights, and strategic recommendations.

The report must be formatted in beautiful GitHub Markdown and structured logically as a professional PDF-ready document.

---
### Business Metadata & Focus:
- Business Context: {business_context}
- Target Industry: {industry}
- Company Stage & Model: {stage} | {business_model}
- Primary Business Goal: {primary_goal}
- Focus KPIs: {kpis}
- Target Audience: {target_audience}
- persistent rules (Playbook): {rules}

---
### Dataset Health & Profile:
- Total Row Count: {row_count}
- Total Columns: {column_count}
- Data Health Score: {health_score}/100 ({health_rating})
- Health Details: Duplicates: {duplicate_rows} ({duplicate_pct}%), Avg Missing: {avg_missing}%, Avg Outliers: {avg_outliers}%

---
### Validated Insights:
{insights}

---
### Strategic Recommendations:
{recommendations}

---
### Report Structuring Guidelines:
1. **Title Block**: Start with an elegant, professional title (e.g. `# Operational Analysis & Strategic Action Plan — [Company Name]`), followed by a metadata sidebar (Author: Autonomous Data Analyst, Date: 2026, Goal: ...).
2. **Section 1: Executive Summary**: Write a rigorous, 3-paragraph strategic synthesis. Do not just restate numbers; analyze the "so what?" and the high-level roadmap.
3. **Section 2: Data Quality & Health Scorecard**: Embed a clean markdown table showing the health stats. Detail how clean the source is and any caveats or sample size warnings.
4. **Section 3: Strategic Deep-Dive Chapters**: For each validated insight, write a dedicated, named subsection (e.g. `### Chapter 3.1: ...`). Integrate specific metrics, describe *why* this occurred, what the business implication is, and reference any corresponding chart (e.g. *See Chart reference: step_...*).
5. **Section 4: Phased Action Roadmap**: Detail the strategic recommendations. Map them into a tabular timeline (Immediate Term: 1-30 Days, Medium Term: 30-90 Days, Long Term: 90+ Days) with explicit rationale, risks, and next steps.
6. **No Placeholders**: Do not use generic words. Write complete, detailed, premium text. Make the document extensive and thorough.

Return ONLY the compiled Markdown text of the report. Do NOT wrap it in markdown code fences. Start directly with the first heading `#`.
"""


def report_generator_node(state: AnalysisState) -> dict:
    """Compile all findings into a premium, document-style Markdown executive report."""
    trace.record("report_generator", "start")

    summary = state.get("dataframe_summary", {})
    schema = state.get("schema", {})
    health = state.get("data_health_scorecard", {})
    metadata = state.get("parsed_metadata") or {}
    business_context = state.get("business_context", "Generic")
    insights_list = state.get("validated_insights", [])
    recs_list = state.get("recommendations", [])

    # Format insights for prompt
    insights_str = ""
    for idx, i in enumerate(insights_list, 1):
        insights_str += f"{idx}. {i.get('title')} (Confidence: {i.get('confidence').upper()})\n"
        if i.get("metric_value"):
            insights_str += f"   - Key Stat: {i.get('metric_value')}\n"
        insights_str += f"   - Description: {i.get('description')}\n"
        if i.get("supporting_data"):
            insights_str += f"   - Supporting Data: {i.get('supporting_data')}\n"
        insights_str += "\n"

    if not insights_str:
        insights_str = "No validated insights generated."

    # Format recommendations for prompt
    recs_str = ""
    for idx, r in enumerate(recs_list, 1):
        recs_str += f"{idx}. Action: {r.get('action')}\n"
        recs_str += f"   - Rationale: {r.get('rationale')}\n"
        recs_str += f"   - Expected Impact: {r.get('expected_impact')}\n"
        recs_str += f"   - Risk & Mitigation: {r.get('risk')}\n"
        recs_str += f"   - Suggested Next Step: {r.get('suggested_next_step')}\n\n"

    if not recs_str:
        recs_str = "No strategic recommendations generated."

    prompt = REPORT_PROMPT.format(
        business_context=business_context,
        industry=metadata.get("industry", "Generic"),
        stage=metadata.get("company_stage", "Not specified"),
        business_model=metadata.get("business_model", "Not specified"),
        primary_goal=metadata.get("primary_goal", "Maximize business value"),
        kpis=", ".join(metadata.get("important_kpis", ["Revenue", "Growth"])),
        target_audience=metadata.get("target_audience", "General Stakeholders"),
        rules=", ".join(metadata.get("playbook_rules", ["Standard analysis defaults"])),
        row_count=summary.get("row_count", "unknown"),
        column_count=summary.get("column_count", "unknown"),
        health_score=health.get("overall_score", 100.0),
        health_rating=health.get("health_rating", "Excellent"),
        duplicate_rows=health.get("duplicate_rows", 0),
        duplicate_pct=health.get("duplicate_percentage", 0.0),
        avg_missing=health.get("average_missing_percentage", 0.0),
        avg_outliers=health.get("average_outlier_percentage", 0.0),
        insights=insights_str,
        recommendations=recs_str
    )

    wait_for_quota()
    llm = get_llm(temperature=0.2)
    response = llm.invoke(prompt)

    content = response.content
    if isinstance(content, list):
        content = "".join([part.get("text", "") if isinstance(part, dict) else str(part) for part in content])
    
    report_markdown = content.strip()

    # Strip code block fences if the model accidentally wrapped it
    if report_markdown.startswith("```"):
        lines = report_markdown.split("\n")
        report_markdown = "\n".join(lines[1:])
        if report_markdown.endswith("```"):
            report_markdown = report_markdown[:-3].strip()

    log.info("Executive Written Report generated successfully: %d characters", len(report_markdown))
    trace.record("report_generator", "complete", {"report_length": len(report_markdown)})

    return {
        "executive_report": report_markdown
    }
