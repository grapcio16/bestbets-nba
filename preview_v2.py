"""Safe preview entrypoint for BestBets iframe-free experiment.

Production still uses app.py and stays unchanged.
Deploy this entrypoint on a DIFFERENT Streamlit app if desired.
"""
import streamlit as st

st.set_page_config(
    page_title="BestBets V2 | Preview",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="collapsed",
)
from bestbets_v2_preview import main
main()
