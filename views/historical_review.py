"""Historical habit review dashboard.

Provides an all-habits overview (charts, per-habit breakdown, DOW analysis,
keystone habits, momentum, correlations, lead/lag, consistency heatmap) and
a single-habit deep-dive when one is selected in the sidebar.
"""

from collections import defaultdict
from datetime import date, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from scipy.cluster.hierarchy import fcluster, leaves_list, linkage
from scipy.spatial.distance import squareform
from scipy.stats import fisher_exact, ttest_ind

from data_loader import load_habits
from helpers import (
    GREEN,
    MUTED,
    RED,
    TD_STYLE,
    YELLOW,
    compute_slope,
    compute_streak,
    html_table_close,
    html_table_open,
    rate_color,
    trend_label,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def dow_cards(series: pd.Series):
    """Render day-of-week colored cards for a 0–100 series."""
    dow_df = pd.DataFrame({"rate": series.values, "day": series.index.day_name()})
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    dow_avg = dow_df.groupby("day")["rate"].mean().reindex(day_order)
    dcols = st.columns(7)
    for col, (day, val) in zip(dcols, dow_avg.items(), strict=True):
        color, text = ("#555", "—") if pd.isna(val) else (rate_color(val), f"{val:.0f}%")
        col.markdown(
            f"""<div style="text-align:center;padding:12px 4px;border-radius:8px;
                border:1px solid #2a2a2a;background:#161616">
                <div style="font-size:0.75rem;color:#888;margin-bottom:6px">{day[:3]}</div>
                <div style="font-size:1.4rem;font-weight:600;color:{color}">{text}</div>
            </div>""",
            unsafe_allow_html=True,
        )


def daily_chart(rate_series: pd.Series, title: str):
    """Bar + 7-day MA + 28-day MA line chart for a 0–100 rate series."""
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
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(range=[0, 105], ticksuffix="%", gridcolor="#222"),
        xaxis=dict(gridcolor="#222"),
        legend=dict(orientation="h", y=1.12),
    )
    st.subheader(title)
    st.plotly_chart(fig, width="stretch")


def weekly_chart(rate_series: pd.Series):
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
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(range=[0, 115], ticksuffix="%", gridcolor="#222"),
        xaxis=dict(gridcolor="#222", tickangle=-45),
        legend=dict(orientation="h", y=1.12),
    )
    st.subheader("Weekly Completion Rates")
    st.plotly_chart(fig, width="stretch")


def monthly_chart(rate_series: pd.Series):
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
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(range=[0, 115], ticksuffix="%", gridcolor="#222"),
        xaxis=dict(gridcolor="#222"),
        legend=dict(orientation="h", y=1.12),
    )
    st.subheader("Monthly Completion Rates")
    st.plotly_chart(fig, width="stretch")


# ── Load data ─────────────────────────────────────────────────────────────────


def load_data() -> pd.DataFrame:
    raw = load_habits()
    rows = []
    for date_str, habits in raw.items():
        for habit, done in habits.items():
            rows.append({"date": pd.to_datetime(date_str), "habit": habit, "done": bool(done)})
    return pd.DataFrame(rows)


df_all = load_data()
all_habits = sorted(df_all["habit"].unique())
min_date = df_all["date"].min().date()
max_date = df_all["date"].max().date()

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("Habit Tracker")

    if "start_date" not in st.session_state:
        st.session_state.start_date = min_date
    if "end_date" not in st.session_state:
        st.session_state.end_date = max_date

    _preset_map = {
        "30d": max_date - timedelta(days=30),
        "90d": max_date - timedelta(days=90),
        "180d": max_date - timedelta(days=180),
        "YTD": date(max_date.year, 1, 1),
        "All": min_date,
    }
    _presets = list(_preset_map.items())
    _row1 = st.columns(3)
    _row2 = st.columns(2)
    for _col, (_label, _pstart) in zip(_row1 + _row2, _presets, strict=True):
        if _col.button(_label, width="stretch"):
            st.session_state.start_date = max(min_date, _pstart)
            st.session_state.end_date = max_date
            st.rerun()

    start = st.date_input("From", key="start_date", min_value=min_date, max_value=max_date)
    end = st.date_input("To", key="end_date", min_value=min_date, max_value=max_date)

    st.divider()
    habit_filter = st.selectbox("Habit focus", ["All habits"] + all_habits)

    from sidebar import render_sidebar_controls

    render_sidebar_controls(max_date)


# ── Filter ────────────────────────────────────────────────────────────────────

df = df_all[(df_all["date"].dt.date >= start) & (df_all["date"].dt.date <= end)].copy()
if df.empty:
    st.warning("No data for the selected range.")
    st.stop()

pivot = df.pivot_table(index="date", columns="habit", values="done", aggfunc="first").sort_index()

# ═════════════════════════════════════════════════════════════════════════════
# SINGLE HABIT VIEW
# ═════════════════════════════════════════════════════════════════════════════

