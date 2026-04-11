"""Tests for extract_habits.parse_habits — markdown parsing logic."""

from pathlib import Path

import pytest

from extract_habits import parse_habits


@pytest.fixture
def tmp_note(tmp_path):
    """Return a factory that writes a daily note file and returns its Path."""

    def _write(content: str) -> Path:
        p = tmp_path / "2026-01-01.md"
        p.write_text(content, encoding="utf-8")
        return p

    return _write


# ── Happy path ────────────────────────────────────────────────────────────────


class TestParseHabitsHappyPath:
    def test_checked_habit(self, tmp_note):
        p = tmp_note("## Habits\n> - [x] Exercise\n")
        result = parse_habits(p)
        assert result == {"Exercise": True}

    def test_unchecked_habit(self, tmp_note):
        p = tmp_note("## Habits\n> - [ ] Meditate\n")
        result = parse_habits(p)
        assert result == {"Meditate": False}

    def test_multiple_habits_mixed(self, tmp_note):
        content = "## Habits\n> - [x] Exercise\n> - [ ] Meditate\n> - [x] Read\n"
        result = parse_habits(tmp_note(content))
        assert result == {"Exercise": True, "Meditate": False, "Read": True}

    def test_uppercase_X_counts_as_checked(self, tmp_note):
        p = tmp_note("## Habits\n> - [X] Exercise\n")
        result = parse_habits(p)
        assert result["Exercise"] is True


# ── Name cleaning ─────────────────────────────────────────────────────────────


class TestNameCleaning:
    def test_strips_bold_markers(self, tmp_note):
        p = tmp_note("## Habits\n> - [x] **Exercise**\n")
        result = parse_habits(p)
        assert "Exercise" in result
        assert "**Exercise**" not in result

    def test_strips_trailing_parenthetical(self, tmp_note):
        p = tmp_note("## Habits\n> - [x] Exercise (30 min)\n")
        result = parse_habits(p)
        assert "Exercise" in result
        assert "Exercise (30 min)" not in result

    def test_strips_bold_and_parenthetical_together(self, tmp_note):
        p = tmp_note("## Habits\n> - [x] **Exercise** (30 min)\n")
        result = parse_habits(p)
        assert "Exercise" in result

    def test_whitespace_trimmed(self, tmp_note):
        p = tmp_note("## Habits\n> - [x]   Spaced Out   \n")
        result = parse_habits(p)
        assert "Spaced Out" in result

    def test_name_with_internal_spaces_preserved(self, tmp_note):
        p = tmp_note("## Habits\n> - [x] Cold shower\n")
        result = parse_habits(p)
        assert "Cold shower" in result


# ── Missing / malformed sections ─────────────────────────────────────────────


class TestMissingSection:
    def test_no_habits_section_returns_none(self, tmp_note):
        p = tmp_note("## Journal\nSome notes here.\n")
        assert parse_habits(p) is None

    def test_empty_file_returns_none(self, tmp_note):
        p = tmp_note("")
        assert parse_habits(p) is None

    def test_habits_header_but_no_checkboxes_returns_none(self, tmp_note):
        p = tmp_note("## Habits\nJust some text, no checkboxes.\n")
        assert parse_habits(p) is None

    def test_content_before_habits_section_is_ignored(self, tmp_note):
        content = "## Journal\n> - [x] This is not a habit\n## Habits\n> - [x] Real Habit\n"
        result = parse_habits(tmp_note(content))
        assert result == {"Real Habit": True}

    def test_checkboxes_outside_habits_section_ignored(self, tmp_note):
        content = "> - [x] Before the header\n## Habits\n> - [x] Actual Habit\n"
        result = parse_habits(tmp_note(content))
        assert "Before the header" not in result
        assert "Actual Habit" in result


# ── Edge cases ────────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_habit_name_cleaned_to_empty_is_skipped(self, tmp_note):
        # A line whose name vanishes after cleaning should not appear in output
        p = tmp_note("## Habits\n> - [x] **(ignored)**\n")
        result = parse_habits(p)
        # Either None or a dict without an empty-string key
        if result is not None:
            assert "" not in result

    def test_returns_dict_not_none_on_valid_input(self, tmp_note):
        p = tmp_note("## Habits\n> - [x] Exercise\n")
        assert isinstance(parse_habits(p), dict)

    def test_all_habits_unchecked_still_returns_dict(self, tmp_note):
        content = "## Habits\n> - [ ] Exercise\n> - [ ] Meditate\n"
        result = parse_habits(tmp_note(content))
        assert result is not None
        assert all(v is False for v in result.values())
