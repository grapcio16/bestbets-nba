"""Readable BestBets Center leaderboard: actual player boxscore statistics only."""
from __future__ import annotations

from html import escape
import pandas as pd
import streamlit as st
from team_logos import logo_data_uri

CSS = """
<style>
.bb-top10-grid-card {
 display:flex; flex-direction:column; gap:11px; padding:15px 17px;
 margin:0 0 12px; background:linear-gradient(120deg,#15253e,#101a2c);
 border:1px solid #304b73; border-radius:16px;
 box-shadow:0 5px 16px rgba(0,0,0,.12); min-height:146px;
}
.bb-top10-header {display:flex;gap:12px;align-items:center;min-width:0;}
.bb-top10-rank {font:800 17px 'Space Grotesk',sans-serif;color:#a1b5d3;
 min-width:40px;text-align:center;letter-spacing:-.02em;}
.bb-top10-rank.medal1 {color:#ffb85e}
.bb-top10-rank.medal2 {color:#e4edf9}
.bb-top10-rank.medal3 {color:#d9a27b}
.bb-top10-logo {width:40px;height:40px;object-fit:contain;flex-shrink:0;}
.bb-top10-ident {display:flex;flex-direction:column;gap:3px;min-width:0;flex:1;}
.bb-top10-ident strong {font:750 17px/1.25 'Space Grotesk',sans-serif;
 color:#f1f6ff;overflow-wrap:anywhere;}
.bb-top10-ident small {font-size:11px;font-weight:700;letter-spacing:.05em;color:#93a8c6;}
.bb-top10-stats {display:grid;grid-template-columns:1.3fr 1fr 1fr;gap:8px;
 border-top:1px solid #293e59;padding-top:11px;}
.bb-top10-stat {display:flex;flex-direction:column;align-items:center;gap:2px;
 color:#9eafc8;font-size:10px;font-weight:700;letter-spacing:.07em;}
.bb-top10-stat strong {font:800 22px 'Space Grotesk',sans-serif;
 color:#eef5ff;letter-spacing:-.03em;}
.bb-top10-stat.main strong {color:#ff8a48;}
@media(max-width:760px){
 .bb-top10-grid-card{padding:13px;gap:10px;}
 .bb-top10-ident strong{font-size:15px;}
 .bb-top10-stat strong{font-size:20px;}
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


def player_card_html(row, rank):
    """Sanitize names/team abbreviations; never print invented player statistics."""
    name = escape(str(row.get("PLAYER_NAME") or "Nieznany zawodnik"))
    team = escape(str(row.get("TEAM_ABBREVIATION") or "—"))
    team_code = str(row.get("TEAM_ABBREVIATION") or "").upper()
    src = escape(logo_data_uri(team_code), quote=True)
    logo = (f'<img class="bb-top10-logo" src="{src}" alt="Logo {team}">' if src else "")
    medal = f"medal{rank}" if rank in (1, 2, 3) else ""
    pts, reb, ast = (stat_text(row.get(key)) for key in ("PTS", "REB", "AST"))
    return f"""
    <div class="bb-top10-grid-card">
      <div class="bb-top10-header">
        <div class="bb-top10-rank {medal}">#{rank:02d}</div>
        {logo}
        <div class="bb-top10-ident"><strong>{name}</strong><small>{team} · NBA</small></div>
      </div>
      <div class="bb-top10-stats">
        <div class="bb-top10-stat main"><strong>{pts}</strong>PUNKTY</div>
        <div class="bb-top10-stat"><strong>{reb}</strong>ZBIÓRKI</div>
        <div class="bb-top10-stat"><strong>{ast}</strong>ASYSTY</div>
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
