"""Business logic for the weekly review page.

Pure computation — no Streamlit imports. All functions take a DataFrame
and reference date as arguments so they remain testable and stateless.
"""

from datetime import date, timedelta

import pandas as pd

# ── Window averages ──────────────────────────────────────────────────────────


def window_avg(
    df: pd.DataFrame, last_date: date, days: int, end: date | None = None
) -> float | None:
    """Overall completion rate as a float [0-100] over *days* ending on *end*."""
    end = end or last_date
    start = end - timedelta(days=days - 1)
    w = df[(df.index.date >= start) & (df.index.date <= end)].astype(float)
    return w.mean(axis=1).mean() * 100 if not w.empty else None


def window_delta(df: pd.DataFrame, last_date: date, days: int) -> tuple[str, str | None, str]:
    """Return (current_pct_str, delta_str, delta_color) comparing current vs prior window."""
    current = window_avg(df, last_date, days)
    prior_end = last_date - timedelta(days=days)
    prior = window_avg(df, last_date, days, end=prior_end)
    if current is None:
        return "—", None, "normal"
    cur_str = f"{current:.0f}%"
    if prior is None:
        return cur_str, None, "normal"
    delta = current - prior
    if abs(delta) < 5:
        return cur_str, "-> stable", "off"
    return cur_str, f"{delta:+.0f}pp", "normal"


# ── Days above 80% ──────────────────────────────────────────────────────────


def days_above_80(
    df: pd.DataFrame, last_date: date, days: int, end: date | None = None
) -> float | None:
    """Average days/week where daily completion >= 80%."""
    end = end or last_date
    start = end - timedelta(days=days - 1)
    w = df[(df.index.date >= start) & (df.index.date <= end)].astype(float)
    if w.empty:
        return None
    rates = w.mean(axis=1) * 100
    chunks = [rates.iloc[i : i + 7] for i in range(0, len(rates), 7)]
    return sum((c >= 80).sum() for c in chunks) / len(chunks)


def days_above_80_delta(
    df: pd.DataFrame, last_date: date, days: int
) -> tuple[str, str | None, str]:
    """Return (value_str, delta_str, delta_color) for days-above-80% vs prior window."""
    current = days_above_80(df, last_date, days)
    if current is None:
        return "—", None, "normal"
    cur_str = f"{current:.1f}/7"
    prior_end = last_date - timedelta(days=days)
    prior = days_above_80(df, last_date, days, end=prior_end)
    if prior is None:
        return cur_str, None, "normal"
    delta = current - prior
    if abs(delta) < 0.5:
        return cur_str, "-> stable", "off"
    return cur_str, f"{delta:+.1f}/wk", "normal"


# ── Overall trends ───────────────────────────────────────────────────────────


def overall_trend(df: pd.DataFrame, last_date: date) -> str:
    """One-word overall trend: compare last 28d completion % to prior 56d."""
    recent = window_avg(df, last_date, 28)
    prior = window_avg(df, last_date, 56, end=last_date - timedelta(days=28))
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


def overall_trend_d80(df: pd.DataFrame, last_date: date) -> str:
    """One-word trend for days-above-80%: compare last 28d to prior 56d."""
    recent = days_above_80(df, last_date, 28)
    prior = days_above_80(df, last_date, 56, end=last_date - timedelta(days=28))
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


def trend_delta_info(
    recent: float | None, prior: float | None, threshold: float, fmt: str
) -> tuple[str | None, str, str]:
    """Compute (delta_str, delta_color, delta_arrow) for a trend metric.

    *fmt* is a format string like "{:+.0f}pp vs prior 56d" or "{:+.1f}/wk vs prior 56d".
    """
    if recent is not None and prior is not None:
        raw_delta = recent - prior
        if abs(raw_delta) < threshold:
            return "-> stable", "off", "off"
        return fmt.format(raw_delta), "normal", "auto"
    return None, "normal", "auto"


