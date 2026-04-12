"""Supabase helpers for reading and writing data files.

Reads/writes rows in the `habit_data` table, keyed by filename.
Each row has a `filename` (text primary key) and `data` (jsonb) column.

Credentials are read from st.secrets: SUPABASE_URL and SUPABASE_KEY.
"""

import streamlit as st
from supabase import create_client


def _client():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


def read_json(filename: str) -> dict:
    result = (
        _client().table("habit_data").select("data").eq("filename", filename).single().execute()
    )
    return result.data["data"]


def write_json(filename: str, data: dict) -> None:
    _client().table("habit_data").upsert({"filename": filename, "data": data}).execute()
