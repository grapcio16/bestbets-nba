"""Readable BestBets Center leaderboard: actual player boxscore statistics only."""
from __future__ import annotations

from html import escape
import pandas as pd
import streamlit as st
from team_logos import logo_data_uri

CSS = """
<style>
.bb-top10-grid-card{
 display:flex;flex-direction:column;gap:12px;padding:16px 18px;margin:0 0 12px;
 background:linear-gradient(120deg,#15253e,#101a2c);
 border:1px solid #304b73;border-radius:16px;box-shadow:0 5px 16px rgba(0,0,0,.12)
}
.bb-top10-header{display:flex;flex-wrap:wrap;align-items:center;gap:10px;min-width:0}
.bb-top10-rank{font:800 17px 'Space Grotesk',sans-serif;color:#a1b5d3;min-width:37px}
.bb-top10-rank.medal1{color:#ffb85e}
.bb-top10-rank.medal2{color:#e4edf9}
.bb-top10-rank.medal3{color:#d9a27b}
.bb-top10-logo{width:38px;height:38px;object-fit:contain;flex-shrink:0}
.bb-top10-ident{display:flex;flex-direction:column;gap:4px;min-width:115px;flex:1}
.bb-top10-name-row{display:flex;align-items:center;gap:7px;flex-wrap:wrap}
.bb-top10-name-row>strong{font:750 17px/1.2 'Space Grotesk',sans-serif;
 color:#f1f6ff;overflow-wrap:anywhere}
.bb-top10-ident small{font-size:11px;font-weight:700;letter-spacing:.05em;color:#93a8c6}
.bb-top10-position{display:inline-flex;align-items:center;justify-content:center;
 border-radius:7px;border:1px solid #3a6aa4;padding:3px 7px;background:#163153;
 font:800 11px 'Space Grotesk',sans-serif;color:#c5e0ff}
.bb-top10-position strong{font:inherit}
.bb-top10-match{display:flex;flex-direction:column;align-items:end;gap:3px;
 border:1px solid #345477;background:#132d4b;border-radius:10px;
 padding:8px 12px;margin-left:auto;flex-shrink:0}
.bb-top10-match small{font-size:9px;color:#98afce;letter-spacing:.10em;font-weight:750}
.bb-top10-match strong{font:800 13px 'Space Grotesk',sans-serif;color:#eaf1ff;white-space:nowrap}
.bb-top10-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));
 gap:7px;border-top:1px solid #293e59;padding-top:12px}
.bb-top10-stat{display:flex;flex-direction:column;align-items:center;gap:3px;
 color:#a7bad5;font-size:10px;font-weight:750;letter-spacing:.06em}
.bb-top10-stat strong{font:800 22px 'Space Grotesk',sans-serif;color:#eef5ff;letter-spacing:-.03em}
.bb-top10-stat.main strong{color:#ff8a48}
@media(max-width:780px){
 .bb-top10-grid-card{padding:13px;gap:10px}
 .bb-top10-name-row>strong{font-size:15px}
 .bb-top10-stat strong{font-size:19px}
 .bb-top10-match{margin-left:0;max-width:100%}
}
@media(max-width:460px){
 .bb-top10-match{width:100%;align-items:start}
 .bb-top10-stat{font-size:9px}
 .bb-top10-stat strong{font-size:17px}
}
</style>
"""

def stat_text(value):
    """Keep stats legible; a missing value must never be shown as zero."""
    try:
        n = float(value)
    except (ValueError, TypeError):
        return "—"
    if not pd.notna(n):
        return "—"
    return str(int(n)) if n.is_integer() else f"{n:.1f}"


def minute_text(value):
    """Format actual ESPN playing time as MM:SS; unknown is not zero."""
    try:
        minutes=float(value)
        if not pd.notna(minutes) or minutes<0:
            return "—"
    except (TypeError, ValueError):
        return "—"
    seconds=round(minutes*60)
    return f"{seconds//60}:{seconds%60:02d}"


def known_text(value):
    """Never surface missing pandas values as the strings 'nan' or 'None'."""
    if value is None:
        return "—"
    try:
        if pd.isna(value):
            return "—"
    except (TypeError, ValueError):
        return "—"
    text=str(value).strip()
    return text if text and text.lower() not in ("nan","none","null") else "—"


def player_card_html(row, rank):
    """Four real game stats, nominal position beside name, actual match in header."""
    name = escape(known_text(row.get("PLAYER_NAME")))
    team = escape(known_text(row.get("TEAM_ABBREVIATION")))
    team_code = known_text(row.get("TEAM_ABBREVIATION")).upper()
    src = escape(logo_data_uri(team_code), quote=True)
    logo = (f'<img class="bb-top10-logo" src="{src}" alt="Logo {team}">' if src else "")
    medal = f"medal{rank}" if rank in (1, 2, 3) else ""
    pts, reb, ast = (stat_text(row.get(key)) for key in ("PTS", "REB", "AST"))
    played = escape(minute_text(row.get("MIN")))
    position = escape(known_text(row.get("POSITION")))
    game = known_text(row.get("MATCHUP"))
    if game == "—":
        opponent = known_text(row.get("OPPONENT"))
        game = f"{team_code} · {opponent}" if opponent != "—" else "—"
    matchup = escape(game)
    return f"""
    <div class="bb-top10-grid-card">
      <div class="bb-top10-header">
        <div class="bb-top10-rank {medal}">#{rank:02d}</div>
        {logo}
        <div class="bb-top10-ident">
          <div class="bb-top10-name-row">
            <strong>{name}</strong>
            <span class="bb-top10-position" title="POZYCJA zawodnika według ESPN"><strong>{position}</strong></span>
          </div>
          <small>{team} · NBA</small>
        </div>
        <div class="bb-top10-match" title="PRZECIWNIK i rzeczywisty MECZ">
          <small>MECZ</small><strong>{matchup}</strong>
        </div>
      </div>
      <div class="bb-top10-stats">
        <div class="bb-top10-stat main"><strong>{pts}</strong>PUNKTY</div>
        <div class="bb-top10-stat"><strong>{reb}</strong>ZBIÓRKI</div>
        <div class="bb-top10-stat"><strong>{ast}</strong>ASYSTY</div>
        <div class="bb-top10-stat"><strong>{played}</strong>MINUTY</div>
      </div>
    </div>"""

def show_top10(top):
    """Two columns on desktop; each player's row remains a complete card."""
    if top is None or top.empty:
        return
    st.markdown(CSS, unsafe_allow_html=True)
    left, right = st.columns(2, gap="medium")
    for i, row in enumerate(top.head(10).to_dict("records")):
        with (left if i % 2 == 0 else right):
            st.markdown(player_card_html(row, i + 1), unsafe_allow_html=True)
