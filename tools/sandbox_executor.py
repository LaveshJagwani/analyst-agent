"""
Python Sandbox Executor — restricted code execution for analysis steps.
"""

import io
import sys
import signal
import traceback
import contextlib
from typing import Any

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns

from langchain_core.tools import tool
from config import EXECUTION_TIMEOUT_SECONDS, CHARTS_DIR


def _timeout_handler(signum, frame):
    raise TimeoutError("Code execution exceeded time limit.")


@tool
def execute_python(code: str, csv_path: str, step_id: int) -> dict:
    """Execute Python analysis code in a sandboxed environment.

    The code has access to: pandas (pd), numpy (np), matplotlib.pyplot (plt),
    seaborn (sns), and a pre-loaded DataFrame called `df`.

    Any matplotlib figures created are automatically saved to the charts directory.

    Args:
        code: Python code to execute.
        csv_path: Path to the CSV file (loaded as `df`).
        step_id: Current analysis step ID (used for naming charts).

    Returns:
        dict with keys: stdout, result, charts, error
    """
    # Prepare namespace with allowed libraries
    df = pd.read_csv(csv_path)

    # Try to parse date columns
    for col in df.columns:
        if df[col].dtype == "object":
            try:
                df[col] = pd.to_datetime(df[col])
            except (ValueError, TypeError):
                pass

    namespace: dict[str, Any] = {
        "pd": pd,
        "np": np,
        "plt": plt,
        "sns": sns,
        "df": df,
        "result": None,  # code can assign to this
    }

    # Capture stdout
    stdout_buffer = io.StringIO()
    charts_saved: list[str] = []

    try:
        # Set timeout on Unix; on Windows we skip signal-based timeout
        try:
            old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(EXECUTION_TIMEOUT_SECONDS)
        except (AttributeError, ValueError):
            pass  # Windows: no SIGALRM

        with contextlib.redirect_stdout(stdout_buffer):
            exec(code, namespace)  # noqa: S102

        # Cancel alarm if it was set
        try:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
        except (AttributeError, ValueError):
            pass

        # Save any open figures
        fig_nums = plt.get_fignums()
        for fig_num in fig_nums:
            fig = plt.figure(fig_num)
            chart_path = str(CHARTS_DIR / f"step_{step_id}_fig_{fig_num}.png")
            fig.savefig(chart_path, dpi=150, bbox_inches="tight")
            charts_saved.append(chart_path)
        plt.close("all")

        # Extract result
        result_value = namespace.get("result")
        if isinstance(result_value, pd.DataFrame):
            result_value = result_value.head(20).to_dict(orient="records")
        elif isinstance(result_value, pd.Series):
            result_value = result_value.head(20).to_dict()

        return {
            "stdout": stdout_buffer.getvalue(),
            "result": str(result_value) if result_value is not None else None,
            "charts": charts_saved,
            "error": None,
        }

    except Exception as exc:
        plt.close("all")
        return {
            "stdout": stdout_buffer.getvalue(),
            "result": None,
            "charts": charts_saved,
            "error": f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}",
        }
