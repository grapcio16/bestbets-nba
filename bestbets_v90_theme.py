"""BestBets v9 reference-first design; completely isolated visual layer."""
import streamlit as st

STYLE = r"""
<style>
:root{
 --bb-orange:#ff791d;
 --bb-orange-soft:#ffab4d;
 --bb-blue:#00baff;
 --bb-blue-deep:#065da8;
 --bb-green:#05ec78;
 --bb-red:#ff514c;
 --bb-bg:#030914;
 --bb-panel:#07192e;
 --bb-border:#2d537c;
}
.stApp, [data-testid="stAppViewContainer"]{
 color:#f8faff!important;
 background:
  radial-gradient(ellipse 24% 60% at 0% 90%,rgba(255,102,21,.09),transparent 67%),
  radial-gradient(ellipse 42% 45% at 100% 0%,rgba(0,114,237,.17),transparent 70%),
  linear-gradient(125deg,#02070f,#041325 57%,#030916)!important;
}
[data-testid="stHeader"]{height:0!important;min-height:0!important;background:transparent!important}
[data-testid="stMain"]{background:transparent!important;min-width:0!important}
[data-testid="stMainBlockContainer"], .block-container {
 max-width:none!important;width:100%!important;
 padding:5px 14px 25px!important;
 margin-left:0!important;margin-right:0!important;
}
[data-testid="stMain"] [data-testid="stVerticalBlock"]{gap:6px!important}
[data-testid="stMain"] [data-testid="stHorizontalBlock"]{gap:10px!important}
[data-testid="stMain"] [data-testid="column"]{min-width:0!important}
[data-testid="stSidebar"]{
 background:
 radial-gradient(ellipse 110% 45% at -20% 102%,rgba(255,104,15,.27),transparent 68%),
 linear-gradient(160deg,#030a17,#07162b 71%,#090d19)!important;
 width:183px!important;min-width:183px!important;
 border-right:1px solid #203e60!important;
 box-shadow:4px 0 25px rgba(0,0,0,.38)!important;
}
[data-testid="stSidebarUserContent"]{padding:6px 11px!important}
[data-testid="stSidebar"] .stVerticalBlock{gap:6px!important}
.bb90-brand{
 display:flex!important;align-items:center;gap:7px;
 margin:0 0 24px!important;padding:4px 0 15px!important;
 border-bottom:0!important;min-height:75px;
}
.bb90-brand img{width:58px!important;height:58px!important;object-fit:contain!important}
.bb90-brand b{font-weight:1000!important;font-style:italic;font-size:21px!important;color:white!important;letter-spacing:-.075em!important;white-space:nowrap}
.bb90-brand b span{color:#ff7426!important}
.bb90-brand small{display:block;letter-spacing:.13em;color:#8cb8ee;font-size:6px;font-weight:950}
[data-testid="stSidebar"] [data-testid="stButton"] button{
 width:100%!important;min-height:41px!important;margin:0!important;
 border:1px solid transparent!important;border-radius:9px!important;
 padding:8px 9px!important;background:transparent!important;
 color:#dce6f5!important;font-size:12px!important;font-weight:800!important;
 text-align:left!important;justify-content:flex-start!important;
 box-shadow:none!important;
}
[data-testid="stSidebar"] [data-testid="stButton"] button p{text-align:left!important;line-height:1.23!important}
[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"]{
 background:linear-gradient(92deg,rgba(252,107,20,.38),rgba(87,47,38,.43) 59%,#0e263d)!important;
 border:1px solid #ff892a!important;border-left:4px solid #ffa23f!important;
 box-shadow:0 0 14px rgba(255,116,21,.43),inset 0 0 12px rgba(253,113,24,.1)!important;
 color:#fff!important;
}
[data-testid="stSidebar"] [data-testid="stButton"] button:hover{border-color:#2b7fa9!important;background:#102943!important}
.bb90-sidebar-divider{height:1px;background:#284665;margin:35px 5px 20px}
.bb90-sidebar-flare{height:30px;margin-top:25px;border-bottom:2px solid rgba(255,128,28,.4)}
/* Blank pages deliberately have no functioning stats/forms yet. */
.bb90-blank-page{
 min-height:450px;display:flex;flex-direction:column;justify-content:center;align-items:center;
 border:1px solid #1a3a5e;border-radius:14px;
 background:radial-gradient(ellipse at center,rgba(0,131,245,.1),transparent 65%),#061326;
}
.bb90-blank-page .bb90-blank-mark{font-size:38px;color:#ff9d43}
.bb90-blank-page h2{font-size:28px;color:#fff!important;margin:10px 0 5px!important}
.bb90-blank-page p{color:#91b2d0;font-size:13px}
/* Search, exact top alignment of reference */
.st-key-bb83_search{
 width:75%!important;max-width:none!important;margin:6px auto 6px!important;
 min-height:52px!important;padding:4px 8px 4px 13px!important;
 border:1.5px solid #00cfff!important;border-radius:100px!important;
 background:linear-gradient(95deg,#04101f,#081d36 73%,#16243c)!important;
 box-shadow:0 0 0 2px rgba(0,160,255,.12),0 0 18px rgba(0,158,255,.61),inset 0 0 16px rgba(0,149,255,.11)!important;
}
.st-key-bb83_search [data-testid="stForm"]{padding:0!important;border:0!important;background:transparent!important}
.st-key-bb83_search [data-testid="stForm"] [data-testid="stHorizontalBlock"]{gap:6px!important;align-items:center!important}
.st-key-bb83_search [data-testid="stTextInput"] input{
 height:40px!important;border:none!important;background:transparent!important;
 font-size:16px!important;font-weight:800!important;box-shadow:none!important;color:#f5fbff!important;
}
.st-key-bb83_search [data-baseweb="input"]>div{background:transparent!important;border:0!important;box-shadow:none!important}
.st-key-bb83_search button[kind="primary"]{
 width:100%!height:43px!important;min-height:43px!important;border-radius:99px!important;
 background:linear-gradient(95deg,#ffae3e,#ff7613)!important;border:1px solid #ffc268!important;
 color:#fff!important;font-size:18px!important;box-shadow:0 0 18px rgba(255,134,25,.62)!important;
}
.st-key-bb83-suggest{width:93%!important;margin:0 auto 10px!important}
.st-key-bb83-suggest [data-testid="stHorizontalBlock"]{gap:8px!important}
.st-key-bb83-suggest .stButton>button{
 min-height:32px!important;padding:5px 8px!important;
 border:1px solid #426a90!important;border-radius:99px!important;
 background:linear-gradient(180deg,#102840,#07192e)!important;
 color:#e7f2ff!important;font-size:11px!important;font-weight:800!important;
 box-shadow:inset 0 1px rgba(144,202,241,.11)!important;
}
.st-key-bb83-suggest .stButton>button:hover{border-color:#00cbff!important;box-shadow:0 0 11px rgba(0,180,255,.3)!important}
.st-key-bb83-suggest .stButton>button p{
 white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;
}
/* Existing player data widgets inherit these styles; no hard-coded demo data. */
.bb83-hero,.bb90-empty-hero{
 display:flex;gap:7px;align-items:stretch;width:100%;
 min-height:126px;border:1px solid #16849b;border-radius:13px;overflow:hidden;
 background:
  radial-gradient(ellipse 20% 90% at 8% 48%,rgba(0,231,130,.24),transparent 92%),
  radial-gradient(ellipse 30% 75% at 100% 101%,rgba(0,130,255,.33),transparent),
  radial-gradient(ellipse 30% 75% at 97% 0%,rgba(255,117,26,.19),transparent),
  linear-gradient(105deg,#062925,#071528 49%,#0a1e38 100%);
 box-shadow:inset 0 1px rgba(156,244,215,.16),0 0 15px rgba(0,138,255,.13);
}
.bb83-hero .bb83-portrait{flex:0 0 155px!important;min-height:126px!important}
.bb83-portrait img{width:155px!important;height:134px!important;object-fit:contain!important}
.bb83-team-back img{width:98px!important;height:98px!important}
.bb83-identity{flex:1 1 220px!important;min-width:160px!important}
.bb83-identity h2{font-size:33px!important;font-weight:1000!important;margin:0 0 7px!important}
.bb83-identity-line{font-size:12px!important}
.bb83-hero-metric{min-width:80px!important}
.bb83-hero-metric b{font-size:23px!important}
.bb83-grade{min-width:112px!important;margin-left:7px!important}
.bb83-grade b{font-size:34px!important}
.st-key-bb83-controls [data-testid="stHorizontalBlock"]{gap:8px!important}
.st-key-bb83-controls [data-baseweb="select"]>div,.st-key-bb83-controls input{
 min-height:38px!important;height:38px!important;border-radius:8px!important;
 background:#0b2038!important;border:1px solid #385e83!important;color:#fff!important;
}
.st-key-bb83-controls [data-testid="stSegmentedControl"]{
 min-height:38px!important;border:1px solid #35577c!important;
 background:#07192c!important;border-radius:9px!important;
}
.st-key-bb83-controls [data-testid="stSegmentedControl"] button[aria-checked="true"]{
 background:linear-gradient(115deg,#076cbb,#052c64)!important;
 color:#fff!important;border:1px solid #07baff!important;
 box-shadow:0 0 10px rgba(0,163,255,.45)!important;
}
.bb83-chart-head strong{font-size:17px!important}
.bb83-chart-head strong span{color:#ffa132!important}
.st-key-bb83-research [data-testid="stPlotlyChart"]{
 border:1px solid #2169a8!important;border-top-color:#ff8c27!important;
 background:linear-gradient(155deg,#071328,#061a2f)!important;
 border-radius:12px!important;padding:4px!important;
}
.bb83-rate-card{background:#07182b!important;border:1px solid #2f5b85!important;border-radius:10px!important;min-height:82px!important}
.bb83-rate-card b{color:#07ea7b!important;font-size:25px!important}
.bb83-defense{border-color:#ff8b2c!important;background:linear-gradient(100deg,#101929,#071828)!important}
.bb83-take,.bb90-empty-take{
 display:flex;align-items:center;gap:17px;min-height:50px;padding:11px 15px;
 margin:8px 0 6px;border:1px solid #f17e27;border-radius:12px;
 background:
 radial-gradient(ellipse 32% 95% at 104% 150%,rgba(0,169,255,.46),transparent 80%),
 linear-gradient(105deg,#19172a,#061a2f 68%,#073055);
 box-shadow:0 0 13px rgba(255,115,23,.14);
}
.bb83-take strong,.bb90-empty-take strong{
 color:#fff;font-size:17px;font-weight:950;white-space:nowrap;
 border-right:1px solid #627d9b;padding-right:16px;
}
.bb90-empty-take strong{color:#ffad45}
.bb90-empty-take span{font-size:12px;color:#afc7e1}
/* The first page has no chosen player. These are genuinely empty reference slots. */
.bb90-empty-hero{padding:13px 15px;align-items:center;min-height:136px}
.bb90-empty-avatar{
 width:96px;height:96px;flex-shrink:0;display:grid;place-items:center;
 border-radius:50%;border:2px solid #14df95;
 color:#4af5b1;font-size:42px;box-shadow:0 0 22px rgba(0,237,134,.24);
}
.bb90-empty-name{flex:1;min-width:0;display:flex;flex-direction:column;gap:6px}
.bb90-empty-label{font-size:9px;font-weight:950;letter-spacing:.14em;color:#8cbbef}
.bb90-empty-name strong{font-size:32px;line-height:1.1;letter-spacing:-.04em}
.bb90-empty-name span{color:#afc4d9;font-size:12px}
.bb90-empty-metric{
 min-width:85px;min-height:64px;padding:7px 10px;
 border-left:1px solid #32587c;display:flex;align-items:center;flex-direction:column;gap:3px;
}
.bb90-empty-metric small,.bb90-empty-grade small{font-size:10px;font-weight:950;color:#adbfda}
.bb90-empty-metric b{font-size:25px;line-height:1;color:#fff}
.bb90-empty-grade{
 border:1px solid #4b8ac4;background:linear-gradient(115deg,#0c2240,#081528);
 border-radius:11px;min-width:125px;min-height:85px;padding:12px 8px;
 text-align:center;box-shadow:0 0 13px rgba(0,137,240,.2);
}
.bb90-empty-grade b{display:block;color:#05ed83;font-size:32px;margin-top:3px}
.bb90-empty-grid{display:grid;grid-template-columns:1.55fr 1fr;gap:13px;margin:12px 0 0}
.bb90-empty-chart{
 min-height:282px;position:relative;overflow:hidden;border:1px solid #246599;
 border-top-color:#ed8b32;border-radius:13px;padding:10px 15px;
 background:linear-gradient(140deg,#07152a,#071d36);
}
.bb90-empty-chart h3{font-size:17px;margin:0!important;font-weight:950}
.bb90-empty-chart h3 span{color:#ffa43d}
.bb90-empty-chart-center{
 display:grid;place-items:center;min-height:215px;text-align:center;
 font-size:14px;color:#78a3cc;
}
.bb90-empty-axis{height:1px;background:#375e87;position:absolute;left:20px;right:20px;bottom:23px}
.bb90-empty-insights{display:flex;flex-direction:column;gap:8px}
.bb90-empty-hits{display:grid;grid-template-columns:repeat(4,1fr);gap:7px}
.bb90-empty-hits div{
 border:1px solid #315986;border-radius:10px;background:#091d34;
 padding:10px 5px;text-align:center;font-size:12px;font-weight:900;
}
.bb90-empty-hits small{display:block;font-size:22px;color:#04ee7e;margin-top:6px}
.bb90-empty-averages{display:grid;grid-template-columns:repeat(3,1fr);gap:7px}
.bb90-empty-averages div{
 text-align:center;border:1px solid #2b547c;border-radius:10px;
 background:#0a1e33;padding:10px 2px;font-size:11px;color:#c7dbf1;
}
.bb90-empty-averages b{display:block;font-size:21px;color:#f7faff}
.bb90-empty-averages div:nth-child(2){border-color:#05bbfa;box-shadow:0 0 12px rgba(0,151,255,.32)}
.bb90-empty-defense{
 border:1px solid #fc882b;border-radius:12px;
 background:radial-gradient(ellipse at 100% 0%,rgba(254,108,20,.21),transparent 70%),#0b1b32;
 padding:13px 14px;min-height:93px;font-size:14px;font-weight:900;
}
.bb90-empty-defense small{font-size:12px;color:#9dbbde;font-weight:600}
/* Permanent six preview panels: no data invented. */
.st-key-bb90-footer{margin-top:12px}
.st-key-bb90-footer [data-testid="stHorizontalBlock"]{gap:9px!important}
.st-key-bb90-footer [data-testid="stVerticalBlockBorderWrapper"]{
 border:1px solid #2476af!important;border-radius:11px!important;
 box-shadow:0 0 12px rgba(0,118,236,.17)!important;
 background:linear-gradient(145deg,#081e36,#071323)!important;
 overflow:hidden!important;
}
.st-key-bb90-footer [data-testid="column"]:nth-child(even) [data-testid="stVerticalBlockBorderWrapper"]{
 border-color:#ea812b!important;
 box-shadow:0 0 11px rgba(249,111,31,.19)!important;
}
.st-key-bb90-footer [data-testid="stVerticalBlockBorderWrapper"]>div{padding:0!important}
.bb90-mini-card{min-height:138px;padding:6px;color:#e9f2ff;overflow:hidden}
.bb90-mini-heading{font-size:11px;color:#f6fbff;font-weight:950;margin:0 0 8px}
.bb90-mini-brand{font-size:10px;font-style:italic;font-weight:950}
.bb90-mini-brand b span{color:#ff7e20}
.bb90-mini-kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:3px;margin:7px 0}
.bb90-mini-kpis div{text-align:center;padding:7px 1px;background:#0d2c48;border:1px solid #1e5c8e;border-radius:6px}
.bb90-mini-kpis small{display:block;font-size:7px;white-space:nowrap;overflow:hidden}
.bb90-mini-kpis strong{font-size:15px;color:#ffd07b}
.bb90-mini-kpis .green{color:#00ed7a}
.bb90-mini-kpis .red{color:#ff514c}
.bb90-mini-person{display:flex;gap:6px;align-items:center;border:1px solid #21537d;border-radius:7px;background:#0b253e;padding:5px;font-size:10px}
.bb90-mini-person span{font-weight:900}
.bb90-mini-person small{display:block;color:#9dc0dd;font-size:8px;font-weight:500}
.bb90-mini-match{display:flex;justify-content:space-between;align-items:center;min-height:73px;text-align:center}
.bb90-mini-match>span:nth-child(2){display:flex;flex-direction:column}
.bb90-mini-match small{font-size:8px;color:#8aaed0}
.bb90-mini-match b{font-size:15px}
.bb90-orb{font-size:36px;color:#11d890}
.bb90-orb.right{color:#fa6b39}
.bb90-mini-bar{height:9px;background:#dd4938;border-radius:7px;overflow:hidden}
.bb90-mini-bar span{display:block;background:#01d18e;width:50%;height:100%}
.bb90-mini-caption{font-size:8px;color:#8ab1d5;padding-top:5px}
.bb90-mini-search{font-size:10px;color:#b3d1e8;white-space:nowrap;overflow:hidden;padding:5px;background:#102b46;border:1px solid #355c7e;border-radius:7px}
.bb90-mini-list{padding:5px 3px;border-bottom:1px solid #1a3b5b;font-size:10px;white-space:nowrap;overflow:hidden;color:#d5e7f5}
.bb90-mini-list b{color:#fa9932;margin-right:6px}
.bb90-mini-list em{float:right;color:#88abc8;font-size:9px;font-style:normal}
.bb90-mini-short{display:grid;grid-template-columns:27px 1fr 88px;gap:3px;align-items:center;font-size:9px;padding:4px 0;border-bottom:1px solid #534130}
.bb90-mini-short b{color:#fff}.bb90-mini-short span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.bb90-mini-short small{text-align:right;font-size:8px;color:#9daeca;white-space:nowrap;overflow:hidden}
.st-key-bb90-footer [data-testid="stButton"] button{
 min-height:30px!important;padding:3px!important;
 background:transparent!important;border:0!important;
 color:#e2efff!important;font-size:12px!important;
 font-weight:850!important;box-shadow:none!important;border-radius:7px!important;
}
.st-key-bb90-footer [data-testid="stButton"] button:hover{background:#0d3154!important;box-shadow:0 0 12px rgba(0,152,255,.23)!important}
/* Existing Player Props data: chart and analytics occupy the same row. */
.st-key-bb83-research [data-testid="stHorizontalBlock"]{gap:12px!important}
.st-key-bb83-research .bb83-rate-grid{grid-template-columns:repeat(4,minmax(0,1fr))!important}
@media (min-width:1650px) {
 [data-testid="stSidebar"]{width:12.5vw!important;min-width:12.5vw!important}
 .bb90-brand img{width:4.4vw!important;height:4.4vw!important}
 .bb90-brand b{font-size:1.5vw!important}
 [data-testid="stSidebar"] [data-testid="stButton"] button{font-size:.92vw!important;min-height:3vw!important}
 [data-testid="stMainBlockContainer"]{padding:.7vw 1vw 2vw!important}
 .st-key-bb83_search{min-height:3.6vw!important;padding:.3vw .5vw!important}
 .st-key-bb83_search [data-testid="stTextInput"] input{height:2.9vw!important;font-size:1.12vw!important}
 .st-key-bb83_search button[kind="primary"]{height:3vw!important;min-height:3vw!important;font-size:1.3vw!important}
 .st-key-bb83-suggest .stButton>button{min-height:2.5vw!important;font-size:.76vw!important}
 .bb83-hero,.bb90-empty-hero{min-height:9.5vw!important}
 .bb90-empty-avatar{height:6.5vw;width:6.5vw;font-size:2.8vw}
 .bb90-empty-name strong{font-size:2.2vw}
 .bb90-empty-name span{font-size:.9vw}
 .bb90-empty-metric{min-width:6.5vw}
 .bb90-empty-metric b{font-size:1.9vw}
 .bb90-empty-grade{min-width:9vw}
 .bb90-empty-grid{gap:1vw}
 .bb90-empty-chart{min-height:18.5vw}
 .bb90-empty-chart-center{min-height:14vw}
 .bb90-empty-insights{gap:.6vw}
 .bb90-empty-hits div{padding:.75vw .2vw;font-size:1vw}
 .bb90-empty-hits small{font-size:1.7vw}
 .bb90-empty-defense{min-height:6vw;padding:1vw}
 .bb90-empty-take{min-height:3.8vw}
 .bb90-mini-card{min-height:10.5vw;padding:.65vw}
 .bb90-mini-heading{font-size:.83vw}
 .bb90-mini-brand{font-size:.83vw}
 .bb90-mini-kpis small{font-size:.56vw}
 .bb90-mini-kpis strong{font-size:1.15vw}
 .bb90-mini-person{font-size:.8vw}
 .bb90-mini-match{min-height:5.7vw}
 .bb90-orb{font-size:2.7vw}
 .bb90-mini-search{font-size:.8vw;padding:.4vw}
 .bb90-mini-list{font-size:.8vw;padding:.4vw .2vw}
 .bb90-mini-short{font-size:.72vw;padding:.34vw 0;grid-template-columns:2.3vw 1fr 6vw}
 .bb90-mini-short small{font-size:.65vw}
 .st-key-bb90-footer [data-testid="stButton"] button{font-size:.92vw!important;min-height:2.4vw!important}
 .bb83-identity h2{font-size:2.3vw!important}
 .bb83-hero-metric b{font-size:1.8vw!important}
 .bb83-grade b{font-size:2.5vw!important}
}
@media(max-width:1100px){
 .bb90-empty-hero{flex-wrap:wrap}
 .bb90-empty-grid{grid-template-columns:1fr}
 .st-key-bb90-footer [data-testid="stHorizontalBlock"]{flex-wrap:wrap!important}
 .st-key-bb90-footer [data-testid="stHorizontalBlock"]>[data-testid="column"]{flex:1 1 31%!important;min-width:31%!important}
 .st-key-bb83-research [data-testid="stHorizontalBlock"]{flex-wrap:wrap!important}
 .st-key-bb83-research [data-testid="stHorizontalBlock"]>[data-testid="column"]{flex:1 1 100%!important;min-width:100%!important}
}
@media(max-width:650px){
 [data-testid="stMainBlockContainer"]{padding:12px 8px 25px!important}
 .st-key-bb83_search{width:100%!important}
 .st-key-bb83-suggest{width:100%!important}
 .st-key-bb83-suggest [data-testid="stHorizontalBlock"]{flex-wrap:wrap!important}
 .st-key-bb83-suggest [data-testid="stHorizontalBlock"]>[data-testid="column"]{flex:1 1 47%!important;min-width:47%!important}
 .bb90-empty-name strong{font-size:23px}
 .bb90-empty-metric{flex:1 1 22%}
 .bb90-empty-hits{grid-template-columns:repeat(2,1fr)}
 .st-key-bb90-footer [data-testid="stHorizontalBlock"]>[data-testid="column"]{flex:1 1 47%!important;min-width:47%!important}
 .bb90-mini-short{grid-template-columns:27px 1fr}.bb90-mini-short small{display:none}
}
</style>
"""
def apply_v90_theme():
    st.markdown(STYLE,unsafe_allow_html=True)
