"""Loads habit data from local disk (dev), Supabase (prod), or example files (demo).

Mode is determined internally:
- `demo`: session has `demo_mode` flag set (anonymous visitor)
- `supabase`: `SUPABASE_URL` is in st.secrets
- `local`: fallback, reads `data/habits.json` (or example file if absent)

Views and the sidebar should never branch on the backend themselves — call
the functions here and let this module handle it.
"""

import json
from pathlib import Path

import streamlit as st

_REPO_ROOT = Path(__file__).resolve().parent
_DATA_DIR = _REPO_ROOT / "data"
_LOCAL_HABITS = _DATA_DIR / "habits.json"
_EXAMPLE_HABITS = _DATA_DIR / "habits.example.json"
_LOCAL_WEEK_REVIEW_CONFIG = _DATA_DIR / "week_review_config.json"
_EXAMPLE_WEEK_REVIEW_CONFIG = _DATA_DIR / "week_review_config.example.json"

_HABITS_FILENAME = "habits.json"
_WEEK_REVIEW_CONFIG_FILENAME = "week_review_config.json"


def local_habits_path() -> Path:
    """Path where extract_habits.py should write its output."""
    return _LOCAL_HABITS


def current_mode() -> str:
    """Return 'demo', 'supabase', or 'local'."""
    if st.session_state.get("demo_mode"):
        return "demo"
    if hasattr(st, "secrets") and st.secrets.get("SUPABASE_URL"):
        return "supabase"
    return "local"


def data_source_label() -> str:
    return {"demo": "Data: sample", "supabase": "Data: Supabase", "local": "Data: local"}[
        current_mode()
    ]


def can_run_extraction() -> bool:
    """True when this process can reach the Obsidian vault to extract notes.

    Cloud deployments set REMOTE_MODE in secrets to disable the extract button.
    """
    if st.session_state.get("demo_mode"):
        return False
    return not (hasattr(st, "secrets") and st.secrets.get("REMOTE_MODE"))


@st.cache_data
def fetch_raw_habits(mode: str) -> dict:
    """Load raw habits dict. `mode` is passed explicitly so cache keys on it."""
    if mode == "demo":
        return json.loads(_EXAMPLE_HABITS.read_text(encoding="utf-8"))
    if mode == "supabase":
        from supabase_sync import read_json

        return read_json(_HABITS_FILENAME)
    path = _LOCAL_HABITS if _LOCAL_HABITS.exists() else _EXAMPLE_HABITS
    return json.loads(path.read_text(encoding="utf-8"))


@st.cache_data
def fetch_week_review_config(mode: str) -> dict | None:
    if mode == "demo":
        return (
            json.loads(_EXAMPLE_WEEK_REVIEW_CONFIG.read_text(encoding="utf-8"))
            if _EXAMPLE_WEEK_REVIEW_CONFIG.exists()
            else None
        )
    if mode == "supabase":
        from supabase_sync import read_json

        try:
            return read_json(_WEEK_REVIEW_CONFIG_FILENAME)
        except Exception:
            return None
    if _LOCAL_WEEK_REVIEW_CONFIG.exists():
        return json.loads(_LOCAL_WEEK_REVIEW_CONFIG.read_text(encoding="utf-8"))
    return None


def load_habits() -> dict:
    return fetch_raw_habits(current_mode())


def load_week_review_config() -> dict | None:
    return fetch_week_review_config(current_mode())


def persist_habits_after_extract() -> None:
    """Push the freshly-extracted local habits.json to the remote backend, if any."""
    if current_mode() != "supabase":
        return
    from supabase_sync import write_json

    write_json(_HABITS_FILENAME, json.loads(_LOCAL_HABITS.read_text(encoding="utf-8")))
