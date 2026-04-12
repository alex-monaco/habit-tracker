"""Tests for analytics/week_review.py — pure business logic, no I/O."""

from datetime import date, timedelta

import pandas as pd

from analytics.week_review import (
    avg_wk_range,
    build_habit_rows,
    classify_habits,
    days_above_80,
    days_above_80_delta,
    habit_avg_wk,
    overall_trend,
    overall_trend_d80,
    tier,
    trend_delta_info,
    window_avg,
    window_delta,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_df(habits: dict[str, list[bool]], start: date) -> pd.DataFrame:
    """Build a DataFrame with a DatetimeIndex from a dict of habit -> daily bools."""
    n = len(next(iter(habits.values())))
    idx = pd.date_range(start, periods=n, freq="D")
    return pd.DataFrame(habits, index=idx)


EMPTY_DF = pd.DataFrame(index=pd.DatetimeIndex([], name="date"))


# ── window_avg ───────────────────────────────────────────────────────────────


class TestWindowAvg:
    def test_empty_df_returns_none(self):
        assert window_avg(EMPTY_DF, date(2026, 3, 1), 7) is None

    def test_all_true_returns_100(self):
        df = _make_df({"A": [True] * 7, "B": [True] * 7}, date(2026, 3, 1))
        result = window_avg(df, date(2026, 3, 7), 7)
        assert result == 100.0

    def test_half_true_returns_50(self):
        df = _make_df({"A": [True] * 7, "B": [False] * 7}, date(2026, 3, 1))
        result = window_avg(df, date(2026, 3, 7), 7)
        assert result == 50.0

    def test_custom_end_date(self):
        df = _make_df({"A": [True] * 14}, date(2026, 3, 1))
        # Only look at the first 7 days
        result = window_avg(df, date(2026, 3, 14), 7, end=date(2026, 3, 7))
        assert result == 100.0


# ── window_delta ─────────────────────────────────────────────────────────────


class TestWindowDelta:
    def test_no_data_returns_dash(self):
        cur, delta, color = window_delta(EMPTY_DF, date(2026, 3, 1), 7)
        assert cur == "—"
        assert delta is None

    def test_stable_delta(self):
        # Both windows at 100% -> delta is 0 -> stable
        df = _make_df({"A": [True] * 14}, date(2026, 3, 1))
        cur, delta, color = window_delta(df, date(2026, 3, 14), 7)
        assert "%" in cur
        assert delta == "-> stable"

    def test_large_delta(self):
        # First 7 days all False, next 7 all True -> big positive delta
        df = _make_df({"A": [False] * 7 + [True] * 7}, date(2026, 3, 1))
        cur, delta, color = window_delta(df, date(2026, 3, 14), 7)
        assert "%" in cur
        assert "+" in delta


# ── days_above_80 ────────────────────────────────────────────────────────────


class TestDaysAbove80:
    def test_empty_returns_none(self):
        assert days_above_80(EMPTY_DF, date(2026, 3, 1), 7) is None

    def test_all_100_returns_7(self):
        df = _make_df({"A": [True] * 7}, date(2026, 3, 1))
        result = days_above_80(df, date(2026, 3, 7), 7)
        assert result == 7.0

    def test_mixed_rates(self):
        # 5 habits, only 3 True on each day -> 60% < 80%, so 0 days above 80
        df = _make_df(
            {f"H{i}": [True] * 7 for i in range(3)}
            | {f"L{i}": [False] * 7 for i in range(2)},
            date(2026, 3, 1),
        )
        result = days_above_80(df, date(2026, 3, 7), 7)
        assert result == 0.0


# ── days_above_80_delta ──────────────────────────────────────────────────────


class TestDaysAbove80Delta:
    def test_no_data_returns_dash(self):
        cur, delta, color = days_above_80_delta(EMPTY_DF, date(2026, 3, 1), 7)
        assert cur == "—"
        assert delta is None

    def test_stable(self):
        df = _make_df({"A": [True] * 14}, date(2026, 3, 1))
        cur, delta, color = days_above_80_delta(df, date(2026, 3, 14), 7)
        assert "/7" in cur
        assert delta == "-> stable"

    def test_changing(self):
        df = _make_df({"A": [False] * 7 + [True] * 7}, date(2026, 3, 1))
        cur, delta, color = days_above_80_delta(df, date(2026, 3, 14), 7)
        assert "/7" in cur
        assert "/wk" in delta


# ── overall_trend ────────────────────────────────────────────────────────────


class TestOverallTrend:
    def test_insufficient_data_returns_dash(self):
        assert overall_trend(EMPTY_DF, date(2026, 3, 1)) == "—"

    def test_solid(self):
        # 84 days of all True -> both recent and prior are 100%
        df = _make_df({"A": [True] * 84}, date(2026, 1, 1))
        assert overall_trend(df, date(2026, 3, 25)) == "Solid"

    def test_struggling(self):
        # 84 days of all False -> both windows at 0%
        df = _make_df({"A": [False] * 84}, date(2026, 1, 1))
        assert overall_trend(df, date(2026, 3, 25)) == "Struggling"

    def test_improving(self):
        # Prior 56 days low, recent 28 days high
        df = _make_df({"A": [False] * 56 + [True] * 28}, date(2026, 1, 1))
        assert overall_trend(df, date(2026, 3, 25)) == "Improving"

    def test_slipping(self):
        # Prior 56 days high, recent 28 days low
        df = _make_df({"A": [True] * 56 + [False] * 28}, date(2026, 1, 1))
        assert overall_trend(df, date(2026, 3, 25)) == "Slipping"


# ── overall_trend_d80 ───────────────────────────────────────────────────────


class TestOverallTrendD80:
    def test_insufficient_data_returns_dash(self):
        assert overall_trend_d80(EMPTY_DF, date(2026, 3, 1)) == "—"

    def test_solid(self):
        df = _make_df({"A": [True] * 84}, date(2026, 1, 1))
        assert overall_trend_d80(df, date(2026, 3, 25)) == "Solid"

    def test_struggling(self):
        df = _make_df({"A": [False] * 84}, date(2026, 1, 1))
        assert overall_trend_d80(df, date(2026, 3, 25)) == "Struggling"

    def test_improving(self):
        df = _make_df({"A": [False] * 56 + [True] * 28}, date(2026, 1, 1))
        assert overall_trend_d80(df, date(2026, 3, 25)) == "Improving"


# ── trend_delta_info ─────────────────────────────────────────────────────────


class TestTrendDeltaInfo:
    def test_both_none(self):
        delta_str, color, arrow = trend_delta_info(None, None, 5.0, "{:+.0f}pp")
        assert delta_str is None

    def test_stable(self):
        delta_str, color, arrow = trend_delta_info(80.0, 78.0, 5.0, "{:+.0f}pp")
        assert delta_str == "-> stable"
        assert color == "off"

    def test_above_threshold(self):
        delta_str, color, arrow = trend_delta_info(80.0, 60.0, 5.0, "{:+.0f}pp vs prior 56d")
        assert "+20pp" in delta_str

    def test_below_threshold_negative(self):
        delta_str, color, arrow = trend_delta_info(60.0, 80.0, 5.0, "{:+.0f}pp")
        assert "-20pp" in delta_str


# ── avg_wk_range ─────────────────────────────────────────────────────────────


class TestAvgWkRange:
    def test_missing_habit_returns_none(self):
        df = _make_df({"A": [True] * 7}, date(2026, 3, 1))
        assert avg_wk_range(df, "B", date(2026, 3, 1), date(2026, 3, 7)) is None

    def test_empty_range_returns_none(self):
        df = _make_df({"A": [True] * 7}, date(2026, 3, 1))
        # Date range outside data
        assert avg_wk_range(df, "A", date(2026, 4, 1), date(2026, 4, 7)) is None

    def test_all_true_returns_7(self):
        df = _make_df({"A": [True] * 7}, date(2026, 3, 1))
        result = avg_wk_range(df, "A", date(2026, 3, 1), date(2026, 3, 7))
        assert result == 7.0


# ── habit_avg_wk ─────────────────────────────────────────────────────────────


class TestHabitAvgWk:
    def test_formats_correctly(self):
        df = _make_df({"A": [True] * 7}, date(2026, 3, 1))
        assert habit_avg_wk(df, date(2026, 3, 7), "A", 7) == "7.0"

    def test_missing_habit_returns_dash(self):
        df = _make_df({"A": [True] * 7}, date(2026, 3, 1))
        assert habit_avg_wk(df, date(2026, 3, 7), "B", 7) == "—"


# ── build_habit_rows ─────────────────────────────────────────────────────────


class TestBuildHabitRows:
    def test_empty_habits_list(self):
        df = _make_df({"A": [True] * 7}, date(2026, 3, 1))
        assert build_habit_rows(df, date(2026, 3, 7), []) == []

    def test_single_habit(self):
        df = _make_df({"A": [True] * 90}, date(2026, 1, 1))
        rows = build_habit_rows(df, date(2026, 3, 31), ["A"])
        assert len(rows) == 1
        assert rows[0]["Habit"] == "A"
        assert "7-day" in rows[0]
        assert "28-day" in rows[0]
        assert "84-day" in rows[0]
        assert "prior 56-day" in rows[0]


# ── tier ─────────────────────────────────────────────────────────────────────


class TestTier:
    def test_high_value_green(self):
        assert tier("7.0") == 2

    def test_mid_value_yellow(self):
        assert tier("5.0") == 1

    def test_low_value_red(self):
        assert tier("2.0") == 0

    def test_dash_returns_none(self):
        assert tier("—") is None

    def test_boundary_6_is_green(self):
        assert tier("6.0") == 2

    def test_boundary_4_is_yellow(self):
        assert tier("4.0") == 1

    def test_just_below_6(self):
        assert tier("5.9") == 1

    def test_just_below_4(self):
        assert tier("3.9") == 0


# ── classify_habits ──────────────────────────────────────────────────────────


class TestClassifyHabits:
    def test_solid_habit(self):
        # Habit always done for 90 days -> both t28 and t_prior are tier 2
        df = _make_df({"A": [True] * 90}, date(2026, 1, 1))
        rows = build_habit_rows(df, date(2026, 3, 31), ["A"])
        buckets = classify_habits(rows, df, date(2026, 3, 31))
        assert len(buckets["solid"]) == 1
        assert buckets["solid"][0][0] == "A"

    def test_struggling_habit(self):
        # Habit never done -> both tiers are 0
        df = _make_df({"A": [False] * 90}, date(2026, 1, 1))
        rows = build_habit_rows(df, date(2026, 3, 31), ["A"])
        buckets = classify_habits(rows, df, date(2026, 3, 31))
        assert len(buckets["struggling"]) == 1

    def test_insufficient_data(self):
        # Only 7 days of data -> prior 56-day will be "—"
        df = _make_df({"A": [True] * 7}, date(2026, 3, 25))
        rows = build_habit_rows(df, date(2026, 3, 31), ["A"])
        buckets = classify_habits(rows, df, date(2026, 3, 31))
        assert len(buckets["insufficient"]) == 1

    def test_improving_habit(self):
        # Prior low, recent high
        df = _make_df({"A": [False] * 56 + [True] * 28 + [True] * 6}, date(2026, 1, 1))
        rows = build_habit_rows(df, date(2026, 3, 31), ["A"])
        buckets = classify_habits(rows, df, date(2026, 3, 31))
        assert len(buckets["improving"]) == 1
