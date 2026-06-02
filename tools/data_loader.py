"""
Data Loader — unified ingestion layer for CSV, Excel, Parquet, and SQLite.

Converts any supported source format into a standardised temp Parquet file so
that the rest of the pipeline (sandbox executor, schema analyzer) is completely
format-agnostic.  The caller is responsible for deleting the returned path.
"""

import os
import sqlite3
import tempfile
from typing import Optional

import pandas as pd

from config import MAX_FILE_SIZE_MB


# ── Internal helpers ──────────────────────────────────────────────────────────

def _validate_path(path: str) -> None:
    """Raise if the file is missing or exceeds the size limit."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"File not found: {path}")
    size_mb = os.path.getsize(path) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise ValueError(
            f"File too large ({size_mb:.1f} MB). Limit is {MAX_FILE_SIZE_MB} MB."
        )


def _profile_dataframe(df: pd.DataFrame) -> tuple[dict, dict]:
    """
    Classify columns, compute summary statistics, and calculate a Data Health Scorecard.

    Returns:
        (schema_dict, summary_dict)
    """
    if df.empty:
        raise ValueError("Dataset is empty — no rows found.")

    # Column type classification
    numeric_cols: list[str] = df.select_dtypes(include="number").columns.tolist()
    categorical_cols: list[str] = df.select_dtypes(
        include=["object", "category"]
    ).columns.tolist()

    # Heuristic: detect date-like string columns
    date_cols: list[str] = []
    for col in categorical_cols:
        try:
            pd.to_datetime(df[col].dropna().head(20))
            date_cols.append(col)
        except (ValueError, TypeError):
            pass
    categorical_cols = [c for c in categorical_cols if c not in date_cols]

    # Duplicate rows
    dup_rows = int(df.duplicated().sum())
    dup_pct = round((dup_rows / len(df)) * 100, 2)

    # Missing value percentages
    missing_pct = (df.isnull().sum() / len(df) * 100).round(2).to_dict()
    avg_missing = round(sum(missing_pct.values()) / len(missing_pct), 2) if missing_pct else 0.0

    # Outliers profiling using Interquartile Range (IQR)
    outlier_pcts = {}
    for col in numeric_cols:
        col_data = df[col].dropna()
        if len(col_data) > 0:
            q1 = col_data.quantile(0.25)
            q3 = col_data.quantile(0.75)
            iqr = q3 - q1
            if iqr > 0:
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                outliers = col_data[(col_data < lower) | (col_data > upper)]
                outlier_pcts[col] = round((len(outliers) / len(col_data)) * 100, 2)
            else:
                outlier_pcts[col] = 0.0
        else:
            outlier_pcts[col] = 0.0

    avg_outliers = round(sum(outlier_pcts.values()) / len(outlier_pcts), 2) if outlier_pcts else 0.0

    # Overall Health Score (0 - 100)
    health_score = 100.0
    health_score -= (avg_missing * 0.4)
    health_score -= (avg_outliers * 0.3)
    health_score -= (dup_pct * 0.3)
    health_score = max(0.0, round(health_score, 1))

    data_health = {
        "overall_score": health_score,
        "duplicate_rows": dup_rows,
        "duplicate_percentage": dup_pct,
        "average_missing_percentage": avg_missing,
        "average_outlier_percentage": avg_outliers,
        "column_outlier_percentages": outlier_pcts,
        "health_rating": "Excellent" if health_score >= 90 else "Good" if health_score >= 75 else "Fair" if health_score >= 50 else "Poor"
    }

    schema: dict = {
        "columns": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "missing_pct": missing_pct,
        "numeric_columns": numeric_cols,
        "categorical_columns": categorical_cols,
        "date_columns": date_cols,
    }

    summary: dict = {
        "row_count": len(df),
        "column_count": len(df.columns),
        "sample_rows": df.head(5).to_dict(orient="records"),
        "memory_usage_mb": round(
            df.memory_usage(deep=True).sum() / (1024 * 1024), 2
        ),
        "numeric_stats": (
            df[numeric_cols].describe().to_dict() if numeric_cols else {}
        ),
        "data_health": data_health
    }

    return schema, summary


# ── Public API ────────────────────────────────────────────────────────────────

def load_dataframe(
    source_type: str,
    source_config: dict,
) -> tuple[str, dict, dict]:
    """
    Load a dataset from any supported source and write it as a temp Parquet file.

    Supported source types
    ----------------------
    "csv"     : source_config = {"path": "/path/to/file.csv"}
    "excel"   : source_config = {"path": "/path/to/file.xlsx",
                                  "sheet": 0}          # optional, default=first sheet
    "parquet" : source_config = {"path": "/path/to/file.parquet"}
    "sqlite"  : source_config = {"path": "/path/to/db.sqlite",
                                  "table": "my_table",  # optional
                                  "query": "SELECT ..."}# optional; takes precedence over table

    Returns
    -------
    (parquet_path, schema_dict, summary_dict)
        parquet_path — absolute path to a temp Parquet file.
                       THE CALLER MUST DELETE THIS FILE when done.
    """
    path: str = source_config.get("path", "")

    # ── Load into DataFrame ────────────────────────────────────────────────────
    if source_type == "csv":
        _validate_path(path)
        df = pd.read_csv(path)
        # Best-effort date parsing on object columns
        for col in df.select_dtypes(include="object").columns:
            try:
                df[col] = pd.to_datetime(df[col])
            except (ValueError, TypeError):
                pass

    elif source_type == "excel":
        _validate_path(path)
        sheet = source_config.get("sheet", 0)
        df = pd.read_excel(path, sheet_name=sheet, engine="openpyxl")

    elif source_type == "parquet":
        _validate_path(path)
        df = pd.read_parquet(path)

    elif source_type == "sqlite":
        _validate_path(path)
        conn = sqlite3.connect(path)
        try:
            query: Optional[str] = source_config.get("query")
            table: Optional[str] = source_config.get("table")

            if query:
                df = pd.read_sql_query(query, conn)
            elif table:
                df = pd.read_sql_query(f'SELECT * FROM "{table}"', conn)
            else:
                # Auto-detect: pick the first user-defined table
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
                tables = [row[0] for row in cursor.fetchall()]
                if not tables:
                    raise ValueError(
                        "No user tables found in the SQLite database."
                    )
                df = pd.read_sql_query(f'SELECT * FROM "{tables[0]}"', conn)
        finally:
            conn.close()

    else:
        raise ValueError(
            f"Unsupported source type: '{source_type}'. "
            "Valid options are: csv, excel, parquet, sqlite."
        )

    # ── Profile ───────────────────────────────────────────────────────────────
    schema, summary = _profile_dataframe(df)
    summary["source_type"] = source_type  # surface in UI

    # ── Serialise to standardised temp Parquet ─────────────────────────────────
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".parquet")
    tmp.close()
    df.to_parquet(tmp.name, index=False)

    return tmp.name, schema, summary


def detect_source_type(filename: str) -> str:
    """
    Infer the source type from a file extension.

    Returns one of: "csv", "excel", "parquet", "sqlite"
    Raises ValueError for unsupported extensions.
    """
    ext = os.path.splitext(filename)[-1].lower()
    mapping = {
        ".csv": "csv",
        ".xlsx": "excel",
        ".xls": "excel",
        ".parquet": "parquet",
        ".db": "sqlite",
        ".sqlite": "sqlite",
        ".sqlite3": "sqlite",
    }
    if ext not in mapping:
        raise ValueError(
            f"Unsupported file extension '{ext}'. "
            "Accepted formats: .csv, .xlsx, .xls, .parquet, .db, .sqlite, .sqlite3"
        )
    return mapping[ext]
