"""Loads habit data from local disk (dev), Supabase (prod), or example files (demo).

Mode is determined by data_mode():
- `demo`: unauthenticated or demo session
- `supabase`: authenticated + SUPABASE_URL configured
- `local`: authenticated, local dev fallback

Views and the sidebar should never branch on the backend themselves — call
the functions here and let this module handle it.
"""

import json
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

from ui.auth import is_authenticated

_REPO_ROOT = Path(__file__).resolve().parent.parent
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

def data_mode() -> str:
    """Return the data access mode: 'demo', 'supabase', or 'local'."""
    if not is_authenticated():
        return "demo"
    if hasattr(st, "secrets") and st.secrets.get("SUPABASE_URL"):
        return "supabase"
    return "local"


def data_source_label() -> str:

    return {"demo": "Data: sample", "supabase": "Data: Supabase", "local": "Data: local"}[
        data_mode()
    ]


def can_run_extraction() -> bool:
    """True when this process can reach the Obsidian vault to extract notes.

    Cloud deployments set REMOTE_MODE in secrets to disable the extract button.
    """

    if data_mode() == "demo":
        return False
    return not (hasattr(st, "secrets") and st.secrets.get("REMOTE_MODE"))


@st.cache_data
def fetch_raw_habits(mode: str) -> dict:
    """Load raw habits dict. `mode` is passed explicitly so cache keys on it."""
    if mode == "demo":
        return json.loads(_EXAMPLE_HABITS.read_text(encoding="utf-8"))
    if mode == "supabase":
        from services.supabase_sync import read_json

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
        from services.supabase_sync import read_json

        try:
            return read_json(_WEEK_REVIEW_CONFIG_FILENAME)
        except Exception:
            return None
    if _LOCAL_WEEK_REVIEW_CONFIG.exists():
        return json.loads(_LOCAL_WEEK_REVIEW_CONFIG.read_text(encoding="utf-8"))
    return None


def load_habits() -> dict:

    return fetch_raw_habits(data_mode())


def load_week_review_config() -> dict | None:

    return fetch_week_review_config(data_mode())


def run_extraction() -> tuple[str, str]:
    """Extract new habits from the vault and persist them.

    Returns (level, message) where level is 'success', 'error', or 'info'.
    """
    habits = load_habits()
    max_date = max(date.fromisoformat(d) for d in habits)
    next_day = max_date + timedelta(days=1)
    yesterday = date.today() - timedelta(days=1)

    if next_day > yesterday:
        return ("info", "Already up to date.")

    vault_dir = st.secrets.get("VAULT_DIR", "")
    if not vault_dir:
        return ("error", "VAULT_DIR is not set in secrets.toml.")

    from extract_habits import extract

    try:
        summary = extract(vault_dir, next_day, yesterday, _LOCAL_HABITS)
        _persist_habits_after_extract()
        if data_mode() == "supabase":
            summary += " and successfully uploaded to Supabase."
        return ("success", summary)
    except Exception as e:
        return ("error", str(e))


def _persist_habits_after_extract() -> None:
    """Push the freshly-extracted local habits.json to the remote backend, if any."""
    if data_mode() != "supabase":
        return
    from services.supabase_sync import write_json

    write_json(_HABITS_FILENAME, json.loads(_LOCAL_HABITS.read_text(encoding="utf-8")))
