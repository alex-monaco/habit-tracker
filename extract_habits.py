"""Extract habit completion data from Obsidian daily notes into JSON."""

import json
import re
from datetime import date, timedelta
from pathlib import Path

CHECKBOX_RE = re.compile(r">\s*-\s*\[(x| )\]\s*(.+)", re.IGNORECASE)
_NOTES_SUBPATH = "03-Resources/Calendar/Daily Notes"


def parse_habits(filepath: Path) -> dict | None:
    """Parse habits from a daily note file. Returns None if no habits section."""
    text = filepath.read_text(encoding="utf-8")

    match = re.search(r"^## Habits\s*$", text, re.MULTILINE)
    if not match:
        return None

    habits_text = text[match.end() :]
    habits = {}

    for m in CHECKBOX_RE.finditer(habits_text):
        checked = m.group(1).lower() == "x"
        raw_name = m.group(2)

        name = raw_name.replace("**", "")
        name = re.sub(r"\s*\(.*?\)\s*$", "", name)
        name = name.strip()

        if name:
            habits[name] = checked

    return habits or None


def extract(vault_dir: str | Path, start: date, end: date, output_path: str | Path) -> str:
    """Extract habits from vault for a date range, merging into output_path.

    Returns a human-readable summary string.
    """
    daily_notes_dir = Path(vault_dir) / _NOTES_SUBPATH
    output_path = Path(output_path)

    data = {}
    if output_path.exists():
        data = json.loads(output_path.read_text(encoding="utf-8"))

    current = start
    while current <= end:
        date_str = current.isoformat()
        filepath = daily_notes_dir / f"{date_str}.md"
        if filepath.exists():
            habits = parse_habits(filepath)
            if habits is not None:
                data[date_str] = habits
        current += timedelta(days=1)

    sorted_data = dict(sorted(data.items()))
    output_path.write_text(
        json.dumps(sorted_data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    dates_in_range = [d for d in sorted_data if start.isoformat() <= d <= end.isoformat()]
    return (
        f"Processed {len(dates_in_range)} days ({start} to {end})\n"
        f"Total days in file: {len(sorted_data)}"
    )
