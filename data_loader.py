"""Loads habit data from local disk (dev) or a private GitHub repo (prod).

Production mode is triggered by the presence of `GH_TOKEN` in st.secrets.
When set, the loader fetches `habits.json` from the private repo named in
`GH_DATA_REPO` (format: "owner/repo") on branch `GH_DATA_BRANCH` (default "main").

Dev mode reads `data/habits.json` if present, falling back to
`data/habits.example.json` so the app runs for anyone cloning the public repo.
"""

import json
from pathlib import Path

import requests
import streamlit as st

_REPO_ROOT = Path(__file__).resolve().parent
_LOCAL_HABITS = _REPO_ROOT / "data" / "habits.json"
_EXAMPLE_HABITS = _REPO_ROOT / "data" / "habits.example.json"
_LOCAL_WEEK_REVIEW_CONFIG = _REPO_ROOT / "data" / "week_review_config.json"


def fetch_raw_habits() -> dict:
    token = _gh_token()
    if token:
        return _fetch_json_from_github(token, "habits.json")
    path = _LOCAL_HABITS if _LOCAL_HABITS.exists() else _EXAMPLE_HABITS
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_week_review_config() -> dict | None:
    """Return the week review config dict, or None if absent."""
    token = _gh_token()
    if token:
        try:
            return _fetch_json_from_github(token, "week_review_config.json")
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return None
            raise
    if _LOCAL_WEEK_REVIEW_CONFIG.exists():
        return json.loads(_LOCAL_WEEK_REVIEW_CONFIG.read_text(encoding="utf-8"))
    return None


def _gh_token() -> str | None:
    return st.secrets.get("GH_TOKEN") if hasattr(st, "secrets") else None


def _fetch_json_from_github(token: str, filename: str) -> dict:
    repo = st.secrets.get("GH_DATA_REPO")
    if not repo:
        raise RuntimeError(
            "GH_TOKEN is set but GH_DATA_REPO is missing. "
            'Add GH_DATA_REPO = "owner/repo" to .streamlit/secrets.toml.'
        )
    branch = st.secrets.get("GH_DATA_BRANCH", "main")
    url = f"https://raw.githubusercontent.com/{repo}/{branch}/{filename}"
    resp = requests.get(
        url,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3.raw",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()
