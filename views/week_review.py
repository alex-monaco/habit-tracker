"""Weekly habit review dashboard.

Displays a 7-day, 28-day, and 84-day heatmap of habit completions,
per-habit averages, and trend classifications (solid, slipping, etc.).
"""

from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data_loader import fetch_raw_habits, fetch_week_review_config
from helpers import GREEN, RED, YELLOW
from sidebar import render_sidebar_controls

st.title("Habit Week Review")


# ── Load data ─────────────────────────────────────────────────────────────────


@st.cache_data
def load_data(demo_mode: bool = False):
    raw = fetch_raw_habits()
    df = pd.DataFrame.from_dict(raw, orient="index")
    df.index = pd.to_datetime(df.index)
    df.sort_index(inplace=True)
    return df


df = load_data(demo_mode=st.session_state.get("demo_mode", False))

# Apply habit order/filter from config
_cfg = fetch_week_review_config()
if _cfg:
    _ordered = [h for h in _cfg.get("habits", []) if h in df.columns]
    if _ordered:
        df = df[_ordered]

# 7-day window ending on the last date with data
last_date = df.index.max().date()
week_start = last_date - timedelta(days=6)
week = df[(df.index.date >= week_start) & (df.index.date <= last_date)]

render_sidebar_controls(last_date)

if week.empty:
    st.warning("No data for the last 7 days.")
    st.stop()

# ── Stats row ─────────────────────────────────────────────────────────────────

latest_date = week.index.max().strftime("%B %-d, %Y")


def window_avg_float(days: int, end: date = None) -> "float | None":
    """Overall completion rate as a float [0–100] over *days* days ending on *end*."""
    end = end or last_date
    start = end - timedelta(days=days - 1)
    w = df[(df.index.date >= start) & (df.index.date <= end)].astype(float)
    return w.mean(axis=1).mean() * 100 if not w.empty else None


def window_delta(days: int) -> tuple[str, str | None, str]:
    """Return (current_pct_str, delta_str, delta_color) comparing current vs prior same-length window."""
    current = window_avg_float(days)
    prior_end = last_date - timedelta(days=days)
    prior = window_avg_float(days, end=prior_end)
    if current is None:
        return "—", None, "normal"
    cur_str = f"{current:.0f}%"
    if prior is None:
        return cur_str, None, "normal"
    delta = current - prior
    if abs(delta) < 5:
        return cur_str, "-> stable", "off"
    return cur_str, f"{delta:+.0f}pp", "normal"


def _days_above_80_float(days: int, end: date = None) -> "float | None":
    end = end or last_date
    start = end - timedelta(days=days - 1)
    w = df[(df.index.date >= start) & (df.index.date <= end)].astype(float)
    if w.empty:
        return None
    rates = w.mean(axis=1) * 100
    chunks = [rates.iloc[i : i + 7] for i in range(0, len(rates), 7)]
    return sum((c >= 80).sum() for c in chunks) / len(chunks)


def days_above_80_delta(days: int) -> tuple[str, str | None, str]:
    """Return (value_str, delta_str, delta_color) for days-above-80% vs prior same-length window."""
    current = _days_above_80_float(days)
    if current is None:
        return "—", None, "normal"
    cur_str = f"{current:.1f}/7"
    prior_end = last_date - timedelta(days=days)
    prior = _days_above_80_float(days, end=prior_end)
    if prior is None:
        return cur_str, None, "normal"
    delta = current - prior
    if abs(delta) < 0.5:
        return cur_str, "-> stable", "off"
    return cur_str, f"{delta:+.1f}/wk", "normal"


def overall_trend_d80() -> str:
    """One-word trend for days-above-80%: compare last 28d to prior 56d."""
    recent = _days_above_80_float(28)
    prior = _days_above_80_float(56, end=last_date - timedelta(days=28))
    if recent is None or prior is None:
        return "—"
    if recent >= 6 and prior >= 6:
        return "Solid"
    if recent < 3.5 and prior < 3.5:
        return "Struggling"
    delta = recent - prior
    if delta >= 0.5:
        return "Improving"
    if delta <= -0.5:
        return "Slipping"
    return "Okay"


