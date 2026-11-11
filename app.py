"""BestBets v9 — screenshot-first MVP landing.

Statistical sources and previous application modules remain in the repository.
Only the public entrypoint has changed; no NBA data or simulations are deleted.
"""
import streamlit as st

st.set_page_config(
    page_title="BestBets | NBA Intelligence",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)

from bestbets_v90 import main

main()
