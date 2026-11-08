"""BestBets schedule UI v7.10 — real match information, never model forecasts.

Shared Streamlit date navigation and compact, accessible cards for Center and Schedule.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from html import escape

import pandas as pd
import streamlit as st

from teams import TEAM_FULL
from team_logos import logo_data_uri, refresh_logos_in_background
from viewer_time import games_on_day, localize

SELECTED_DAY_KEY = "bb_schedule_selected_day"

SCHEDULE_CSS = """
<style>
.bb-fixture-card{
  margin:0 0 12px;
  padding:15px 19px 13px;
  border-radius:17px;
  background:linear-gradient(125deg,rgba(24,38,63,.98),rgba(11,21,38,.98));
  border:1px solid #2b4772;
  box-shadow:0 6px 24px rgba(0,0,0,.11);
}
.bb-fixture-top{display:flex;align-items:center;justify-content:space-between;gap:12px;
  font-size:11px;font-weight:700;color:#9fb5d5;margin-bottom:12px;}
.bb-fixture-date{font-variant-numeric:tabular-nums;letter-spacing:.025em;}
.bb-fixture-state{font-size:10px;padding:4px 9px;border-radius:99px;
  background:#21344e;color:#a6c9fa;border:1px solid #34557a;white-space:nowrap;}
.bb-fixture-state.live{color:#ffe0b8;background:#422814;border-color:#b36a28;}
.bb-fixture-state.final{color:#b4dfd0;background:#173c35;border-color:#2c7762;}
.bb-fixture-body{display:grid;grid-template-columns:minmax(0,1fr) minmax(78px,.65fr) minmax(0,1fr);
  align-items:center;column-gap:9px;text-align:center;}
.bb-fixture-team{display:flex;flex-direction:column;align-items:center;gap:4px;min-width:0;}
.bb-fixture-team img{width:60px;height:60px;object-fit:contain;display:block;}
.bb-fixture-team strong{font-family:'Space Grotesk',sans-serif;font-size:15px;
  font-weight:700;color:#f6f8fc;line-height:1.25;overflow-wrap:anywhere;}
.bb-fixture-team small{font-size:10px;color:#91a4c0;letter-spacing:.065em;font-weight:700;}
.bb-fixture-center{display:flex;flex-direction:column;align-items:center;gap:4px;min-width:0;}
.bb-fixture-center .vs{font-size:11px;letter-spacing:.16em;color:#7185a5;font-weight:800;}
.bb-fixture-center .kickoff{font-family:'Space Grotesk',sans-serif;font-size:24px;
  font-weight:800;color:#ff873d;font-variant-numeric:tabular-nums;line-height:1.1;}
.bb-fixture-center .score{font-family:'Space Grotesk',sans-serif;font-size:23px;
  font-weight:800;color:#fff2de;font-variant-numeric:tabular-nums;white-space:nowrap;}
.bb-fixture-center .score-label{font-size:10px;color:#a8bdd6;font-weight:700;}
.bb-fixture-bottom{margin-top:13px;padding-top:10px;border-top:1px solid #293d5b;
  display:flex;justify-content:space-between;gap:9px;flex-wrap:wrap;
  color:#99abc5;font-size:11px;line-height:1.5;}
.bb-fixture-bottom strong{color:#d8e7fc;font-weight:600}
@media(max-width:760px){
  .bb-fixture-card{padding:12px 10px 10px;border-radius:14px;}
  .bb-fixture-team img{width:45px;height:45px;}
  .bb-fixture-team strong{font-size:12px;}
  .bb-fixture-center .kickoff,.bb-fixture-center .score{font-size:19px;}
  .bb-fixture-body{grid-template-columns:minmax(0,1fr) minmax(69px,.65fr) minmax(0,1fr);gap:3px;}
  .bb-fixture-top,.bb-fixture-bottom{font-size:10px;}
}
</style>
"""


def result_type(game):
    """Return a safe UI state from source status code, not a predicted outcome."""
    try:
        code = int(game.get("status_code"))
    except (ValueError, TypeError):
        code = 0
    if code == 3:
        return "final"
    if code == 2:
        return "live"
    return "scheduled"


def real_score(game):
    """Only display scores from games already in progress or finished."""
    if result_type(game) == "scheduled":
        return None
    parts = []
    for key in ("away_score", "home_score"):
        value = game.get(key)
        if value is None or pd.isna(value) or str(value).strip() in ("", "-", "None"):
            return None
        try:
            val = float(value)
            if val < 0 or not pd.notna(val):
                return None
            parts.append(str(int(val)) if val.is_integer() else str(val))
        except (TypeError, ValueError):
            return None
    return " : ".join(parts)


def card_html(game, zone):
    """Render a single fixture. No simulation, odds or model fields are consumed."""
    away = str(game.get("away") or "").upper()
    home = str(game.get("home") or "").upper()
    start = localize(game.get("start_utc"), zone)
    if pd.isna(start):
        raise ValueError("Invalid UTC kickoff in schedule row")
    ts = start.strftime("%d.%m.%Y • %H:%M")
    clock = start.strftime("%H:%M")
    state = result_type(game)
    status_name = {"final": "Zakończony", "live": "Na żywo", "scheduled": "Zaplanowany"}[state]
    score = real_score(game)
    display_score = score if score else clock
    score_label = ("WYNIK KOŃCOWY" if state == "final" else "WYNIK NA ŻYWO") if score else "CZAS LOKALNY"
    away_name = str(game.get("away_name") or TEAM_FULL.get(away,away)).strip()
    home_name = str(game.get("home_name") or TEAM_FULL.get(home,home)).strip()
    zone_label = str(zone)
    away_img = escape(logo_data_uri(away), quote=True)
    home_img = escape(logo_data_uri(home), quote=True)
    img_a = f'<img src="{away_img}" alt="Logo {escape(away)}" loading="lazy">' if away_img else ""
    img_h = f'<img src="{home_img}" alt="Logo {escape(home)}" loading="lazy">' if home_img else ""
    center_class = "score" if score else "kickoff"
    return f"""
    <div class="bb-fixture-card">
      <div class="bb-fixture-top">
        <span class="bb-fixture-date">🏀 {escape(ts)}</span>
        <span class="bb-fixture-state {state}">{escape(status_name)}</span>
      </div>
      <div class="bb-fixture-body">
        <div class="bb-fixture-team">{img_a}<strong>{escape(away_name)}</strong><small>GOŚCIE · {escape(away)}</small></div>
        <div class="bb-fixture-center">
          <span class="vs">VS</span>
          <span class="{center_class}">{escape(display_score)}</span>
          <span class="score-label">{escape(score_label)}</span>
        </div>
        <div class="bb-fixture-team">{img_h}<strong>{escape(home_name)}</strong><small>GOSPODARZE · {escape(home)}</small></div>
      </div>
      <div class="bb-fixture-bottom">
        <span>Strefa: <strong>{escape(zone_label)}</strong></span>
        <span>{escape(status_name)} · dane z terminarza NBA/ESPN</span>
      </div>
    </div>"""


def _move_date(days: int):
    new_day = st.session_state[SELECTED_DAY_KEY] + timedelta(days=days)
    st.session_state[SELECTED_DAY_KEY] = new_day
    st.session_state["bb_schedule_calendar"] = new_day


def _reset_date(zone):
    new_day = datetime.now(zone).date()
    st.session_state[SELECTED_DAY_KEY] = new_day
    st.session_state["bb_schedule_calendar"] = new_day


def _calendar_changed():
    st.session_state[SELECTED_DAY_KEY] = st.session_state["bb_schedule_calendar"]


def day_navigation(prefix: str, zone):
    """Shared date between Center and Schedule; arrows and calendar stay in sync."""
    today = datetime.now(zone).date()
    if SELECTED_DAY_KEY not in st.session_state:
        st.session_state[SELECTED_DAY_KEY] = today
    if "bb_schedule_calendar" not in st.session_state:
        st.session_state["bb_schedule_calendar"] = st.session_state[SELECTED_DAY_KEY]
    previous, calendar, following, reset = st.columns([1, 2.5, 1, 1.35], vertical_alignment="bottom")
    with previous:
        st.button("◀", key=f"{prefix}_previous_day", help="Poprzedni dzień",
                  on_click=_move_date, args=(-1,), use_container_width=True)
    with following:
        st.button("▶", key=f"{prefix}_next_day", help="Następny dzień",
                  on_click=_move_date, args=(1,), use_container_width=True)
    with reset:
        st.button("Dzisiaj", key=f"{prefix}_today", use_container_width=True,
                  on_click=_reset_date, args=(zone,))
    with calendar:
        st.date_input("Wybierz datę", key="bb_schedule_calendar",
                      format="DD.MM.YYYY", on_change=_calendar_changed)
    return st.session_state[SELECTED_DAY_KEY]


def display_cards(games: pd.DataFrame, zone, *, compact=False):
    """Only actual match state and actual scores; deliberately no simulations."""
    st.markdown(SCHEDULE_CSS, unsafe_allow_html=True)
    if games is None or games.empty:
        st.info("Brak spotkań w wybranym dniu lub źródło nie udostępnia tej daty.")
        return
    refresh_logos_in_background()
    ordered = games.sort_values("start_utc").drop_duplicates("game_id")
    st.caption(f"Spotkania: {len(ordered)} · godziny i daty w strefie {zone}")
    for _, row in ordered.iterrows():
        st.markdown(card_html(row, zone), unsafe_allow_html=True)
