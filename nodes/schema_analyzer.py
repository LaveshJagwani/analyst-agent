"""
Node 2: Data Loader & Schema Analyzer
Deterministic node — no LLM calls.
Loads from any supported source via data_loader, writes a standardised
temp Parquet file, and profiles the dataset schema.
"""

from state import AnalysisState
from tools.data_loader import load_dataframe
from logger import trace, log


def schema_analyzer_node(state: AnalysisState) -> dict:
    """Load the data source and extract schema + dataframe summary."""

    # Resolve source type and config — support both new multi-source fields
    # and the legacy file_path (CLI path).
    source_type: str = state.get("source_type", "csv")
    source_config: dict = state.get(
        "source_config",
        {"path": state.get("file_path", "")},
    )

    trace.record("schema_analyzer", "start", {
        "source_type": source_type,
        "source_config": {k: v for k, v in source_config.items() if k != "query"},
    })

    try:
        parquet_path, schema, summary = load_dataframe(source_type, source_config)
    except Exception as exc:
        error_msg = str(exc)
        log.error("Data load failed: %s", error_msg)
        trace.record("schema_analyzer", "error", error_msg)
        return {
            "schema": {"error": error_msg},
            "dataframe_summary": {"error": error_msg},
            "parquet_path": None,
        }

    # ── Data quality warnings ──────────────────────────────────────────────────
    warnings: list[str] = []
    if summary["row_count"] < 10:
        warnings.append(
            f"Very small dataset ({summary['row_count']} rows). Results may be unreliable."
        )
    if not schema["numeric_columns"]:
        warnings.append("No numeric columns detected. Quantitative analysis will be limited.")

    high_missing = {
        col: pct for col, pct in schema["missing_pct"].items() if pct > 30
    }
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
        "parquet_path": parquet_path,
        "data_health_score": summary.get("data_health", {}).get("overall_score", 100),
        "warnings": warnings,
    })

    return {
        "schema": schema,
        "dataframe_summary": summary,
        "data_health_scorecard": summary.get("data_health", {}),
        "parquet_path": parquet_path,
    }
