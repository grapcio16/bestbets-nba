"""Hoopzaro — interactive NBA analysis frontend.

Only the public presentation entrypoint is replaced. The previous Streamlit
screens, NBA/ESPN sources, player data and simulation engines remain intact
in the same repository.
"""
import streamlit as st

control_center_requested = st.query_params.get("control_center") == "1"

st.set_page_config(
    page_title="HOOPZARO | NBA Analytics",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded" if control_center_requested else "collapsed",
)

if control_center_requested:
    from admin_control_center import render
    render()
else:
    from bestbets_custom_screen import main
    main()
