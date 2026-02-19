"""
Market Research Tool — dynamic industry benchmarking via Tavily web search.
"""

from langchain_core.tools import tool
from config import TAVILY_API_KEY


@tool
def market_research(
    industry: str,
    region: str = "Global",
    company_stage: str = "Unknown",
    kpis: list[str] | None = None,
) -> dict:
    """Search the web for current industry benchmarks and market conditions.

    Uses Tavily to find up-to-date benchmark data for the given industry,
    region, and company stage. Returns structured research findings.

    Args:
        industry: Industry vertical (e.g. "SaaS", "E-commerce", "FinTech").
        region: Geographic region (e.g. "India", "US", "Global").
        company_stage: Company stage (e.g. "Seed", "Series A", "Growth").
        kpis: Specific KPIs to benchmark (e.g. ["churn rate", "ARR growth"]).

    Returns:
        dict with research findings, sources, and benchmark data.
    """
    if not TAVILY_API_KEY:
        return {
            "error": "TAVILY_API_KEY not set. Add it to your .env file.",
            "fallback": True,
        }

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=TAVILY_API_KEY)

        # Build targeted queries
        kpi_str = ", ".join(kpis) if kpis else "key performance indicators"
        queries = [
            f"{industry} industry benchmarks {company_stage} stage {region} 2024 2025 {kpi_str}",
            f"{industry} market trends {region} current state competitive landscape",
        ]

        all_results: list[dict] = []
        sources: list[str] = []

        for query in queries:
            response = client.search(
                query=query,
                search_depth="advanced",
                max_results=5,
                include_answer=True,
            )
            if response.get("answer"):
                all_results.append({
                    "query": query,
                    "answer": response["answer"],
                })
            for r in response.get("results", []):
                sources.append(r.get("url", ""))

        return {
            "industry": industry,
            "region": region,
            "company_stage": company_stage,
            "research_findings": all_results,
            "sources": list(set(sources)),
            "error": None,
        }

    except Exception as exc:
        return {
            "error": f"Market research failed: {exc}",
            "fallback": True,
        }
