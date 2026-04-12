"""Authentication gate. Bypassed locally when HABIT_DEV_MODE is set in secrets.toml."""

import streamlit as st


def _dev_mode() -> bool:
    return bool(st.secrets.get("HABIT_DEV_MODE"))


def require_auth() -> None:
    if _dev_mode():
        return

    if "auth" not in st.secrets:
        st.error(
            "Auth is not configured. Set HABIT_DEV_MODE = true in secrets.toml for local dev, "
            "or configure [auth] in .streamlit/secrets.toml for production."
        )
        st.stop()

    if st.session_state.get("demo_mode"):
        return

    if not st.user.is_logged_in:
        st.title("Habit Tracker")
        st.write("Sign in to continue.")
        if st.button("Sign in with Google"):
            st.login()
        st.divider()
        st.caption("Just exploring?")
        if st.button("View with sample data"):
            st.session_state["demo_mode"] = True
            st.rerun()
        st.stop()

    allowed = st.secrets.get("ALLOWED_EMAILS", [])
    if st.user.email not in allowed:
        st.error(f"{st.user.email} is not authorized to view this app.")
        if st.button("Sign out"):
            st.logout()
        st.stop()


def render_auth_controls() -> None:
    if st.session_state.get("demo_mode"):
        st.sidebar.info("Viewing with sample data")
        if st.sidebar.button("Sign in", width="stretch"):
            st.session_state.pop("demo_mode", None)
            st.rerun()
        return
    if _dev_mode() or "auth" not in st.secrets:
        return
    if not st.user.is_logged_in:
        return
    st.sidebar.caption(f"Signed in as {st.user.email}")
    if st.sidebar.button("Sign out", width="stretch"):
        st.logout()
