"""BestBets v8.3: approved-reference presentation layer.

The reference screenshot is a layout specification, not a static background:
search, filters, graphs, cards and links remain interactive and accessible.
Data is always rendered from real NBA/ESPN sources, never from the image.
"""
from __future__ import annotations
import streamlit as st

REFERENCE_CSS = r"""
<style>
:root{
 --bb83-ink:#020814;--bb83-deep:#051126;--bb83-panel:#07192e;
 --bb83-blue:#00baff;--bb83-blue2:#0878ff;--bb83-orange:#ff7a21;
 --bb83-green:#09ed79;--bb83-red:#ff574d;
 --bb83-line:#315a83;--bb83-white:#f5faff;
}
.stApp,[data-testid="stAppViewContainer"]{
 color:#f4f9ff!important;
 background:
 radial-gradient(ellipse 65% 60% at 104% -8%,rgba(0,116,222,.16),transparent),
 radial-gradient(ellipse 49% 45% at 6% 72%,rgba(255,91,19,.055),transparent),
 linear-gradient(139deg,#01060e 0%,#041124 63%,#020814 100%)!important;
}
[data-testid="stHeader"]{
 background:linear-gradient(90deg,rgba(2,7,16,.92),rgba(2,9,21,.96))!important;
 height:34px!important;
}
[data-testid="stToolbar"]{opacity:.82}
.block-container{
 max-width:1690px!important;
 padding:6px 17px 24px!important;
}
[data-testid="stSidebar"]{
 width:219px!important;min-width:219px!important;
 background:
 radial-gradient(ellipse at 100% 100%,rgba(255,103,20,.14),transparent 42%),
 linear-gradient(177deg,#040d19,#05152a 70%,#060b17)!important;
 border-right:1px solid #173d66!important;
 box-shadow:4px 0 32px rgba(0,0,0,.33)!important;
}
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"]{
 padding:8px 13px 14px!important;
}
[data-testid="stSidebar"] .stVerticalBlock{gap:5px!important}
.bbm-brand{margin:0 0 22px!important;padding:6px 7px 17px!important;border-bottom:1px solid #2c4b6e!important}
.bbm-brand b{font-size:23px!important;font-style:italic!important;font-weight:950!important;letter-spacing:-.058em!important;white-space:nowrap}
.bbm-brand b span{color:#ff751e!important}
.bbm-brand img{width:52px!important;height:52px!important;box-shadow:0 0 22px rgba(255,127,27,.25)}
.bbm-brand .bbm-eyebrow{font-size:8px!important;color:#77b8f4!important}
.bbm-nav-label{font-size:9px!important;letter-spacing:.13em!important;margin:7px 9px 8px!important;color:#7193bf!important}
[data-testid="stSidebar"] .stButton>button{
 min-height:45px!important;
 margin:1px 0!important;
 background:transparent!important;
 border:1px solid transparent!important;
 border-radius:12px!important;
 font-size:13px!important;letter-spacing:-.01em!important;
 color:#ebf4ff!important;
 padding:11px 14px!important;
 font-weight:700!important;
}
[data-testid="stSidebar"] .stButton>button:hover{
 background:#102849!important;
 border-color:#315e86!important;
 box-shadow:0 0 15px rgba(0,147,255,.12)!important;
}
[data-testid="stSidebar"] .stButton>button[kind="primary"]{
 background:
 linear-gradient(111deg,rgba(255,109,22,.38),rgba(113,49,30,.23) 54%,rgba(13,32,57,.88))!important;
 color:#fff!important;
 border:1px solid #ff8b39!important;
 box-shadow:inset 3px 0 #ffa044,0 0 17px rgba(255,102,25,.35)!important;
}
.bbm-sidebar-footer{font-size:9px!important;color:#82a8d0!important;margin-top:11px!important}
.bbm-topbar{
 padding:12px 20px!important;
 background:linear-gradient(111deg,#0d2543,#09172c 70%,#111f3a)!important;
 border:1px solid #2a5483!important;
 border-radius:14px!important;
 margin:5px 0 10px!important;
}
.bbm-topbar h1{font-size:26px!important;margin:2px 0!important}
.bbm-topbar p{font-size:11px!important}
.stTextInput input,.stNumberInput input,.stTextArea textarea{
 color:#f6fbff!important;background:linear-gradient(115deg,#081b30,#10192b)!important;
 border:1px solid #345b88!important;
}
.stTextInput input:focus{
 border-color:#00c5ff!important;
 box-shadow:0 0 0 2px rgba(0,180,255,.2),0 0 18px rgba(0,191,255,.20)!important;
}
.stButton:not([data-testid="stSidebar"] .stButton)>button[kind="primary"]{
 background:linear-gradient(105deg,#ff9f3f,#ff6e14)!important;
 border-color:#ffc169!important;color:#081023!important;
 box-shadow:0 0 21px rgba(255,115,23,.26)!important;
 font-weight:950!important;
}
.stButton:not([data-testid="stSidebar"] .stButton)>button:hover{
 border-color:#48b5ff!important;box-shadow:0 0 12px rgba(0,179,255,.14)!important;
}
.bbm-ref-aux{
 padding:6px 0 0;color:#88aacb;font-size:11px;
}
.bbm-ref-screen{width:100%}
.bb83-kicker{
 font-weight:950;letter-spacing:.18em;color:#ff9b47;font-size:10px;
}
.bb83-page-marker{height:0;overflow:hidden;margin:0!important;padding:0!important}
/* Search toolbar — prominent cyan focus ring and bright orange search action. */
.st-key-bb83_search{
 position:relative;
 border:1px solid #00bdfd!important;border-radius:999px!important;
 background:linear-gradient(100deg,#041021,#071d36 60%,#171c2c)!important;
 padding:6px 9px 6px 17px!important;
 box-shadow:0 0 0 2px rgba(0,173,255,.14),0 0 22px rgba(0,177,253,.30),inset 0 0 19px rgba(14,88,170,.15)!important;
}
.st-key-bb83_search [data-testid="stForm"]{border:0!important;padding:0!important;background:transparent!important}
.st-key-bb83_search [data-testid="stForm"] [data-testid="stVerticalBlock"]{gap:0!important}
.st-key-bb83_search [data-testid="stForm"] [data-testid="stHorizontalBlock"]{gap:.5rem!important;align-items:center!important}
.st-key-bb83_search [data-testid="stTextInput"] input{
 height:40px!important;border:0!important;background:transparent!important;
 box-shadow:none!important;font-weight:800!important;font-size:17px!important;
}
.st-key-bb83_search button[kind="primary"]{
 border-radius:99px!important;min-height:42px!important;
 font-size:18px!important;
}
.bb83-shortcut-title{font-size:10px;color:#799aba;display:none}
.st-key-bb83-suggest [data-testid="stHorizontalBlock"]{gap:8px!important}
.st-key-bb83-suggest .stButton>button{
 min-height:33px!important;padding:5px 9px!important;
 background:linear-gradient(105deg,#0b192c,#0c1c33)!important;
 border:1px solid #385979!important;
 border-radius:99px!important;font-size:11px!important;
 white-space:normal!important;color:#e6f3ff!important;
 box-shadow:inset 0 0 12px rgba(29,97,173,.11)!important;
}
.st-key-bb83-suggest .stButton>button:hover{
 border-color:#00aaff!important;box-shadow:0 0 16px rgba(0,170,255,.25)!important;
}
[data-testid="stMain"]:has(.bb83-page-marker) .block-container>.stVerticalBlock{
 gap:6px!important;
}
[data-testid="stMain"]:has(.bb83-page-marker) .stCaptionContainer p{
 font-size:10px!important;color:#81a1be!important;
}
[data-testid="stMain"]:has(.bb83-page-marker) .stAlert{
 padding:8px 12px!important;font-size:12px!important;
}
.bb83-empty{
 margin:10px 0;padding:19px 21px;
 min-height:205px;border:1px solid #2c638e;border-radius:18px;
 background:radial-gradient(ellipse at 11% 12%,rgba(0,182,237,.18),transparent 40%),
  radial-gradient(ellipse at 100% 100%,rgba(255,105,21,.19),transparent 38%),#08162a;
 display:flex;flex-direction:column;justify-content:center;
 box-shadow:inset 0 1px rgba(121,197,247,.13);
}
.bb83-empty strong{font-size:27px;font-weight:950;display:block;color:#f8fbff}
.bb83-empty p{color:#b2c8e2;font-size:13px;max-width:640px}
.bb83-empty-row{display:flex;gap:8px;flex-wrap:wrap}
.bb83-empty-chip{border:1px solid #38779b;padding:7px 11px;border-radius:10px;background:#0b2741;color:#9deaff;font-weight:800;font-size:12px}
/* Featured player hero. Photo and all metrics always share the same card. */
.bb83-hero{
 display:flex;align-items:stretch;gap:8px;
 border:1px solid #2a7896;border-radius:18px;
 min-height:124px;
 background:radial-gradient(ellipse at 7% 65%,rgba(0,197,139,.17),transparent 31%),
  radial-gradient(ellipse at 99% 98%,rgba(246,102,27,.23),transparent 30%),
  linear-gradient(113deg,#072b2b,#061628 34%,#041125 74%,#10223a);
 box-shadow:inset 0 1px rgba(107,244,205,.22),0 0 17px rgba(0,164,211,.12);
 overflow:hidden;padding:0 12px 0 0;
}
.bb83-portrait{
 position:relative;flex:0 0 170px;min-height:125px;
 display:flex;align-items:flex-end;justify-content:center;
 background:radial-gradient(circle at 38% 47%,rgba(45,235,153,.21),transparent 65%);
}
.bb83-portrait img{
 position:relative;z-index:1;height:128px!important;width:170px!important;
 max-width:100%!important;object-fit:contain!important;object-position:bottom!important;
 filter:drop-shadow(0 8px 9px rgba(0,0,0,.48));
}
.bb83-portrait .bb83-team-back{position:absolute;z-index:0;top:15px;left:14px;opacity:.20}
.bb83-team-back img{width:95px!important;height:95px!important;object-fit:contain}
.bb83-identity{
 flex:1 1 250px;min-width:170px;display:flex;flex-direction:column;
 justify-content:center;padding:13px 4px;
}
.bb83-identity h2{
 font-size:clamp(24px,2.5vw,39px)!important;
 font-weight:950!important;letter-spacing:-.055em!important;
 margin:0 0 8px!important;line-height:1.05!important;
 white-space:nowrap;
}
.bb83-identity-line{display:flex;align-items:center;gap:10px;flex-wrap:wrap;color:#dce8f9;font-size:12px}
.bb83-team-badge{
 display:inline-flex;align-items:center;gap:5px;
 border:1px solid #05d675;border-radius:20px;padding:3px 9px;
 background:linear-gradient(95deg,#054727,#033323);
 color:#baffd5;font-weight:950;font-size:12px;
 box-shadow:0 0 9px rgba(7,237,113,.29);
}
.bb83-identity small{color:#8dabcb;font-size:10px;margin-top:7px}
.bb83-hero-metrics{display:flex;align-items:center;flex:0 0 auto;padding:9px 0;gap:0}
.bb83-hero-metric{
 min-width:88px;padding:6px 11px;display:flex;flex-direction:column;
 justify-content:center;align-items:center;gap:4px;border-left:1px solid #2e4a69;
}
.bb83-hero-metric label{
 font-size:10px;font-weight:850;color:#b5c8df;letter-spacing:.05em
}
.bb83-hero-metric b{font-size:23px;color:#fff;font-weight:950;line-height:1}
.bb83-hero-metric em{font-size:10px;color:#aec5e0;font-style:normal}
.bb83-grade{
 align-self:center;min-width:110px;padding:10px 9px;
 margin-left:10px;border:1px solid #577ca4;
 border-radius:12px;text-align:center;
 background:linear-gradient(150deg,#11253d,#08152b);
 box-shadow:0 0 13px rgba(2,156,237,.12);
}
.bb83-grade small{font-size:10px;color:#b5c5d9;font-weight:850;display:block;letter-spacing:.05em}
.bb83-grade b{display:block;color:#22ec91;font-size:34px;font-weight:950;line-height:1.18;margin-top:4px}
.bb83-grade em{display:block;color:#82a5c0;font-size:9px;font-style:normal}
/* Single action row, replacing stacked controls. */
.st-key-bb83-controls{margin:2px 0 1px}
.st-key-bb83-controls [data-testid="stHorizontalBlock"]{gap:7px!important;align-items:flex-end!important}
.st-key-bb83-controls [data-testid="stVerticalBlock"]{gap:3px!important}
.st-key-bb83-controls label p{
 color:#a8c5e3!important;font-weight:850!important;font-size:10px!important;
}
.st-key-bb83-controls [data-baseweb="select"]>div,.st-key-bb83-controls input{
 height:34px!important;min-height:34px!important;
 border-radius:9px!important;border:1px solid #365c81!important;
 background:linear-gradient(125deg,#0e2137,#0a172b)!important;
 font-size:13px!important;font-weight:850!important;color:#fff!important;
}
.st-key-bb83-controls [data-testid="stSegmentedControl"]{
 background:linear-gradient(125deg,#0e2137,#08172c)!important;
 border:1px solid #2a517e!important;border-radius:10px!important;
 padding:2px!important;
}
.st-key-bb83-controls [data-testid="stSegmentedControl"] button{
 font-size:11px!important;font-weight:900!important;
 padding:5px 6px!important;white-space:nowrap!important;
 min-height:31px!important;
}
.st-key-bb83-controls [data-testid="stSegmentedControl"] button[aria-checked="true"]{
 border:1px solid #00adff!important;
 background:linear-gradient(115deg,#0966b4,#0d2951)!important;
 color:#fff!important;box-shadow:0 0 11px rgba(0,175,255,.46)!important;
}
.st-key-bb83-controls [data-testid="stRadio"]{
 margin-top:2px;
}
/* Chart (left) and stats + matchup (right): one horizontal compact workspace */
.st-key-bb83-research [data-testid="stHorizontalBlock"]{gap:10px!important;align-items:stretch!important}
.st-key-bb83-research [data-testid="stVerticalBlock"]{gap:5px!important}
.bb83-chart-head{
 margin:0;padding:7px 10px 4px;display:flex;justify-content:space-between;align-items:baseline;
 gap:8px;
}
.bb83-chart-head strong{font-size:15px;font-weight:950;color:#fff}
.bb83-chart-head strong span{color:#ff9c47;font-size:18px;margin-right:7px}
.bb83-chart-head small{font-size:10px;color:#97c3e8}
.st-key-bb83-research [data-testid="stPlotlyChart"]{
 border:1px solid #116aaf!important;border-radius:14px!important;
 padding:0px 6px 2px!important;
 background:radial-gradient(ellipse at 0 0,rgba(255,130,18,.12),transparent 35%),
  linear-gradient(115deg,#08152b,#03162a)!important;
 box-shadow:inset 0 0 19px rgba(0,139,255,.09),0 0 12px rgba(0,161,255,.09);
}
.bb83-right-panel{display:flex;flex-direction:column;gap:8px;padding-top:7px}
.bb83-rate-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}
.bb83-rate-card{
 padding:9px 5px;text-align:center;
 background:linear-gradient(142deg,#091c33,#051126);
 border:1px solid #2d5980;border-radius:11px;min-width:0;
 box-shadow:inset 0 1px rgba(88,176,237,.16);
}
.bb83-rate-card small{display:block;color:#c0d0e0;font-size:11px;font-weight:800}
.bb83-rate-card b{
 display:block;color:#0fea85;font-size:24px;font-weight:950;
 letter-spacing:-.04em;margin:3px 0 1px;
}
.bb83-rate-card b.under{color:#ff7e82}
.bb83-rate-card em{font-size:10px;color:#bfcee2;font-style:normal}
.bb83-split-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}
.bb83-split-card{
 text-align:center;border:1px solid #31557f;padding:9px 5px;
 border-radius:10px;background:#0b1c34;
}
.bb83-split-card small{display:block;color:#b4c8e0;font-size:10px}
.bb83-split-card b{font-size:20px;color:#eff8ff;font-weight:950}
.bb83-split-card.accent{
 border-color:#03b6ff;background:radial-gradient(ellipse at center,rgba(0,126,255,.25),#071c37);
 box-shadow:0 0 13px rgba(0,174,255,.29),inset 0 0 11px rgba(15,89,180,.2)
}
.bb83-defense{
 border:1px solid #fc822d;border-radius:13px;padding:12px 13px;
 background:radial-gradient(ellipse at 100% 0%,rgba(245,103,26,.27),transparent 42%),
  linear-gradient(115deg,#0d1a2e,#071426);
 box-shadow:0 0 15px rgba(249,103,32,.16);
}
.bb83-defense h4{
 margin:0 0 8px!important;font-size:15px!important;
 font-weight:950!important;color:#f4fbff!important;
}
.bb83-defense h4 span{color:#ffa04a;margin-right:5px}
.bb83-defense-inner{display:flex;align-items:center;gap:12px}
.bb83-defense-logo{flex:0 0 56px;display:grid;place-items:center}
.bb83-defense-logo img{height:52px!important;width:52px!important;object-fit:contain}
.bb83-defense-points{color:#d5e2f2;font-size:11px;line-height:1.9}
.bb83-defense-points div:before{content:"●";font-size:9px;color:#05ed75;margin-right:7px}
.bb83-defense-points b{color:#fff}
.bb83-take{
 display:flex;align-items:center;gap:20px;margin:8px 0 3px;
 min-height:54px;padding:12px 16px;border-radius:13px;
 border:1px solid #ff8f39;
 background:
 radial-gradient(ellipse at 102% 102%,rgba(0,130,255,.33),transparent 30%),
 linear-gradient(100deg,rgba(241,96,26,.17),#061326 55%,#0c2541);
 box-shadow:0 0 15px rgba(255,109,27,.17),inset 0 1px rgba(254,163,90,.15);
}
.bb83-take strong{
 color:#fff;font-size:18px;font-weight:950;white-space:nowrap;
 border-right:1px solid #5685a5;padding-right:18px;
}
.bb83-take strong span{color:#ff8c27;font-size:19px;margin-right:5px}
.bb83-take>span{color:#dceaf9;font-size:12px;line-height:1.5}
.bb83-take em{font-style:normal;color:#02ed78;font-weight:950}
.bb83-pra-inline{
 display:flex;gap:8px;flex-wrap:wrap;align-items:center;
 font-size:11px;color:#ddedff;
 background:#0e243b;border:1px solid #316288;border-radius:9px;padding:7px 11px;
}
.bb83-pra-inline strong{color:#ffb16f;font-weight:900}
.bb83-pra-inline b{color:#1af3a1}
.bb83-extra-options [data-testid="stExpander"]{border:1px solid #273d5a!important}
/* Six functional link cards, matching the screenshot's bottom preview strip. */
.bb83-footer-heading{border-top:1px solid #193b5c;padding-top:7px;margin-top:5px;color:#799dc3;font-size:10px;letter-spacing:.14em;font-weight:900}
.st-key-bb83-footer [data-testid="stHorizontalBlock"]{gap:8px!important}
.st-key-bb83-footer [data-testid="stVerticalBlock"]{gap:4px!important}
.st-key-bb83-footer [data-testid="stVerticalBlockBorderWrapper"]{
 background:linear-gradient(140deg,#09233e,#041529 80%)!important;
 border:1px solid #1577c3!important;border-radius:14px!important;
 box-shadow:0 0 12px rgba(0,137,255,.13)!important;
}
.st-key-bb83-footer [data-testid="stVerticalBlockBorderWrapper"]:nth-child(odd){
 border-color:#cf7733!important;
}
.bb83-mini-kicker{font-size:10px;color:#ffa85e;font-weight:900;letter-spacing:.04em}
.bb83-mini-title{font-weight:950;font-size:13px;color:#f4faff;margin:4px 0}
.bb83-mini-body{font-size:11px;color:#a7c4e4;line-height:1.55;min-height:34px}
.bb83-mini-body b{color:#22ec9e;font-weight:950}
.st-key-bb83-footer .stButton>button{
 font-size:11px!important;min-height:29px!important;padding:4px!important;
 border:1px solid #305e8e!important;border-radius:9px!important;
 color:#fff!important;background:linear-gradient(120deg,#142b49,#122139)!important;
}
/* Remove default spacer balloons from Streamlit in dedicated props workspace. */
[data-testid="stMain"]:has(.bb83-page-marker) .stMarkdown{margin-bottom:0!important}
[data-testid="stMain"]:has(.bb83-page-marker) [data-testid="stBottomBlockContainer"]{display:none}
/* Ensure everything stays readable on smaller screens; do not clip content. */
@media(max-width:1350px){
 .bb83-portrait{flex-basis:120px}
 .bb83-portrait img{width:130px!important}
 .bb83-hero-metric{min-width:67px;padding:4px 7px}
 .bb83-hero-metric b{font-size:20px}
 .bb83-grade{min-width:78px;margin-left:2px}
 .bb83-identity h2{font-size:27px!important}
}
@media(max-width:1060px){
 .bb83-hero{flex-wrap:wrap;justify-content:space-between}
 .bb83-identity{flex:1}
 .bb83-hero-metrics{width:calc(100% - 24px);justify-content:space-evenly}
 .st-key-bb83-research [data-testid="stHorizontalBlock"]{flex-wrap:wrap!important}
 .st-key-bb83-research [data-testid="stHorizontalBlock"]>div{min-width:100%!important}
 .bb83-rate-card b{font-size:22px}
}
@media(max-width:700px){
 .block-container{padding:5px 10px 28px!important}
 .bb83-hero{gap:2px}
 .bb83-portrait{flex:0 0 92px;min-height:108px}
 .bb83-portrait img{height:110px!important;width:100px!important}
 .bb83-identity h2{font-size:23px!important;white-space:normal}
 .bb83-identity-line{font-size:10px}
 .bb83-hero-metrics{flex-wrap:wrap}
 .bb83-hero-metric{flex:1 1 60px}
 .bb83-grade{min-width:74px}
 .bb83-rate-grid{gap:4px}
 .bb83-rate-card b{font-size:18px}
 .bb83-rate-card small{font-size:9px}
 .bb83-take{display:block}
 .bb83-take strong{display:block;border-right:0;border-bottom:1px solid #315779;padding:0 0 7px;margin-bottom:7px}
 .st-key-bb83_search [data-testid="stTextInput"] input{font-size:13px!important}
 .st-key-bb83-suggest [data-testid="stHorizontalBlock"]{flex-wrap:wrap!important}
 .st-key-bb83-suggest [data-testid="stHorizontalBlock"]>div{flex:1 1 46%!important;min-width:46%!important}
 .st-key-bb83-footer [data-testid="stHorizontalBlock"]{flex-wrap:wrap!important}
 .st-key-bb83-footer [data-testid="stHorizontalBlock"]>div{flex:1 1 46%!important;min-width:46%!important}
 .st-key-bb83-controls [data-testid="stHorizontalBlock"]{flex-wrap:wrap!important}
 .st-key-bb83-controls [data-testid="stHorizontalBlock"]>div{flex:1 1 44%!important;min-width:44%!important}
}
</style>
"""

def apply_reference_theme():
    st.markdown(REFERENCE_CSS,unsafe_allow_html=True)
