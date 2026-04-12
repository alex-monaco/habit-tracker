"""Tests for constants, stats, and HTML table helpers — pure functions, no I/O."""

import numpy as np
import pandas as pd

from core.constants import GREEN, RED, YELLOW, rate_color
from core.stats import compute_slope, compute_streak, trend_label
from ui.html_tables import html_table_close, html_table_open

# ── rate_color ────────────────────────────────────────────────────────────────


class TestRateColor:
    def test_above_80_is_green(self):
        assert rate_color(80) == GREEN
        assert rate_color(100) == GREEN
        assert rate_color(95.5) == GREEN

    def test_50_to_79_is_yellow(self):
        assert rate_color(50) == YELLOW
        assert rate_color(79.9) == YELLOW
        assert rate_color(65) == YELLOW

    def test_below_50_is_red(self):
        assert rate_color(0) == RED
        assert rate_color(49.9) == RED
        assert rate_color(25) == RED

    def test_boundary_exactly_80(self):
        assert rate_color(80) == GREEN

    def test_boundary_exactly_50(self):
        assert rate_color(50) == YELLOW

    def test_just_below_80(self):
        assert rate_color(79.99) == YELLOW


# ── compute_streak ────────────────────────────────────────────────────────────


def s(values):
    """Helper: build a boolean Series from a list."""
    return pd.Series(values, dtype=bool)


class TestComputeStreak:
    def test_all_true(self):
        current, best = compute_streak(s([True, True, True]))
        assert current == 3
        assert best == 3

    def test_all_false(self):
        current, best = compute_streak(s([False, False, False]))
        assert current == 0
        assert best == 0

    def test_current_streak_broken_at_end(self):
        # Streak ends (False at tail) — current should be 0
        current, best = compute_streak(s([True, True, False]))
        assert current == 0
        assert best == 2

    def test_current_streak_running(self):
        current, best = compute_streak(s([False, True, True, True]))
        assert current == 3
        assert best == 3

    def test_gap_in_middle(self):
        current, best = compute_streak(s([True, True, False, True]))
        assert current == 1
        assert best == 2

    def test_single_true(self):
        current, best = compute_streak(s([True]))
        assert current == 1
        assert best == 1

    def test_single_false(self):
        current, best = compute_streak(s([False]))
        assert current == 0
        assert best == 0

    def test_empty_series(self):
        current, best = compute_streak(s([]))
        assert current == 0
        assert best == 0

    def test_best_is_longest_run_not_most_recent(self):
        # Long run early, short run at end
        current, best = compute_streak(s([True, True, True, False, True]))
        assert current == 1
        assert best == 3


# ── compute_slope ─────────────────────────────────────────────────────────────


class TestComputeSlope:
    def test_too_short_returns_zeros(self):
        series = pd.Series([100.0] * 5)
        slope, r2, n, volatile = compute_slope(series)
        assert slope == 0.0
        assert r2 == 0.0
        assert n == 5
        assert volatile is False

    def test_exactly_7_points_processed(self):
        series = pd.Series([100.0] * 7)
        slope, r2, n, volatile = compute_slope(series)
        assert n == 7

    def test_flat_series_near_zero_slope(self):
        series = pd.Series([50.0] * 30)
        slope, r2, n, volatile = compute_slope(series)
        assert abs(slope) < 0.01

    def test_increasing_series_positive_slope(self):
        series = pd.Series(np.linspace(0, 100, 30))
        slope, r2, n, volatile = compute_slope(series)
        assert slope > 0

    def test_decreasing_series_negative_slope(self):
        series = pd.Series(np.linspace(100, 0, 30))
        slope, r2, n, volatile = compute_slope(series)
        assert slope < 0

    def test_returns_four_values(self):
        series = pd.Series(range(20))
        result = compute_slope(series)
        assert len(result) == 4

    def test_r2_between_0_and_1(self):
        series = pd.Series(np.linspace(10, 90, 30))
        _, r2, _, _ = compute_slope(series)
        assert 0.0 <= r2 <= 1.0


# ── trend_label ───────────────────────────────────────────────────────────────


class TestTrendLabel:
    def test_volatile_overrides_everything(self):
        assert trend_label(50.0, r2=0.9, volatile=True) == "↕ Volatile"
        assert trend_label(-50.0, r2=0.9, volatile=True) == "↕ Volatile"

    def test_low_r2_is_stable(self):
        assert trend_label(20.0, r2=0.05) == "→ Stable"

    def test_improving(self):
        assert trend_label(10.0, r2=0.8) == "↑ Improving"
        assert trend_label(5.1, r2=0.5) == "↑ Improving"

    def test_declining(self):
        assert trend_label(-10.0, r2=0.8) == "↓ Declining"
        assert trend_label(-5.1, r2=0.5) == "↓ Declining"

    def test_stable_within_threshold(self):
        assert trend_label(5.0, r2=0.8) == "→ Stable"
        assert trend_label(-5.0, r2=0.8) == "→ Stable"
        assert trend_label(0.0, r2=0.8) == "→ Stable"

    def test_boundary_exactly_5(self):
        # 5.0 is NOT > 5, so stable
        assert trend_label(5.0, r2=0.8) == "→ Stable"

    def test_default_r2_and_volatile(self):
        # Defaults: r2=1.0, volatile=False
        assert trend_label(10.0) == "↑ Improving"
        assert trend_label(-10.0) == "↓ Declining"
        assert trend_label(0.0) == "→ Stable"


# ── html_table_open / html_table_close ───────────────────────────────────────


class TestHtmlTable:
    def test_open_contains_column_labels(self):
        html = html_table_open([("Habit", "left"), ("Rate", "center")])
        assert "Habit" in html
        assert "Rate" in html

    def test_open_contains_alignment(self):
        html = html_table_open([("Score", "right")])
        assert "text-align:right" in html

    def test_open_has_table_tag(self):
        html = html_table_open([("A", "left")])
        assert html.startswith("<table")

    def test_open_has_thead_and_tbody(self):
        html = html_table_open([("A", "left")])
        assert "<thead>" in html
        assert "<tbody>" in html

    def test_open_multiple_columns(self):
        cols = [("Name", "left"), ("Streak", "center"), ("Trend", "right")]
        html = html_table_open(cols)
        for label, _ in cols:
            assert label in html

    def test_close_returns_closing_tags(self):
        html = html_table_close()
        assert "</tbody>" in html
        assert "</table>" in html

    def test_open_close_form_valid_structure(self):
        html = html_table_open([("X", "left")]) + "<tr><td>val</td></tr>" + html_table_close()
        assert html.count("<table") == 1
        assert html.count("</table>") == 1
        assert html.count("<tbody>") == 1
        assert html.count("</tbody>") == 1
