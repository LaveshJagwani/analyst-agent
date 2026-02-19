"""
Chart Exporter Tool — save matplotlib/seaborn figures to disk.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from langchain_core.tools import tool
from config import CHARTS_DIR


@tool
def export_chart(step_id: int, title: str = "chart") -> dict:
    """Save the current matplotlib figure to the charts directory.

    Args:
        step_id: Analysis step ID (used in filename).
        title: Descriptive title for the chart filename.

    Returns:
        dict with 'path' to the saved chart or 'error'.
    """
    fig_nums = plt.get_fignums()
    if not fig_nums:
        return {"error": "No active matplotlib figure to export."}

    saved: list[str] = []
    for fig_num in fig_nums:
        fig = plt.figure(fig_num)
        safe_title = title.replace(" ", "_").replace("/", "_")[:40]
        chart_path = str(CHARTS_DIR / f"step_{step_id}_{safe_title}_{fig_num}.png")
        fig.savefig(chart_path, dpi=150, bbox_inches="tight", facecolor="white")
        saved.append(chart_path)

    plt.close("all")
    return {"paths": saved}
