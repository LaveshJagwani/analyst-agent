"""
Node 2: File Loader & Schema Analyzer
Deterministic node — no LLM calls. Loads CSV and profiles the dataset.
"""

from state import AnalysisState
from tools.csv_loader import load_csv
from logger import trace, log


def schema_analyzer_node(state: AnalysisState) -> dict:
    """Load the CSV and extract schema + dataframe summary."""
    file_path = state["file_path"]
    trace.record("schema_analyzer", "start", {"file_path": file_path})

    result = load_csv.invoke({"file_path": file_path})

    if "error" in result:
        log.error("CSV load failed: %s", result["error"])
        trace.record("schema_analyzer", "error", result["error"])
        return {
            "schema": {"error": result["error"]},
            "dataframe_summary": {"error": result["error"]},
        }

    schema = result["schema"]
    summary = result["dataframe_summary"]

    # Warn on data quality issues
    warnings = []
    if summary["row_count"] < 10:
        warnings.append(f"Very small dataset ({summary['row_count']} rows). Results may be unreliable.")
    if not schema["numeric_columns"]:
        warnings.append("No numeric columns detected. Quantitative analysis will be limited.")

    high_missing = {col: pct for col, pct in schema["missing_pct"].items() if pct > 30}
    if high_missing:
        warnings.append(f"High missing data (>30%): {high_missing}")

    if warnings:
        for w in warnings:
            log.warning(w)
        summary["warnings"] = warnings

    trace.record("schema_analyzer", "complete", {
        "rows": summary["row_count"],
        "columns": summary["column_count"],
        "numeric": len(schema["numeric_columns"]),
        "categorical": len(schema["categorical_columns"]),
        "date": len(schema["date_columns"]),
        "warnings": warnings,
    })

    return {
        "schema": schema,
        "dataframe_summary": summary,
    }
