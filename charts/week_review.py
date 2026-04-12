"""Plotly figure builders for the weekly review page.

All functions return go.Figure objects — no Streamlit rendering here.
"""

from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go

from charts.common import DARK_LAYOUT, STEPPED_COLORSCALE
from core.constants import GREEN, RED, YELLOW

# ── Shared layout ────────────────────────────────────────────────────────────

CHART_LAYOUT = dict(
    margin=dict(l=0, r=10, t=10, b=0),
    **DARK_LAYOUT,
    font=dict(color="#e2e8f0"),
    showlegend=True,
    legend=dict(orientation="h", yanchor="top", y=1, xanchor="left", x=0),
    yaxis=dict(range=[0, 105], ticksuffix="%", gridcolor="#222", showgrid=True),
    xaxis=dict(showgrid=False),
)

# ── Heatmap constants ────────────────────────────────────────────────────────

LABEL_MARGIN = 200
SUMMARY_COL = "Avg/wk"
COL_PX = 38
TOTAL_PX = 70

# ── Bar charts ───────────────────────────────────────────────────────────────


def build_bar_fig(daily_rates: pd.Series, ma7: pd.Series) -> go.Figure:
    """Colored bar chart of daily completion rates with 7-day MA line."""
    bar_colors = [GREEN if v >= 80 else YELLOW if v >= 50 else RED for v in daily_rates]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=daily_rates.index,
            y=daily_rates.values,
            marker_color=bar_colors,
            name="Daily rate",
            hovertemplate="%{x|%b %-d}: %{y:.0f}%<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=ma7.index,
            y=ma7.values,
            mode="lines",
            name="7-day avg",
            line=dict(color="#e2e8f0", width=2),
            hovertemplate="%{x|%b %-d} 7d avg: %{y:.0f}%<extra></extra>",
        )
    )
    fig.add_hline(y=80, line_dash="dot", line_color=GREEN, line_width=1)
    fig.add_hline(y=50, line_dash="dot", line_color=YELLOW, line_width=1)
    fig.update_layout(height=200, bargap=0.15, **CHART_LAYOUT)
    return fig


def build_weekly_bar_fig(daily_rates: pd.Series, ma28) -> go.Figure:
    """Bar chart aggregated into 7-day chunks with optional 28-day MA line."""
    chunks, labels, ma28_vals = [], [], []
    for i in range(0, len(daily_rates), 7):
        chunk = daily_rates.iloc[i : i + 7]
        d0 = chunk.index[0].strftime("%-m/%-d")
        d1 = chunk.index[-1].strftime("%-m/%-d")
        chunks.append(chunk.mean())
        labels.append(f"{d0}–{d1}")
        if ma28 is not None:
            ma28_vals.append(ma28.loc[chunk.index].mean())

    colors = [GREEN if v >= 80 else YELLOW if v >= 50 else RED for v in chunks]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=labels,
            y=chunks,
            marker_color=colors,
            name="Weekly avg",
            hovertemplate="%{x}: %{y:.0f}%<extra></extra>",
        )
    )
    if ma28_vals:
        fig.add_trace(
            go.Scatter(
                x=labels,
                y=ma28_vals,
                mode="lines",
                name="28-day avg",
                line=dict(color="#818cf8", width=2),
                hovertemplate="%{x} 28d avg: %{y:.0f}%<extra></extra>",
            )
        )
    fig.add_hline(y=80, line_dash="dot", line_color=GREEN, line_width=1)
    fig.add_hline(y=50, line_dash="dot", line_color=YELLOW, line_width=1)
    fig.update_layout(height=180, bargap=0.25, **{**CHART_LAYOUT, "showlegend": ma28 is not None})
    return fig


