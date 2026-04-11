"""Authentication gate. Bypassed locally when HABIT_DEV_MODE is set."""

import os

import streamlit as st


def require_auth() -> None:
    if os.environ.get("HABIT_DEV_MODE"):
        return

    if "auth" not in st.secrets:
        st.error(
            "Auth is not configured. Set HABIT_DEV_MODE=1 for local dev, "
            "or configure [auth] in .streamlit/secrets.toml for production."
        )
        st.stop()

    if not st.user.is_logged_in:
        st.title("Habit Tracker")
        st.write("Sign in to continue.")
        if st.button("Sign in with Google"):
            st.login()
        st.stop()

    allowed = st.secrets.get("ALLOWED_EMAILS", [])
    if st.user.email not in allowed:
        st.error(f"{st.user.email} is not authorized to view this app.")
        if st.button("Sign out"):
            st.logout()
        st.stop()


def render_auth_controls() -> None:
    if os.environ.get("HABIT_DEV_MODE") or "auth" not in st.secrets:
        return
    if not st.user.is_logged_in:
        return
    st.sidebar.caption(f"Signed in as {st.user.email}")
    if st.sidebar.button("Sign out", width="stretch"):
        st.logout()
