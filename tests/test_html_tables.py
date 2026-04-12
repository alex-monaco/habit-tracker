"""Tests for ui/html_tables.py — table primitives, trend cells, and habit pills."""

import numpy as np

from core.constants import GREEN, MUTED, RED
from ui.html_tables import habit_tags, html_table_close, html_table_open, trend_cell


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


# ── trend_cell ───────────────────────────────────────────────────────────────


class TestTrendCell:
    def test_none_returns_dash(self):
        result = trend_cell(None)
        assert "—" in result

    def test_nan_returns_dash(self):
        result = trend_cell(float("nan"))
        assert "—" in result

    def test_large_positive_delta_green_up(self):
        result = trend_cell(15)
        assert GREEN in result
        assert "↑" in result
        assert "+15pp" in result

    def test_large_negative_delta_red_down(self):
        result = trend_cell(-20)
        assert RED in result
        assert "↓" in result
        assert "-20pp" in result

    def test_small_delta_muted_arrow(self):
        result = trend_cell(5)
        assert MUTED in result
        assert "→" in result

    def test_boundary_exactly_10_is_muted(self):
        result = trend_cell(10)
        assert "→" in result

    def test_boundary_exactly_neg10_is_muted(self):
        result = trend_cell(-10)
        assert "→" in result

    def test_just_above_10_is_green(self):
        result = trend_cell(10.1)
        assert "↑" in result


# ── habit_tags ───────────────────────────────────────────────────────────────


class TestHabitTags:
    def test_empty_list_returns_dash(self):
        result = habit_tags([], positive=True)
        assert "—" in result

    def test_positive_tag_green(self):
        result = habit_tags([("Exercise", 15)], positive=True)
        assert GREEN in result
        assert "Exercise" in result
        assert "+15pp" in result

    def test_negative_tag_red(self):
        result = habit_tags([("Reading", -12)], positive=False)
        assert RED in result
        assert "Reading" in result
        assert "-12pp" in result

    def test_positive_mode_ignores_negative_deviations(self):
        result = habit_tags([("A", -5), ("B", 10)], positive=True)
        assert "B" in result
        assert "A" not in result or "—" not in result

    def test_negative_mode_ignores_positive_deviations(self):
        result = habit_tags([("A", 5), ("B", -10)], positive=False)
        assert "B" in result
        # A has positive deviation, should not appear in negative mode
        assert "A" not in result.split("B")[0] or result.count("A") == 0

    def test_zero_deviation_excluded(self):
        result = habit_tags([("A", 0)], positive=True)
        assert "—" in result
