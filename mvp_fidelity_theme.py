"""BestBets v8.5: large-desktop reference fidelity & live footer previews.

Applied AFTER all legacy theme layers, scoped to Player Props to avoid
changing unrelated NBA screens. Designed for wide/zoomed-out browsers.
"""
from __future__ import annotations
import streamlit as st

FIDELITY_CSS = r"""
<style>
/* High-density visual reference: scale by VIEWPORT, not fixed small rem.
   Many users have 2560/3000 CSS-pixel browsers at 67%-80% zoom. */
[data-testid="stMain"]:has(.bb83-page-marker) {
  --bb85-orange:#ff7d1c;
  --bb85-cyan:#00bfff;
  --bb85-green:#09ed73;
  --bb85-outline:#295783;
}
[data-testid="stSidebar"] .bbm-brand {
  border:0!important;
  padding-bottom:14px!important;
}
[data-testid="stSidebar"] .bbm-brand b {
  letter-spacing:-.055em!important;
}
[data-testid="stMain"]:has(.bb83-page-marker) .st-key-bb83-suggest .stButton>button {
  border-radius:999px!important;
  background:linear-gradient(180deg,#0e253f,#08192c)!important;
  border:1px solid #53728f!important;
  color:#e8f4ff!important;
}
[data-testid="stMain"]:has(.bb83-page-marker) .st-key-bb83-research [data-testid="stPlotlyChart"] {
  border-top-color:#ec792e!important;
  box-shadow:inset 0 1px rgba(255,110,31,.18),0 0 13px rgba(0,123,251,.15)!important;
}
[data-testid="stMain"]:has(.bb83-page-marker) .bb83-hero{
  border-color:#118b99!important;
}
[data-testid="stMain"]:has(.bb83-page-marker) .bb83-rate-card{
  background:linear-gradient(130deg,#051428,#071d34)!important;
}
[data-testid="stMain"]:has(.bb83-page-marker) .bb83-defense{
  border-top-color:#ff9639!important;
}
[data-testid="stMain"]:has(.bb83-page-marker) .bb83-take{
  border-bottom-color:#15b8ef!important;
}
[data-testid="stMain"]:has(.bb83-page-marker) .st-key-bb83-footer{
  margin:10px 0 0!important;
}
[data-testid="stMain"]:has(.bb83-page-marker) .st-key-bb83-footer [data-testid="stVerticalBlockBorderWrapper"]{
  overflow:hidden!important;
  min-height:0!important;
  max-height:none!important;
  padding:0!important;
  border-radius:12px!important;
  background:linear-gradient(155deg,#071a30 8%,#06111f 90%)!important;
}
[data-testid="stMain"]:has(.bb83-page-marker) .st-key-bb83-footer [data-testid="stVerticalBlockBorderWrapper"] > div{
  padding:0!important;
}
[data-testid="stMain"]:has(.bb83-page-marker) .st-key-bb83-footer [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlock"]{
  gap:0!important;
}
.bb85-preview{
  min-height:153px;
  color:#eef6ff;
  overflow:hidden;
  border-radius:10px;
  padding:8px;
  position:relative;
}
.bb85-preview-head{
  margin:-8px -8px 6px;
  padding:6px 8px;
  background:linear-gradient(95deg,rgba(16,47,85,.85),rgba(7,23,40,.5));
  border-bottom:1px solid #2c5073;
  font-size:10px;
  font-weight:950;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
}
.bb85-preview-head span{
  color:#ffad51;
}
.bb85-brandline{
  display:flex;align-items:center;gap:5px;
  font-size:11px;font-weight:950;font-style:italic;
}
.bb85-brandline>span{font-size:22px}
.bb85-brandline strong{color:#fff}
.bb85-brandline strong span{color:#ff802a}
.bb85-tiny-kpis{
  display:grid;grid-template-columns:repeat(3,minmax(0,1fr));
  gap:3px;margin:6px 0;
}
.bb85-tiny-kpis>div{
  min-width:0;display:flex;flex-direction:column;align-items:center;
  gap:4px;padding:5px 1px;
  border:1px solid #2a5079;border-radius:6px;
  background:#0d2741;
}
.bb85-tiny-kpis small{
  display:block;color:#8cbbec;font-size:8px;letter-spacing:.05em
}
.bb85-tiny-kpis b{
  font-size:17px;color:#ffad48;line-height:1
}
.bb85-tiny-kpis .green b{color:#00f58c}
.bb85-callout{
  display:flex;align-items:center;gap:5px;
  border:1px solid #2f5c81;border-radius:6px;
  padding:5px;background:#0b2942;
}
.bb85-avatar{font-size:18px}
.bb85-callout>span:nth-child(2){flex:1;min-width:0}
.bb85-callout b{display:block;font-size:9px;white-space:nowrap}
.bb85-callout small{display:block;font-size:8px;color:#9fbcd9}
.bb85-pill{border:1px solid #09d976;border-radius:10px;color:#02e46c;font-size:9px;padding:1px 5px}
.bb85-preview-title{font-size:10px;font-weight:900;color:#dae8f8}
.bb85-sim-versus{
  margin:5px 0 2px;display:flex;align-items:center;justify-content:space-evenly;
  gap:4px;min-height:70px;
}
.bb85-sim-versus img{width:40px!important;height:40px!important;object-fit:contain!important}
.bb85-sim-versus>div{text-align:center;display:flex;flex-direction:column;gap:3px}
.bb85-sim-versus small{font-size:7px;color:#90b0d6}
.bb85-sim-versus strong{font-size:16px;color:#dceaff}
.bb85-ball{font-size:26px;color:#61aeff}
.bb85-sim-track{display:flex;height:8px;border-radius:6px;overflow:hidden;background:#193450}
.bb85-sim-track i:first-child{display:block;width:50%;background:linear-gradient(90deg,#007bc4,#08d998)}
.bb85-sim-track i:nth-child(2){display:block;width:50%;background:linear-gradient(90deg,#ff9d25,#ff542c)}
.bb85-preview-bottom{display:flex;justify-content:space-between;gap:4px;margin-top:6px;font-size:8px;color:#9bbcd9}
.bb85-preview-bottom strong{color:#3ee5b4;font-size:8px}
.bb85-search-mini{
  color:#b8d1ef;padding:5px 7px;border-radius:8px;border:1px solid #325b7e;
  background:linear-gradient(95deg,#112b47,#0b1a2d);font-size:9px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  margin:3px 0 6px;min-height:23px;
}
.bb85-compact-row,.bb85-person-row,.bb85-team-row{
  display:flex;align-items:center;gap:6px;min-height:23px;
  padding:3px 5px;border-bottom:1px solid #173753;
  font-size:9px;color:#dbe7f7;min-width:0;
}
.bb85-compact-row strong{color:#ffb85a}
.bb85-compact-row span{flex:1}
.bb85-compact-row em{color:#ff8f34;font-style:normal}
.bb85-person-row>span{font-size:15px}
.bb85-person-row b,.bb85-team-row b{
  font-size:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1;min-width:0;
}
.bb85-person-row small,.bb85-team-row small{
  font-size:8px;color:#a5c6ec;white-space:nowrap;
}
.bb85-team-row img{
  height:19px!important;width:19px!important;object-fit:contain!important;flex-shrink:0;
}
.bb85-shortcut-panel{
  background:radial-gradient(ellipse at 100% 0%,rgba(255,122,24,.14),transparent 60%),#071626;
}
.bb85-shortcut-panel .bb85-preview-head{
  border-bottom-color:#895124;color:#ffad63!important;background:#261c1a;
}
.bb85-shortcut-row{
  display:grid;grid-template-columns:31px minmax(0,1fr) 69px;
  gap:4px;align-items:center;border-bottom:1px solid #3a2b20;
  padding:4px 0;font-size:9px;
}
.bb85-shortcut-row strong{color:#f9faff;font-size:9px}
.bb85-shortcut-row span{
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#c7d4e8;
}
.bb85-shortcut-row small{
  font-size:8px;color:#9cb8d5;text-align:right;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
}
[data-testid="stMain"]:has(.bb83-page-marker) .st-key-bb83-footer [data-testid="stButton"] button{
  border:0!important;background:transparent!important;box-shadow:none!important;
  color:#d0e4f9!important;font-weight:800!important;border-radius:7px!important;
}
[data-testid="stMain"]:has(.bb83-page-marker) .st-key-bb83-footer [data-testid="stButton"] button:hover{
  color:#fff!important;background:#103457!important;
  box-shadow:0 0 12px rgba(0,151,255,.28)!important;
}
/* At high CSS viewport widths (browser zoom 67% etc.) all reference
   proportions are scaled back up; this was missing in v8.4. */
@media(min-width:1650px){
  [data-testid="stSidebar"]{
    width:14vw!important;min-width:14vw!important;
  }
  [data-testid="stSidebar"] [data-testid="stSidebarUserContent"]{
    padding:1.2vw 1.1vw!important;
  }
  [data-testid="stSidebar"] .bbm-brand{
    min-height:6.4vw!important;margin:0 0 2vw!important;
    padding:.3vw 0 1.2vw!important;
  }
  [data-testid="stSidebar"] .bbm-brand img{
    width:4.1vw!important;height:4.1vw!important;
  }
  [data-testid="stSidebar"] .bbm-brand b{font-size:1.75vw!important}
  [data-testid="stSidebar"] .bbm-brand .bbm-eyebrow{font-size:.55vw!important}
  [data-testid="stSidebar"] .stButton>button{
    min-height:3.5vw!important;font-size:1vw!important;
    padding:.7vw .9vw!important;border-radius:.8vw!important;
  }
  [data-testid="stSidebar"] .bbm-sidebar-footer{font-size:.7vw!important}
  [data-testid="stMain"]:has(.bb83-page-marker) .block-container,
  [data-testid="stAppViewContainer"]:has(.bb83-page-marker) [data-testid="stMainBlockContainer"]{
    padding:.55vw 1.0vw 2vw!important;
  }
  .st-key-bb83_search{
    width:75%!important;max-width:none!important;
    height:4vw!important;min-height:4vw!important;
    padding:.35vw .5vw .35vw 1.25vw!important;
    margin:.2vw auto .55vw!important;
  }
  .st-key-bb83_search [data-testid="stTextInput"] input{
    height:3.2vw!important;font-size:1.26vw!important;
  }
  .st-key-bb83_search button[kind="primary"]{
    height:3.3vw!important;min-height:3.3vw!important;
    font-size:1.3vw!important;
  }
  .st-key-bb83-suggest{margin:0 auto .9vw!important}
  .st-key-bb83-suggest [data-testid="stHorizontalBlock"]{gap:.9vw!important}
  .st-key-bb83-suggest .stButton>button{
    min-height:2.5vw!important;border-radius:999px!important;
    font-size:.79vw!important;padding:.35vw .55vw!important;
  }
  .bb83-hero{
    min-height:9.4vw!important;border-radius:1vw!important;
    margin:0 0 .45vw!important;
  }
  .bb83-portrait{
    min-height:9.4vw!important;flex-basis:12vw!important;
  }
  .bb83-portrait img{
    height:10vw!important;width:12vw!important;
  }
  .bb83-team-back img{height:7.2vw!important;width:7.2vw!important}
  .bb83-identity{min-width:13vw!important}
  .bb83-identity h2{font-size:2.4vw!important;margin:0 0 .55vw!important}
  .bb83-identity-line{font-size:.95vw!important;gap:.7vw!important}
  .bb83-identity small{font-size:.7vw!important;margin-top:.55vw!important}
  .bb83-team-badge{font-size:.8vw!important;padding:.24vw .5vw!important}
  .bb83-hero-metric{min-width:6.3vw!important;padding:.35vw .45vw!important}
  .bb83-hero-metric label{font-size:.85vw!important}
  .bb83-hero-metric b{font-size:1.8vw!important}
  .bb83-hero-metric em{font-size:.69vw!important}
  .bb83-grade{
    flex:0 0 9.1vw!important;min-width:0!important;
    padding:.7vw .4vw!important;border-radius:.8vw!important;
  }
  .bb83-grade small{font-size:.8vw!important}
  .bb83-grade b{font-size:2.5vw!important}
  .bb83-grade em{font-size:.7vw!important}
  .st-key-bb83-controls{margin:.55vw 0 .75vw!important}
  .st-key-bb83-controls [data-testid="stHorizontalBlock"]{gap:.7vw!important}
  .st-key-bb83-controls label p{font-size:.8vw!important}
  .st-key-bb83-controls [data-baseweb="select"]>div,
  .st-key-bb83-controls [data-baseweb="input"]>div,
  .st-key-bb83-controls [data-testid="stNumberInput"] input,
  .st-key-bb83-controls [data-testid="stSegmentedControl"]{
    height:3vw!important;min-height:3vw!important;
    border-radius:.7vw!important;
  }
  .st-key-bb83-controls [data-testid="stSegmentedControl"] button{
    min-height:2.6vw!important;padding:.4vw .5vw!important;
    font-size:.86vw!important;
  }
  .bb83-chart-head{min-height:2.5vw!important;padding:.4vw!important}
  .bb83-chart-head strong{font-size:1.25vw!important}
  .bb83-chart-head small{font-size:.8vw!important}
  .st-key-bb83-research > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"]{
    gap:1.1vw!important;
  }
  .st-key-bb83-research [data-testid="stPlotlyChart"]{
    border-radius:1vw!important;
  }
  .bb83-rate-grid{gap:.58vw!important}
  .bb83-rate-card{
    min-height:5.6vw!important;padding:.65vw .3vw!important;border-radius:.85vw!important;
  }
  .bb83-rate-card small{font-size:.83vw!important}
  .bb83-rate-card b{font-size:1.9vw!important}
  .bb83-rate-card em{font-size:.75vw!important}
  .bb83-split-grid{gap:.6vw!important}
  .bb83-split-card{min-height:4.7vw!important;padding:.5vw .25vw!important}
  .bb83-split-card small{font-size:.8vw!important}
  .bb83-split-card b{font-size:1.6vw!important}
  .bb83-defense{min-height:7vw!important;padding:.6vw .8vw!important}
  .bb83-defense h4{font-size:1vw!important;margin:0 0 .35vw!important}
  .bb83-defense-points{font-size:.78vw!important;line-height:1.6!important}
  .bb83-defense-logo img{width:4vw!important;height:4vw!important}
  .bb83-take{
    min-height:3.9vw!important;padding:.75vw 1.1vw!important;
    gap:1vw!important;margin:.6vw 0 .3vw!important;
  }
  .bb83-take strong{font-size:1.25vw!important}
  .bb83-take>span{font-size:.88vw!important}
  .st-key-bb83-footer{margin:.9vw 0 0!important}
  .st-key-bb83-footer [data-testid="stHorizontalBlock"]{gap:.8vw!important}
  .bb85-preview{min-height:11vw!important;padding:.6vw!important;border-radius:.8vw!important}
  .bb85-preview-head{
    margin:-.6vw -.6vw .45vw!important;padding:.46vw .6vw!important;
    font-size:.79vw!important;
  }
  .bb85-brandline{font-size:.9vw!important}
  .bb85-brandline>span{font-size:1.6vw!important}
  .bb85-tiny-kpis{gap:.35vw!important;margin:.5vw 0!important}
  .bb85-tiny-kpis>div{padding:.45vw .12vw!important;border-radius:.5vw!important}
  .bb85-tiny-kpis small{font-size:.6vw!important}
  .bb85-tiny-kpis b{font-size:1.3vw!important}
  .bb85-callout{padding:.4vw!important}
  .bb85-callout b{font-size:.65vw!important}
  .bb85-callout small{font-size:.55vw!important}
  .bb85-avatar{font-size:1.4vw!important}
  .bb85-pill{font-size:.6vw!important}
  .bb85-preview-title{font-size:.8vw!important}
  .bb85-sim-versus{min-height:5.1vw!important}
  .bb85-sim-versus img{width:3.3vw!important;height:3.3vw!important}
  .bb85-sim-versus small{font-size:.6vw!important}
  .bb85-sim-versus strong{font-size:1.3vw!important}
  .bb85-sim-track{height:.55vw!important}
  .bb85-preview-bottom{font-size:.65vw!important}
  .bb85-preview-bottom strong{font-size:.65vw!important}
  .bb85-search-mini{min-height:2.1vw!important;padding:.45vw .5vw!important;font-size:.73vw!important}
  .bb85-compact-row,.bb85-person-row,.bb85-team-row{
    min-height:1.7vw!important;padding:.25vw .3vw!important;font-size:.75vw!important;
  }
  .bb85-person-row>span{font-size:1.2vw!important}
  .bb85-person-row b,.bb85-team-row b{font-size:.72vw!important}
  .bb85-person-row small,.bb85-team-row small{font-size:.62vw!important}
  .bb85-team-row img{height:1.5vw!important;width:1.5vw!important}
  .bb85-shortcut-row{
    grid-template-columns:2.5vw minmax(0,1fr) 5.2vw!important;
    padding:.34vw 0!important;gap:.25vw!important;font-size:.7vw!important;
  }
  .bb85-shortcut-row strong{font-size:.72vw!important}
  .bb85-shortcut-row small{font-size:.64vw!important}
  .st-key-bb83-footer .stButton>button{
    min-height:2.1vw!important;font-size:.85vw!important;padding:.25vw!important;
  }
}
/* Below desktop, retain compact readable layouts and avoid overflow. */
@media(max-width:1150px){
  .bb85-preview{min-height:145px}
  .bb85-shortcut-row{grid-template-columns:29px minmax(0,1fr)!important}
  .bb85-shortcut-row small{display:none}
}
@media(max-width:620px){
  .bb85-preview{min-height:140px}
  .bb85-preview-head{white-space:normal}
  .bb85-shortcut-row span{font-size:9px}
  .bb85-team-row small{display:none}
}

/* Specificity lock: these desktop dimensions override v8.4's
   earlier app-scoped !important rules, which beat plain class selectors. */
@media(min-width:1650px){
  :is(#bb85-force-sidebar,[data-testid="stSidebar"]){
    width:14vw!important;min-width:14vw!important;
  }
  :is(#bb85-force-sidebar,[data-testid="stSidebar"]) .bbm-brand{
    min-height:6.4vw!important;padding:.3vw 0 1vw!important;margin-bottom:1.7vw!important;
  }
  :is(#bb85-force-sidebar,[data-testid="stSidebar"]) .bbm-brand img{
    width:4.1vw!important;height:4.1vw!important;
  }
  :is(#bb85-force-sidebar,[data-testid="stSidebar"]) .bbm-brand b{
    font-size:1.7vw!important;
  }
  :is(#bb85-force-sidebar,[data-testid="stSidebar"]) .bbm-brand .bbm-eyebrow{
    font-size:.55vw!important;
  }
  :is(#bb85-force-sidebar,[data-testid="stSidebar"]) .stButton>button{
    min-height:3.4vw!important;font-size:1vw!important;
    padding:.7vw .9vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .st-key-bb83_search{
    width:75%!important;max-width:none!important;
    min-height:4vw!important;padding:.35vw .5vw .35vw 1.25vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .st-key-bb83-suggest .stButton>button{
    min-height:2.5vw!important;font-size:.79vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .bb83-hero{
    min-height:9.4vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .bb83-portrait{
    min-height:9.4vw!important;flex-basis:12vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .bb83-portrait img{
    height:10vw!important;width:12vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .bb83-team-back img{
    height:7.2vw!important;width:7.2vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .bb83-identity h2{
    font-size:2.4vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .bb83-identity-line{
    font-size:.95vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .bb83-identity small{
    font-size:.7vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .bb83-team-badge{
    font-size:.8vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .bb83-hero-metric{
    min-width:6.3vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .bb83-hero-metric label{
    font-size:.85vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .bb83-hero-metric b{
    font-size:1.8vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .bb83-hero-metric em{
    font-size:.69vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .bb83-grade{
    min-width:0!important;flex-basis:9.1vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .bb83-grade b{
    font-size:2.5vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .st-key-bb83-controls [data-baseweb="select"]>div,
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .st-key-bb83-controls [data-baseweb="input"]>div,
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .st-key-bb83-controls [data-testid="stNumberInput"] input{
    min-height:3vw!important;height:3vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .st-key-bb83-controls [data-testid="stSegmentedControl"] button{
    font-size:.86vw!important;min-height:2.6vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .bb83-chart-head strong{
    font-size:1.25vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .bb83-rate-grid{
    gap:.58vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .bb83-rate-card{
    min-height:5.6vw!important;padding:.65vw .3vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .bb83-rate-card small{
    font-size:.83vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .bb83-rate-card b{
    font-size:1.9vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .bb83-rate-card em{
    font-size:.75vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .bb83-split-card{
    min-height:4.7vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .bb83-split-card small{
    font-size:.8vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .bb83-split-card b{
    font-size:1.6vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .bb83-defense{
    min-height:7vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .bb83-defense h4{
    font-size:1vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .bb83-defense-points{
    font-size:.78vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .bb83-take{
    min-height:3.9vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .bb83-take strong{
    font-size:1.25vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .bb83-take>span{
    font-size:.88vw!important;
  }
  :is(#bb85-force,[data-testid="stMain"]:has(.bb83-page-marker)) .st-key-bb83-footer [data-testid="stVerticalBlockBorderWrapper"]{
    min-height:11vw!important;max-height:none!important;
  }
}

</style>
"""

def apply_fidelity_theme():
    st.markdown(FIDELITY_CSS,unsafe_allow_html=True)
