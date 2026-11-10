"""Original BestBets design system — responsive dark NBA intelligence UI.

One global stylesheet ensures Center, Schedule, Simulations, Player screens,
Odds/Props, Tracker and Research share identical navigation, typography,
control surfaces and chart containers. All styles are presentation only.
"""
import streamlit as st

PREMIUM_CSS = r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600;700;800&display=swap');
:root {
  --bb-void:#070b17; --bb-bg:#091124; --bb-surface:#101b32;
  --bb-surface-2:#152440; --bb-stroke:#273b60; --bb-stroke-hi:#415c8e;
  --bb-text:#f0f5ff; --bb-muted:#93a8c7;
  --bb-blue:#4c8dff; --bb-violet:#8375ff; --bb-mint:#2cddb1;
  --bb-red:#fa6478; --bb-gold:#f6be64;
  --bb-radius:18px;
}
html,body,[data-testid="stAppViewContainer"]{font-family:'DM Sans',sans-serif!important}
.stApp,[data-testid="stAppViewContainer"]{
 background:
   radial-gradient(ellipse at 85% -5%,rgba(70,65,188,.21),transparent 40%),
   radial-gradient(ellipse at 12% 32%,rgba(31,76,146,.15),transparent 42%),
   linear-gradient(160deg,var(--bb-void),var(--bb-bg) 55%,#090d1b)!important;
 color:var(--bb-text)!important;
}
[data-testid="stHeader"]{background:rgba(7,11,23,.85)!important;backdrop-filter:blur(16px)}
.block-container{max-width:1490px;padding-top:1.25rem;padding-bottom:4rem}
h1,h2,h3,h4,h5,.bb-title{font-family:'Space Grotesk',sans-serif!important;letter-spacing:-.035em!important;color:var(--bb-text)!important}
h2{font-size:clamp(1.5rem,2vw,1.95rem)!important}
h3{font-size:clamp(1.14rem,1.6vw,1.38rem)!important}
p,.stMarkdown p{line-height:1.58}
[data-testid="stCaptionContainer"] p,.stCaption{color:var(--bb-muted)!important;font-size:.81rem}
hr,[data-testid="stDivider"]{border-color:var(--bb-stroke)!important}
[data-testid="stSidebar"]{
 background:linear-gradient(165deg,#101932,#0b1427 55%,#0a1021)!important;
 border-right:1px solid #283756!important;
 box-shadow:15px 0 50px rgba(2,5,16,.27)!important;
}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"]{gap:.62rem}
[data-testid="stSidebar"] .stRadio [role="radiogroup"]{gap:4px}
[data-testid="stSidebar"] .stRadio [role="radiogroup"] label{
 border-radius:12px;padding:9px 11px;transition:background .15s,border-color .15s;
 border:1px solid transparent;font-weight:600;
}
[data-testid="stSidebar"] .stRadio [role="radiogroup"] label:hover{background:#182b4a;border-color:#29436d}
[data-testid="stSidebar"] .stRadio [role="radiogroup"] label:has(input:checked){
 background:linear-gradient(100deg,rgba(76,141,255,.21),rgba(131,117,255,.08));
 border-color:rgba(87,135,241,.6);
 box-shadow:inset 3px 0 var(--bb-blue);
}
[data-testid="stSidebar"] .stRadio [role="radiogroup"] [data-testid="stMarkdownContainer"] p{color:#dfe9ff!important}
[data-testid="stMetric"],[data-testid="stVerticalBlockBorderWrapper"]{
 background:linear-gradient(150deg,rgba(24,40,70,.94),rgba(13,23,43,.95))!important;
 border:1px solid var(--bb-stroke)!important;border-radius:var(--bb-radius)!important;
 box-shadow:0 11px 32px rgba(0,0,0,.1);
}
[data-testid="stMetric"]{padding:17px 19px!important;min-height:100px}
[data-testid="stMetricLabel"] p{color:var(--bb-muted)!important;font-size:11px!important;text-transform:uppercase;letter-spacing:.09em;font-weight:800!important}
[data-testid="stMetricValue"]{font-family:'Space Grotesk',sans-serif!important;font-weight:800!important;font-size:clamp(24px,2.3vw,34px)!important;color:#f8fbff!important}
[data-testid="stMetricDelta"]{font-weight:700}
.stButton button,.stDownloadButton button,[data-testid="stFormSubmitButton"] button{
 border-radius:12px!important;min-height:40px!important;border:1px solid #345078!important;
 background:#172742!important;color:#eaf3ff!important;
 font-family:'DM Sans',sans-serif!important;font-weight:750!important;
 transition:transform .15s,box-shadow .15s,background .15s;
}
.stButton button:hover,.stDownloadButton button:hover,[data-testid="stFormSubmitButton"] button:hover{
 background:#213c64!important;border-color:#5a85c1!important;
 transform:translateY(-1px);box-shadow:0 5px 17px rgba(22,89,185,.18);
}
.stButton button[kind="primary"],[data-testid="stFormSubmitButton"] button[kind="primary"]{
 background:linear-gradient(112deg,#4c88fe,#6a66ed)!important;
 border-color:#719fff!important;color:white!important;
 box-shadow:0 7px 22px rgba(69,97,246,.18)!important;
}
.stButton button[kind="primary"]:hover{background:linear-gradient(112deg,#669bff,#7b79f8)!important}
.stDownloadButton button{background:linear-gradient(105deg,#133c44,#164f52)!important;border-color:#2b817a!important;color:#aaf4e2!important}
.stButton button:disabled,.stDownloadButton button:disabled{opacity:.45;transform:none}
[data-baseweb="input"] > div,[data-baseweb="select"] > div,
[data-baseweb="textarea"] > div,[data-testid="stDateInput"] input,
[data-testid="stNumberInput"] input {
 background:#101d35!important;color:#f2f6ff!important;
 border:1px solid #30476d!important;border-radius:11px!important;
}
[data-baseweb="input"] > div:focus-within,[data-baseweb="select"] > div:focus-within{
 border-color:#6c8bff!important;box-shadow:0 0 0 3px rgba(104,128,255,.12)!important
}
input::placeholder,textarea::placeholder{color:#7e95b7!important}
[data-testid="stFileUploader"] section{
 border:1px dashed #4e6b9c!important;border-radius:17px!important;
 background:rgba(30,51,87,.31)!important;
}
[data-testid="stDataFrame"],[data-testid="stDataEditor"]{
 border:1px solid var(--bb-stroke)!important;border-radius:14px!important;overflow:hidden;
}
[data-testid="stTabs"] [role="tablist"]{border-bottom:1px solid #2a4167;gap:8px}
[data-testid="stTabs"] button[role="tab"]{
 color:#9cb2d4!important;font-weight:750!important;border-radius:10px 10px 0 0;
 padding:9px 15px!important;
}
[data-testid="stTabs"] button[aria-selected="true"]{
 color:#e8edff!important;background:rgba(70,102,197,.16)!important;
 border-bottom:2px solid #6c89ff!important;
}
[data-testid="stTabs"] button:hover{color:white!important}
[data-testid="stExpander"]{border-color:#2c4267;border-radius:13px;overflow:hidden}
[data-testid="stAlert"]{border-radius:14px!important;border:1px solid rgba(94,121,176,.3)}
[data-testid="stPlotlyChart"]{
 padding:9px;border:1px solid rgba(48,73,115,.64);
 border-radius:16px;background:linear-gradient(165deg,rgba(15,25,49,.85),rgba(10,17,33,.7));
}
[data-testid="stRadio"]:not([data-testid="stSidebar"] *) [role="radiogroup"] label{
 border:1px solid #2a4165;border-radius:11px;padding:7px 11px;
 background:#101d35;
}
[data-testid="stRadio"]:not([data-testid="stSidebar"] *) [role="radiogroup"] label:has(input:checked){
 border-color:#6c86ed;background:#20365c;
}
.bb-hero{
 border:1px solid #365589!important;
 background:radial-gradient(circle at 7% 18%,rgba(96,88,248,.3),transparent 27%),
   linear-gradient(115deg,#15264a,#121c39 55%,#111a31)!important;
 box-shadow:0 18px 40px rgba(0,0,0,.18), inset 0 1px rgba(170,205,255,.07)!important;
 border-radius:24px!important;
}
.bb-title{font-size:clamp(32px,3.5vw,48px)!important}
.bb-title span{background:linear-gradient(95deg,#86acff,#a694ff);color:transparent!important;background-clip:text;-webkit-background-clip:text}
.bb-kicker{color:#a9b5ff!important}
.bb-sub,.bb-muted{color:#a2b6d4!important}
.bb-panel,.bb-gamecard,.bb-fixture-card,.bb-top10-grid-card,.bb-glow{
 background:linear-gradient(135deg,#182743,#111e36)!important;
 border:1px solid #2d4875!important;border-radius:17px!important;
 box-shadow:0 8px 24px rgba(0,0,0,.1);
}
.bb-gamecard{max-width:none!important}
.bb-gamehead span,.bb-gamefooter b{color:#8cb8ff!important}
.bb-versus b{color:var(--bb-mint)!important}
.bb-winbar{background:#253958!important}
.bb-tag{background:rgba(78,93,187,.18)!important;color:#b9c0ff!important;border-color:#525da3!important}
.bb-warning{background:rgba(142,87,45,.14)!important;border-color:#9c7341!important;color:#f4d5a2!important}
.bb-glow b{color:#b6c7ff!important}
.bb-healthy{color:var(--bb-mint)!important}.bb-danger{color:var(--bb-red)!important}
.bb-legend>div{background:#121f39!important;border-color:#30486a!important}
.bb-footer{border-top-color:#293c5a!important;color:#8298bb!important}
.bb-search-hero{
 padding:24px 27px 20px;margin-bottom:16px;border-radius:21px;
 background:radial-gradient(ellipse at 0 0,rgba(100,75,220,.25),transparent 40%),
   linear-gradient(125deg,#172b58,#121b35 60%,#152044);
 border:1px solid #4264aa;box-shadow:0 16px 38px rgba(8,14,36,.32);
}
.bb-eyebrow{font-size:10px;letter-spacing:.18em;font-weight:800;color:#a6b9ff;text-transform:uppercase;margin-bottom:9px}
.bb-search-title{font:800 clamp(23px,3vw,35px)/1.13 'Space Grotesk',sans-serif;color:#fff}
.bb-search-description{font-size:13px;color:#aec1e2;margin-top:10px;line-height:1.5}
.bb-search-examples{display:flex;flex-wrap:wrap;gap:7px;margin-top:16px}
.bb-search-examples span{padding:6px 9px;border-radius:9px;
 background:rgba(82,124,219,.16);border:1px solid rgba(95,134,218,.35);
 color:#bfd2ff;font-size:11px}
.bb-prop-hero{
 padding:22px 25px;border:1px solid #425d94;border-radius:22px;
 background:radial-gradient(ellipse at 100% 0%,rgba(91,91,210,.21),transparent 48%),
   linear-gradient(118deg,#192b52,#111b35);
 box-shadow:0 15px 32px rgba(0,0,0,.18);margin:10px 0 20px;
}
.bb-prop-top{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
.bb-prop-name{font:800 clamp(21px,2.5vw,30px) 'Space Grotesk',sans-serif;color:#fff}
.bb-prop-subtitle{font-size:12px;color:#9fb9de;letter-spacing:.03em;margin-top:5px}
.bb-prop-label{padding:9px 13px;border-radius:11px;border:1px solid #475d9c;
 background:rgba(87,104,182,.18);color:#e7eaff;font-weight:800;font-size:13px}
.bb-prop-label.over{color:#82edd1;border-color:#2d8c7b;background:rgba(37,135,107,.18)}
.bb-prop-label.under{color:#ff9aa3;border-color:#a9536a;background:rgba(162,62,82,.16)}
.bb-prop-strip{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:17px 0 4px}
.bb-prop-tile{padding:12px;border:1px solid #344b76;border-radius:12px;background:rgba(8,15,32,.46)}
.bb-prop-tile .name{font-size:10px;font-weight:800;letter-spacing:.09em;color:#9ab0d3;text-transform:uppercase}
.bb-prop-tile .val{display:block;color:#f5f9ff;font:800 23px 'Space Grotesk',sans-serif;margin-top:4px}
.bb-prop-tile .val.over{color:var(--bb-mint)}.bb-prop-tile .val.under{color:#ff8692}
.bb-prop-tile .desc{font-size:10px;color:#90a7cd;margin-top:5px}
.bb-highlight-bar{height:6px;overflow:hidden;border-radius:30px;display:flex;background:#2c3454;margin:14px 0}
.bb-highlight-bar .over{background:var(--bb-mint)}.bb-highlight-bar .under{background:var(--bb-red)}
@media(max-width:850px){
 .block-container{padding:1rem .8rem 3rem;max-width:100%}
 .bb-hero{padding:16px!important;border-radius:17px!important;gap:12px}
 .bb-search-hero,.bb-prop-hero{padding:18px 15px;border-radius:16px}
 .bb-prop-strip{grid-template-columns:repeat(2,minmax(0,1fr))}
 .bb-prop-tile .val{font-size:22px}
 [data-testid="stMetric"]{padding:12px!important;min-height:88px}
 [data-testid="stPlotlyChart"]{padding:4px}
}
@media(max-width:460px){
 .bb-search-title{font-size:24px}
 .bb-prop-name{font-size:22px}
 .bb-prop-strip{gap:7px}
 .bb-prop-tile{padding:10px}
 [data-testid="stMetricValue"]{font-size:23px!important}
}
</style>
"""


def apply_premium_theme():
    st.markdown(PREMIUM_CSS, unsafe_allow_html=True)
