"""Shared sidebar controls rendered on every page."""

import subprocess
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

from auth import render_auth_controls
from data_loader import (
    can_run_extraction,
    data_source_label,
    local_habits_path,
    persist_habits_after_extract,
)

_EXTRACT_SCRIPT = Path(__file__).resolve().parent / "extract_habits.py"


def render_sidebar_controls(max_date: date):
    """Render the Extract latest and Reload data buttons into the sidebar."""
    st.sidebar.divider()

    if can_run_extraction() and st.sidebar.button("⬇ Extract latest", width="stretch"):
        _next_day = (max_date + timedelta(days=1)).isoformat()
        _yesterday = (date.today() - timedelta(days=1)).isoformat()
        if _next_day <= _yesterday:
            _result = subprocess.run(
                [
                    "python3",
                    str(_EXTRACT_SCRIPT),
                    "--start",
                    _next_day,
                    "--end",
                    _yesterday,
                    "--output",
                    str(local_habits_path()),
                ],
                capture_output=True,
                text=True,
            )
            if _result.returncode == 0:
                try:
                    persist_habits_after_extract()
                    st.session_state["_extract_msg"] = ("success", _result.stdout.strip())
                except Exception as e:
                    st.session_state["_extract_msg"] = (
                        "error",
                        f"Extracted locally but remote sync failed: {e}",
                    )
            else:
                st.session_state["_extract_msg"] = ("error", _result.stderr.strip())
        else:
            st.session_state["_extract_msg"] = ("info", "Already up to date.")
        st.cache_data.clear()
        st.rerun()

    if "_extract_msg" in st.session_state:
        _kind, _msg = st.session_state.pop("_extract_msg")
        {"success": st.sidebar.success, "error": st.sidebar.error, "info": st.sidebar.info}[_kind](
            _msg
        )

    if st.sidebar.button("↺ Reload data", width="stretch"):
        st.cache_data.clear()
        st.rerun()

    st.sidebar.caption(data_source_label())

    render_auth_controls()
