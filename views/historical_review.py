"""Historical habit review dashboard.

Provides an all-habits overview (charts, per-habit breakdown, DOW analysis,
keystone habits, momentum, correlations, lead/lag, consistency heatmap) and
a single-habit deep-dive when one is selected in the sidebar.
"""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from analytics.historical import (
    build_correlation_display,
    build_trend_df,
    compute_consistency_data,
    compute_correlations,
    compute_dow_data,
    compute_dow_heatmap_data,
    compute_dow_threshold,
    compute_keystone_habits,
    compute_lead_lag,
    compute_momentum,
    compute_single_habit_momentum,
    compute_trend_rows,
    compute_weekly_rhythm_data,
    validate_clusters,
)
from charts.historical import (
    build_consistency_heatmap,
    build_correlation_matrix,
    build_daily_chart,
    build_dow_heatmap,
    build_monthly_chart,
    build_weekly_chart,
    build_weekly_rhythm,
)
from core.constants import GREEN, MUTED, RED, YELLOW, rate_color
from core.stats import compute_slope, compute_streak, trend_label
from services.data_loader import load_habits
from ui.html_tables import TD_STYLE, habit_tags, html_table_close, html_table_open, trend_cell


def _dow_cards(series: pd.Series):
    """Render day-of-week colored cards for a 0-100 series."""
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


# ── Load data ────────────────────────────────────────────────────────────────


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

# ── Sidebar ──────────────────────────────────────────────────────────────────

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

    from ui.sidebar import render_sidebar_controls

    render_sidebar_controls()


# ── Filter ───────────────────────────────────────────────────────────────────

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
    h_rate_series = h.fillna(False).astype(float) * 100
    h_rate = h.mean() * 100
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
    st.subheader("Completion Over Time")
    st.plotly_chart(build_daily_chart(h_rate_series), width="stretch")
    st.subheader("Weekly Completion Rates")
    st.plotly_chart(build_weekly_chart(h_rate_series), width="stretch")
    st.subheader("Monthly Completion Rates")
    st.plotly_chart(build_monthly_chart(h_rate_series), width="stretch")
    st.divider()

    # Day of week
    st.subheader("Day of Week")
    _dow_cards(h.astype(float) * 100)
    st.divider()

    # Momentum
    momentum_data = compute_single_habit_momentum(h)
    if momentum_data:
        st.subheader("Momentum")
        st.caption("How likely you are to do this habit based on whether you did it yesterday")
        m1, m2, m3 = st.columns(3)
        m1.metric("After doing it", f"{momentum_data['after_doing']:.0f}%")
        m2.metric("After skipping it", f"{momentum_data['after_skipping']:.0f}%")
        m3.metric("Momentum score", f"{momentum_data['score']:+.0f}%")
        st.divider()

    # Weekly rhythm heatmap
    st.subheader("Weekly Rhythm")
    st.caption(
        "Each column is one week · rows are Mon–Sun · green = done · red = skipped · dark = not tracked"
    )
    rhythm_data = compute_weekly_rhythm_data(h)
    st.plotly_chart(build_weekly_rhythm(rhythm_data), width="stretch")

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


def _trend_word(delta):
    if delta is None:
        return "—"
    if delta >= 10:
        return "Improving"
    if delta <= -10:
        return "Declining"
    return "Stable"


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
st.subheader("Daily Completion Rates")
st.plotly_chart(build_daily_chart(daily_rate), width="stretch")
st.subheader("Weekly Completion Rates")
st.plotly_chart(build_weekly_chart(daily_rate), width="stretch")
st.subheader("Monthly Completion Rates")
st.plotly_chart(build_monthly_chart(daily_rate), width="stretch")
st.divider()

# ── Per-habit breakdown ──────────────────────────────────────────────────────

st.subheader("Per-Habit Breakdown")

_DOW_THRESHOLD = compute_dow_threshold(pivot)
trend_rows = compute_trend_rows(pivot, date.today(), _DOW_THRESHOLD)
trend_df = build_trend_df(trend_rows)

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

    _rate_html = f'<span style="color:{rate_color(row["Rate28"])}">{row["Rate28"]:.0f}%</span>'

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

    _trend14_html = trend_cell(row["Trend14"])
    _trend28_html = trend_cell(row["Trend28"])

    if row["BestDays"]:
        _pills = "".join(
            f'<span style="display:inline-block;margin:0 3px 2px 0;padding:1px 7px;'
            f'border-radius:9px;background:#14532d;color:#4ade80;font-size:0.75rem">{d}</span>'
            for d in row["BestDays"]
        )
    else:
        _pills = '<span style="color:#4b5563;font-size:0.8rem">—</span>'

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

# ── Day of week ──────────────────────────────────────────────────────────────

st.subheader("Day of Week")

