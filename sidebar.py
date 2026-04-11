"""Shared sidebar controls rendered on every page."""

import subprocess
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

_REPO_ROOT = Path(__file__).resolve().parent
_LOCAL_DATA = _REPO_ROOT / "data" / "habits.json"
_EXTRACT_SCRIPT = _REPO_ROOT / "extract_habits.py"


def _is_remote_mode() -> bool:
    return bool(st.secrets.get("GH_TOKEN")) if hasattr(st, "secrets") else False


def render_sidebar_controls(max_date: date):
    """Render the Extract latest and Reload data buttons into the sidebar."""
    st.sidebar.divider()

    if not _is_remote_mode() and st.sidebar.button("⬇ Extract latest", width="stretch"):
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
                    str(_LOCAL_DATA),
                ],
                capture_output=True,
                text=True,
            )
            if _result.returncode == 0:
                st.session_state["_extract_msg"] = ("success", _result.stdout.strip())
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
