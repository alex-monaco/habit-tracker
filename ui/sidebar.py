"""Shared sidebar controls rendered on every page."""

import streamlit as st

from services.data_loader import (
    can_push_week_review_config,
    can_run_extraction,
    data_source_label,
    push_week_review_config,
    run_extraction,
)
from ui.auth import is_authenticated

_MSG_RENDERERS = {
    "success": st.sidebar.success,
    "error": st.sidebar.error,
    "info": st.sidebar.info,
}


def render_sidebar_controls():
    """Render the Extract latest, Reload data buttons and authentication controls if configured into the sidebar."""
    st.sidebar.divider()

    if can_run_extraction() and st.sidebar.button("⬇ Extract latest", width="stretch"):
        st.session_state["_extract_msg"] = run_extraction()
        st.cache_data.clear()
        st.rerun()

    if "_extract_msg" in st.session_state:
        level, msg = st.session_state.pop("_extract_msg")
        _MSG_RENDERERS[level](msg)

    if can_push_week_review_config() and st.sidebar.button("↑ Upload habit config", width="stretch"):
        st.session_state["_config_msg"] = push_week_review_config()
        st.cache_data.clear()
        st.rerun()

    if "_config_msg" in st.session_state:
        level, msg = st.session_state.pop("_config_msg")
        _MSG_RENDERERS[level](msg)

    if st.sidebar.button("↺ Reload data", width="stretch"):
        st.cache_data.clear()
        st.rerun()

    st.sidebar.caption(data_source_label())

    if is_authenticated():
        if st.user.is_logged_in:
            st.sidebar.caption(f"Signed in as {st.user.email}")
            if st.sidebar.button("Sign out", width="stretch"):
                st.cache_data.clear()
                st.session_state.clear()
                st.logout()
    elif "auth" in st.secrets:
        st.sidebar.info("Viewing with sample data")
        if st.sidebar.button("Sign in", width="stretch"):
            st.cache_data.clear()
            st.login()