def build_charts(df: pd.DataFrame, last_date: date, days: int) -> tuple[go.Figure, go.Figure]:
    """Return (daily_bar_fig, weekly_bar_fig) for the given day window."""
    window = df[
        (df.index.date >= (last_date - timedelta(days=days - 1))) & (df.index.date <= last_date)
    ]
    daily_rates = window.astype(float).mean(axis=1) * 100

    ext_start = last_date - timedelta(days=days - 1 + 27)
    rates_ext = (
        df[(df.index.date >= ext_start) & (df.index.date <= last_date)].astype(float).mean(axis=1)
        * 100
    )
    ma7 = rates_ext.rolling(7).mean().loc[daily_rates.index]
    ma28 = rates_ext.rolling(28).mean().loc[daily_rates.index]

    return build_bar_fig(daily_rates, ma7), build_weekly_bar_fig(daily_rates, ma28)


# ── Heatmaps ─────────────────────────────────────────────────────────────────


def build_daily_heatmap(window: pd.DataFrame, show_text: bool = True) -> go.Figure:
    """Heatmap with one column per day plus an Avg/wk summary column."""
    w = window.sort_index()
    col_labels = [d.strftime("%a %-m/%-d") for d in w.index]
    habit_heat = w.T.astype(float)
    habit_heat.columns = col_labels
    all_row = w.astype(float).mean(axis=1).to_frame().T
    all_row.columns = col_labels
    all_row.index = ["All habits"]

    habit_avgs = habit_heat.mean(axis=1)
    y_labels = ["All habits"] + habit_heat.index.tolist()
    heat = pd.concat([all_row, habit_heat])

    daily_rates = w.astype(float).mean(axis=1) * 100
    chunks = [daily_rates.iloc[i : i + 7] for i in range(0, len(daily_rates), 7)]
    all_habits_avg = sum((c >= 80).sum() for c in chunks) / len(chunks) / 7

    total_vals = {"All habits": all_habits_avg, **habit_avgs.dropna().to_dict()}

    x_labels = [SUMMARY_COL] + col_labels
    z_rows, text_rows, hover_rows = [], [], []
    for lbl in y_labels:
        val = total_vals.get(lbl)
        summary_z = val if val is not None else float("nan")
        summary_txt = f"{val * 7:.1f}" if val is not None else " "

        daily_vals = heat.loc[lbl, col_labels].tolist()
        daily_z = [float("nan") if pd.isna(v) else v for v in daily_vals]
        daily_txt = [
            " " if pd.isna(v) else f"{v:.0%}" if (show_text and lbl == "All habits") else " "
            for v in daily_vals
        ]

        summary_hover = f"{val * 7:.1f}" if val is not None else ""
        daily_hover = [f"{v:.0%}" if not pd.isna(v) else "" for v in daily_vals]

        z_rows.append([summary_z] + daily_z)
        text_rows.append([summary_txt] + daily_txt)
        hover_rows.append([summary_hover] + daily_hover)

    fig = go.Figure(
        go.Heatmap(
            z=z_rows,
            x=x_labels,
            y=y_labels,
            colorscale=STEPPED_COLORSCALE,
            zmin=0,
            zmax=1,
            showscale=False,
            xgap=3,
            ygap=3,
            text=text_rows,
            texttemplate="%{text}",
            textfont=dict(color="black"),
            customdata=hover_rows,
            hovertemplate="%{y} — %{x}: %{customdata}<extra></extra>",
        )
    )

    fig.add_hline(y=0.5, line_color="#334155", line_width=1)

    for lbl in y_labels:
        fig.add_annotation(
            x=0,
            xref="paper",
            xshift=-(LABEL_MARGIN - 12),
            xanchor="left",
            y=lbl,
            yref="y",
            text=lbl,
            showarrow=False,
            font=dict(color="#e2e8f0", size=12),
        )

    fig_width = LABEL_MARGIN + TOTAL_PX + len(col_labels) * COL_PX

    fig.update_layout(
        width=fig_width,
        height=max(300, 36 * len(y_labels) + 60),
        margin=dict(l=LABEL_MARGIN, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0"),
        xaxis=dict(side="top", tickfont=dict(size=11), showgrid=False),
        yaxis=dict(autorange="reversed", showticklabels=False),
    )
    return fig


def build_weekly_heatmap(window: pd.DataFrame) -> go.Figure:
    """Heatmap where each column is a 7-day week aggregate."""
    w = window.sort_index()

    chunks = []
    i = 0
    while i < len(w):
        chunk = w.iloc[i : i + 7]
        chunks.append(chunk)
        i += 7

    week_labels = []
    for chunk in chunks:
        d0 = chunk.index[0].strftime("%-m/%-d")
        d1 = chunk.index[-1].strftime("%-m/%-d")
        week_labels.append(f"{d0}–{d1}")

    habit_weekly = pd.DataFrame(
        {
            lbl: chunk.astype(float).mean(axis=0)
            for lbl, chunk in zip(week_labels, chunks, strict=True)
        },
    )

    all_row = pd.DataFrame(
        {
            lbl: [chunk.astype(float).mean(axis=1).mean()]
            for lbl, chunk in zip(week_labels, chunks, strict=True)
        },
        index=["All habits"],
    )

    habit_avgs = habit_weekly.mean(axis=1)
    all_habits_avg = all_row.values.mean()

    total_vals = {"All habits": all_habits_avg, **habit_avgs.dropna().to_dict()}
    y_labels = ["All habits"] + habit_weekly.index.tolist()
    heat = pd.concat([all_row, habit_weekly])

    x_labels = [SUMMARY_COL] + week_labels
    z_rows, text_rows, hover_rows = [], [], []
    for lbl in y_labels:
        val = total_vals.get(lbl)
        summary_z = val if val is not None else float("nan")
        summary_txt = f"{val * 7:.1f}" if val is not None else " "

        weekly_vals = heat.loc[lbl, week_labels].tolist()
        weekly_z = [float("nan") if pd.isna(v) else v for v in weekly_vals]
        weekly_txt = [
            " " if pd.isna(v) else f"{v:.0%}" if lbl == "All habits" else " " for v in weekly_vals
        ]

        summary_hover = f"{val * 7:.1f}" if val is not None else ""
        weekly_hover = [f"{v:.0%}" if not pd.isna(v) else "" for v in weekly_vals]

        z_rows.append([summary_z] + weekly_z)
        text_rows.append([summary_txt] + weekly_txt)
        hover_rows.append([summary_hover] + weekly_hover)

    WEEK_COL_PX = 56
    fig_width = LABEL_MARGIN + TOTAL_PX + len(week_labels) * WEEK_COL_PX

    fig = go.Figure(
        go.Heatmap(
            z=z_rows,
            x=x_labels,
            y=y_labels,
            colorscale=STEPPED_COLORSCALE,
            zmin=0,
            zmax=1,
            showscale=False,
            xgap=3,
            ygap=3,
            text=text_rows,
            texttemplate="%{text}",
            textfont=dict(color="black"),
            customdata=hover_rows,
            hovertemplate="%{y} — %{x}: %{customdata}<extra></extra>",
        )
    )

    fig.add_hline(y=0.5, line_color="#334155", line_width=1)

    for lbl in y_labels:
        fig.add_annotation(
            x=0,
            xref="paper",
            xshift=-(LABEL_MARGIN - 12),
            xanchor="left",
            y=lbl,
            yref="y",
            text=lbl,
            showarrow=False,
            font=dict(color="#e2e8f0", size=12),
        )

    fig.update_layout(
        width=fig_width,
        height=max(300, 36 * len(y_labels) + 60),
        margin=dict(l=LABEL_MARGIN, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0"),
        xaxis=dict(side="top", tickfont=dict(size=11), showgrid=False),
        yaxis=dict(autorange="reversed", showticklabels=False),
    )
    return fig
