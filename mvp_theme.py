"""BestBets MVP — unified, original premium application theme.

Single visual language for all user-facing views: deep navy, electric-blue
navigation, orange action highlights, green/red *observed* outcomes. The CSS
does not hide source-quality errors or invent performance measurements.
"""
from __future__ import annotations
import streamlit as st

MVP_CSS = r"""
<style>
:root{
 --bb-bg:#050916;--bb-shell:#0b1325;--bb-card:#0d182c;
 --bb-card-hi:#13213b;--bb-edge:#263c5f;--bb-text:#f3f7ff;
 --bb-muted:#a0b3d0;--bb-blue:#21a9ff;--bb-orange:#ff812c;
 --bb-green:#1bdc8d;--bb-red:#fa5b65;
}
.stApp, [data-testid="stAppViewContainer"]{
 background:
 radial-gradient(ellipse at 82% 6%,rgba(25,82,170,.16),transparent 35%),
 radial-gradient(ellipse at 13% 58%,rgba(21,51,113,.10),transparent 50%),
 linear-gradient(145deg,#060b17,#070e1d 65%,#060b17)!important;
 color:var(--bb-text)!important;
 font-family:"Inter","Segoe UI",system-ui,sans-serif!important;
}
[data-testid="stHeader"]{background:rgba(5,9,22,.89)!important;backdrop-filter:blur(16px)}
.block-container{max-width:1510px!important;padding-top:.8rem!important;padding-bottom:2.7rem!important}
h1,h2,h3,h4{font-weight:800!important;letter-spacing:-.028em!important;color:#f5f9ff!important}
h1{font-size:2.2rem!important}h2{font-size:1.6rem!important}h3{font-size:1.23rem!important}
[data-testid="stCaptionContainer"] p{font-size:.84rem;color:var(--bb-muted)!important}
[data-testid="stSidebar"]{
 background:linear-gradient(176deg,#0b1427,#070f1e)!important;
 border-right:1px solid #1e3657!important;
}
[data-testid="stSidebar"] .stButton>button{
 background:transparent!important;
 border:1px solid transparent!important;box-shadow:none!important;
 border-radius:13px!important;color:#a9bbd6!important;
 justify-content:flex-start!important;text-align:left!important;
 padding:12px 15px!important;width:100%;font-weight:700!important;
 transition:background .17s,color .17s,border-color .17s!important
}
[data-testid="stSidebar"] .stButton>button:hover{
 background:#14233c!important;color:#fff!important;border-color:#35577c!important;
}
[data-testid="stSidebar"] .stButton>button[kind="primary"]{
 color:#fff!important;
 background:linear-gradient(95deg,rgba(255,122,41,.23),rgba(25,61,112,.46))!important;
 border:1px solid rgba(255,135,57,.59)!important;
 box-shadow:inset 3px 0 #ff822b,0 0 20px rgba(255,124,46,.08)!important;
}
[data-testid="stSidebar"] .stVerticalBlock{gap:.35rem}
[data-testid="stSidebar"] hr{border-color:#233754}
.bbm-brand{
 padding:12px 11px 19px;display:flex;align-items:center;gap:10px;
 margin-bottom:16px;border-bottom:1px solid #233852;
}
.bbm-brand b{font-style:italic;font-size:23px;letter-spacing:-.04em}
.bbm-brand b span{color:#ff822c}
.bbm-brand img{height:43px;width:43px;object-fit:contain;border-radius:11px}
.bbm-nav-label{
 color:#6580a6;font-size:10px;font-weight:900;letter-spacing:.15em;
 margin:14px 12px 9px;text-transform:uppercase
}
.bbm-sidebar-footer{font-size:11px;color:#7593b7;padding:11px 13px;border-top:1px solid #203452;margin-top:20px}
.bbm-topbar{
 display:flex;justify-content:space-between;gap:14px;align-items:center;
 padding:18px 23px;margin:4px 0 17px;
 border-radius:19px;
 background:radial-gradient(circle at 95% 0%,rgba(246,119,39,.17),transparent 27%),
  linear-gradient(110deg,#122343,#0b162b 70%);
 border:1px solid #2e4771;
 box-shadow:0 10px 34px rgba(0,0,0,.18)
}
.bbm-eyebrow{font-size:10px;letter-spacing:.2em;color:#7daeff;font-weight:900;text-transform:uppercase}
.bbm-topbar h1{font-size:clamp(22px,3vw,33px)!important;line-height:1.15;margin:5px 0 4px!important}
.bbm-topbar p{font-size:12px;color:#9cb1d1;line-height:1.45;margin:0}
.bbm-mini-tag{
 white-space:nowrap;font-size:11px;font-weight:800;letter-spacing:.045em;
 border:1px solid #46628c;color:#bed2fa;background:rgba(23,48,87,.6);
 padding:8px 12px;border-radius:11px
}
.bbm-intro{
 background:linear-gradient(119deg,#0f2242,#101b30 63%,#111e35);
 border:1px solid #2c4f80;border-radius:19px;
 padding:20px 22px;margin-bottom:14px
}
.bbm-intro strong{font-size:20px;color:#fff;letter-spacing:-.02em}
.bbm-intro p{font-size:12px;color:#a3b8d6;margin-top:5px;margin-bottom:0}
.bbm-orange{color:#ff9a4e}.bbm-blue{color:#58c2ff}.bbm-green{color:#28e09b}.bbm-red{color:#ff7182}
.bbm-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:9px 0 20px}
.bbm-kpi{padding:17px 18px;background:linear-gradient(141deg,#14243f,#0d172a);
 border:1px solid #2c4368;border-radius:16px;min-height:94px}
.bbm-kpi small{display:block;color:#879fbe;letter-spacing:.105em;text-transform:uppercase;font-weight:850;font-size:10px}
.bbm-kpi b{display:block;font-size:28px;font-weight:850;margin:5px 0 1px;color:#f6faff}
.bbm-kpi span{font-size:11px;color:#a0b3d0}
.bbm-section{
 display:flex;align-items:baseline;justify-content:space-between;gap:10px;
 margin:17px 0 10px
}
.bbm-section h3{margin:0!important}.bbm-section small{color:#839cbd;font-size:11px}
.bbm-card{padding:16px 18px;border-radius:16px;
 background:linear-gradient(145deg,rgba(21,39,69,.96),rgba(11,21,39,.96));
 border:1px solid #2c456f;box-shadow:0 9px 26px rgba(0,0,0,.11);margin-bottom:11px}
.bbm-player-head{
 background:linear-gradient(105deg,rgba(12,53,65,.78),rgba(12,23,42,.96) 56%,rgba(13,34,62,.95));
 border:1px solid #366481;border-radius:20px;padding:18px 22px;
 display:flex;align-items:center;gap:18px;
}
.bbm-headshot{
 width:103px;height:111px;object-fit:contain;object-position:bottom;
 border-radius:14px;background:#112e37;flex-shrink:0;
}
.bbm-player-head-main{flex:1;min-width:120px}
.bbm-player-head-main h2{font-size:clamp(22px,3vw,37px)!important;margin:0 0 5px}
.bbm-player-head-main small{color:#b2c6de;font-size:12px}
.bbm-player-pills{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:9px}
.bbm-pill{
 border:1px solid #2f6e64;border-radius:99px;padding:4px 10px;
 background:#17392f;color:#81f1c3;font-size:11px;font-weight:850;
}
.bbm-player-stats{display:grid;grid-template-columns:repeat(3,minmax(86px,1fr));gap:12px;flex:1;max-width:440px}
.bbm-player-stat{padding:9px;border-left:1px solid #2d4e69}
.bbm-player-stat small{color:#87a3c6;font-size:10px;font-weight:800;letter-spacing:.08em}
.bbm-player-stat b{font-size:24px;color:#f6fbff;display:block;margin-top:3px}
.bbm-player-stat em{font-size:10px;color:#7698bd;font-style:normal}
.bbm-hero-search{
 padding:19px 20px 12px;border:1px solid #315b86;border-radius:18px;
 background:radial-gradient(ellipse at 92% -12%,rgba(255,126,31,.17),transparent 48%),
 linear-gradient(113deg,#0f213c,#0c152a);
}
.bbm-kicker{font-size:11px;color:#ff9a4a;font-weight:900;letter-spacing:.16em}
.bbm-hero-search h2{margin:5px 0 4px!important;font-size:25px!important}
.bbm-hero-search p{font-size:12px;color:#a7bbd7;margin:0}
.bbm-two{display:grid;grid-template-columns:2fr 1fr;gap:13px}
.bbm-result-tile{padding:13px 15px;background:#101d34;border:1px solid #2c496d;border-radius:15px}
.bbm-result-tile small{font-size:10px;color:#94a9cb;font-weight:750;letter-spacing:.06em}
.bbm-result-tile b{font-size:23px;font-weight:850;display:block;margin:5px 0;color:#fff}
.bbm-result-tile em{font-size:11px;color:#879dbc;font-style:normal}
.bbm-note{
 background:#111d32;border:1px solid #2a4567;border-radius:14px;
 padding:13px 15px;color:#b8cce6;font-size:12px;margin:13px 0
}
.bbm-take{
 display:flex;gap:12px;align-items:center;
 border:1px solid rgba(241,120,43,.65);border-radius:14px;
 padding:14px 16px;background:linear-gradient(115deg,#211d27,#0d1a2c 70%,#102847);
 margin:15px 0
}
.bbm-take strong{color:#ff9b58;white-space:nowrap;font-size:15px}
.bbm-take span{color:#cfdbed;font-size:12px;line-height:1.6}
.bbm-venue-row{display:flex;gap:9px;margin:10px 0}
.bbm-venue-row div{flex:1;padding:11px 12px;border-radius:13px;border:1px solid #2e4a70;background:#111d33}
.bbm-venue-row small{color:#9db0ce;font-size:10px;display:block}
.bbm-venue-row strong{display:block;font-size:17px;margin-top:3px}
.bbm-team-head{
 display:flex;gap:16px;align-items:center;padding:17px 20px;
 background:linear-gradient(110deg,#142746,#111d32);border:1px solid #35517a;border-radius:18px
}
.bbm-team-head img{width:74px;height:74px;object-fit:contain}
.bbm-team-head h2{margin:0!important}.bbm-team-head small{color:#9ab0cd}
[data-testid="stMetric"]{
 background:linear-gradient(145deg,#152641,#101b30)!important;
 border:1px solid #2e476c!important;border-radius:14px!important;
 padding:15px!important;min-height:95px!important
}
[data-testid="stMetricLabel"] p{color:#92aacb!important;font-size:10px!important;font-weight:850!important;letter-spacing:.055em}
[data-testid="stMetricValue"]{font-family:"Inter",system-ui!important;font-size:24px!important;font-weight:850!important}
[data-testid="stPlotlyChart"]{
 background:linear-gradient(150deg,#0c172a,#0c1425)!important;
 border:1px solid #2b4669!important;border-radius:17px!important;padding:10px!important
}
[data-testid="stDataFrame"],[data-testid="stDataEditor"]{
 border:1px solid #314765!important;border-radius:12px!important;overflow:hidden
}
[data-baseweb="input"]>div,[data-baseweb="select"]>div,[data-testid="stNumberInput"] input{
 background:#0d1a2e!important;color:#f5f9ff!important;border:1px solid #334d71!important;border-radius:11px!important
}
[data-testid="stTabs"] button[role="tab"]{font-weight:800!important;color:#a2bcda!important}
[data-testid="stTabs"] button[aria-selected="true"]{
 border-bottom-color:#ff8d43!important;color:#f7faff!important
}
.stButton:not([data-testid="stSidebar"] .stButton)>button[kind="primary"]{
 background:linear-gradient(108deg,#ff9a3e,#fb6d20)!important;
 color:#0b1425!important;border:1px solid #ffae67!important;
 border-radius:12px!important;font-weight:850!important;
 box-shadow:0 6px 22px rgba(252,118,37,.12)!important
}
.stButton:not([data-testid="stSidebar"] .stButton)>button{
 background:#14253f;border:1px solid #314e78;border-radius:12px;
 color:#e5f1ff;font-weight:750;
}
.stButton:not([data-testid="stSidebar"] .stButton)>button:hover{
 border-color:#4e94d2;color:#fff;background:#1b3658
}
.stTextInput input,.stTextArea textarea{font-size:14px!important}
.stTextInput input:focus{border-color:#36a9ff!important;box-shadow:0 0 0 3px rgba(30,154,255,.10)}
[data-testid="stExpander"]{background:rgba(12,24,44,.5);border-radius:12px}
.bbm-game-card{
 padding:20px;border:1px solid #2f4a70;border-radius:17px;
 background:linear-gradient(120deg,#14233e,#0e1a30);
}
.bbm-compact{font-size:11px;color:#839fc3}

/* Existing fixture and 5000-draw card internals share MVP colors. */
.bb-fixture-card,.bb-gamecard{
 background:linear-gradient(125deg,#11213a,#0b1629)!important;
 border:1px solid #314c75!important;border-radius:17px!important;
 box-shadow:0 8px 29px rgba(1,5,17,.16)!important;
}
.bb-fixture-date,.bb-gamehead span,.bb-gamefooter b{
 color:#ffab63!important
}
.bb-fixture-bottom{display:none!important}
.bb-fixture-top{margin-bottom:10px!important}
.bb-fixture-state.live{color:#ffc28c!important}
.bb-gamecard .bb-winbar>div:first-child{
 background:var(--bb-orange)!important
}
.bb-gamecard .bb-winbar>div:nth-child(2){
 background:var(--bb-green)!important
}
.bb-gamecard .bb-versus b{color:#d6e8ff!important}
.bb-gamecard .bb-gamefooter{border-top:1px solid #233b5b}

/* BESTBETS MATCHUP INTELLIGENCE — vibrant, compact game cards */
.bbm-sim-game{
 margin:11px 0 6px;padding:17px 20px 14px;
 border-radius:19px;border:1px solid #33547c;
 background:
  radial-gradient(ellipse at 0 0,rgba(24,166,245,.12),transparent 42%),
  radial-gradient(ellipse at 100% 100%,rgba(255,119,29,.12),transparent 42%),
  linear-gradient(111deg,#122640 0%,#0e1b32 58%,#111c32 100%);
 box-shadow:0 10px 34px rgba(0,0,0,.15),inset 0 1px rgba(104,173,244,.12);
}
.bbm-sim-game-top{
 display:flex;align-items:center;justify-content:space-between;
 gap:10px;padding-bottom:13px;border-bottom:1px solid #2a456a;
 font-size:12px;font-weight:800;color:#c9dcf4;flex-wrap:wrap;
}
.bbm-live-dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#fb8d37;box-shadow:0 0 12px #fa8b36;margin-right:8px}
.bbm-sim-source{
 padding:5px 9px;border:1px solid #325b84;border-radius:99px;
 color:#76c5fa!important;font-size:10px!important;letter-spacing:.06em;
}
.bbm-sim-game-grid{
 display:grid;grid-template-columns:minmax(0,2.4fr) minmax(155px,1fr);
 gap:18px;align-items:center;padding:12px 0 12px;
}
.bbm-sim-matchup{display:grid;grid-template-columns:1fr 28px 1fr;align-items:center;gap:10px;min-width:0}
.bbm-sim-team{display:flex;align-items:center;gap:10px;min-width:0}
.bbm-sim-team img{width:46px!important;height:46px!important;flex-shrink:0;filter:drop-shadow(0 3px 8px rgba(0,0,0,.36))}
.bbm-sim-team>div{min-width:0;flex:1}
.bbm-sim-abbr{font-size:10px;font-weight:850;letter-spacing:.11em;color:#9eb2d0;margin-bottom:2px}
.bbm-sim-team strong{font-size:13px;font-weight:850;display:block;color:#eff6ff;line-height:1.28}
.bbm-sim-score{font-size:23px;font-weight:900;font-variant-numeric:tabular-nums;white-space:nowrap}
.bbm-sim-versus{font-weight:900;font-size:11px;color:#637da1;text-align:center}
.bbm-sim-summary{
 border-left:1px solid #2c4868;padding-left:21px;text-align:right;
}
.bbm-sim-small{font-size:10px;letter-spacing:.07em;color:#9cb2d3;font-weight:750}
.bbm-sim-small b{color:#e9f3ff;font-weight:850}
.bbm-sim-total{font-size:clamp(29px,3vw,35px);font-weight:900;color:#fff;line-height:1.35;font-variant-numeric:tabular-nums}
.bbm-orange{color:#ff9c52!important}.bbm-green{color:#23e29c!important}
.bbm-sim-winbar{display:flex;overflow:hidden;height:9px;background:#233a57;border-radius:99px}
.bbm-sim-winbar>div:first-child{background:linear-gradient(90deg,#ea7541,#ffa54a)}
.bbm-sim-winbar>div:last-child{background:linear-gradient(90deg,#2acaad,#17dd88)}
.bbm-sim-winlabels{
 display:flex;justify-content:space-between;font-weight:850;
 font-size:11px;letter-spacing:.03em;margin-top:9px
}
.bbm-sim-detail-hero{
 padding:17px 20px 15px;border-radius:19px;
 background:
 radial-gradient(ellipse at 0 100%,rgba(16,163,230,.20),transparent 43%),
 radial-gradient(ellipse at 100% 0%,rgba(255,116,42,.20),transparent 43%),
 linear-gradient(115deg,#152943,#111e32 52%,#14223b);
 border:1px solid #42628b;box-shadow:inset 0 1px rgba(142,201,255,.16);
 margin-bottom:10px;
}
.bbm-sim-detail-kicker{
 color:#a9bddb;font-size:10px;letter-spacing:.17em;font-weight:850;text-align:center;margin-bottom:10px
}
.bbm-sim-detail-match{
 display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);
 align-items:center;gap:10px;
}
.bbm-sim-detail-side{display:flex;gap:12px;align-items:center;min-width:0}
.bbm-sim-detail-side.right{flex-direction:row-reverse;text-align:right}
.bbm-sim-detail-side img{height:62px!important;width:62px!important;flex:0 0 auto;object-fit:contain}
.bbm-sim-detail-side strong{
 display:block;color:#f5faff;font-size:clamp(14px,1.6vw,18px);
 font-weight:900;line-height:1.21;
}
.bbm-sim-detail-side em{display:block;font-size:11px;font-style:normal;font-weight:850;margin-top:5px}
.bbm-sim-detail-code{display:block;font-size:10px;color:#99afcb;letter-spacing:.12em;font-weight:800;margin-bottom:3px}
.bbm-sim-detail-middle{text-align:center;min-width:150px}
.bbm-sim-projected{
 font-size:clamp(27px,3.5vw,43px);font-weight:950;letter-spacing:-.05em;
 line-height:1.06;color:#f4f9ff;white-space:nowrap;font-variant-numeric:tabular-nums;
}
.bbm-sim-projected span{font-size:22px;color:#879ebc;margin:0 5px}
.bbm-sim-detail-middle small{color:#9bb2d1;font-size:9px;letter-spacing:.12em;font-weight:800}
.bbm-sim-kpis{
 display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin:10px 0
}
.bbm-sim-kpis>div{
 padding:11px 12px;border:1px solid #2d5176;border-radius:13px;
 background:linear-gradient(136deg,#142c49,#0f1b31);
}
.bbm-sim-kpis small{font-size:9px;display:block;color:#95afd0;font-weight:850;letter-spacing:.07em;min-height:22px}
.bbm-sim-kpis strong{font-size:clamp(18px,2.2vw,25px);display:block;color:#f2f9ff;font-weight:900;font-variant-numeric:tabular-nums;margin-top:4px}
.bbm-sim-section-title{
 display:flex;gap:12px;align-items:center;flex-wrap:wrap;
 color:#f4f9ff;font-size:15px;font-weight:900;
 margin:14px 0 9px;letter-spacing:.02em;
}
.bbm-sim-section-title>span{color:#83a3c6;font-weight:600;font-size:11px;letter-spacing:0}
.bbm-sim-section-title>img{height:30px!important;width:30px!important;object-fit:contain}
.bbm-sim-form-card{
 background:linear-gradient(137deg,#162e46,#101e33);
 border:1px solid #2f6884;border-radius:16px;padding:14px;min-height:172px
}
.bbm-sim-form-card.home{
 border-color:#327559;background:linear-gradient(137deg,#133c36,#0d2531)
}
.bbm-sim-form-heading{display:flex;align-items:center;gap:10px;margin-bottom:11px}
.bbm-sim-form-heading img{width:39px!important;height:39px!important;object-fit:contain}
.bbm-sim-form-heading small{font-size:9px;letter-spacing:.12em;color:#9ab7cc;font-weight:850;display:block}
.bbm-sim-form-heading strong{font-size:13px;font-weight:900;color:#fff}
.bbm-sim-form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
.bbm-sim-form-grid>div{padding:7px 10px;border-radius:10px;background:rgba(2,11,23,.26);border:1px solid #2a465e}
.bbm-sim-form-grid small{color:#87a8c3;font-weight:850;display:block;font-size:9px;letter-spacing:.08em}
.bbm-sim-form-grid b{font-size:18px;color:#f2faff;font-weight:950;display:block;margin-top:2px}
.bbm-sim-injury{
 display:flex;align-items:center;justify-content:space-between;gap:9px;
 padding:9px 12px;border:1px solid #68445b;border-radius:11px;
 background:linear-gradient(90deg,rgba(122,41,63,.27),rgba(21,29,51,.78));
 margin-bottom:6px
}
.bbm-sim-injury b{color:#fff;font-size:12px;font-weight:850}
.bbm-sim-injury span{color:#ffc091;font-weight:750;font-size:11px;text-align:right}
.bbm-sim-take{
 display:flex;align-items:center;gap:17px;
 margin:15px 0 0;border-radius:14px;padding:13px 15px;
 background:linear-gradient(111deg,rgba(191,88,39,.20),#112338 64%,rgba(27,101,172,.18));
 border:1px solid rgba(255,132,59,.56);
}
.bbm-sim-take strong{font-size:13px;font-weight:950;color:#ffab6c;white-space:nowrap}
.bbm-sim-take span{font-size:11px;color:#cfddf1;line-height:1.5}
/* Streamlit dialogs render in a portal; give them the same dark-blue shell. */
div[data-testid="stDialog"] div[role="dialog"],
div[data-testid="stDialog"] div[data-testid="stDialogContent"],
div[data-testid="stDialog"] [data-testid="stVerticalBlockBorderWrapper"]{
 background:linear-gradient(153deg,#0d1a31,#0a1328)!important;
 border-color:#304f79!important;color:#e7f1ff!important;
}
div[data-testid="stDialog"] div[role="dialog"]{
 width:min(1120px,96vw)!important;max-width:1120px!important;
 border:1px solid #3c6089!important;border-radius:22px!important;
 box-shadow:0 22px 95px rgba(1,4,15,.8),0 0 40px rgba(15,113,207,.10)!important;
}
div[data-testid="stDialog"] [data-testid="stMarkdownContainer"] p{
 color:#a6bcd8;
}
div[data-testid="stDialog"] [data-testid="stRadio"] label{
 background:#12233c!important;border:1px solid #355b84!important;
 border-radius:10px!important;padding:8px 12px!important;
}
div[data-testid="stDialog"] [data-testid="stRadio"] label:has(input:checked){
 background:#183d60!important;border-color:#ff8b3e!important;
 color:#fff!important;box-shadow:inset 2px 0 #ff8b3e!important;
}
@media(max-width:980px){
 .bbm-sim-game-grid{grid-template-columns:1fr;gap:9px}
 .bbm-sim-summary{border-left:0;border-top:1px solid #2c4868;padding:10px 0 0;text-align:left}
 .bbm-sim-total{display:inline;margin-right:10px}
 .bbm-sim-detail-side img{width:48px!important;height:48px!important}
 .bbm-sim-detail-middle{min-width:115px}
}
@media(max-width:640px){
 .bbm-sim-game{padding:12px}
 .bbm-sim-game-top{font-size:10px}
 .bbm-sim-source{font-size:9px!important}
 .bbm-sim-matchup{grid-template-columns:1fr 21px 1fr;gap:4px}
 .bbm-sim-team{flex-direction:column;align-items:flex-start;gap:4px}
 .bbm-sim-team img{width:38px!important;height:38px!important}
 .bbm-sim-score{font-size:21px}
 .bbm-sim-detail-hero{padding:10px 9px}
 .bbm-sim-detail-match{gap:4px}
 .bbm-sim-detail-side{flex-direction:column;align-items:center;text-align:center;gap:3px}
 .bbm-sim-detail-side.right{flex-direction:column;align-items:center;text-align:center}
 .bbm-sim-detail-side img{height:38px!important;width:38px!important}
 .bbm-sim-detail-side strong{font-size:11px}
 .bbm-sim-detail-code{font-size:8px}
 .bbm-sim-detail-middle{min-width:87px}
 .bbm-sim-projected{font-size:20px}
 .bbm-sim-projected span{font-size:13px}
 .bbm-sim-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}
 .bbm-sim-kpis strong{font-size:20px}
 .bbm-sim-form-grid{gap:5px}
 .bbm-sim-form-grid b{font-size:15px}
 .bbm-sim-take{display:block}
 .bbm-sim-take span{display:block;margin-top:7px}
}

@media(max-width:950px){
 .bbm-player-head{flex-wrap:wrap}
 .bbm-player-stats{max-width:100%;width:100%}
 .bbm-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
 .bbm-two{grid-template-columns:1fr}
}
@media(max-width:620px){
 .block-container{padding:.7rem .65rem 2rem!important}
 .bbm-topbar{padding:14px;border-radius:15px}
 .bbm-topbar h1{font-size:23px!important}
 .bbm-mini-tag{display:none}
 .bbm-grid{gap:7px}
 .bbm-kpi{padding:11px;min-height:79px}
 .bbm-kpi b{font-size:22px}
 .bbm-player-head{padding:13px}
 .bbm-player-head-main h2{font-size:22px!important}
 .bbm-headshot{width:74px;height:82px}
 .bbm-player-stats{gap:5px}
 .bbm-player-stat b{font-size:20px}
 .bbm-team-head{padding:12px}
 .bbm-team-head img{width:58px;height:58px}
}
</style>
"""

def apply_mvp_theme():
    st.markdown(MVP_CSS, unsafe_allow_html=True)