def overall_trend() -> str:
    """One-word overall trend: compare last 28d completion % to prior 56d."""
    recent = window_avg_float(28)
    prior = window_avg_float(56, end=last_date - timedelta(days=28))
    if recent is None or prior is None:
        return "—"
    if recent >= 80 and prior >= 80:
        return "Solid"
    if recent < 50 and prior < 50:
        return "Struggling"
    delta = recent - prior
    if delta >= 5:
        return "Improving"
    if delta <= -5:
        return "Slipping"
    return "Okay"


_TREND_HELP = "Compares your last 28-day completion % to the prior 56-day baseline. Solid: both ≥ 80%. Struggling: both < 50%. Improving/Slipping: ≥ 5pp change. Okay: within 5pp."

(c0,) = st.columns(1)
c0.metric("Latest data", latest_date, border=True)

_wow_val, _wow_delta, _wow_color = window_delta(7)
_mom_val, _mom_delta, _mom_color = window_delta(28)
_qoq_val, _qoq_delta, _qoq_color = window_delta(84)

_RATE_HELP = "Average % of all habits completed per day. Delta shows change vs the prior period of the same length."
_DAYS80_STATUS_HELP = "Overall trend for days above 80%: compares your last 28-day avg to the prior 56-day baseline. Solid: both ≥ 6/7. Struggling: both < 3.5/7. Improving/Slipping: ≥ 0.5 days/wk change. Okay: within 0.5 days/wk."
_DAYS80_HELP = "Average days/week where you completed ≥ 80% of all habits. Delta compares each window to the prior period of the same length; stable means less than 0.5 days/week difference."

_trend_word = overall_trend()
_recent_28 = window_avg_float(28)
_prior_56 = window_avg_float(56, end=last_date - timedelta(days=28))
if _recent_28 is not None and _prior_56 is not None:
    _raw_delta = _recent_28 - _prior_56
    if abs(_raw_delta) < 5:
        _trend_delta, _trend_dcol, _trend_darrow = "-> stable", "off", "off"
    else:
        _trend_delta, _trend_dcol, _trend_darrow = (
            f"{_raw_delta:+.0f}pp vs prior 56d",
            "normal",
            "auto",
        )
else:
    _trend_delta, _trend_dcol, _trend_darrow = None, "normal", "auto"

st.caption("Completion rate")
c1, c2, c3, c4 = st.columns([1.4, 1, 1, 1])
c1.metric(
    "Status",
    _trend_word,
    delta=_trend_delta,
    delta_color=_trend_dcol,
    delta_arrow=_trend_darrow,
    help=_TREND_HELP,
    border=True,
)
c2.metric(
    "Week",
    _wow_val,
    delta=_wow_delta,
    delta_color=_wow_color,
    delta_arrow="off" if _wow_color == "off" else "auto",
    help=_RATE_HELP,
    border=True,
)
c3.metric(
    "Month",
    _mom_val,
    delta=_mom_delta,
    delta_color=_mom_color,
    delta_arrow="off" if _mom_color == "off" else "auto",
    help=_RATE_HELP,
    border=True,
)
c4.metric(
    "Quarter",
    _qoq_val,
    delta=_qoq_delta,
    delta_color=_qoq_color,
    delta_arrow="off" if _qoq_color == "off" else "auto",
    help=_RATE_HELP,
    border=True,
)

_d80_wow_val, _d80_wow_delta, _d80_wow_color = days_above_80_delta(7)
_d80_mom_val, _d80_mom_delta, _d80_mom_color = days_above_80_delta(28)
_d80_qoq_val, _d80_qoq_delta, _d80_qoq_color = days_above_80_delta(84)

_d80_trend_word = overall_trend_d80()
_d80_recent_28 = _days_above_80_float(28)
_d80_prior_56 = _days_above_80_float(56, end=last_date - timedelta(days=28))
if _d80_recent_28 is not None and _d80_prior_56 is not None:
    _d80_raw_delta = _d80_recent_28 - _d80_prior_56
    if abs(_d80_raw_delta) < 0.5:
        _d80_trend_delta, _d80_trend_dcol, _d80_trend_darrow = "-> stable", "off", "off"
    else:
        _d80_trend_delta, _d80_trend_dcol, _d80_trend_darrow = (
            f"{_d80_raw_delta:+.1f}/wk vs prior 56d",
            "normal",
            "auto",
        )
