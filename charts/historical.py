"""Plotly figure builders for the historical analysis page.

All functions return go.Figure objects — no Streamlit rendering here.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from charts.common import DARK_LAYOUT, DIVERGING_COLORSCALE, GRADIENT_COLORSCALE
from core.constants import rate_color

# ── Time-series charts ───────────────────────────────────────────────────────


def build_daily_chart(rate_series: pd.Series) -> go.Figure:
    """Bar + 7-day MA + 28-day MA line chart for a 0-100 rate series."""
    ma7 = rate_series.rolling(7, min_periods=1).mean()
    ma28 = rate_series.rolling(28, min_periods=1).mean()
    fig = go.Figure()
    fig.add_bar(
        x=rate_series.index,
        y=rate_series.values,
        name="Daily",
        marker_color=[rate_color(v) for v in rate_series.values],
        opacity=0.6,
    )
    fig.add_scatter(
        x=ma7.index,
        y=ma7.values,
        mode="lines",
        name="7-day avg",
        line=dict(color="#60a5fa", width=2),
    )
    fig.add_scatter(
        x=ma28.index,
        y=ma28.values,
        mode="lines",
        name="28-day avg",
        line=dict(color="#f59e0b", width=2, dash="dot"),
    )
    fig.update_layout(
        height=260,
        margin=dict(t=10, b=10, l=0, r=0),
        **DARK_LAYOUT,
        yaxis=dict(range=[0, 105], ticksuffix="%", gridcolor="#222"),
        xaxis=dict(gridcolor="#222"),
        legend=dict(orientation="h", y=1.12),
    )
    return fig


def build_weekly_chart(rate_series: pd.Series) -> go.Figure:
    """Weekly aggregated bar chart with 4-week MA."""
    weekly = rate_series.resample("W-MON", label="left", closed="left").mean()
    ma4 = weekly.rolling(4, min_periods=1).mean()
    x_labels = weekly.index.strftime("W%W %b %d").tolist()
    colors = [rate_color(v) for v in weekly.values]
    fig = go.Figure()
    fig.add_bar(
        x=x_labels,
        y=weekly.values,
        name="Weekly",
        marker_color=colors,
        opacity=0.7,
        text=[f"{v:.0f}%" for v in weekly.values],
        textposition="outside",
    )
    fig.add_scatter(
        x=x_labels,
        y=ma4.values,
        mode="lines",
        name="4-week avg",
        line=dict(color="#60a5fa", width=2),
    )
    fig.update_layout(
        height=220,
        margin=dict(t=10, b=10, l=0, r=0),
        **DARK_LAYOUT,
        yaxis=dict(range=[0, 115], ticksuffix="%", gridcolor="#222"),
        xaxis=dict(gridcolor="#222", tickangle=-45),
        legend=dict(orientation="h", y=1.12),
    )
    return fig


def build_monthly_chart(rate_series: pd.Series) -> go.Figure:
    """Monthly aggregated bar chart with 3-month MA."""
    monthly = rate_series.resample("MS").mean()
    ma3 = monthly.rolling(3, min_periods=1).mean()
    x_labels = monthly.index.strftime("%b %Y").tolist()
    colors = [rate_color(v) for v in monthly.values]
    fig = go.Figure()
    fig.add_bar(
        x=x_labels,
        y=monthly.values,
        name="Monthly",
        marker_color=colors,
        opacity=0.7,
        text=[f"{v:.0f}%" for v in monthly.values],
        textposition="outside",
    )
    fig.add_scatter(
        x=x_labels,
        y=ma3.values,
        mode="lines",
        name="3-month avg",
        line=dict(color="#60a5fa", width=2),
    )
    fig.update_layout(
        height=220,
        margin=dict(t=10, b=10, l=0, r=0),
        **DARK_LAYOUT,
        yaxis=dict(range=[0, 115], ticksuffix="%", gridcolor="#222"),
        xaxis=dict(gridcolor="#222"),
        legend=dict(orientation="h", y=1.12),
    )
    return fig


# ── DOW heatmap ──────────────────────────────────────────────────────────────


def build_dow_heatmap(dow_data: dict) -> go.Figure:
    """Per-habit day-of-week heatmap figure."""
    fig = go.Figure(
        go.Heatmap(
            z=dow_data["z"],
            x=dow_data["day_abbr"],
            y=dow_data["y_labels"],
            colorscale=GRADIENT_COLORSCALE,
            zmin=0,
            zmax=100,
            showscale=False,
            xgap=3,
            ygap=3,
            text=dow_data["cell_text"],
            texttemplate="%{text}",
            textfont=dict(size=11, color="rgba(255,255,255,0.85)"),
            customdata=dow_data["hover_text"],
            hovertemplate="%{y}<br>%{x}: %{customdata}<extra></extra>",
        )
    )
    fig.update_layout(
        height=max(200, len(dow_data["y_labels"]) * 36),
        margin=dict(t=10, b=10, l=0, r=0),
        **DARK_LAYOUT,
        xaxis=dict(tickfont=dict(size=12)),
        yaxis=dict(autorange="reversed", automargin=True),
    )
    return fig


# ── Correlation matrix ───────────────────────────────────────────────────────


def build_correlation_matrix(
    corr_display: np.ndarray, corr_text: np.ndarray, habits_list: list[str]
) -> go.Figure:
    """Lower-triangle correlation heatmap."""
    n = len(habits_list)
    fig = go.Figure(
        go.Heatmap(
            z=corr_display,
            x=habits_list,
            y=habits_list,
            colorscale=DIVERGING_COLORSCALE,
            zmin=-1,
            zmax=1,
            text=corr_text,
            texttemplate="%{text}",
            hovertemplate="%{y} × %{x}: %{text}<extra></extra>",
            showscale=True,
            xgap=2,
            ygap=2,
        )
    )
    fig.update_layout(
        height=max(300, n * 45),
        margin=dict(t=10, b=10, l=0, r=0),
        **DARK_LAYOUT,
        xaxis=dict(tickangle=-45),
        yaxis=dict(autorange="reversed"),
    )
    return fig


# ── Consistency heatmap ──────────────────────────────────────────────────────


def build_consistency_heatmap(data: dict) -> go.Figure:
    """Full consistency heatmap: every habit x every day."""
    fig = go.Figure(
        go.Heatmap(
            z=data["z"],
            x=data["date_strs"],
            y=data["y_labels"],
            colorscale=DIVERGING_COLORSCALE,
            zmin=-1,
            zmax=1,
            showscale=False,
            xgap=2,
            ygap=2,
            hovertemplate="%{y}<br>%{x}: %{customdata}<extra></extra>",
            customdata=data["customdata"],
        )
    )
    fig.update_layout(
        height=max(200, len(data["y_labels"]) * 28),
        margin=dict(t=10, b=10, l=0, r=0),
        **DARK_LAYOUT,
        xaxis=dict(tickvals=data["tick_vals"], ticktext=data["tick_text"], tickangle=-45),
        yaxis=dict(autorange="reversed"),
    )
    return fig


# ── Weekly rhythm heatmap (single habit) ─────────────────────────────────────


def build_weekly_rhythm(rhythm_data: dict) -> go.Figure:
    """Weekly rhythm heatmap for a single habit."""
    fig = go.Figure(
        go.Heatmap(
            z=rhythm_data["z"],
            x=rhythm_data["week_labels"],
            y=rhythm_data["dow_labels"],
            colorscale=DIVERGING_COLORSCALE,
            zmin=-1,
            zmax=1,
            showscale=False,
            xgap=3,
            ygap=3,
            text=rhythm_data["hover"],
            hovertemplate="%{text}<extra></extra>",
        )
    )
    fig.update_layout(
        height=220,
        margin=dict(t=10, b=40, l=0, r=0),
        **DARK_LAYOUT,
        xaxis=dict(
            tickvals=rhythm_data["tick_x"],
            ticktext=rhythm_data["tick_lbl"],
            tickangle=-45,
        ),
        yaxis=dict(autorange="reversed"),
    )
    return fig
