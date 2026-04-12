"""Weekly habit review dashboard.

Displays a 7-day, 28-day, and 84-day heatmap of habit completions,
per-habit averages, and trend classifications (solid, slipping, etc.).
"""

from datetime import timedelta

import pandas as pd
import streamlit as st

from analytics.week_review import (
    build_habit_rows,
    classify_habits,
    days_above_80,
    days_above_80_delta,
    overall_trend,
    overall_trend_d80,
    trend_delta_info,
    window_avg,
    window_delta,
)
from charts.week_review import build_charts, build_daily_heatmap, build_weekly_heatmap
from core.constants import GREEN, RED, YELLOW
from services.data_loader import load_habits, load_week_review_config
from ui.sidebar import render_sidebar_controls

st.title("Habit Week Review")


# ── Load data ─────────────────────────────────────────────────────────────────


def load_data():
    raw = load_habits()
    df = pd.DataFrame.from_dict(raw, orient="index")
    df.index = pd.to_datetime(df.index)
    df.sort_index(inplace=True)
    return df


df = load_data()

# Apply habit order/filter from config
_cfg = load_week_review_config()
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

_TREND_HELP = "Compares your last 28-day completion % to the prior 56-day baseline. Solid: both ≥ 80%. Struggling: both < 50%. Improving/Slipping: ≥ 5pp change. Okay: within 5pp."
_RATE_HELP = "Average % of all habits completed per day. Delta shows change vs the prior period of the same length."
_DAYS80_STATUS_HELP = "Overall trend for days above 80%: compares your last 28-day avg to the prior 56-day baseline. Solid: both ≥ 6/7. Struggling: both < 3.5/7. Improving/Slipping: ≥ 0.5 days/wk change. Okay: within 0.5 days/wk."
_DAYS80_HELP = "Average days/week where you completed ≥ 80% of all habits. Delta compares each window to the prior period of the same length; stable means less than 0.5 days/week difference."

(c0,) = st.columns(1)
c0.metric("Latest data", latest_date, border=True)

# Completion rate metrics
_wow_val, _wow_delta, _wow_color = window_delta(df, last_date, 7)
_mom_val, _mom_delta, _mom_color = window_delta(df, last_date, 28)
_qoq_val, _qoq_delta, _qoq_color = window_delta(df, last_date, 84)

_trend_word = overall_trend(df, last_date)
_recent_28 = window_avg(df, last_date, 28)
_prior_56 = window_avg(df, last_date, 56, end=last_date - timedelta(days=28))
_trend_delta, _trend_dcol, _trend_darrow = trend_delta_info(
    _recent_28, _prior_56, 5, "{:+.0f}pp vs prior 56d"
)

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

# Days above 80% metrics
_d80_wow_val, _d80_wow_delta, _d80_wow_color = days_above_80_delta(df, last_date, 7)
_d80_mom_val, _d80_mom_delta, _d80_mom_color = days_above_80_delta(df, last_date, 28)
_d80_qoq_val, _d80_qoq_delta, _d80_qoq_color = days_above_80_delta(df, last_date, 84)

_d80_trend_word = overall_trend_d80(df, last_date)
_d80_recent_28 = days_above_80(df, last_date, 28)
_d80_prior_56 = days_above_80(df, last_date, 56, end=last_date - timedelta(days=28))
_d80_trend_delta, _d80_trend_dcol, _d80_trend_darrow = trend_delta_info(
    _d80_recent_28, _d80_prior_56, 0.5, "{:+.1f}/wk vs prior 56d"
)

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

# ── Daily completion rate bar chart ──────────────────────────────────────────

st.subheader("Completion Rate Charts")
tab84, tab28 = st.tabs(["84 Days", "28 Days"])
with tab84:
    bar, trend = build_charts(df, last_date, 84)
    st.plotly_chart(bar, width="stretch")
    st.plotly_chart(trend, width="stretch")
with tab28:
    bar, trend = build_charts(df, last_date, 28)
    st.plotly_chart(bar, width="stretch")
    st.plotly_chart(trend, width="stretch")

st.divider()

# ── Heatmap ──────────────────────────────────────────────────────────────────

month_start = last_date - timedelta(days=27)
month = df[(df.index.date >= month_start) & (df.index.date <= last_date)]
quarter_start = last_date - timedelta(days=83)
quarter = df[(df.index.date >= quarter_start) & (df.index.date <= last_date)]

st.subheader("Heat Maps")

htab_week, htab_month, htab_quarter = st.tabs(["7 Days", "28 Days", "12 Weeks"])
with htab_week:
    st.plotly_chart(build_daily_heatmap(week), width="content")
with htab_month:
    st.plotly_chart(build_daily_heatmap(month, show_text=True), width="content")
with htab_quarter:
    st.plotly_chart(build_weekly_heatmap(quarter), width="content")

# ── Per-habit avg/wk table ───────────────────────────────────────────────────

st.divider()
st.subheader("Habit averages")

habits = list(week.columns)
rows = build_habit_rows(df, last_date, habits)


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

# ── Trend summary ────────────────────────────────────────────────────────────

st.divider()
st.subheader("Per-Habit Trends")

buckets = classify_habits(rows, df, last_date)


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


_BUCKET_LABELS = [
    ("struggling", "Struggling"),
    ("slipping", "Slipping"),
    ("improving", "Improving"),
    ("okay", "Okay"),
    ("solid", "Solid"),
]

for key, label in _BUCKET_LABELS:
    entries = buckets[key]
    if entries:
        st.markdown(f"**{label}** — {len(entries)} habit{'s' if len(entries) != 1 else ''}")
        st.table(_trend_table(entries))

if buckets["insufficient"]:
    with st.expander(
        f"Not enough data — {len(buckets['insufficient'])} habit{'s' if len(buckets['insufficient']) != 1 else ''}"
    ):
        st.table(_trend_table(buckets["insufficient"]))

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