else:
    _d80_trend_delta, _d80_trend_dcol, _d80_trend_darrow = None, "normal", "auto"

st.caption("Days above 80%")
c5, c6, c7, c8 = st.columns([1.4, 1, 1, 1])
c5.metric(
    "Status",
    _d80_trend_word,
    delta=_d80_trend_delta,
    delta_color=_d80_trend_dcol,
    delta_arrow=_d80_trend_darrow,
    help=_DAYS80_STATUS_HELP,
    border=True,
)
c6.metric(
    "Week",
    _d80_wow_val,
    delta=_d80_wow_delta,
    delta_color=_d80_wow_color,
    delta_arrow="off" if _d80_wow_color == "off" else "auto",
    help=_DAYS80_HELP,
    border=True,
)
c7.metric(
    "Month",
    _d80_mom_val,
    delta=_d80_mom_delta,
    delta_color=_d80_mom_color,
    delta_arrow="off" if _d80_mom_color == "off" else "auto",
    help=_DAYS80_HELP,
    border=True,
)
c8.metric(
    "Quarter",
    _d80_qoq_val,
    delta=_d80_qoq_delta,
    delta_color=_d80_qoq_color,
    delta_arrow="off" if _d80_qoq_color == "off" else "auto",
    help=_DAYS80_HELP,
    border=True,
)

st.divider()

# ── Daily completion rate bar chart ───────────────────────────────────────────

_CHART_LAYOUT = dict(
    margin=dict(l=0, r=10, t=10, b=0),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#e2e8f0"),
    showlegend=True,
    legend=dict(orientation="h", yanchor="top", y=1, xanchor="left", x=0),
    yaxis=dict(range=[0, 105], ticksuffix="%", gridcolor="#222", showgrid=True),
    xaxis=dict(showgrid=False),
)


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
    fig.update_layout(height=200, bargap=0.15, **_CHART_LAYOUT)
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
    fig.update_layout(height=180, bargap=0.25, **{**_CHART_LAYOUT, "showlegend": ma28 is not None})
    return fig


def build_charts(days: int):
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


st.subheader("Completion Rate Charts")
tab84, tab28 = st.tabs(["84 Days", "28 Days"])
with tab84:
    bar, trend = build_charts(84)
    st.plotly_chart(bar, width="stretch")
    st.plotly_chart(trend, width="stretch")
with tab28:
    bar, trend = build_charts(28)
    st.plotly_chart(bar, width="stretch")
    st.plotly_chart(trend, width="stretch")


st.divider()


# ── Heatmap ───────────────────────────────────────────────────────────────────

LABEL_MARGIN = 200
COLORSCALE = [
    [0, RED],
    [0.499, RED],
    [0.5, YELLOW],
    [0.799, YELLOW],
    [0.8, GREEN],
    [1.0, GREEN],
]

SUMMARY_COL = "Avg/wk"
COL_PX = 38  # pixels per day column
TOTAL_PX = 70  # fixed pixels for Avg/wk column


def render_heatmap(window: pd.DataFrame, show_text: bool = True):
    """Build a Plotly heatmap figure with one column per day plus an Avg/wk summary column."""
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

    # Avg days above 80% per 7-day chunk for "All habits"
    daily_rates = w.astype(float).mean(axis=1) * 100
    chunks = [daily_rates.iloc[i : i + 7] for i in range(0, len(daily_rates), 7)]
    all_habits_avg = sum((c >= 80).sum() for c in chunks) / len(chunks) / 7

    total_vals = {"All habits": all_habits_avg, **habit_avgs.dropna().to_dict()}

    # Build full z matrix: Avg/wk column first, then daily columns
    x_labels = [SUMMARY_COL] + col_labels
    z_rows, text_rows, hover_rows = [], [], []
    for lbl in y_labels:
        # Avg/wk cell
        val = total_vals.get(lbl)
        summary_z = val if val is not None else float("nan")
        summary_txt = f"{val * 7:.1f}" if val is not None else " "

        # Daily cells
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
            colorscale=COLORSCALE,
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

    # Left-aligned habit name annotations
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

    # Fixed width so Avg/wk always has space
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