# ── Per-habit averages ───────────────────────────────────────────────────────


def avg_wk_range(df: pd.DataFrame, habit: str, start: date, end: date) -> float | None:
    """Float avg/wk for habit over [start, end], or None if no data."""
    if habit not in df.columns:
        return None
    col = df[(df.index.date >= start) & (df.index.date <= end)][habit].astype(float).dropna()
    return col.mean() * 7 if not col.empty else None


def habit_avg_wk(df: pd.DataFrame, last_date: date, habit: str, days: int) -> str:
    """Format a single habit's avg completions/week over the last *days* days."""
    start = last_date - timedelta(days=days - 1)
    v = avg_wk_range(df, habit, start, last_date)
    return f"{v:.1f}" if v is not None else "—"


def build_habit_rows(df: pd.DataFrame, last_date: date, habits: list[str]) -> list[dict]:
    """Build per-habit avg/wk rows for the 7-day, 28-day, 84-day, and prior-56-day windows."""
    prior_start = last_date - timedelta(days=83)
    prior_end = last_date - timedelta(days=28)

    def _fmt(v):
        return f"{v:.1f}" if v is not None else "—"

    return [
        {
            "Habit": h,
            "7-day": habit_avg_wk(df, last_date, h, 7),
            "28-day": habit_avg_wk(df, last_date, h, 28),
            "84-day": habit_avg_wk(df, last_date, h, 84),
            "prior 56-day": _fmt(avg_wk_range(df, h, prior_start, prior_end)),
        }
        for h in habits
    ]


# ── Trend classification ────────────────────────────────────────────────────


def tier(val_str: str) -> int | None:
    """Map an avg/wk string to a tier: 2 (green), 1 (yellow), 0 (red), or None."""
    try:
        v = float(val_str)
        return 2 if v >= 6.0 else 1 if v >= 4.0 else 0
    except (ValueError, TypeError):
        return None


def classify_habits(rows: list[dict], df: pd.DataFrame, last_date: date) -> dict[str, list]:
    """Classify habits into trend buckets: struggling, slipping, improving, okay, solid, insufficient.

    Returns a dict with those keys, each containing a list of tuples.
    """
    recent_start = last_date - timedelta(days=27)
    prior_start = last_date - timedelta(days=83)
    prior_end = last_date - timedelta(days=28)

    buckets = {
        "struggling": [],
        "slipping": [],
        "improving": [],
        "okay": [],
        "solid": [],
        "insufficient": [],
    }

    for r in rows:
        h = r["Habit"]
        t7 = tier(r["7-day"])
        t28 = tier(r["28-day"])
        t_prior = tier(r["prior 56-day"])

        if t7 is None or t28 is None or t_prior is None:
            buckets["insufficient"].append((h, r["7-day"], r["28-day"], r["prior 56-day"]))
            continue

        if t28 == 2 and t_prior == 2:
            buckets["solid"].append((h, r["7-day"], r["28-day"], r["prior 56-day"]))
            continue

        if t28 == 0 and t_prior == 0:
            buckets["struggling"].append((h, r["7-day"], r["28-day"], r["prior 56-day"]))
            continue

        v_recent = avg_wk_range(df, h, recent_start, last_date)
        v_prior = avg_wk_range(df, h, prior_start, prior_end)

        if v_recent is None or v_prior is None:
            buckets["insufficient"].append((h, r["7-day"], r["28-day"], r["prior 56-day"]))
            continue

        delta = round(v_recent - v_prior, 1)
        delta_str = f"{delta:+.1f}/wk vs prior 56 days"

        if delta <= -0.5:
            buckets["slipping"].append((h, r["7-day"], r["28-day"], r["prior 56-day"], delta_str))
        elif delta >= 0.5:
            buckets["improving"].append((h, r["7-day"], r["28-day"], r["prior 56-day"], delta_str))
        else:
            buckets["okay"].append((h, r["7-day"], r["28-day"], r["prior 56-day"]))

    return buckets
