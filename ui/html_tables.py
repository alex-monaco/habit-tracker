"""Reusable HTML table rendering primitives for dark-mode Streamlit dashboards."""

import numpy as np

from core.constants import GREEN, MUTED, RED

# Common cell style used across all hand-built tables
TD_STYLE = "padding:10px 14px;border-bottom:1px solid #1f2937"

# Header cell style (slightly different border color)
TH_STYLE = "padding:8px 14px;text-align:left;border-bottom:1px solid #374151"


def html_table_open(columns: list[tuple[str, str]]) -> str:
    """Return the opening <table><thead>...<tbody> HTML for a dark-mode table.

    *columns* is a list of (label, alignment) tuples, e.g.:
        [("Habit", "left"), ("Rate", "center")]
    """
    header_cells = "".join(
        f'<th style="{TH_STYLE};text-align:{align}">{label}</th>' for label, align in columns
    )
    return (
        '<table style="width:100%;border-collapse:collapse;font-size:0.9rem">'
        '<thead><tr style="color:#9ca3af;font-size:0.8rem;'
        'text-transform:uppercase;letter-spacing:0.05em">'
        f"{header_cells}"
        "</tr></thead><tbody>"
    )


def html_table_close() -> str:
    """Return the closing </tbody></table> tags."""
    return "</tbody></table>"


def trend_cell(delta) -> str:
    """Return an HTML span with colored arrow + pp delta for a trend cell."""
    if delta is None or (isinstance(delta, float) and np.isnan(delta)):
        return '<span style="color:#4b5563;font-size:0.8rem">—</span>'
    color = GREEN if delta > 10 else RED if delta < -10 else MUTED
    arrow = "↑" if delta > 10 else "↓" if delta < -10 else "→"
    return f'<span style="color:{color}">{arrow} {delta:+.0f}pp</span>'


def habit_tags(habits, positive) -> str:
    """Render colored pill-style HTML tags for habits deviating from their DOW average."""
    html = ""
    for h, dev in habits:
        if (positive and dev > 0) or (not positive and dev < 0):
            c = GREEN if positive else RED
            html += (
                f'<span style="display:inline-block;padding:1px 7px;margin:2px 2px;'
                f'border-radius:10px;border:1px solid {c};color:{c};font-size:0.72rem" '
                f'title="{h}">{h} {dev:+.0f}pp</span>'
            )
    return html or '<span style="color:#4b5563;font-size:0.72rem">—</span>'
