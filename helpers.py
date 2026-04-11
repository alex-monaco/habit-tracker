"""Shared constants and utilities used by both dashboard pages."""

import numpy as np
import pandas as pd

# ── Color constants (Tailwind palette) ───────────────────────────────────────

RED = "#f87171"  # Tailwind red-400
YELLOW = "#fbbf24"  # Tailwind amber-400
GREEN = "#4ade80"  # Tailwind green-400
GRAY = "#374151"  # Tailwind gray-700
MUTED = "#6b7280"  # Tailwind gray-500


def rate_color(v: float) -> str:
    """Return green/yellow/red hex color for a 0–100 percentage value."""
    return GREEN if v >= 80 else YELLOW if v >= 50 else RED


# ── Streak computation ───────────────────────────────────────────────────────


def compute_streak(bool_series: pd.Series):
    """Return (current_streak, best_streak) from a boolean Series ordered by date."""
    vals = bool_series.tolist()
    current = run = best = 0
    for v in reversed(vals):
        if v:
            current += 1
        else:
            break
    for v in vals:
        if v:
            run += 1
            best = max(best, run)
        else:
            run = 0
    return current, best


# ── Trend helpers ────────────────────────────────────────────────────────────


def compute_slope(series: pd.Series):
    """Fit a linear trend on a 7-day smoothed series.

    Returns (slope_per_day, r_squared, n, volatile).
    volatile = True when R² is low but variance is high (non-linear swings, not just flat).
    """
    s = series.dropna().astype(float)
    n = len(s)
    if n < 7:
        return 0.0, 0.0, n, False
    smoothed = s.rolling(7, min_periods=1).mean()
    x = np.arange(n, dtype=float)
    coeffs = np.polyfit(x, smoothed.values, 1)
    slope = float(coeffs[0])
    y_hat = np.polyval(coeffs, x)
    ss_res = float(np.sum((smoothed.values - y_hat) ** 2))
    ss_tot = float(np.sum((smoothed.values - smoothed.values.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    volatile = r2 < 0.15 and float(smoothed.std()) > 15.0
    return slope, r2, n, volatile


def trend_label(total_change: float, r2: float = 1.0, volatile: bool = False) -> str:
    """Map total pp change over a period to a human-readable trend label."""
    if volatile:
        return "↕ Volatile"
    if r2 < 0.15:
        return "→ Stable"
    if total_change > 5:
        return "↑ Improving"
    if total_change < -5:
        return "↓ Declining"
    return "→ Stable"


# ── HTML table helpers ───────────────────────────────────────────────────────

# Common cell style used across all hand-built tables
TD_STYLE = "padding:10px 14px;border-bottom:1px solid #1f2937"

# Header cell style (slightly different border color)
TH_STYLE = "padding:8px 14px;text-align:left;border-bottom:1px solid #374151"


def html_table_open(columns: list[tuple[str, str]]) -> str:
    """Return the opening <table><thead>...<tbody> HTML for a dark-mode table.

    *columns* is a list of (label, alignment) tuples, e.g.:
        [("Habit", "left"), ("Rate", "center")]
    """
    header_cells = "".join(
        f'<th style="{TH_STYLE};text-align:{align}">{label}</th>' for label, align in columns
    )
    return (
        '<table style="width:100%;border-collapse:collapse;font-size:0.9rem">'
        '<thead><tr style="color:#9ca3af;font-size:0.8rem;'
        'text-transform:uppercase;letter-spacing:0.05em">'
        f"{header_cells}"
        "</tr></thead><tbody>"
    )


def html_table_close() -> str:
    """Return the closing </tbody></table> tags."""
    return "</tbody></table>"
