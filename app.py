"""BestBets MVP v8.0 — focused NBA intelligence experience.

Only the six core product areas and small supporting workspace screens
are exposed. Old research/OCR/odds/tracker code remains in dedicated modules
and git history, but is not part of the public navigation during rebuild.
"""
import streamlit as st

st.set_page_config(
    page_title="BestBets | NBA Intelligence",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)

from mvp_app import main

main()
