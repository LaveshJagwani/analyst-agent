"""
CSV Loader Tool — deterministic data ingestion and schema extraction.
"""

import os
import pandas as pd
from langchain_core.tools import tool
from config import MAX_FILE_SIZE_MB


@tool
def load_csv(file_path: str) -> dict:
    """Load a CSV file and extract its schema profile.

    Returns a dict with:
      - schema: column types, missing percentages, date/numeric/categorical lists
      - dataframe_summary: row_count, column_count, sample_rows, memory_usage
    """
    # ── Validate path ─────────────────────────────────────────────────────────
    if not os.path.isfile(file_path):
        return {"error": f"File not found: {file_path}"}

    size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        return {"error": f"File too large ({size_mb:.1f} MB). Limit is {MAX_FILE_SIZE_MB} MB."}

    # ── Load ──────────────────────────────────────────────────────────────────
    df = pd.read_csv(file_path)

    if df.empty:
        return {"error": "CSV is empty — no rows found."}

    # ── Column classification ─────────────────────────────────────────────────
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    categorical_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()

    # Detect date columns heuristically
    date_cols: list[str] = []
    for col in categorical_cols:
        try:
            pd.to_datetime(df[col].dropna().head(20))
            date_cols.append(col)
        except (ValueError, TypeError):
            pass
    # Remove detected date cols from categorical
    categorical_cols = [c for c in categorical_cols if c not in date_cols]

    # ── Missing values ────────────────────────────────────────────────────────
    missing_pct = (df.isnull().sum() / len(df) * 100).round(2).to_dict()

    # ── Schema dict ───────────────────────────────────────────────────────────
    schema = {
        "columns": {
            col: str(dtype) for col, dtype in df.dtypes.items()
        },
        "missing_pct": missing_pct,
        "numeric_columns": numeric_cols,
        "categorical_columns": categorical_cols,
        "date_columns": date_cols,
    }

    # ── Summary dict ──────────────────────────────────────────────────────────
    dataframe_summary = {
        "row_count": len(df),
        "column_count": len(df.columns),
        "sample_rows": df.head(5).to_dict(orient="records"),
        "memory_usage_mb": round(df.memory_usage(deep=True).sum() / (1024 * 1024), 2),
        "numeric_stats": df[numeric_cols].describe().to_dict() if numeric_cols else {},
    }

    return {
        "schema": schema,
        "dataframe_summary": dataframe_summary,
    }