if habit_filter != "All habits" and habit_filter in pivot.columns:
    h = pivot[habit_filter]
    h_rate_series = h.fillna(False).astype(float) * 100  # 0 or 100 per day (for chart)
    h_rate = h.mean() * 100  # skips NaN — only counts tracked days
    h_slope, h_r2, h_n, h_volatile = compute_slope(h_rate_series)
    h_total_change = h_slope * h_n
    h_current, h_best = compute_streak(h.fillna(False).astype(bool))

    h_days_tracked = int(h.notna().sum())

    # Stats
    st.subheader(habit_filter)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(
        "Days tracked",
        h_days_tracked,
        help="Number of days this habit was tracked in the selected range",
    )
    c2.metric(
        "Completion rate",
        f"{h_rate:.0f}%",
        help="Percentage of tracked days this habit was completed",
    )
    c3.metric(
        "Current streak",
        f"{h_current}d",
        help="Consecutive days this habit has been completed up to today",
    )
    c4.metric(
        "Best streak", f"{h_best}d", help="Longest consecutive run of days this habit was completed"
    )
    c5.metric(
        "Trend",
        trend_label(h_total_change, h_r2, h_volatile),
        help=f"Estimated {h_total_change:+.0f}pp change over period · R²={h_r2:.2f}",
    )
    st.divider()

    # Completion over time
    daily_chart(h_rate_series, "Completion Over Time")
    weekly_chart(h_rate_series)
    monthly_chart(h_rate_series)
    st.divider()

    # Day of week
    st.subheader("Day of Week")
    dow_cards(h.astype(float) * 100)
    st.divider()

    # Momentum
    col_clean = h.dropna()
    both = pd.DataFrame({"today": col_clean, "yesterday": col_clean.shift(1)}).dropna()
    if len(both) >= 5:
        p_done = both[both["yesterday"] == True]["today"].mean()
        p_skip = both[both["yesterday"] == False]["today"].mean()
        if not (pd.isna(p_done) or pd.isna(p_skip)):
            st.subheader("Momentum")
            st.caption("How likely you are to do this habit based on whether you did it yesterday")
            m1, m2, m3 = st.columns(3)
            momentum = (p_done - p_skip) * 100
            m_color = GREEN if momentum > 10 else YELLOW if momentum > 0 else RED
            m1.metric("After doing it", f"{p_done * 100:.0f}%")
            m2.metric("After skipping it", f"{p_skip * 100:.0f}%")
            m3.metric("Momentum score", f"{momentum:+.0f}%")
            st.divider()

    # Weekly rhythm heatmap
    st.subheader("Weekly Rhythm")
    st.caption(
        "Each column is one week · rows are Mon–Sun · green = done · red = skipped · dark = not tracked"
    )

    _dates = h.index
    _week_starts = _dates - pd.to_timedelta(_dates.dayofweek, unit="D")
    _grid_df = pd.DataFrame(
        {
            "week": _week_starts,
            "dow": _dates.dayofweek,
            "val": h.map({True: 1.0, False: -1.0}).values,
        }
    )
    _week_grid = _grid_df.pivot(index="dow", columns="week", values="val").reindex(index=range(7))
    _unique_weeks = _week_grid.columns  # DatetimeIndex of Monday dates
    _week_labels = [f"{w.month}/{w.day}" for w in _unique_weeks]
    _z = _week_grid.values.astype(float)

    # Hover text: actual date + status per cell
    _hover = np.empty(_z.shape, dtype=object)
    for _ci, _ws in enumerate(_unique_weeks):
        for _ri in range(7):
            _d = _ws + pd.Timedelta(days=_ri)
            _status = (
                "no data"
                if np.isnan(_z[_ri, _ci])
                else ("done" if _z[_ri, _ci] == 1 else "skipped")
            )
            _hover[_ri, _ci] = f"{_d.strftime('%b %d, %Y')}: {_status}"

    # X-axis: one label per month at its first week
    _seen_months, _tick_x, _tick_lbl = set(), [], []
    for _i, _w in enumerate(_unique_weeks):
        _mk = (_w.year, _w.month)
        if _mk not in _seen_months:
            _seen_months.add(_mk)
            _tick_x.append(_week_labels[_i])
            _tick_lbl.append(_w.strftime("%b %Y"))

    _fig_wr = go.Figure(
        go.Heatmap(
            z=_z,
            x=_week_labels,
            y=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            colorscale=[[0.0, "#f87171"], [0.5, "#374151"], [1.0, "#4ade80"]],
            zmin=-1,
            zmax=1,
            showscale=False,
            xgap=3,
            ygap=3,
            text=_hover,
            hovertemplate="%{text}<extra></extra>",
        )
    )
    _fig_wr.update_layout(
        height=220,
        margin=dict(t=10, b=40, l=0, r=0),
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(tickvals=_tick_x, ticktext=_tick_lbl, tickangle=-45),
        yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(_fig_wr, width="stretch")

    st.stop()

# ═════════════════════════════════════════════════════════════════════════════
# ALL HABITS VIEW
# ═════════════════════════════════════════════════════════════════════════════

daily_rate = pivot.mean(axis=1) * 100

# Stats
days_tracked = len(pivot)
avg_rate = daily_rate.mean()
current_streak, best_streak = compute_streak(daily_rate >= 80)
_dr = daily_rate.dropna()
_r28_overall = _dr.iloc[-28:].mean() if len(_dr) >= 28 else None
_p28_overall = _dr.iloc[-56:-28].mean() if len(_dr) >= 56 else None
_r14_overall = _dr.iloc[-14:].mean() if len(_dr) >= 14 else None
_p14_overall = _dr.iloc[-28:-14].mean() if len(_dr) >= 28 else None
trend28_overall = (
    (_r28_overall - _p28_overall)
    if (_r28_overall is not None and _p28_overall is not None)
    else None
)
trend14_overall = (
    (_r14_overall - _p14_overall)
    if (_r14_overall is not None and _p14_overall is not None)
    else None
)

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric(
    "Days tracked", days_tracked, help="Number of days in the selected date range with habit data"
)
c2.metric(
    "Avg completion", f"{avg_rate:.0f}%", help="Average percentage of habits completed per day"
)
c3.metric(
    "Current streak", f"{current_streak}d", help="Consecutive days with ≥80% habits completed"
)
c4.metric("Best streak", f"{best_streak}d", help="Consecutive days with ≥80% habits completed")


def _trend_word(delta):
    """Map a pp delta to a one-word trend label for the stats row."""
    if delta is None:
        return "—"
    if delta >= 10:
        return "Improving"
    if delta <= -10:
        return "Declining"
    return "Stable"


c5.metric(
    "28d trend",
    _trend_word(trend28_overall),
    help=f"Last 28 days vs prior 28 days ({trend28_overall:+.1f}pp)"
    if trend28_overall is not None
    else "Last 28 days vs prior 28 days (Not enough data yet)",
)
c6.metric(
    "14d trend",
    _trend_word(trend14_overall),
    help=f"Last 14 days vs prior 14 days ({trend14_overall:+.1f}pp)"
    if trend14_overall is not None
    else "Last 14 days vs prior 14 days (Not enough data yet)",
)
st.divider()

# Completion Charts
daily_chart(daily_rate, "Daily Completion Rates")
weekly_chart(daily_rate)
monthly_chart(daily_rate)
st.divider()

# Per-habit rates
st.subheader("Per-Habit Breakdown")

# Compute DOW threshold from data: 75th percentile of |day_rate - habit_avg|
# across all habit×day combinations with ≥4 occurrences
_dow_deltas = []
for _h in pivot.columns:
    _c = pivot[_h].dropna().astype(float)
    _havg = _c.mean() * 100
    for _day, _grp in _c.groupby(_c.index.day_name()):
        if len(_grp) >= 4:
            _dow_deltas.append(abs(_grp.mean() * 100 - _havg))
_DOW_THRESHOLD = float(np.percentile(_dow_deltas, 75)) if _dow_deltas else 15.0

# Trend table
trend_rows = []
_today = date.today()
for habit in pivot.columns:
    col = pivot[habit]
    rate = col.mean() * 100
    cur, best = compute_streak(col.fillna(False).astype(bool))

    done_dates = col[col == True].index
    days_since = (_today - done_dates[-1].date()).days if len(done_dates) else None

    _vals = col.dropna().astype(float)

    def _window_mean(s, start, end):
        w = s.iloc[start:end] if end else s.iloc[start:]
        m = w.mean()
        return None if pd.isna(m) or len(w) == 0 else float(m) * 100

    # 14-day trend: last 14 days vs prior 14 days (2 complete weeks each)
    _r14 = _window_mean(_vals, -14, None) if len(_vals) >= 14 else None
    _p14 = _window_mean(_vals, -28, -14) if len(_vals) >= 28 else None
    trend14 = (_r14 - _p14) if (_r14 is not None and _p14 is not None) else None

    # 28-day trend: last 28 days vs prior 28 days (4 complete weeks each)
    _r28 = _window_mean(_vals, -28, None)
    _p28 = _window_mean(_vals, -56, -28) if len(_vals) >= 56 else None
    trend28 = (_r28 - _p28) if (_r28 is not None and _p28 is not None) else None

    # Urgency for sorting: use 28d trend if available, else 14d
    _sort_trend = trend28 if trend28 is not None else (trend14 if trend14 is not None else 0.0)
    urgency = 0 if _sort_trend < -10 else 2 if _sort_trend > 10 else 1
    _tier_rate = _r28 if _r28 is not None else rate
    tier_order = 0 if _tier_rate < 50 else 1 if _tier_rate < 80 else 2
    tier = ["Needs Attention", "Okay", "Solid"][tier_order]

    # Best days of week: days ≥15pp above habit average with ≥4 occurrences
    _dow_abbr = {
        "Monday": "Mon",
        "Tuesday": "Tue",
        "Wednesday": "Wed",
        "Thursday": "Thu",
        "Friday": "Fri",
        "Saturday": "Sat",
        "Sunday": "Sun",
    }
    _col_clean = col.dropna().astype(float)
    _dow_rates = _col_clean.groupby(_col_clean.index.day_name())
    _best_days = []
    _struggle_days = []
    for _day, _group in _dow_rates:
        if len(_group) < 4:
            continue
        _delta = _group.mean() * 100 - rate
        if _delta >= _DOW_THRESHOLD:
            _best_days.append(_dow_abbr[_day])
        elif _delta <= -_DOW_THRESHOLD:
            _struggle_days.append(_dow_abbr[_day])
    # Sort by day order
    _dow_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    _best_days = [d for d in _dow_order if d in _best_days]
    _struggle_days = [d for d in _dow_order if d in _struggle_days]

    trend_rows.append(
        {
            "Habit": habit,
            "Rate": rate,
            "Rate28": _r28,
            "Trend14": trend14,
            "Trend28": trend28,
            "CurStreak": cur,
            "BestStreak": best,
            "DaysSince": days_since,
            "Tier": tier,
            "TierOrder": tier_order,
            "Urgency": urgency,
            "BestDays": _best_days,
            "StruggleDays": _struggle_days,
        }
    )

trend_df = (
    pd.DataFrame([r for r in trend_rows if r["Rate28"] is not None])
    .assign(Trend28Sort=lambda d: d["Trend28"].fillna(0))
    .assign(Rate28Sort=lambda d: d["Rate28"].fillna(d["Rate"]))
    .sort_values(["TierOrder", "Trend28Sort", "Rate28Sort"], ascending=[True, True, False])
)

_TIER_COLOR = {"Solid": GREEN, "Okay": YELLOW, "Needs Attention": RED}
_hdr = html_table_open(
    [
        ("Habit", "left"),
        ("28d Rate", "center"),
        ("Streak", "left"),
        ("28d Trend", "center"),
        ("14d Trend", "center"),
        ("Best Days", "left"),
        ("Struggle Days", "left"),
    ]
)
_rows_html = []
_cur_tier = None
for _, row in trend_df.iterrows():
    if row["Tier"] != _cur_tier:
        _cur_tier = row["Tier"]
        _tc = _TIER_COLOR[_cur_tier]
        _rows_html.append(
            f'<tr><td colspan="7" style="padding:10px 14px 4px;font-size:0.72rem;'
            f'font-weight:700;color:{_tc};letter-spacing:0.08em">'
            f"{_cur_tier.upper()}</td></tr>"
        )

    # 28d Rate
    _rate_html = f'<span style="color:{rate_color(row["Rate28"])}">{row["Rate28"]:.0f}%</span>'

    # Streak
    _dim = f'style="color:{MUTED};font-size:0.85em"'
    if row["CurStreak"] >= 3:
        _sc = GREEN
    elif row["CurStreak"] > 0:
        _sc = YELLOW
    else:
        _sc = None
    if _sc:
        _streak_html = (
            f'<span style="color:{_sc}">{row["CurStreak"]}d</span> '
            f"<span {_dim}>(best: {row['BestStreak']}d)</span>"
        )
    elif row["DaysSince"] is not None:
        _streak_html = (
            f'<span style="color:{RED}">broken · last {row["DaysSince"]}d ago</span> '
            f"<span {_dim}>(best: {row['BestStreak']}d)</span>"
        )
    else:
        _streak_html = (
            f'<span style="color:{RED}">never</span> '
            f"<span {_dim}>(best: {row['BestStreak']}d)</span>"
        )

    # 7d / 28d trend cells
    def _trend_cell(delta):
        """Return an HTML span with colored arrow + pp delta for a trend cell."""
        if delta is None or (isinstance(delta, float) and np.isnan(delta)):
            return '<span style="color:#4b5563;font-size:0.8rem">—</span>'
        color = GREEN if delta > 10 else RED if delta < -10 else MUTED
        arrow = "↑" if delta > 10 else "↓" if delta < -10 else "→"
        return f'<span style="color:{color}">{arrow} {delta:+.0f}pp</span>'

    _trend14_html = _trend_cell(row["Trend14"])
    _trend28_html = _trend_cell(row["Trend28"])

    # Best days pills
    if row["BestDays"]:
        _pills = "".join(
            f'<span style="display:inline-block;margin:0 3px 2px 0;padding:1px 7px;'
            f'border-radius:9px;background:#14532d;color:#4ade80;font-size:0.75rem">{d}</span>'
            for d in row["BestDays"]
        )
    else:
        _pills = '<span style="color:#4b5563;font-size:0.8rem">—</span>'

    # Struggle days pills
    if row["StruggleDays"]:
        _struggle_pills = "".join(
            f'<span style="display:inline-block;margin:0 3px 2px 0;padding:1px 7px;'
            f'border-radius:9px;background:#450a0a;color:#f87171;font-size:0.75rem">{d}</span>'
            for d in row["StruggleDays"]
        )
    else:
        _struggle_pills = '<span style="color:#4b5563;font-size:0.8rem">—</span>'

    _rows_html.append(
        f"<tr>"
        f"<td style='{TD_STYLE}'>{row['Habit']}</td>"
        f"<td style='{TD_STYLE};text-align:center'>{_rate_html}</td>"
        f"<td style='{TD_STYLE}'>{_streak_html}</td>"
        f"<td style='{TD_STYLE};text-align:center'>{_trend28_html}</td>"
        f"<td style='{TD_STYLE};text-align:center'>{_trend14_html}</td>"
        f"<td style='{TD_STYLE}'>{_pills}</td>"
        f"<td style='{TD_STYLE}'>{_struggle_pills}</td>"
        f"</tr>"
    )

st.write(_hdr + "".join(_rows_html) + html_table_close(), unsafe_allow_html=True)

with st.expander("What do these columns mean?"):
    st.markdown(
        "**28d Rate** — your completion rate for the last 28 days (4 full weekly cycles). "
        "Shows current level rather than historical average. Uses all available data if fewer than 28 days exist.\n\n"
        "**Streak** — current consecutive-day streak and your all-time best. "
        "Green = active streak of 3+ days, amber = 1–2 days, red = broken (shows days since last done).\n\n"
        "**28d** — last 28 days vs the prior 28 days. "
        "Answers: is this month better than last month? "
        "Needs 56 days of data. ↑ = improving, ↓ = declining, → = stable (within ±10pp).\n\n"
        "**14d** — last 14 days vs the prior 14 days. "
        "Answers: are the last 2 weeks better than the 2 weeks before? "
        "Needs 28 days of data. Most useful when it disagrees with 28d — a declining 28d with an improving 14d means you're actively turning it around.\n\n"
        "**Best Days** — days of the week where your completion rate is consistently above your average "
        f"(threshold: ≥{_DOW_THRESHOLD:.0f}pp above average, min 4 occurrences).\n\n"
        f"**Struggle Days** — days where your completion rate is consistently below your average "
        f"(threshold: ≥{_DOW_THRESHOLD:.0f}pp below average, min 4 occurrences).\n\n"
        "**Tiers** — Needs Attention (<50%), Okay (50–79%), Solid (≥80%), based on 28d rate. "
        "Within each tier, habits are sorted by 28d trend ascending so the most declining habits appear first."
    )
st.divider()

# Day of week
st.subheader("Day of Week")

_dow_day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_dow_overall = daily_rate.mean()
_dow_avg = daily_rate.groupby(daily_rate.index.day_name()).mean().reindex(_dow_day_order)

# Per-habit DOW rates, counts, and overall rates (for relative deviation)
_dow_by_habit = {}
_habit_overall = {}
for _h in pivot.columns:
    _c = pivot[_h].dropna().astype(float)
    _dow_by_habit[_h] = _c.groupby(_c.index.day_name()).mean() * 100
    _habit_overall[_h] = _c.mean() * 100

# Per-day habit pills: ≥15pp vs habit's overall average, ≥4 occurrences on that day
_pills_per_day = {}
for _day in _dow_day_order:
    _day_habits = []
    for _h in pivot.columns:
        _col = pivot[_h].dropna().astype(float)
        _on_day = _col[_col.index.day_name() == _day]
        if len(_on_day) < 4:
            continue
        _dev = _on_day.mean() * 100 - _col.mean() * 100
        if abs(_dev) >= _DOW_THRESHOLD:
            _day_habits.append((_h, _dev))
    _pills_per_day[_day] = sorted(_day_habits, key=lambda x: x[1])  # worst first


def _habit_tags(habits, positive):
    """Render colored pill-style HTML tags for habits deviating from their DOW average."""
    html = ""
    for _ph, _dev in habits:
        if (positive and _dev > 0) or (not positive and _dev < 0):
            _c = GREEN if positive else RED
            html += (
                f'<span style="display:inline-block;padding:1px 7px;margin:2px 2px;'
                f'border-radius:10px;border:1px solid {_c};color:{_c};font-size:0.72rem" '
                f'title="{_ph}">{_ph} {_dev:+.0f}pp</span>'
            )
    return html or '<span style="color:#4b5563;font-size:0.72rem">—</span>'


_dow_table = html_table_open(
    [
        ("Day", "left"),
        ("Rate", "center"),
        ("vs Avg", "center"),
        ("Struggling", "left"),
        ("Thriving", "left"),
    ]
)
for _day in _dow_day_order:
    _val = _dow_avg[_day]
    if pd.isna(_val):
        _dow_table += (
            f'<tr><td style="{TD_STYLE}">{_day[:3]}</td>'
            f'<td style="{TD_STYLE}" colspan="4"><span style="color:#4b5563">no data</span></td></tr>'
        )
        continue
    _delta = _val - _dow_overall
    _delta_col = GREEN if _delta > 2 else RED if _delta < -2 else MUTED
    _delta_str = f"{_delta:+.0f}pp"
    _pills = _pills_per_day[_day]
    _dow_table += (
        f"<tr>"
        f'<td style="{TD_STYLE};font-weight:600">{_day[:3]}</td>'
        f'<td style="{TD_STYLE};text-align:center"><span style="color:{rate_color(_val)}">{_val:.0f}%</span></td>'
        f'<td style="{TD_STYLE};text-align:center"><span style="color:{_delta_col}">{_delta_str}</span></td>'
        f'<td style="{TD_STYLE}">{_habit_tags(_pills, positive=False)}</td>'
        f'<td style="{TD_STYLE}">{_habit_tags(_pills, positive=True)}</td>'
        f"</tr>"
    )
_dow_table += html_table_close()
st.write(_dow_table, unsafe_allow_html=True)

with st.expander("What do these columns mean?"):
    st.markdown(
        "**Rate** — average completion rate across all habits for that day of the week, colored green (≥80%), amber (≥50%), or red (<50%).\n\n"
        "**vs Avg** — how that day's rate compares to your overall daily average in percentage points. "
        "Green means above average, red means below, gray means within ±2pp (no meaningful difference).\n\n"
        f"**Struggling** — habits whose completion rate on this day is ≥{_DOW_THRESHOLD:.0f}pp below their overall average, "
        "with at least 4 occurrences of that weekday in the selected range.\n\n"
        f"**Thriving** — habits whose completion rate on this day is ≥{_DOW_THRESHOLD:.0f}pp above their overall average.\n\n"
        "A dash (—) means no habit has a consistent pattern on that day — "
        "either not enough data yet or your habits are consistent across all days."
    )

with st.expander("Per-habit breakdown by day"):
    _day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    _day_abbr = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    _habits_dow = pivot.mean().sort_values(ascending=False).index.tolist()

    _z_dow, _cell_text, _hover_text = [], [], []
    for _h in _habits_dow:
        _col = pivot[_h].dropna().astype(float) * 100
        _by_rate = _col.groupby(_col.index.day_name()).mean().reindex(_day_order)
        _by_n = _col.groupby(_col.index.day_name()).count().reindex(_day_order)
        _z_dow.append(_by_rate.values)
        _cell_text.append([f"{r:.0f}%" if not np.isnan(r) else "" for r in _by_rate.values])
        _hover_text.append(
            [
                f"{r:.0f}% (n={int(n)})" if not np.isnan(r) else "no data"
                for r, n in zip(_by_rate.values, _by_n.values, strict=True)
            ]
        )

    _z_dow = np.array(_z_dow, dtype=float)

    _overall_dow = daily_rate.groupby(daily_rate.index.day_name()).mean().reindex(_day_order)
    _overall_n = daily_rate.groupby(daily_rate.index.day_name()).count().reindex(_day_order)
    _z_dow_full = np.vstack([_z_dow, _overall_dow.values.reshape(1, -1)])
    _y_full = _habits_dow + ["── Daily avg"]
    _cell_text_full = _cell_text + [[f"{v:.0f}%" if not np.isnan(v) else "" for v in _overall_dow]]
    _hover_text_full = _hover_text + [
        [
            f"{r:.0f}% (n={int(n)})" if not np.isnan(r) else "no data"
            for r, n in zip(_overall_dow.values, _overall_n.values, strict=True)
        ]
    ]

    _fig_dow = go.Figure(
        go.Heatmap(
            z=_z_dow_full,
            x=_day_abbr,
            y=_y_full,
            colorscale=[
                [0.0, "#f87171"],
                [0.5, "#fbbf24"],
                [0.8, "#4ade80"],
                [1.0, "#4ade80"],
            ],
            zmin=0,
            zmax=100,
            showscale=False,
            xgap=3,
            ygap=3,
            text=_cell_text_full,
            texttemplate="%{text}",
            textfont=dict(size=11, color="rgba(255,255,255,0.85)"),
            customdata=_hover_text_full,
            hovertemplate="%{y}<br>%{x}: %{customdata}<extra></extra>",
        )
    )
    _fig_dow.update_layout(
        height=max(200, len(_y_full) * 36),
        margin=dict(t=10, b=10, l=0, r=0),
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(tickfont=dict(size=12)),
        yaxis=dict(autorange="reversed", automargin=True),
    )
    st.plotly_chart(_fig_dow, width="stretch")
st.divider()

# Keystone habits
st.subheader("Keystone Habits")
st.caption(
    "Which habits, when done, reliably lift your whole routine — and which specific habits they bring with them"
)
ks_min_days = st.session_state.get("ks_min_days", 5)
ks_rows = []
for habit in pivot.columns:
    # Only use rows where this habit has a recorded value
    habit_col = pivot[habit].dropna()
    done_idx = habit_col[habit_col == True].index
    skip_idx = habit_col[habit_col == False].index
    if len(done_idx) < ks_min_days or len(skip_idx) < ks_min_days:
        continue
    other_habits = [h for h in pivot.columns if h != habit]
    # Compute other-habit rate only on rows where this habit is observed
    base = pivot.loc[habit_col.index, other_habits]
    other_rate = base.mean(axis=1) * 100
    done_vals = other_rate[other_rate.index.isin(done_idx)].dropna().astype(float)
    skip_vals = other_rate[other_rate.index.isin(skip_idx)].dropna().astype(float)
    done_rate = done_vals.mean()
    skip_rate = skip_vals.mean()
    _, p_val = ttest_ind(done_vals, skip_vals, equal_var=False)
    # Breadth: individual other habits significantly lifted or suppressed
    lifted = []
    suppressed = []
    for other in other_habits:
        d = base.loc[done_idx, other].dropna().astype(float)
        s = base.loc[skip_idx, other].dropna().astype(float)
        if len(d) >= 5 and len(s) >= 5:
            _, p_other = ttest_ind(d, s, equal_var=False)
            if p_other < 0.05:
                delta = (d.mean() - s.mean()) * 100
                if delta > 0:
                    lifted.append((other, delta))
                else:
                    suppressed.append((other, delta))
    lifted.sort(key=lambda x: x[1], reverse=True)
    suppressed.sort(key=lambda x: x[1])
    if p_val >= 0.05:
        continue
    completion_rate = habit_col.mean() * 100
    overall_median = other_rate.median()
    consistency = (done_vals >= overall_median).mean() * 100
    ks_rows.append(
        {
            "Habit": habit,
            "CompletionRate": completion_rate,
            "Impact": done_rate - skip_rate,
            "Consistency": consistency,
            "Done Days": len(done_vals),
            "Skip Days": len(skip_vals),
            "p": p_val,
            "Lifted": lifted,
            "Suppressed": suppressed,
            "Total": len(other_habits),
        }
    )

if ks_rows:
    ks_df = pd.DataFrame(ks_rows).sort_values("Impact", ascending=False)
    rows_html = ""
    for _, row in ks_df.iterrows():
        i_color = GREEN if row["Impact"] > 5 else YELLOW if row["Impact"] > 0 else RED
        lifted, suppressed, total = row["Lifted"], row["Suppressed"], int(row["Total"])
        up, down = len(lifted), len(suppressed)
        up_str = (
            f'<span style="color:{GREEN}">{up}↑</span>'
            if up > 0
            else f'<span style="color:{MUTED}">0↑</span>'
        )
        down_str = (
            f'<span style="color:{RED}">{down}↓</span>'
            if down > 0
            else f'<span style="color:{MUTED}">0↓</span>'
        )
        pill_style = "display:inline-block;font-size:0.7rem;padding:1px 6px;border-radius:10px;margin:2px 2px 0 0;white-space:nowrap"
        lifted_pills = "".join(
            f'<span style="{pill_style};background:#052e16;color:{GREEN};border:1px solid #166534">{h} <span style="opacity:0.7">+{delta:.0f}%</span></span>'
            for h, delta in lifted
        )
        suppressed_pills = "".join(
            f'<span style="{pill_style};background:#2d0a0a;color:{RED};border:1px solid #7f1d1d">{h} <span style="opacity:0.7">{delta:.0f}%</span></span>'
            for h, delta in suppressed
        )
        breadth_pills = (
            f'<div style="margin-top:5px;line-height:1.6">{lifted_pills}{suppressed_pills}</div>'
            if (lifted or suppressed)
            else ""
        )
        cr = row["CompletionRate"]
        cr_color = GREEN if cr >= 70 else YELLOW if cr >= 40 else RED
        cr_badge = f'<span style="margin-left:7px;font-size:0.72rem;color:{cr_color};font-weight:400">{cr:.0f}%</span>'
        cons = row["Consistency"]
        cons_color = GREEN if cons >= 70 else YELLOW if cons >= 50 else RED
        rows_html += (
            f"<tr>"
            f'<td style="{TD_STYLE}">{row["Habit"]}{cr_badge}</td>'
            f'<td style="{TD_STYLE};text-align:center;font-weight:600;color:{i_color}">{row["Impact"]:+.1f}%'
            f'<div style="color:{MUTED};font-size:0.75rem;font-weight:400">{int(row["Done Days"])}d done / {int(row["Skip Days"])}d skipped</div></td>'
            f'<td style="{TD_STYLE};text-align:center;font-weight:600;color:{cons_color}">{cons:.0f}%'
            f'<div style="color:{MUTED};font-size:0.75rem;font-weight:400">of done-days above median</div></td>'
            f'<td style="{TD_STYLE}">'
            f'<div style="text-align:center;font-weight:600">{up_str} {down_str}<span style="color:{MUTED};font-weight:400">/{total}</span></div>'
            f"{breadth_pills}</td>"
            f"</tr>"
        )
    header = html_table_open(
        [
            ("Habit", "left"),
            ("Impact", "center"),
            ("Consistency", "center"),
            ("Breadth", "center"),
        ]
    )
    st.markdown(header + rows_html + html_table_close(), unsafe_allow_html=True)
    st.caption(
        f"Only statistically significant habits shown (p < 0.05). Requires ≥{ks_min_days} done and ≥{ks_min_days} skipped days."
    )
    with st.expander("What do these columns mean?"):
        st.markdown(
            "**Habit** — the habit being tested, with its overall completion rate.\n\n"
            "**Impact** — the average other-habit completion rate on done-days minus skipped-days. "
            "A +20% impact means your other habits collectively complete 20 percentage points more often on days you do this habit.\n\n"
            "**Consistency** — of your done-days, what % had other-habit completion above the overall median. "
            "Impact can be inflated by a handful of exceptional days; consistency tells you whether the lift is a dependable pattern. "
            "High impact + low consistency = erratic. High impact + high consistency = reliable.\n\n"
            "**Breadth** — which individual habits are significantly lifted (green) or suppressed (red) on done-days, with their per-habit delta. "
            "The count shows how many out of all other habits are individually affected."
        )
else:
    st.caption(
        f"No statistically significant keystone habits found — need ≥{ks_min_days} done and ≥{ks_min_days} skipped days per habit, with p < 0.05."
    )

with st.expander("Controls"):
    st.slider(
        "Min sample (days)",
        min_value=0,
        max_value=30,
        value=ks_min_days,
        step=5,
        key="ks_min_days",
        help="Minimum done and skipped days required per habit to appear in this table",
    )

st.divider()

# Momentum
st.subheader("Habit Momentum")
st.caption("How strongly yesterday's outcome predicts today's — and whether streaks compound")
mom_rows = []
for habit in pivot.columns:
    col = pivot[habit].dropna()
    if len(col) < 10:
        continue
    both = pd.DataFrame({"today": col, "yesterday": col.shift(1)}).dropna()
    if len(both) < 5:
        continue
    p_done = both[both["yesterday"] == True]["today"].mean()
    p_skip = both[both["yesterday"] == False]["today"].mean()
    if pd.isna(p_done) or pd.isna(p_skip):
        continue
    # Fisher exact test on 2x2 contingency: yesterday x today
    n11 = int(((both["yesterday"] == True) & (both["today"] == True)).sum())
    n10 = int(((both["yesterday"] == True) & (both["today"] == False)).sum())
    n01 = int(((both["yesterday"] == False) & (both["today"] == True)).sum())
    n00 = int(((both["yesterday"] == False) & (both["today"] == False)).sum())
    _, p_val = fisher_exact([[n11, n10], [n01, n00]])
    if p_val >= 0.05:
        continue
    # Streak depth: P(done today | done both yesterday and day before)
    triple = pd.DataFrame(
        {
            "today": col,
            "yesterday": col.shift(1),
            "day_before": col.shift(2),
        }
    ).dropna()
    streak_rows = triple[(triple["yesterday"] == True) & (triple["day_before"] == True)]
    streak_rate = streak_rows["today"].mean() * 100 if len(streak_rows) >= 5 else None
    completion_rate = col.mean() * 100
    mom_rows.append(
        {
            "Habit": habit,
            "CompletionRate": completion_rate,
            "Momentum": (p_done - p_skip) * 100,
            "After1": p_done * 100,
            "Recovery": p_skip * 100,
            "StreakRate": streak_rate,
            "p": p_val,
        }
    )

if mom_rows:
    mom_df = pd.DataFrame(mom_rows).sort_values("Momentum", ascending=False)
    rows_html = ""
    for _, row in mom_df.iterrows():
        m_color = GREEN if row["Momentum"] > 10 else YELLOW if row["Momentum"] > 0 else RED
        cr = row["CompletionRate"]
        cr_color = GREEN if cr >= 70 else YELLOW if cr >= 40 else RED
        cr_badge = f'<span style="margin-left:7px;font-size:0.72rem;color:{cr_color};font-weight:400">{cr:.0f}%</span>'
        rec = row["Recovery"]
        rec_color = GREEN if rec >= 70 else YELLOW if rec >= 40 else RED
        if row["StreakRate"] is not None:
            streak_delta = row["StreakRate"] - row["After1"]
            sd_color = GREEN if streak_delta > 5 else MUTED
            streak_cell = f'{row["StreakRate"]:.0f}%<div style="color:{sd_color};font-size:0.75rem">{streak_delta:+.0f}% vs 1-day</div>'
        else:
            streak_cell = f'<span style="color:{MUTED}">—</span>'
        rows_html += (
            f"<tr>"
            f'<td style="{TD_STYLE}">{row["Habit"]}{cr_badge}</td>'
            f'<td style="{TD_STYLE};text-align:center;font-weight:600;color:{m_color}">{row["Momentum"]:+.0f}%'
            f'<td style="{TD_STYLE};text-align:center;font-weight:600;color:{rec_color}">{rec:.0f}%</td>'
            f'<td style="{TD_STYLE};text-align:center;font-weight:600">{streak_cell}</td>'
            f"</tr>"
        )
    header = html_table_open(
        [
            ("Habit", "left"),
            ("Momentum", "center"),
            ("Recovery", "center"),
            ("2-Day Momentum", "center"),
        ]
    )
    st.markdown(header + rows_html + html_table_close(), unsafe_allow_html=True)
    st.caption("Only statistically significant habits shown (p < 0.05).")
    with st.expander("What do these columns mean?"):
        st.markdown(
            "**Habit** — the habit being tested, with its overall completion rate.\n\n"
            "**Momentum** — how much more likely you are to do this habit today if you did it yesterday vs skipped it. "
            "High momentum = self-reinforcing. Protect streaks for these habits.\n\n"
            "**Recovery** — your probability of doing this habit today after skipping it yesterday. "
            "High recovery = self-correcting, a miss doesn't derail you. "
            "Low recovery = once you break the streak it's hard to restart. "
            "Read this alongside Momentum: high momentum + low recovery = fragile; high momentum + high recovery = robust.\n\n"
            "**2-Day Momentum** — your probability of doing this habit after 2 consecutive done-days, with the delta vs the 1-day rate. "
            "A positive delta means streaks genuinely compound. A flat or negative delta means the habit doesn't build beyond day one."
        )
else:
    st.caption("No statistically significant momentum found.")
st.divider()


# Correlation matrix
st.subheader("Habit Correlations")
habits_list = list(pivot.columns)
n = len(habits_list)
MIN_SHARED = 20


def phi_and_p(a, b):
    """Compute phi coefficient and Fisher exact p-value for two binary arrays."""
    n11 = int(((a == 1) & (b == 1)).sum())
    n10 = int(((a == 1) & (b == 0)).sum())
    n01 = int(((a == 0) & (b == 1)).sum())
    n00 = int(((a == 0) & (b == 0)).sum())
    denom = ((n11 + n10) * (n01 + n00) * (n11 + n01) * (n10 + n00)) ** 0.5
    phi = float((n11 * n00 - n10 * n01) / denom) if denom else 0.0
    _, p = fisher_exact([[n11, n10], [n01, n00]])
    return phi, float(p), n11, n10, n01, n00


# Build phi matrix — NaN for insufficient data
phi_matrix = np.full((n, n), np.nan)
np.fill_diagonal(phi_matrix, 1.0)
pair_rows = []
habits_orig = list(habits_list)
for i in range(n):
    for j in range(i):
        h1, h2 = habits_orig[i], habits_orig[j]
        shared = pivot[[h1, h2]].dropna().astype(int)
        if len(shared) < MIN_SHARED:
            continue
        a, b = shared[h1].values, shared[h2].values
        phi, p, n11, n10, n01, n00 = phi_and_p(a, b)
        phi_matrix[i][j] = phi_matrix[j][i] = phi
        pair_rows.append(
            {
                "Habit A": h1,
                "A Rate": a.mean() * 100,
                "Habit B": h2,
                "B Rate": b.mean() * 100,
                "Both Done": n11 / len(a) * 100,
                "Phi": phi,
                "P": p,
                "Days": len(shared),
            }
        )

# Impute missing pairs with mean of known off-diagonal phi values
# (better than 0 which assumes no correlation and biases clustering)
known_phis = phi_matrix[~np.isnan(phi_matrix) & ~np.eye(n, dtype=bool)]
impute_val = float(np.mean(known_phis)) if len(known_phis) else 0.0
phi_imputed = np.where(np.isnan(phi_matrix), impute_val, phi_matrix)

# Cluster with average linkage, cut at distance 0.7 (phi ≥ 0.3)
# Post-hoc validate each cluster: require avg known phi ≥ 0.3
# and ≥ 50% of pairs to have sufficient data
cluster_labels = None
if n > 2:
    dist = np.clip(1 - phi_imputed, 0, 2)
    np.fill_diagonal(dist, 0)
    Z = linkage(squareform(dist), method="average")
    order = leaves_list(Z)
    cluster_labels_orig = fcluster(Z, t=0.7, criterion="distance")
    habits_list = [habits_orig[i] for i in order]
    cluster_labels = [int(cluster_labels_orig[i]) for i in order]

# ── Habit clusters ────────────────────────────────────────────────────────────
if cluster_labels:
    raw_clusters = defaultdict(list)
    for habit, label in zip(habits_list, cluster_labels, strict=True):
        raw_clusters[label].append(habit)

    validated = []
    for members in raw_clusters.values():
        if len(members) < 3:
            continue
        pairs_total = len(members) * (len(members) - 1) / 2
        known_phi_vals = []
        for ii, ha in enumerate(members):
            for jj, hb in enumerate(members):
                if jj >= ii:
                    continue
                shared = pivot[[ha, hb]].dropna().astype(int)
                if len(shared) < MIN_SHARED:
                    continue
                phi, _, *_ = phi_and_p(shared[ha].values, shared[hb].values)
                known_phi_vals.append(phi)
        if not known_phi_vals:
            continue
        coverage = len(known_phi_vals) / pairs_total
        avg_phi = float(np.mean(known_phi_vals))
        if avg_phi >= 0.3 and coverage >= 0.5:
            validated.append((members, avg_phi))

    if validated:
        st.markdown("**Habit Groups** — habits that tend to rise and fall together")
        for members, avg_phi in sorted(validated, key=lambda x: x[1], reverse=True):
            st.markdown(
                f"- {', '.join(f'**{h}**' for h in members)} "
                f"<span style='color:#888;font-size:0.8rem'>avg phi {avg_phi:+.2f}</span>",
                unsafe_allow_html=True,
            )
        st.caption(
            "Groups require ≥3 habits, avg phi ≥ 0.3, and ≥50% of pairs with sufficient data."
        )
        st.divider()

# Build display matrix (lower triangle, reordered for matrix view)
corr_display = np.full((n, n), np.nan)
corr_text = np.full((n, n), "", dtype=object)
for i, h1 in enumerate(habits_list):
    for j, h2 in enumerate(habits_list):
        if j >= i:
            continue
        shared = pivot[[h1, h2]].dropna().astype(int)
        if len(shared) < MIN_SHARED:
            corr_text[i][j] = "—"
            continue
        a, b = shared[h1].values, shared[h2].values
        phi, _, *_ = phi_and_p(a, b)
        corr_display[i][j] = phi
        corr_text[i][j] = f"{phi:.2f}"

# ── Notable pairs (significant + strong) ─────────────────────────────────────
if pair_rows:
    pairs_df = pd.DataFrame(pair_rows)
    notable = pairs_df[(pairs_df["Phi"].abs() >= 0.3) & (pairs_df["P"] < 0.05)].sort_values(
        "Phi", ascending=False
    )
    positive = notable[notable["Phi"] > 0]
    negative = notable[notable["Phi"] < 0]

    def render_pairs_table(df, section_label, caption_text):
        """Render a styled HTML table of notable habit-pair correlations."""
        rows_html = ""
        for _, row in df.iterrows():
            phi = row["Phi"]
            color = (
                GREEN
                if phi >= 0.4
                else "#86efac"
                if phi >= 0.3
                else RED
                if phi <= -0.4
                else "#fca5a5"
            )
            rows_html += (
                f"<tr>"
                f'<td style="{TD_STYLE}">{row["Habit A"]}'
                f'<span style="color:{MUTED};font-size:0.8rem"> {row["A Rate"]:.0f}%</span></td>'
                f'<td style="{TD_STYLE}">{row["Habit B"]}'
                f'<span style="color:{MUTED};font-size:0.8rem"> {row["B Rate"]:.0f}%</span></td>'
                f'<td style="{TD_STYLE};text-align:center">{row["Both Done"]:.0f}%</td>'
                f'<td style="{TD_STYLE};text-align:center;font-weight:600;color:{color}">{phi:+.2f}</td>'
                f'<td style="{TD_STYLE};text-align:center;color:{MUTED}">{int(row["Days"])}</td>'
                f"</tr>"
            )
        header = html_table_open(
            [
                ("Habit A", "left"),
                ("Habit B", "left"),
                ("Both Done", "center"),
                ("Phi", "center"),
                ("Days", "center"),
            ]
        )
        st.markdown(f"**{section_label}**")
        if rows_html:
            st.markdown(header + rows_html + html_table_close(), unsafe_allow_html=True)
        else:
            st.caption("None with sufficient significance in the selected range.")
        st.caption(caption_text)

    render_pairs_table(
        positive,
        "Habits that tend to happen together",
        "phi ≥ 0.3. Habit completion rates shown in grey. Both Done = % of shared days both completed.",
    )
    render_pairs_table(
        negative.sort_values("Phi"),
        "Habits that rarely happen on the same day",
        "phi ≤ -0.3. Habit completion rates shown in grey. Both Done = % of shared days both completed.",
    )
else:
    st.caption("Not enough shared data yet — need ≥20 days per pair.")

with st.expander("Show correlation matrix"):
    fig3 = go.Figure(
        go.Heatmap(
            z=corr_display,
            x=habits_list,
            y=habits_list,
            colorscale=[[0, "#f87171"], [0.5, "#374151"], [1, "#4ade80"]],
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
    fig3.update_layout(
        height=max(300, n * 45),
        margin=dict(t=10, b=10, l=0, r=0),
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(tickangle=-45),
        yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(fig3, width="stretch")
st.divider()

# Lead/Lag (T-1) Correlations
st.subheader("Lead/Lag Correlations (T-1)")
st.caption(
    "Does yesterday's habit predict today's? Phi coefficient between Habit A done on day T-1 and Habit B done on day T."
)

lag_rows = []
habits_for_lag = list(pivot.columns)
pivot_sorted = pivot.sort_index()

for lead_habit in habits_for_lag:
    for lag_habit in habits_for_lag:
        if lead_habit == lag_habit:
            continue
        combined = (
            pd.DataFrame(
                {
                    "lead": pivot_sorted[lead_habit].shift(1),
                    "lag": pivot_sorted[lag_habit],
                }
            )
            .dropna()
            .astype(int)
        )
        if len(combined) < MIN_SHARED:
            continue
        a, b = combined["lead"].values, combined["lag"].values
        phi, p, n11, n10, n01, n00 = phi_and_p(a, b)
        lag_rows.append(
            {
                "Yesterday (Lead)": lead_habit,
                "Today (Lag)": lag_habit,
                "Lead Rate": a.mean() * 100,
                "Lag Rate": b.mean() * 100,
                "Both": n11 / len(a) * 100,
                "Phi": phi,
                "P": p,
                "Days": len(combined),
            }
        )

if lag_rows:
    lag_df = pd.DataFrame(lag_rows)
    notable_lag = lag_df[(lag_df["Phi"].abs() >= 0.25) & (lag_df["P"] < 0.05)].sort_values(
        "Phi", ascending=False
    )
    pos_lag = notable_lag[notable_lag["Phi"] > 0]
    neg_lag = notable_lag[notable_lag["Phi"] < 0]

    def render_lag_table(df, section_label, caption_text):
        """Render a styled HTML table of notable lead/lag correlations."""
        if df.empty:
            st.markdown(f"**{section_label}**")
            st.caption("None with sufficient significance in the selected range.")
            st.caption(caption_text)
            return
        rows_html = ""
        for _, row in df.iterrows():
            phi = row["Phi"]
            color = (
                GREEN
                if phi >= 0.4
                else "#86efac"
                if phi >= 0.25
                else RED
                if phi <= -0.4
                else "#fca5a5"
            )
            rows_html += (
                f"<tr>"
                f'<td style="{TD_STYLE}">{row["Yesterday (Lead)"]}'
                f'<span style="color:{MUTED};font-size:0.8rem"> {row["Lead Rate"]:.0f}%</span></td>'
                f'<td style="{TD_STYLE}">{row["Today (Lag)"]}'
                f'<span style="color:{MUTED};font-size:0.8rem"> {row["Lag Rate"]:.0f}%</span></td>'
                f'<td style="{TD_STYLE};text-align:center">{row["Both"]:.0f}%</td>'
                f'<td style="{TD_STYLE};text-align:center;font-weight:600;color:{color}">{phi:+.2f}</td>'
                f'<td style="{TD_STYLE};text-align:center;color:{MUTED}">{int(row["Days"])}</td>'
                f"</tr>"
            )
        header = html_table_open(
            [
                ("Yesterday", "left"),
                ("Today", "left"),
                ("Co-occur %", "center"),
                ("Phi", "center"),
                ("Days", "center"),
            ]
        )
        st.markdown(f"**{section_label}**")
        st.markdown(header + rows_html + html_table_close(), unsafe_allow_html=True)
        st.caption(caption_text)

    render_lag_table(
        pos_lag,
        "Yesterday's habit predicts doing today's habit",
        "phi ≥ 0.25. Yesterday's habit completion rate shown in grey next to it. Co-occur % = days both occurred.",
    )
    render_lag_table(
        neg_lag.sort_values("Phi"),
        "Yesterday's habit predicts skipping today's habit",
        "phi ≤ -0.25. A negative lead/lag relationship — worth understanding why.",
    )
else:
    st.caption("Not enough shared data yet — need ≥20 paired days per habit pair.")

st.divider()

# Consistency heatmap
st.subheader("Consistency Heatmap")
habits_sorted = pivot.mean().sort_values(ascending=False).index.tolist()

# Build y-axis labels: "Habit Name  82%"
habit_rates_map = (pivot.mean() * 100).to_dict()
y_labels = [f"{h}  {habit_rates_map[h]:.0f}%" for h in habits_sorted]

# -1 = skipped, 1 = done, NaN = no data (renders as background)
z_numeric = pivot[habits_sorted].apply(lambda col: col.map({True: 1.0, False: -1.0}))
z_vals = z_numeric.T.values.astype(float)

# Daily summary row: completion % mapped to [-1, 1] range
daily_pct = pivot.mean(axis=1) * 100
daily_z_row = (daily_pct.fillna(0) / 50) - 1  # 0%→-1, 50%→0, 100%→1
daily_z_row = daily_z_row.values.reshape(1, -1).astype(float)
daily_hover = np.array([[f"{v:.0f}% of habits done" for v in daily_pct.values]])

z_combined = np.vstack([z_vals, daily_z_row])
y_combined = y_labels + ["── Daily total"]
custom_habit = np.where(np.isnan(z_vals), "no data", np.where(z_vals == 1, "done", "skipped"))
custom_combined = np.vstack([custom_habit, daily_hover])

colorscale = [
    [0.0, "#f87171"],  # -1 → red
    [0.5, "#374151"],  #  0 → gray
    [1.0, "#4ade80"],  #  1 → green
]

# Month boundary ticks
date_strs = pivot.index.strftime("%Y-%m-%d").tolist()
month_starts = pivot.index[pivot.index.to_series().dt.day == 1]
if len(month_starts) >= 1:
    tick_vals = month_starts.strftime("%Y-%m-%d").tolist()
    tick_text = [d.strftime("%b %Y") for d in month_starts]
else:
    tick_vals = tick_text = None

fig4 = go.Figure(
    go.Heatmap(
        z=z_combined,
        x=date_strs,
        y=y_combined,
        colorscale=colorscale,
        zmin=-1,
        zmax=1,
        showscale=False,
        xgap=2,
        ygap=2,
        hovertemplate="%{y}<br>%{x}: %{customdata}<extra></extra>",
        customdata=custom_combined,
    )
)
fig4.update_layout(
    height=max(200, len(y_combined) * 28),
    margin=dict(t=10, b=10, l=0, r=0),
    paper_bgcolor="rgba(0,0,0,0)",
    xaxis=dict(tickvals=tick_vals, ticktext=tick_text, tickangle=-45),
    yaxis=dict(autorange="reversed"),
)
st.plotly_chart(fig4, width="stretch")
