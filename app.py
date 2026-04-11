"""Main entry point. Run with: streamlit run app.py"""

import streamlit as st

from auth import require_auth

st.set_page_config(page_title="Habit Tracker", layout="wide")

require_auth()

pg = st.navigation(
    [
        st.Page("views/week_review.py", title="Weekly Review", icon="📋"),
        st.Page("views/historical_review.py", title="Historical Analysis", icon="📊"),
    ]
)
pg.run()