_dow_day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
dow_data = compute_dow_data(pivot, daily_rate, _DOW_THRESHOLD)

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
    _val = dow_data["dow_avg"][_day]
    if pd.isna(_val):
        _dow_table += (
            f'<tr><td style="{TD_STYLE}">{_day[:3]}</td>'
            f'<td style="{TD_STYLE}" colspan="4"><span style="color:#4b5563">no data</span></td></tr>'
        )
        continue
    _delta = _val - dow_data["dow_overall"]
    _delta_col = GREEN if _delta > 2 else RED if _delta < -2 else MUTED
    _delta_str = f"{_delta:+.0f}pp"
    _pills = dow_data["pills_per_day"][_day]
    _dow_table += (
        f"<tr>"
        f'<td style="{TD_STYLE};font-weight:600">{_day[:3]}</td>'
        f'<td style="{TD_STYLE};text-align:center"><span style="color:{rate_color(_val)}">{_val:.0f}%</span></td>'
        f'<td style="{TD_STYLE};text-align:center"><span style="color:{_delta_col}">{_delta_str}</span></td>'
        f'<td style="{TD_STYLE}">{habit_tags(_pills, positive=False)}</td>'
        f'<td style="{TD_STYLE}">{habit_tags(_pills, positive=True)}</td>'
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
    dow_heatmap_data = compute_dow_heatmap_data(pivot, daily_rate)
    st.plotly_chart(build_dow_heatmap(dow_heatmap_data), width="stretch")
st.divider()

# ── Keystone habits ──────────────────────────────────────────────────────────

st.subheader("Keystone Habits")
st.caption(
    "Which habits, when done, reliably lift your whole routine — and which specific habits they bring with them"
)

ks_min_days = st.session_state.get("ks_min_days", 5)
ks_rows = compute_keystone_habits(pivot, ks_min_days)

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

# ── Momentum ─────────────────────────────────────────────────────────────────

st.subheader("Habit Momentum")
st.caption("How strongly yesterday's outcome predicts today's — and whether streaks compound")

mom_rows = compute_momentum(pivot)

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

# ── Correlations ─────────────────────────────────────────────────────────────

st.subheader("Habit Correlations")

MIN_SHARED = 20
corr_result = compute_correlations(pivot, MIN_SHARED)
habits_list = corr_result["habits_list"]
cluster_labels = corr_result["cluster_labels"]
pair_rows = corr_result["pair_rows"]

# Habit clusters
if cluster_labels:
    validated = validate_clusters(cluster_labels, habits_list, pivot, MIN_SHARED)
    if validated:
        st.markdown("**Habit Groups** — habits that tend to rise and fall together")
        for members, avg_phi in validated:
            st.markdown(
                f"- {', '.join(f'**{h}**' for h in members)} "
                f"<span style='color:#888;font-size:0.8rem'>avg phi {avg_phi:+.2f}</span>",
                unsafe_allow_html=True,
            )
        st.caption(
            "Groups require ≥3 habits, avg phi ≥ 0.3, and ≥50% of pairs with sufficient data."
        )
        st.divider()

# Notable pairs
if pair_rows:
    pairs_df = pd.DataFrame(pair_rows)
    notable = pairs_df[(pairs_df["Phi"].abs() >= 0.3) & (pairs_df["P"] < 0.05)].sort_values(
        "Phi", ascending=False
    )
    positive = notable[notable["Phi"] > 0]
    negative = notable[notable["Phi"] < 0]

    def _render_pairs_table(df, section_label, caption_text):
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
                f'<td style="{TD_STYLE}">{row["Habit A"]}<span style="color:{MUTED};font-size:0.8rem"> {row["A Rate"]:.0f}%</span></td>'
                f'<td style="{TD_STYLE}">{row["Habit B"]}<span style="color:{MUTED};font-size:0.8rem"> {row["B Rate"]:.0f}%</span></td>'
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

    _render_pairs_table(
        positive,
        "Habits that tend to happen together",
        "phi ≥ 0.3. Habit completion rates shown in grey. Both Done = % of shared days both completed.",
    )
    _render_pairs_table(
        negative.sort_values("Phi"),
        "Habits that rarely happen on the same day",
        "phi ≤ -0.3. Habit completion rates shown in grey. Both Done = % of shared days both completed.",
    )
else:
    st.caption("Not enough shared data yet — need ≥20 days per pair.")

with st.expander("Show correlation matrix"):
    corr_display, corr_text = build_correlation_display(habits_list, pivot, MIN_SHARED)
    st.plotly_chart(build_correlation_matrix(corr_display, corr_text, habits_list), width="stretch")
st.divider()

# ── Lead/Lag ─────────────────────────────────────────────────────────────────

st.subheader("Lead/Lag Correlations (T-1)")
st.caption(
    "Does yesterday's habit predict today's? Phi coefficient between Habit A done on day T-1 and Habit B done on day T."
)

lag_rows = compute_lead_lag(pivot, MIN_SHARED)

if lag_rows:
    lag_df = pd.DataFrame(lag_rows)
    notable_lag = lag_df[(lag_df["Phi"].abs() >= 0.25) & (lag_df["P"] < 0.05)].sort_values(
        "Phi", ascending=False
    )
    pos_lag = notable_lag[notable_lag["Phi"] > 0]
    neg_lag = notable_lag[notable_lag["Phi"] < 0]

    def _render_lag_table(df, section_label, caption_text):
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
                f'<td style="{TD_STYLE}">{row["Yesterday (Lead)"]}<span style="color:{MUTED};font-size:0.8rem"> {row["Lead Rate"]:.0f}%</span></td>'
                f'<td style="{TD_STYLE}">{row["Today (Lag)"]}<span style="color:{MUTED};font-size:0.8rem"> {row["Lag Rate"]:.0f}%</span></td>'
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

    _render_lag_table(
        pos_lag,
        "Yesterday's habit predicts doing today's habit",
        "phi ≥ 0.25. Yesterday's habit completion rate shown in grey next to it. Co-occur % = days both occurred.",
    )
    _render_lag_table(
        neg_lag.sort_values("Phi"),
        "Yesterday's habit predicts skipping today's habit",
        "phi ≤ -0.25. A negative lead/lag relationship — worth understanding why.",
    )
else:
    st.caption("Not enough shared data yet — need ≥20 paired days per habit pair.")

st.divider()

# ── Consistency heatmap ──────────────────────────────────────────────────────

st.subheader("Consistency Heatmap")
consistency_data = compute_consistency_data(pivot)
st.plotly_chart(build_consistency_heatmap(consistency_data), width="stretch")
