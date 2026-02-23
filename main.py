"""
Autonomous Data Analyst Agent — CLI Entry Point
Usage:
    python main.py --csv path/to/data.csv
    python main.py --csv data.csv --metadata "We are a B2B SaaS company..."
    python main.py --csv data.csv --metadata metadata.json --benchmark
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import OUTPUT_DIR, CHARTS_DIR, LANGSMITH_ENABLED, LANGCHAIN_PROJECT
from tools.pptx_exporter import export_pptx
from langsmith import Client
from graph import analyst_graph
from logger import log, trace


def load_metadata(metadata_arg: str | None) -> str | dict | None:
    """Load metadata from a file path or treat as inline text."""
    if metadata_arg is None:
        return None

    # If it's a file path, read it
    if os.path.isfile(metadata_arg):
        with open(metadata_arg, "r", encoding="utf-8") as f:
            content = f.read().strip()
        # Try JSON first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return content  # Treat as unstructured text

    # Inline text
    return metadata_arg


def print_results(final_state: dict):
    """Pretty-print the final analysis results."""
    print("\n" + "═" * 70)
    print("  📊  AUTONOMOUS DATA ANALYST — RESULTS")
    print("═" * 70)

    # Business Context
    ctx = final_state.get("business_context", "Unknown")
    print(f"\n🏢  Business Context: {ctx}")

    # Metadata
    meta = final_state.get("parsed_metadata")
    if meta:
        print(f"📋  Parsed Metadata: {json.dumps(meta, indent=2, default=str)}")

    # Insights
    insights = final_state.get("validated_insights", [])
    if insights:
        print(f"\n💡  Validated Insights ({len(insights)}):")
        print("─" * 50)
        for i, insight in enumerate(insights, 1):
            title = insight.get("title", "Insight")
            desc = insight.get("description", "")
            conf = insight.get("confidence", "?")
            metric = insight.get("metric_value", "")
            print(f"  {i}. [{conf.upper()}] {title}")
            if metric:
                print(f"     📈 {metric}")
            print(f"     {desc}")
            print()

    # Recommendations
    recs = final_state.get("recommendations", [])
    if recs:
        print(f"🎯  Strategic Recommendations ({len(recs)}):")
        print("─" * 50)
        for i, rec in enumerate(recs, 1):
            print(f"  {i}. ACTION: {rec.get('action', 'N/A')}")
            print(f"     WHY: {rec.get('rationale', '')}")
            print(f"     IMPACT: {rec.get('expected_impact', '')}")
            print(f"     RISK: {rec.get('risk', '')}")
            print(f"     NEXT: {rec.get('suggested_next_step', '')}")
            print()

    # Benchmarks
    bench = final_state.get("benchmark_results")
    if bench and not bench.get("error"):
        print("📊  Industry Benchmarks:")
        print("─" * 50)
        if bench.get("market_positioning"):
            print(f"  Position: {bench['market_positioning']}")
        for comp in bench.get("comparisons", []):
            print(f"  • {comp.get('kpi')}: {comp.get('company_value')} vs {comp.get('benchmark_value')} ({comp.get('deviation_pct')} deviation) — {comp.get('positioning')}")
        if bench.get("sources"):
            print(f"\n  Sources: {', '.join(bench['sources'][:5])}")
        print()

    # Charts
    charts = final_state.get("generated_charts", [])
    if charts:
        print(f"📈  Generated Charts ({len(charts)}):")
        for c in charts:
            print(f"  📄 {c}")
        print()

    # Presentation
    pres = final_state.get("presentation_payload")
    if pres:
        slides = pres.get("slides", [])
        print(f"🎬  Presentation: \"{pres.get('title', 'N/A')}\" — {len(slides)} slides")

        # Save presentation JSON
        json_path = OUTPUT_DIR / "presentation.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(pres, f, indent=2, default=str)
        print(f"  💾 Data saved to: {json_path}")

        # Generate PPTX
        pptx_path = OUTPUT_DIR / "presentation.pptx"
        try:
            # We wrap the payload back into a result-like dict for the exporter
            export_pptx({"presentation": pres}, pptx_path, charts_dir=CHARTS_DIR)
            print(f"  📊 Presentation generated: {pptx_path}")
        except Exception as e:
            print(f"  ❌ Presentation generation failed: {e}")
        print()

    # Trace
    print(f"📝  Execution trace: {trace.path}")
    if LANGSMITH_ENABLED:
        try:
            client = Client()
            # Get the most recent run in the project
            runs = list(client.list_runs(project_name=LANGCHAIN_PROJECT, limit=1))
            if runs:
                url = client.get_run_url(run=runs[0])
                print(f"LangSmith Trace: {url}")
        except Exception:
            pass
    print("═" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Autonomous Data Analyst Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--csv", required=True,
        help="Path to the CSV file to analyze.",
    )
    parser.add_argument(
        "--metadata", default=None,
        help="Business metadata: inline text, JSON string, or path to .json/.txt file.",
    )
    parser.add_argument(
        "--benchmark", action="store_true",
        help="Enable dynamic industry benchmarking via web research.",
    )
    args = parser.parse_args()

    # Resolve CSV path
    csv_path = os.path.abspath(args.csv)
    if not os.path.isfile(csv_path):
        log.error("CSV file not found: %s", csv_path)
        sys.exit(1)

    # Load metadata
    metadata = load_metadata(args.metadata)

    log.info("=" * 60)
    log.info("  AUTONOMOUS DATA ANALYST AGENT")
    log.info("  CSV: %s", csv_path)
    log.info("  Metadata: %s", "provided" if metadata else "none")
    log.info("  Benchmark: %s", "enabled" if args.benchmark else "disabled")
    log.info("  LangSmith: %s", "enabled" if LANGSMITH_ENABLED else "disabled")
    log.info("=" * 60)

    # Build initial state
    initial_state: dict = {
        "file_path": csv_path,
        "raw_metadata_input": metadata,
        "parsed_metadata": None,
        "dataframe_summary": {},
        "schema": {},
        "business_context": "",
        "analysis_plan": [],
        "current_step_index": 0,
        "execution_results": {},
        "generated_charts": [],
        "validated_insights": [],
        "recommendations": [],
        "benchmark_enabled": args.benchmark,
        "benchmark_results": None,
        "presentation_payload": None,
        "trace_log": [],
    }

    # Run the graph
    log.info("Starting analysis pipeline...")
    final_state = analyst_graph.invoke(initial_state)

    # Display results
    print_results(final_state)
    log.info("Analysis complete!")


if __name__ == "__main__":
    main()
