"""Shared sidebar controls rendered on every page."""

from datetime import date, timedelta

import streamlit as st

from auth import render_auth_controls
from data_loader import (
    can_run_extraction,
    current_mode,
    data_source_label,
    local_habits_path,
    persist_habits_after_extract,
)
from extract_habits import extract


def render_sidebar_controls(max_date: date):
    """Render the Extract latest and Reload data buttons into the sidebar."""
    st.sidebar.divider()

    if can_run_extraction() and st.sidebar.button("⬇ Extract latest", width="stretch"):
        _next_day = max_date + timedelta(days=1)
        _yesterday = date.today() - timedelta(days=1)
        if _next_day <= _yesterday:
            _vault_dir = st.secrets.get("VAULT_DIR", "")
            if not _vault_dir:
                st.session_state["_extract_msg"] = (
                    "error",
                    "VAULT_DIR is not set in secrets.toml.",
                )
            else:
                try:
                    _summary = extract(_vault_dir, _next_day, _yesterday, local_habits_path())
                    persist_habits_after_extract()
                    _suffix = (
                        " and successfully uploaded to Supabase."
                        if current_mode() == "supabase"
                        else ""
                    )
                    st.session_state["_extract_msg"] = ("success", _summary + _suffix)
                except Exception as e:
                    st.session_state["_extract_msg"] = ("error", str(e))
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
