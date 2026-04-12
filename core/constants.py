"""Shared color constants, thresholds, and reference data."""

# ── Colors (Tailwind palette) ────────────────────────────────────────────────

RED = "#f87171"  # Tailwind red-400
YELLOW = "#fbbf24"  # Tailwind amber-400
GREEN = "#4ade80"  # Tailwind green-400
GRAY = "#374151"  # Tailwind gray-700
MUTED = "#6b7280"  # Tailwind gray-500


def rate_color(v: float) -> str:
    """Return green/yellow/red hex color for a 0–100 percentage value."""
    return GREEN if v >= 80 else YELLOW if v >= 50 else RED


# ── Day-of-week reference ────────────────────────────────────────────────────

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAY_TO_ABBR = dict(zip(DAY_ORDER, DAY_ABBR, strict=True))