def render_weekly_heatmap(window: pd.DataFrame):
    """Render a heatmap where each column is a 7-day week aggregate."""
    w = window.sort_index()

    # Chunk into 7-day periods from the start (oldest first)
    chunks = []
    i = 0
    while i < len(w):
        chunk = w.iloc[i : i + 7]
        chunks.append(chunk)
        i += 7

    # Build weekly-aggregated DataFrame: rows=habits, cols=week labels
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
    )  # rows=habits, cols=weeks

    all_row = pd.DataFrame(
        {
            lbl: [chunk.astype(float).mean(axis=1).mean()]
            for lbl, chunk in zip(week_labels, chunks, strict=True)
        },
        index=["All habits"],
    )

    habit_avgs = habit_weekly.mean(axis=1)  # per-habit mean across all weeks
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
            colorscale=COLORSCALE,
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


month_start = last_date - timedelta(days=27)
month = df[(df.index.date >= month_start) & (df.index.date <= last_date)]
quarter_start = last_date - timedelta(days=83)
quarter = df[(df.index.date >= quarter_start) & (df.index.date <= last_date)]


st.subheader("Heat Maps")

htab_week, htab_month, htab_quarter = st.tabs(["7 Days", "28 Days", "12 Weeks"])
with htab_week:
    st.plotly_chart(render_heatmap(week), width="content")
with htab_month:
    st.plotly_chart(render_heatmap(month, show_text=True), width="content")
with htab_quarter:
    st.plotly_chart(render_weekly_heatmap(quarter), width="content")

# ── Per-habit avg/wk table ─────────────────────────────────────────────────────

st.divider()
st.subheader("Habit averages")


def _avg_wk_range(habit: str, start: date, end: date):
    """Float avg/wk for habit over [start, end], or None if no data."""
    if habit not in df.columns:
        return None
    col = df[(df.index.date >= start) & (df.index.date <= end)][habit].astype(float).dropna()
    return col.mean() * 7 if not col.empty else None


def _fmt_avg(v) -> str:
    """Format a numeric avg/wk value, or '—' if None."""
    return f"{v:.1f}" if v is not None else "—"


def habit_avg_wk(habit: str, days: int) -> str:
    """Format a single habit's avg completions/week over the last *days* days."""
    start = last_date - timedelta(days=days - 1)
    return _fmt_avg(_avg_wk_range(habit, start, last_date))


_recent_start = last_date - timedelta(days=27)
_prior_start = last_date - timedelta(days=83)
_prior_end = last_date - timedelta(days=28)

habits = list(week.columns)
rows = [
    {
        "Habit": h,
        "7-day": habit_avg_wk(h, 7),
        "28-day": habit_avg_wk(h, 28),
        "84-day": habit_avg_wk(h, 84),
        "prior 56-day": _fmt_avg(_avg_wk_range(h, _prior_start, _prior_end)),
    }
    for h in habits
]


def _color_avg(val):
    """Styler callback: color a cell red/yellow/green based on avg/wk thresholds."""
    try:
        v = float(val)
        color = GREEN if v >= 6.0 else YELLOW if v >= 4.0 else RED
    except (ValueError, TypeError):
        color = ""
    return f"color: {color}" if color else ""


_COL_STYLES = [{"selector": "th, td", "props": [("width", "90px"), ("min-width", "90px")]}]

st.table(
    pd.DataFrame(rows)
    .set_index("Habit")[["7-day", "28-day", "84-day"]]
    .style.map(_color_avg)
    .set_table_styles(_COL_STYLES)
)

# ── Trend summary ──────────────────────────────────────────────────────────────

st.divider()
st.subheader("Per-Habit Trends")


def _tier(val_str: str):
    """Map an avg/wk string to a tier: 2 (green), 1 (yellow), 0 (red), or None."""
    try:
        v = float(val_str)
        return 2 if v >= 6.0 else 1 if v >= 4.0 else 0
    except (ValueError, TypeError):
        return None


slipping, improving, solid, okay, struggling, insufficient = [], [], [], [], [], []

