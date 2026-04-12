"""Shared Plotly layout constants and colorscales for dark-mode dashboards."""

from core.constants import GREEN, RED, YELLOW

# ── Base layout ──────────────────────────────────────────────────────────────

DARK_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
)

# ── Colorscales ──────────────────────────────────────────────────────────────

# Stepped red/yellow/green for 0–1 completion rates (heatmaps)
STEPPED_COLORSCALE = [
    [0, RED],
    [0.499, RED],
    [0.5, YELLOW],
    [0.799, YELLOW],
    [0.8, GREEN],
    [1.0, GREEN],
]

# Diverging red–gray–green for -1 to 1 values (correlations, done/skipped)
DIVERGING_COLORSCALE = [
    [0.0, "#f87171"],
    [0.5, "#374151"],
    [1.0, "#4ade80"],
]

# Gradient red–yellow–green for 0–100 percentage values (DOW heatmap)
GRADIENT_COLORSCALE = [
    [0.0, "#f87171"],
    [0.5, "#fbbf24"],
    [0.8, "#4ade80"],
    [1.0, "#4ade80"],
]
