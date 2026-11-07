"""Single storage interface: opt-in durable PostgreSQL or local ephemeral SQLite.

The choice is explicit and visible. Credentials are only read from server-side
environment/Streamlit Secrets, never shown, exported or logged.
"""
from __future__ import annotations

import os
from pathlib import Path


def tracker_database_url():
    url=os.environ.get("TRACKER_DATABASE_URL","").strip()
    if url:
        return url
    try:
        import streamlit as st
        return str(st.secrets.get("TRACKER_DATABASE_URL","")).strip()
    except (FileNotFoundError,KeyError,AttributeError,RuntimeError):
        return ""


def local_path():
    return Path(__file__).resolve().parent/"data"/"pregame_forecasts.sqlite3"


def tracker_backend():
    url=tracker_database_url()
    return {"remote":bool(url),"url":url,"label":(
        "PostgreSQL — trwałe przechowywanie prognoz"
        if url else "SQLite — lokalne, nietrwałe na Streamlit Cloud")}


def save(summaries,season,config=None):
    cfg=config or tracker_backend()
    if cfg["remote"]:
        from tracker_postgres import remote_store
        return remote_store(cfg["url"],season,summaries)
    from performance_tracker import store_forecasts
    return store_forecasts(local_path(),season,summaries)


def settle(games,config=None):
    cfg=config or tracker_backend()
    if cfg["remote"]:
        from tracker_postgres import remote_settle
        return remote_settle(cfg["url"],games)
    from performance_tracker import settle_forecasts
    return settle_forecasts(local_path(),games)


def read(season=None,config=None):
    cfg=config or tracker_backend()
    if cfg["remote"]:
        from tracker_postgres import remote_read
        return remote_read(cfg["url"],season)
    from performance_tracker import read_forecasts
    return read_forecasts(local_path(),season)
