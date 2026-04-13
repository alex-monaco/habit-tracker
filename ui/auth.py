"""Authentication gate. Bypassed locally when HABIT_DEV_MODE is set in secrets.toml."""

import streamlit as st


def is_authenticated() -> bool:
    """True for real authorized users or dev mode."""
    if st.secrets.get("HABIT_DEV_MODE"):
        return True
    try:
        return (
            st.user.is_logged_in
            and st.user.email in st.secrets.get("ALLOWED_EMAILS", [])
        )
    except AttributeError:
        return False


def require_auth() -> None:
    """Gate: blocks unauthorized users. Unauthenticated users see demo data automatically."""
    if is_authenticated():
        return

    if "auth" not in st.secrets:
        st.error(
            "Auth is not configured. Set HABIT_DEV_MODE = true in secrets.toml for local dev, "
            "or configure [auth] in .streamlit/secrets.toml for production."
        )
        st.stop()

    if st.user.is_logged_in and st.user.email not in st.secrets.get("ALLOWED_EMAILS", []):
        st.error(f"{st.user.email} is not authorized to view this app.")
        if st.button("Sign out"):
            st.logout()
        st.stop()
