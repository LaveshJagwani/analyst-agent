"""
Central Design System and Aesthetic Theme for Matplotlib and Seaborn charts.
Provides high-fidelity styling, elegant typography, and cohesive color palettes.
"""

import matplotlib as mpl
import matplotlib.pyplot as plt
import seaborn as sns

# Sleek enterprise-level color palette (Hex codes)
THEME_COLORS = {
    "primary": "#1E293B",      # Slate 800 - Dominant color
    "secondary": "#0EA5E9",    # Sky 500 - Highlight / Accent 1
    "success": "#10B981",      # Emerald 500 - Positive metric
    "danger": "#EF4444",       # Red 500 - Churn / Negative metric
    "warning": "#F59E0B",      # Amber 500 - Alert / Neutral
    "info": "#6366F1",         # Indigo 500 - Accent 2
    "light_gray": "#F1F5F9",   # Slate 100 - Backgrounds
    "border_gray": "#CBD5E1",  # Slate 300 - Axis lines
    "grid_gray": "#E2E8F0",    # Slate 200 - Gridlines
    "text_dark": "#0F172A",    # Slate 900 - Title / Dark text
    "text_muted": "#64748B"    # Slate 500 - Subtitle / Axis labels
}

# Array of colors for categories or multi-line plots
PALETTE_CATEGORICAL = [
    "#1E293B",  # Slate
    "#0EA5E9",  # Sky Blue
    "#6366F1",  # Indigo
    "#10B981",  # Emerald Green
    "#EC4899",  # Pink
    "#F59E0B",  # Amber
    "#8B5CF6",  # Violet
    "#14B8A6"   # Teal
]


def apply_plot_theme(is_dark_mode: bool = False):
    """
    Applies custom high-end rcParams presets to Matplotlib and Seaborn.
    Configures typography, border margins, line widths, and elegant grid lines.
    """
    # Initialize Seaborn base theme
    sns.set_theme(style="white", palette=PALETTE_CATEGORICAL)
    
    # Custom styling parameters
    text_color = "#FFFFFF" if is_dark_mode else THEME_COLORS["text_dark"]
    label_color = "#94A3B8" if is_dark_mode else THEME_COLORS["text_muted"]
    grid_color = "#334155" if is_dark_mode else THEME_COLORS["grid_gray"]
    bg_color = "#0F172A" if is_dark_mode else "#FFFFFF"
    
    plt.rcParams.update({
        # Typography
        "font.family": "sans-serif",
        "font.sans-serif": ["Inter", "Roboto", "Helvetica Neue", "Arial", "sans-serif"],
        "text.color": text_color,
        
        # Figure & Spacing
        "figure.facecolor": bg_color,
        "figure.dpi": 200,
        "figure.autolayout": True,
        
        # Axes & Labels
        "axes.facecolor": bg_color,
        "axes.edgecolor": THEME_COLORS["border_gray"],
        "axes.labelcolor": label_color,
        "axes.labelsize": 11,
        "axes.labelpad": 10,
        "axes.titlesize": 14,
        "axes.titleweight": "bold",
        "axes.titlepad": 15,
        "axes.spines.top": False,     # Remove top spine
        "axes.spines.right": False,   # Remove right spine
        
        # Ticks
        "xtick.color": label_color,
        "xtick.labelsize": 9.5,
        "ytick.color": label_color,
        "ytick.labelsize": 9.5,
        
        # Grid lines
        "axes.grid": True,
        "grid.color": grid_color,
        "grid.linestyle": "--",
        "grid.linewidth": 0.8,
        "grid.alpha": 0.7,
        
        # Lines & Markers
        "lines.linewidth": 2.5,
        "lines.markersize": 6,
        "patch.edgecolor": bg_color,
        "patch.force_edgecolor": True
    })


def get_color_palette() -> list[str]:
    """Returns the categorical hexadecimal color palette array."""
    return PALETTE_CATEGORICAL


def get_semantic_color(metric_type: str) -> str:
    """
    Returns a semantic hexadecimal color based on metric health.
    Valid metric types: 'primary', 'secondary', 'success', 'danger', 'warning', 'info'
    """
    return THEME_COLORS.get(metric_type, THEME_COLORS["primary"])