for r in rows:
    h = r["Habit"]
    t7 = _tier(r["7-day"])
    t28 = _tier(r["28-day"])
    t_prior = _tier(r["prior 56-day"])

    # Missing data in any window → not enough history
    if t7 is None or t28 is None or t_prior is None:
        insufficient.append((h, r["7-day"], r["28-day"], r["prior 56-day"]))
        continue

    # Both 28-day and prior 56-day green → solid, skip trend analysis
    if t28 == 2 and t_prior == 2:
        solid.append((h, r["7-day"], r["28-day"], r["prior 56-day"]))
        continue

    # Both 28-day and prior 56-day red → struggling, skip trend analysis
    if t28 == 0 and t_prior == 0:
        struggling.append((h, r["7-day"], r["28-day"], r["prior 56-day"]))
        continue

    v_recent = _avg_wk_range(h, _recent_start, last_date)
    v_prior = _avg_wk_range(h, _prior_start, _prior_end)

    if v_recent is None or v_prior is None:
        insufficient.append((h, r["7-day"], r["28-day"], r["prior 56-day"]))
        continue

    delta = round(v_recent - v_prior, 1)
    delta_str = f"{delta:+.1f}/wk vs prior 56 days"

    if delta <= -0.5:
        slipping.append((h, r["7-day"], r["28-day"], r["prior 56-day"], delta_str))
    elif delta >= 0.5:
        improving.append((h, r["7-day"], r["28-day"], r["prior 56-day"], delta_str))
    else:
        okay.append((h, r["7-day"], r["28-day"], r["prior 56-day"]))


def _trend_table(entries):
    """Return a styled DataFrame for a list of (habit, 7d, 28d, prior56d, ...) tuples."""
    data = [
        {"Habit": h, "7-day": d7, "28-day": d28, "prior 56-day": d56}
        for h, d7, d28, d56, *_ in entries
    ]
    df_t = pd.DataFrame(data).set_index("Habit")
    df_t["7-day"] = pd.to_numeric(df_t["7-day"], errors="coerce")
    df_t = df_t.sort_values("7-day", ascending=True, na_position="last")
    df_t["7-day"] = df_t["7-day"].apply(lambda v: f"{v:.1f}" if pd.notna(v) else "—")
    return df_t.style.map(_color_avg).set_table_styles(_COL_STYLES)


if struggling:
    st.markdown(f"**Struggling** — {len(struggling)} habit{'s' if len(struggling) != 1 else ''}")
    st.table(_trend_table(struggling))

if slipping:
    st.markdown(f"**Slipping** — {len(slipping)} habit{'s' if len(slipping) != 1 else ''}")
    st.table(_trend_table(slipping))

if improving:
    st.markdown(f"**Improving** — {len(improving)} habit{'s' if len(improving) != 1 else ''}")
    st.table(_trend_table(improving))

if okay:
    st.markdown(f"**Okay** — {len(okay)} habit{'s' if len(okay) != 1 else ''}")
    st.table(_trend_table(okay))

if solid:
    st.markdown(f"**Solid** — {len(solid)} habit{'s' if len(solid) != 1 else ''}")
    st.table(_trend_table(solid))

if insufficient:
    with st.expander(
        f"Not enough data — {len(insufficient)} habit{'s' if len(insufficient) != 1 else ''}"
    ):
        st.table(_trend_table(insufficient))

with st.expander("How are these categories determined?"):
    st.markdown("""
**Columns**
- **7-day** and **28-day** — avg completions per week over the last 7 and 28 days
- **prior 56-day** — avg completions per week over the 56 days before the last 28 (days 29–84)

**Categories**
- **Struggling** — both 28-day and prior 56-day are red (< 4/wk). No trend analysis performed.
- **Slipping** — recent 28-day avg has dropped 0.5 or more per week compared to the prior 56-day avg.
- **Improving** — recent 28-day avg has risen 0.5 or more per week compared to the prior 56-day avg.
- **Okay** — recent 28-day and prior 56-day avg are within 0.5/wk of each other (no meaningful trend).
- **Solid** — both 28-day and prior 56-day are green (≥ 6/wk). No trend analysis performed.
- **Not enough data** — one or more windows has no data (habit is too new or recently added).

**Color thresholds**
- Green ≥ 6/wk — hitting the habit 6 or more days a week on average
- Yellow ≥ 4/wk — hitting it 4–5 days a week
- Red < 4/wk — fewer than 4 days a week
""")
