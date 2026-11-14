"""Hoopzaro — interactive NBA analysis frontend.

Only the public presentation entrypoint is replaced. The previous Streamlit
screens, NBA/ESPN sources, player data and simulation engines remain intact
in the same repository.
"""
import streamlit as st

st.set_page_config(
    page_title="HOOPZARO | NBA Analytics",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from bestbets_custom_screen import main

main()
