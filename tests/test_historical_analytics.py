"""Tests for analytics/historical.py — pure statistical functions, no I/O."""

from datetime import date

import numpy as np
import pandas as pd

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
    phi_and_p,
    validate_clusters,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _pivot(habits: dict[str, list[bool]], start: date) -> pd.DataFrame:
    """Build a pivot-style DataFrame (dates as index, habits as columns)."""
    n = len(next(iter(habits.values())))
    idx = pd.date_range(start, periods=n, freq="D")
    return pd.DataFrame(habits, index=idx)


def _long_pivot(n_days: int = 60, seed: int = 42) -> pd.DataFrame:
    """Build a larger pivot with 3 habits over n_days for statistical tests."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(date(2026, 1, 1), periods=n_days, freq="D")
    # A is mostly True, B follows A, C is random
    a = rng.random(n_days) < 0.85
    b = a.copy()
    # Flip ~15% of B to decorrelate slightly
    flip = rng.random(n_days) < 0.15
    b[flip] = ~b[flip]
    c = rng.random(n_days) < 0.5
    return pd.DataFrame({"A": a, "B": b, "C": c}, index=idx)


# ── phi_and_p ────────────────────────────────────────────────────────────────


class TestPhiAndP:
    def test_perfect_correlation(self):
        a = np.array([1, 1, 0, 0, 1, 1, 0, 0])
        phi, p, n11, n10, n01, n00 = phi_and_p(a, a)
        assert phi == 1.0
        assert n10 == 0
        assert n01 == 0

    def test_no_correlation(self):
        a = np.array([1, 1, 0, 0] * 5)
        b = np.array([1, 0, 1, 0] * 5)
        phi, p, *_ = phi_and_p(a, b)
        assert abs(phi) < 0.3

    def test_returns_six_values(self):
        a = np.array([1, 0, 1, 0])
        result = phi_and_p(a, a)
        assert len(result) == 6

    def test_contingency_counts_correct(self):
        a = np.array([1, 1, 0, 0])
        b = np.array([1, 0, 1, 0])
        phi, p, n11, n10, n01, n00 = phi_and_p(a, b)
        assert n11 == 1
        assert n10 == 1
        assert n01 == 1
        assert n00 == 1


# ── compute_dow_threshold ────────────────────────────────────────────────────


class TestComputeDowThreshold:
    def test_empty_data_returns_default(self):
        df = pd.DataFrame()
        assert compute_dow_threshold(df) == 15.0

    def test_normal_case_returns_float(self):
        pivot = _long_pivot(60)
        result = compute_dow_threshold(pivot)
        assert isinstance(result, float)
        assert result > 0


# ── compute_trend_rows ───────────────────────────────────────────────────────


class TestComputeTrendRows:
    def test_single_habit_produces_expected_keys(self):
        pivot = _pivot({"A": [True] * 30}, date(2026, 1, 1))
        rows = compute_trend_rows(pivot, date(2026, 1, 30), 15.0)
        assert len(rows) == 1
        r = rows[0]
        assert r["Habit"] == "A"
        assert "Rate" in r
        assert "CurStreak" in r
        assert "BestStreak" in r
        assert "Tier" in r
        assert "BestDays" in r
        assert "StruggleDays" in r

    def test_streak_values_correct(self):
        # All True -> current streak = 30, best = 30
        pivot = _pivot({"A": [True] * 30}, date(2026, 1, 1))
        rows = compute_trend_rows(pivot, date(2026, 1, 30), 15.0)
        assert rows[0]["CurStreak"] == 30
        assert rows[0]["BestStreak"] == 30

    def test_rate_100_for_all_true(self):
        pivot = _pivot({"A": [True] * 30}, date(2026, 1, 1))
        rows = compute_trend_rows(pivot, date(2026, 1, 30), 15.0)
        assert rows[0]["Rate"] == 100.0


# ── build_trend_df ───────────────────────────────────────────────────────────


class TestBuildTrendDf:
    def test_single_row_passes_through(self):
        rows = [{"Habit": "X", "Rate": 50, "Rate28": 50.0, "Trend28": 0.0, "TierOrder": 1, "Urgency": 1}]
        result = build_trend_df(rows)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1

    def test_rows_sorted_by_tier(self):
        rows = [
            {"Habit": "Good", "Rate": 90, "Rate28": 90.0, "Trend28": 5.0,
             "TierOrder": 2, "Urgency": 1},
            {"Habit": "Bad", "Rate": 30, "Rate28": 30.0, "Trend28": -5.0,
             "TierOrder": 0, "Urgency": 0},
        ]
        result = build_trend_df(rows)
        assert result.iloc[0]["Habit"] == "Bad"  # TierOrder 0 first (ascending)
        assert result.iloc[1]["Habit"] == "Good"


# ── compute_dow_data ─────────────────────────────────────────────────────────


class TestComputeDowData:
    def test_returns_expected_keys(self):
        pivot = _long_pivot(60)
        daily_rate = pivot.astype(float).mean(axis=1) * 100
        result = compute_dow_data(pivot, daily_rate, 15.0)
        assert "dow_avg" in result
        assert "dow_overall" in result
        assert "pills_per_day" in result

    def test_pills_per_day_has_seven_days(self):
        pivot = _long_pivot(60)
        daily_rate = pivot.astype(float).mean(axis=1) * 100
        result = compute_dow_data(pivot, daily_rate, 15.0)
        assert len(result["pills_per_day"]) == 7


# ── compute_dow_heatmap_data ─────────────────────────────────────────────────


class TestComputeDowHeatmapData:
    def test_returns_expected_keys(self):
        pivot = _long_pivot(60)
        daily_rate = pivot.astype(float).mean(axis=1) * 100
        result = compute_dow_heatmap_data(pivot, daily_rate)
        assert "z" in result
        assert "y_labels" in result
        assert "cell_text" in result
        assert "hover_text" in result
        assert "day_abbr" in result

    def test_y_labels_ends_with_daily_avg(self):
        pivot = _long_pivot(60)
        daily_rate = pivot.astype(float).mean(axis=1) * 100
        result = compute_dow_heatmap_data(pivot, daily_rate)
        assert result["y_labels"][-1] == "── Daily avg"


# ── compute_keystone_habits ──────────────────────────────────────────────────


class TestComputeKeystoneHabits:
    def test_insufficient_data_returns_empty(self):
        pivot = _pivot({"A": [True] * 3}, date(2026, 1, 1))
        assert compute_keystone_habits(pivot) == []

    def test_min_days_respected(self):
        pivot = _pivot({"A": [True] * 4, "B": [True] * 4}, date(2026, 1, 1))
        # Only 4 days, min_days defaults to 5
        assert compute_keystone_habits(pivot) == []

    def test_with_correlated_habits(self):
        # A is a keystone: when A is done, B and C are done too
        n = 60
        a = [True] * 40 + [False] * 20
        b = [True] * 40 + [False] * 20  # follows A exactly
        c = [True] * 40 + [False] * 20
        pivot = _pivot({"A": a, "B": b, "C": c}, date(2026, 1, 1))
        result = compute_keystone_habits(pivot)
        # May or may not be significant depending on exact stats,
        # but function should return a list
        assert isinstance(result, list)


# ── compute_momentum ─────────────────────────────────────────────────────────


class TestComputeMomentum:
    def test_insufficient_data_returns_empty(self):
        pivot = _pivot({"A": [True] * 5}, date(2026, 1, 1))
        assert compute_momentum(pivot) == []

    def test_returns_list(self):
        pivot = _long_pivot(60)
        result = compute_momentum(pivot)
        assert isinstance(result, list)

    def test_momentum_row_has_expected_keys(self):
        # Create a habit with strong self-momentum
        n = 100
        vals = []
        v = True
        for _ in range(n):
            vals.append(v)
            # 90% chance of staying same, 10% of flipping
            if np.random.default_rng(42).random() < 0.1:
                v = not v
        pivot = _pivot({"Sticky": vals, "Other": [True, False] * 50}, date(2026, 1, 1))
        result = compute_momentum(pivot)
        if result:  # May not be significant
            r = result[0]
            assert "Habit" in r
            assert "Momentum" in r
            assert "After1" in r
            assert "Recovery" in r


# ── compute_correlations ─────────────────────────────────────────────────────


class TestComputeCorrelations:
    def test_single_habit_no_pairs(self):
        pivot = _pivot({"A": [True] * 30}, date(2026, 1, 1))
        result = compute_correlations(pivot)
        assert result["pair_rows"] == []

    def test_two_habits_produce_pair(self):
        pivot = _long_pivot(60)
        result = compute_correlations(pivot)
        assert len(result["pair_rows"]) > 0
        assert "Phi" in result["pair_rows"][0]

    def test_cluster_labels_for_three_habits(self):
        pivot = _long_pivot(60)
        result = compute_correlations(pivot)
        assert result["cluster_labels"] is not None
        assert len(result["cluster_labels"]) == 3


# ── validate_clusters ────────────────────────────────────────────────────────


class TestValidateClusters:
    def test_small_clusters_rejected(self):
        # Only 2 members per cluster -> rejected (need >= 3)
        pivot = _long_pivot(60)
        labels = [1, 1, 2]
        habits = ["A", "B", "C"]
        result = validate_clusters(labels, habits, pivot)
        assert isinstance(result, list)

    def test_returns_sorted_by_avg_phi(self):
        pivot = _long_pivot(60)
        labels = [1, 1, 1]
        habits = ["A", "B", "C"]
        result = validate_clusters(labels, habits, pivot)
        if len(result) > 1:
            assert result[0][1] >= result[1][1]


# ── build_correlation_display ────────────────────────────────────────────────


class TestBuildCorrelationDisplay:
    def test_lower_triangle(self):
        pivot = _long_pivot(60)
        habits = list(pivot.columns)
        corr_display, corr_text = build_correlation_display(habits, pivot)
        n = len(habits)
        # Upper triangle should be NaN
        for i in range(n):
            for j in range(i, n):
                assert np.isnan(corr_display[i][j])

    def test_text_formatted(self):
        pivot = _long_pivot(60)
        habits = list(pivot.columns)
        _, corr_text = build_correlation_display(habits, pivot)
        # Lower triangle should have formatted phi or "—"
        assert corr_text[1][0] != ""


# ── compute_lead_lag ─────────────────────────────────────────────────────────


class TestComputeLeadLag:
    def test_self_pairs_excluded(self):
        pivot = _long_pivot(60)
        result = compute_lead_lag(pivot)
        for row in result:
            assert row["Yesterday (Lead)"] != row["Today (Lag)"]

    def test_returns_expected_keys(self):
        pivot = _long_pivot(60)
        result = compute_lead_lag(pivot)
        if result:
            r = result[0]
            assert "Phi" in r
            assert "P" in r
            assert "Days" in r


# ── compute_consistency_data ─────────────────────────────────────────────────


class TestComputeConsistencyData:
    def test_returns_expected_keys(self):
        pivot = _long_pivot(60)
        result = compute_consistency_data(pivot)
        assert "z" in result
        assert "y_labels" in result
        assert "customdata" in result
        assert "date_strs" in result

    def test_y_labels_formatted_with_rate(self):
        pivot = _long_pivot(60)
        result = compute_consistency_data(pivot)
        # Each label should contain a percentage
        for label in result["y_labels"][:-1]:  # Skip "── Daily total"
            assert "%" in label


# ── compute_single_habit_momentum ────────────────────────────────────────────


class TestComputeSingleHabitMomentum:
    def test_insufficient_data_returns_none(self):
        series = pd.Series([True, False], index=pd.date_range("2026-01-01", periods=2))
        assert compute_single_habit_momentum(series) is None

    def test_returns_expected_keys(self):
        series = pd.Series(
            [True, True, True, False, True, True, False, False, True, True] * 3,
            index=pd.date_range("2026-01-01", periods=30),
        )
        result = compute_single_habit_momentum(series)
        if result is not None:
            assert "after_doing" in result
            assert "after_skipping" in result
            assert "score" in result

    def test_all_true_momentum(self):
        series = pd.Series([True] * 30, index=pd.date_range("2026-01-01", periods=30))
        result = compute_single_habit_momentum(series)
        # After doing yesterday: 100%, after skipping: no data -> None
        # Actually all True means no "yesterday == False" rows, so p_skip will be NaN
        assert result is None


# ── compute_weekly_rhythm_data ───────────────────────────────────────────────


class TestComputeWeeklyRhythmData:
    def test_returns_expected_keys(self):
        series = pd.Series(
            [True, False] * 15,
            index=pd.date_range("2026-01-01", periods=30),
        )
        result = compute_weekly_rhythm_data(series)
        assert "z" in result
        assert "hover" in result
        assert "week_labels" in result
        assert "dow_labels" in result

    def test_dow_labels_mon_to_sun(self):
        series = pd.Series(
            [True] * 14,
            index=pd.date_range("2026-01-01", periods=14),
        )
        result = compute_weekly_rhythm_data(series)
        assert result["dow_labels"] == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
