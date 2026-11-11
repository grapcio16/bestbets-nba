"""BestBets v9.1: reference-locked neon polish and subtle motion.

Presentation only. No probabilities, rankings, fixtures or player data are
synthesized. The six real navigation links and the real NBA data path remain.
Animations respect the user's reduced-motion setting.
"""
import streamlit as st

REFERENCE_FX_CSS = r"""
<style>
/* v9.1 PHOTO-REFERENCE VISUAL PASS — app only, no external assets */
:root{
 --bb91-ink:#020813;
 --bb91-card:#07172b;
 --bb91-orange:#ff7a1c;
 --bb91-amber:#ffa132;
 --bb91-blue:#00baff;
 --bb91-green:#04ec74;
 --bb91-red:#ff514a;
}
@keyframes bb91-search-breathe{
  0%,100%{box-shadow:0 0 0 1px rgba(0,196,255,.26),0 0 13px rgba(0,164,255,.38),inset 0 0 11px rgba(0,166,255,.12)}
  50%{box-shadow:0 0 0 1px rgba(0,196,255,.57),0 0 24px rgba(0,159,255,.62),inset 0 0 18px rgba(0,166,255,.19)}
}
@keyframes bb91-orange-breathe{
  0%,100%{box-shadow:0 0 10px rgba(255,120,25,.25),inset 0 0 8px rgba(255,137,32,.1)}
  50%{box-shadow:0 0 19px rgba(255,113,17,.52),inset 0 0 13px rgba(255,137,32,.20)}
}
@keyframes bb91-blue-breathe{
  0%,100%{box-shadow:0 0 6px rgba(0,160,255,.2),inset 0 0 8px rgba(0,114,211,.08)}
  50%{box-shadow:0 0 16px rgba(0,160,255,.43),inset 0 0 13px rgba(0,114,211,.15)}
}
@keyframes bb91-ambient-shift{
  0%,100%{background-position:0% 48%}
  50%{background-position:100% 52%}
}
@keyframes bb91-slide-in{
  from{opacity:0;transform:translateY(8px)}
  to{opacity:1;transform:translateY(0)}
}
@keyframes bb91-take-shine{
  0%{transform:translateX(-100%) skewX(-17deg)}
  55%,100%{transform:translateX(520%) skewX(-17deg)}
}
/* 01: Reference palette, visible moving atmosphere in deep navy. */
.stApp,[data-testid="stAppViewContainer"]{
  background:
   radial-gradient(ellipse 44% 38% at 97% 0%,rgba(0,102,229,.16),transparent 77%),
   radial-gradient(ellipse 30% 50% at -5% 96%,rgba(255,88,12,.13),transparent 79%),
   linear-gradient(145deg,#020712 4%,#051426 52%,#030915 100%)!important;
  color:#f6faff!important;
}
[data-testid="stAppViewContainer"]{overflow:hidden!important}
[data-testid="stHeader"]{background:transparent!important;height:0!important;min-height:0!important}
[data-testid="stToolbar"],[data-testid="stDecoration"]{opacity:.65!important}
[data-testid="stMain"]{background:transparent!important}
[data-testid="stMainBlockContainer"],[data-testid="stMain"] .block-container{
 max-width:100%!important;width:100%!important;
 padding:2px 13px 15px!important;margin:0!important;
}
[data-testid="stMain"] [data-testid="stVerticalBlock"]{gap:4px!important}
[data-testid="stMain"] [data-testid="stHorizontalBlock"]{gap:9px!important}
[data-testid="stMain"] [data-testid="column"]{min-width:0!important}
/* 02: Compact left rail, photographic orange curved corners. */
[data-testid="stSidebar"]{
  background:
   radial-gradient(ellipse 140% 40% at -28% 106%,rgba(252,107,12,.25),transparent 75%),
   radial-gradient(ellipse 130% 28% at -10% 0%,rgba(250,83,17,.18),transparent 64%),
   linear-gradient(177deg,#030b18,#07192d 59%,#050d19 100%)!important;
  width:184px!important;min-width:184px!important;
  border-right:1px solid #21436a!important;
  box-shadow:inset -4px 0 10px rgba(0,93,178,.08),4px 0 22px rgba(0,0,0,.32)!important;
}
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"]{
  padding:0 10px 11px!important;
}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"]{gap:4px!important}
[data-testid="stSidebar"] .bb90-brand{
  margin:0 0 9px!important;padding:5px 0 6px!important;
  min-height:72px!important;gap:3px!important;
}
[data-testid="stSidebar"] .bb90-brand img{
  height:57px!important;width:57px!important;
  object-fit:contain!important;box-shadow:none!important;
  filter:drop-shadow(0 0 10px rgba(255,106,19,.26));
}
[data-testid="stSidebar"] .bb90-brand b{
  font-size:19px!important;letter-spacing:-.06em!important;
  text-shadow:0 0 5px rgba(255,255,255,.08);
}
[data-testid="stSidebar"] .bb90-brand small{
  color:#8abcf1!important;font-size:6px!important;letter-spacing:.06em!important;
}
[data-testid="stSidebar"] [data-testid="stButton"] button{
  min-height:38px!important;font-size:12px!important;
  padding:7px 10px!important;
  color:#e8f1fe!important;border-radius:10px!important;
  transition:transform .2s ease,background .2s ease,border-color .2s ease,box-shadow .2s ease!important;
}
[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"]{
  background:linear-gradient(101deg,rgba(255,125,27,.35),rgba(89,51,41,.42) 58%,rgba(18,42,68,.88))!important;
  border:1px solid #ff8b2a!important;
  border-left:4px solid #ff9a32!important;
  box-shadow:inset 0 0 12px rgba(244,96,24,.11),0 0 15px rgba(254,124,22,.33)!important;
  animation:bb91-orange-breathe 5s ease-in-out infinite;
}
[data-testid="stSidebar"] [data-testid="stButton"] button:hover{
  transform:translateX(3px)!important;
  border-color:#ff962d!important;
  box-shadow:0 0 11px rgba(255,114,20,.25)!important;
}
.bb90-sidebar-divider{margin:18px 7px 14px!important;background:#1e3d5b!important}
.bb90-sidebar-flare{
  border:0!important;position:relative;height:50px!important;overflow:visible;
  margin-top:16px!important;
}
.bb90-sidebar-flare:after{
  content:"";pointer-events:none;position:absolute;
  left:-30px;bottom:-60px;height:95px;width:190px;
  border-bottom:2px solid rgba(255,136,34,.85);
  border-radius:0 0 100% 0;
  box-shadow:0 9px 12px rgba(255,102,14,.14);
  transform:rotate(-9deg);
}
/* 03: Search — exactly one neon rail plus small suggested pills. */
.st-key-bb83_search{
  margin:3px auto 4px!important;
  width:75%!important;max-width:1000px!important;
  min-height:47px!important;padding:2px 6px 2px 13px!important;
  border-radius:100px!important;border:1px solid #29c6ff!important;
  background:linear-gradient(102deg,#041326,#091d35 65%,#17213b)!important;
  animation:bb91-search-breathe 6s ease-in-out infinite;
}
.st-key-bb83_search [data-testid="stForm"]{
  background:transparent!important;border:0!important;padding:0!important;
}
.st-key-bb83_search [data-testid="stTextInput"] input{
  height:36px!important;font-size:16px!important;
  color:#f8faff!important;background:transparent!important;
  font-weight:800!important;padding:2px 8px!important;
}
.st-key-bb83_search [data-testid="stTextInput"] input::placeholder{color:#d0e4f9!important}
.st-key-bb83_search [data-baseweb="input"]>div{
  background:transparent!important;border:0!important;box-shadow:none!important;
}
.st-key-bb83_search button[kind="primary"]{
  min-height:39px!important;height:39px!important;
  color:#fff!important;border:1px solid #ffbc52!important;
  background:linear-gradient(114deg,#ffad34,#ff7c0c)!important;
  box-shadow:0 0 13px rgba(255,135,19,.68)!important;
  border-radius:99px!important;
  transition:filter .2s ease,transform .2s ease!important;
}
.st-key-bb83_search button[kind="primary"]:hover{
  transform:scale(1.04)!important;filter:brightness(1.12)!important;
}
.st-key-bb83-suggest{
  width:93%!important;margin:0 auto 5px!important;
}
.st-key-bb83-suggest [data-testid="stHorizontalBlock"]{gap:8px!important}
.st-key-bb83-suggest .stButton>button{
  min-height:30px!important;font-size:11px!important;
  padding:4px 7px!important;border-radius:100px!important;
  border:1px solid #2d536f!important;
  background:linear-gradient(135deg,#0c233c,#07192c)!important;
  box-shadow:inset 0 1px rgba(136,201,239,.15)!important;
  color:#dceafb!important;
  transition:border-color .2s ease,box-shadow .2s ease,transform .2s ease!important;
}
.st-key-bb83-suggest .stButton>button:hover{
  transform:translateY(-1px)!important;
  border-color:#17c7ff!important;
  box-shadow:0 0 13px rgba(0,185,255,.37)!important;
}
/* 04: Hero moves visually to the reference — bold athlete and split metrics. */
[data-testid="stMain"] .bb83-hero{
  height:126px!important;min-height:126px!important;max-height:126px!important;
  gap:5px!important;margin:0 0 3px!important;padding:0 11px 0 0!important;
  border-radius:12px!important;border:1px solid #158898!important;
  background:
    radial-gradient(ellipse 27% 105% at 7% 50%,rgba(0,214,111,.24),transparent 69%),
    radial-gradient(ellipse 33% 85% at 101% 95%,rgba(0,130,255,.29),transparent 76%),
    radial-gradient(ellipse 23% 78% at 98% -6%,rgba(252,111,23,.21),transparent 72%),
    linear-gradient(115deg,#062823,#071a2b 39%,#071223 78%,#132742)!important;
  box-shadow:0 0 10px rgba(2,135,205,.17),inset 0 1px rgba(121,240,211,.13)!important;
  animation:bb91-slide-in .35s ease both;
}
[data-testid="stMain"] .bb83-portrait{
  min-height:126px!important;height:126px!important;
  flex:0 0 164px!important;overflow:hidden!important;
  background:radial-gradient(ellipse at 40% 64%,rgba(0,231,118,.20),transparent 75%)!important;
  align-items:flex-end!important;justify-content:center!important;
}
[data-testid="stMain"] .bb83-portrait img{
  width:175px!important;height:148px!important;
  max-width:none!important;object-fit:cover!important;object-position:center top!important;
  position:relative!important;z-index:2!important;
  transform:scale(1.08);
  transform-origin:center bottom;
  filter:drop-shadow(0 3px 9px rgba(0,0,0,.3));
}
[data-testid="stMain"] .bb83-team-back{
  top:5px!important;left:6px!important;opacity:.65!important;
}
[data-testid="stMain"] .bb83-team-back img{
  width:98px!important;height:98px!important;object-fit:contain!important;
  transform:none!important;filter:none!important;
}
[data-testid="stMain"] .bb83-identity{
  padding:6px 4px!important;min-width:175px!important;justify-content:center!important;
}
[data-testid="stMain"] .bb83-identity h2{
  font-size:clamp(24px,2.35vw,37px)!important;
  margin:0 0 8px!important;line-height:1.08!important;font-weight:1000!important;
  white-space:nowrap!important;
  text-shadow:0 2px 7px rgba(0,0,0,.25);
}
[data-testid="stMain"] .bb83-identity-line{font-size:12px!important;gap:6px!important}
[data-testid="stMain"] .bb83-identity small{font-size:9px!important;margin-top:4px!important}
[data-testid="stMain"] .bb83-team-badge{
  padding:3px 9px!important;border-radius:99px!important;
  border:1px solid #09ec74!important;background:#075334!important;
  box-shadow:0 0 9px rgba(0,237,111,.30)!important;
}
[data-testid="stMain"] .bb83-hero-metrics{padding:4px 0!important;align-self:center!important}
[data-testid="stMain"] .bb83-hero-metric{
  min-width:74px!important;padding:4px 8px!important;
  border-color:#3c526e!important;
}
[data-testid="stMain"] .bb83-hero-metric label{font-size:10px!important;color:#bed0e4!important}
[data-testid="stMain"] .bb83-hero-metric b{font-size:24px!important}
[data-testid="stMain"] .bb83-hero-metric em{font-size:9px!important}
[data-testid="stMain"] .bb83-grade{
  margin:0 0 0 6px!important;min-width:106px!important;align-self:center!important;
  padding:7px 8px!important;border-radius:11px!important;
  border:1px solid #508fbc!important;
  box-shadow:0 0 12px rgba(0,153,249,.24)!important;
}
[data-testid="stMain"] .bb83-grade small{font-size:9px!important}
[data-testid="stMain"] .bb83-grade b{font-size:32px!important;color:#08ec83!important}
/* 05: Controls use blue active chips, but Over is bright green. */
.st-key-bb83-controls{margin:1px 0 4px!important}
.st-key-bb83-controls [data-testid="stHorizontalBlock"]{gap:9px!important}
.st-key-bb83-controls label p{font-size:10px!important;color:#adcbeb!important}
.st-key-bb83-controls [data-baseweb="select"]>div,
.st-key-bb83-controls [data-baseweb="input"]>div,
.st-key-bb83-controls [data-testid="stNumberInput"] input{
  min-height:34px!important;height:34px!important;
  background:#0d2036!important;color:#f4faff!important;
  border:1px solid #3b5b80!important;
  border-radius:9px!important;
}
.st-key-bb83-controls [data-testid="stSegmentedControl"]{
  border:1px solid #3b5776!important;border-radius:9px!important;
  background:linear-gradient(125deg,#07192e,#0d1b31)!important;
  min-height:35px!important;padding:2px!important;
}
.st-key-bb83-controls [data-testid="stSegmentedControl"] button{
  font-size:11px!important;min-height:29px!important;
  padding:3px 8px!important;border-radius:7px!important;
  color:#d8e6fa!important;
  transition:box-shadow .2s ease,background .2s ease!important;
}
.st-key-bb83-controls [data-testid="stSegmentedControl"] button[aria-checked="true"]{
  border:1px solid #00baff!important;color:#fff!important;
  background:linear-gradient(130deg,#0b73c6,#06315c)!important;
  box-shadow:0 0 10px rgba(0,173,255,.62),inset 0 0 8px rgba(5,107,227,.24)!important;
}
.st-key-bb83-controls [data-testid="stHorizontalBlock"]>[data-testid="column"]:nth-child(3)
 [data-testid="stSegmentedControl"] button[aria-checked="true"]{
  border:1px solid #06e86c!important;
  background:linear-gradient(135deg,#068841,#02512a)!important;
  box-shadow:0 0 12px rgba(6,239,103,.66),inset 0 0 9px rgba(13,255,128,.18)!important;
}
/* 06: Reference chart and right side: compact proportions and colored bars. */
.st-key-bb83-research{margin:0!important}
.st-key-bb83-research [data-testid="stHorizontalBlock"]{gap:12px!important}
.bb83-chart-head{min-height:28px!important;padding:2px 8px 4px!important}
.bb83-chart-head strong{font-size:17px!important;color:#f4faff!important}
.bb83-chart-head strong span{font-size:19px!important;color:#ff912e!important}
.bb83-chart-head small{font-size:10px!important}
.st-key-bb83-research [data-testid="stPlotlyChart"]{
  border:1px solid #1e669e!important;border-top-color:#ff8a2a!important;
  border-radius:12px!important;padding:2px 6px 0!important;
  background:radial-gradient(ellipse at 0% 0%,rgba(244,112,22,.10),transparent 39%),linear-gradient(130deg,#071529,#071b32)!important;
  box-shadow:inset 0 1px rgba(55,162,238,.12),0 0 11px rgba(0,113,206,.11)!important;
}
.bb83-right-panel{padding-top:0!important;gap:6px!important}
.bb83-rate-grid{gap:7px!important;grid-template-columns:repeat(4,minmax(0,1fr))!important}
.bb83-rate-card{
  min-height:72px!important;padding:6px 3px!important;
  border:1px solid #315b85!important;
  background:linear-gradient(140deg,#07172b,#061429)!important;
  border-radius:10px!important;
  transition:transform .2s ease,border-color .2s ease,box-shadow .2s ease!important;
}
.bb83-rate-card:hover{
  transform:translateY(-3px);
  border-color:#129fe3!important;
  animation:bb91-blue-breathe 2.5s ease-in-out infinite;
}
.bb83-rate-card small{font-size:10px!important}
.bb83-rate-card b{font-size:23px!important;color:#03ee78!important;margin:2px 0!important}
.bb83-rate-card b.under{color:#ff5963!important}
.bb83-rate-card em{font-size:9px!important}
.bb83-split-grid{gap:7px!important}
.bb83-split-card{min-height:45px!important;padding:5px!important}
.bb83-split-card small{font-size:10px!important}
.bb83-split-card b{font-size:19px!important}
.bb83-split-card.accent{
  border-color:#03bfff!important;
  box-shadow:0 0 12px rgba(0,183,255,.42),inset 0 0 8px rgba(0,123,255,.14)!important;
  animation:bb91-blue-breathe 5s ease-in-out infinite;
}
.bb83-defense{
  border:1px solid #fa8929!important;min-height:81px!important;
  border-radius:12px!important;padding:8px 12px!important;
  background:radial-gradient(ellipse at 99% 0%,rgba(250,112,20,.36),transparent 38%),linear-gradient(120deg,#0b1629,#08172a)!important;
  box-shadow:0 0 12px rgba(255,119,19,.19)!important;
}
.bb83-defense h4{font-size:14px!important;margin:0 0 3px!important}
.bb83-defense-points{font-size:10px!important;line-height:1.55!important}
.bb83-defense-logo img{height:45px!important;width:45px!important}
/* 07: Orange-to-cyan BestBets Take with very subtle traveling highlight. */
.bb83-take,.bb90-empty-take{
  position:relative!important;isolation:isolate;overflow:hidden!important;
  min-height:46px!important;margin:5px 0 4px!important;
  padding:9px 14px!important;border-radius:11px!important;
  border:1px solid #ff882e!important;
  background:
    radial-gradient(ellipse 34% 150% at 100% 100%,rgba(0,191,255,.43),transparent 76%),
    radial-gradient(ellipse 23% 80% at 0% 0%,rgba(241,112,15,.19),transparent 80%),
    linear-gradient(110deg,#111527,#071629 61%,#0d2e54)!important;
  box-shadow:0 0 10px rgba(255,126,27,.18),inset 0 1px rgba(251,168,85,.15)!important;
}
.bb83-take:before,.bb90-empty-take:before{
  content:"";position:absolute;z-index:0;pointer-events:none;
  left:0;top:0;height:100%;width:22%;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.065),transparent);
  animation:bb91-take-shine 12s ease-in-out infinite;
}
.bb83-take strong,.bb90-empty-take strong{
  font-size:17px!important;position:relative!important;
  color:#f8faff!important;z-index:1!important;
}
.bb83-take strong span{color:#ff8d2b!important}
.bb83-take>span,.bb90-empty-take>span{font-size:12px!important;position:relative!important;z-index:1!important}
/* 08: Animated six navigation previews, each retaining its own working link. */
.st-key-bb90-footer{margin-top:8px!important}
.st-key-bb90-footer [data-testid="stHorizontalBlock"]{gap:9px!important}
.st-key-bb90-footer [data-testid="stVerticalBlockBorderWrapper"]{
  min-height:0!important;overflow:hidden!important;
  border-radius:12px!important;
  border:1px solid #187ab5!important;
  background:radial-gradient(ellipse 90% 52% at 100% 0%,rgba(0,140,229,.15),transparent 75%),linear-gradient(139deg,#09223e,#071427 85%)!important;
  box-shadow:inset 0 1px rgba(133,211,251,.12),0 0 11px rgba(0,140,255,.21)!important;
  transition:transform .22s ease,border-color .22s ease,box-shadow .22s ease!important;
}
.st-key-bb90-footer [data-testid="column"]:nth-child(even) [data-testid="stVerticalBlockBorderWrapper"]{
  border-color:#f38a28!important;
  box-shadow:inset 0 1px rgba(255,147,42,.16),0 0 13px rgba(255,116,25,.25)!important;
}
.st-key-bb90-footer [data-testid="stVerticalBlockBorderWrapper"]:hover{
  transform:translateY(-4px)!important;
  border-color:#23baff!important;
  box-shadow:0 0 21px rgba(0,163,255,.44),inset 0 0 11px rgba(0,154,255,.10)!important;
}
.st-key-bb90-footer [data-testid="column"]:nth-child(even) [data-testid="stVerticalBlockBorderWrapper"]:hover{
  border-color:#ffa039!important;
  box-shadow:0 0 21px rgba(255,122,25,.44)!important;
}
.st-key-bb90-footer [data-testid="stVerticalBlockBorderWrapper"]>div{padding:0!important}
.bb90-mini-card{
  min-height:130px!important;padding:6px!important;
  background:transparent!important;
}
.bb90-mini-card.bb90-mini-shortcuts{
  background:linear-gradient(117deg,rgba(255,113,25,.11),transparent 59%)!important;
}
.bb90-mini-heading{font-size:11px!important;margin:0 0 5px!important}
.bb90-mini-search{background:#102741!important;border:1px solid #2f5d85!important}
.bb90-mini-list{font-size:10px!important;padding:4px 3px!important}
.bb90-mini-kpis{margin:5px 0!important}
.bb90-mini-kpis div{padding:5px 1px!important}
.bb90-mini-kpis strong{color:#12e89e}
.bb90-mini-kpis .red{color:#ff5448!important}
.bb90-mini-short{padding:3px 0!important}
.st-key-bb90-footer [data-testid="stButton"] button{
  min-height:27px!important;padding:3px 6px!important;
  font-size:11px!important;color:#eaf3fe!important;
  transition:color .2s ease,text-shadow .2s ease!important;
}
.st-key-bb90-footer [data-testid="stButton"] button:hover{
  color:#fff!important;text-shadow:0 0 7px rgba(0,187,255,.7)!important;
}
/* 09: Default empty landing shares the same premium visual grammar. */
.bb90-empty-hero{
  min-height:126px!important;padding:10px 15px!important;
  border-color:#1a8b92!important;
  animation:bb91-slide-in .4s ease both;
}
.bb90-empty-avatar{
  width:78px!important;height:78px!important;
  border-color:#09e184!important;color:#11eb96!important;
  box-shadow:0 0 17px rgba(0,226,135,.23)!important;
}
.bb90-empty-name strong{font-size:29px!important}
.bb90-empty-metric{min-width:70px!important}
.bb90-empty-grade{min-width:107px!important;min-height:74px!important}
.bb90-empty-grid{margin:8px 0 0!important}
.bb90-empty-chart{
  min-height:260px!important;
  background:linear-gradient(150deg,#07162d,#061b30)!important;
  border-top-color:#ed882a!important;
}
.bb90-empty-chart-center{min-height:195px!important}
.bb90-empty-hits div{padding:7px 4px!important}
.bb90-empty-defense{min-height:80px!important;padding:10px!important}
.bb90-blank-page{border-color:#1f5487!important}
/* 10: Normal-sized displays and zoomed-wide monitors. */
@media (min-width:1650px){
  [data-testid="stSidebar"]{width:12.3vw!important;min-width:12.3vw!important}
  [data-testid="stSidebar"] .bb90-brand{min-height:5vw!important;margin:0 0 .5vw!important}
  [data-testid="stSidebar"] .bb90-brand img{width:3.6vw!important;height:3.6vw!important}
  [data-testid="stSidebar"] .bb90-brand b{font-size:1.26vw!important}
  [data-testid="stSidebar"] [data-testid="stButton"] button{
    min-height:2.65vw!important;font-size:.79vw!important;
  }
  [data-testid="stMainBlockContainer"]{padding:.3vw .75vw 1.5vw!important}
  .st-key-bb83_search{height:3.1vw!important;min-height:3.1vw!important}
  .st-key-bb83_search [data-testid="stTextInput"] input{height:2.5vw!important;font-size:1.07vw!important}
  .st-key-bb83_search button[kind="primary"]{height:2.55vw!important;min-height:2.55vw!important}
  .st-key-bb83-suggest .stButton>button{min-height:2vw!important;font-size:.72vw!important}
  [data-testid="stMain"] .bb83-hero{
    height:8.15vw!important;min-height:8.15vw!important;max-height:8.15vw!important;
  }
  [data-testid="stMain"] .bb83-portrait{
    height:8.15vw!important;min-height:8.15vw!important;flex-basis:11vw!important;
  }
  [data-testid="stMain"] .bb83-portrait img{height:9.15vw!important;width:11.4vw!important}
  [data-testid="stMain"] .bb83-identity h2{font-size:2.05vw!important}
  [data-testid="stMain"] .bb83-identity-line{font-size:.8vw!important}
  [data-testid="stMain"] .bb83-hero-metric{min-width:6vw!important}
  [data-testid="stMain"] .bb83-hero-metric label{font-size:.68vw!important}
  [data-testid="stMain"] .bb83-hero-metric b{font-size:1.65vw!important}
  [data-testid="stMain"] .bb83-grade{min-width:7.6vw!important}
  [data-testid="stMain"] .bb83-grade b{font-size:2.15vw!important}
  .st-key-bb83-controls [data-baseweb="select"]>div,
  .st-key-bb83-controls [data-baseweb="input"]>div,
  .st-key-bb83-controls [data-testid="stNumberInput"] input{height:2.25vw!important;min-height:2.25vw!important}
  .st-key-bb83-controls [data-testid="stSegmentedControl"]{height:2.3vw!important;min-height:2.3vw!important}
  .st-key-bb83-controls [data-testid="stSegmentedControl"] button{min-height:1.95vw!important}
  .bb83-chart-head strong{font-size:1.12vw!important}
  .bb83-rate-card{min-height:4.8vw!important}
  .bb83-rate-card b{font-size:1.55vw!important}
  .bb83-rate-card small{font-size:.7vw!important}
  .bb83-split-card{min-height:3vw!important;padding:.35vw!important}
  .bb83-split-card b{font-size:1.3vw!important}
  .bb83-defense{min-height:5.4vw!important}
  .bb83-defense h4{font-size:.95vw!important}
  .bb83-defense-points{font-size:.68vw!important}
  .bb83-take,.bb90-empty-take{min-height:3.1vw!important}
  .bb83-take strong,.bb90-empty-take strong{font-size:1.15vw!important}
  .bb83-take>span,.bb90-empty-take>span{font-size:.8vw!important}
  .bb90-mini-card{min-height:9vw!important}
  .bb90-mini-heading{font-size:.75vw!important}
  .bb90-mini-list{font-size:.7vw!important}
  .bb90-mini-short{font-size:.69vw!important}
}
@media (max-width:1230px){
  [data-testid="stMain"] .bb83-hero{
    height:auto!important;max-height:none!important;min-height:122px!important;
    flex-wrap:wrap!important;
  }
  [data-testid="stMain"] .bb83-hero-metrics{flex-wrap:wrap!important;justify-content:flex-end!important}
  .bb83-rate-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important}
  .st-key-bb83-controls [data-testid="stHorizontalBlock"]{flex-wrap:wrap!important}
  .st-key-bb83-controls [data-testid="stHorizontalBlock"]>[data-testid="column"]{flex:1 1 43%!important;min-width:43%!important}
}
@media (max-width:700px){
  .st-key-bb83_search{width:100%!important}
  .st-key-bb83-suggest{width:100%!important}
  [data-testid="stMain"] .bb83-portrait{flex-basis:95px!important;height:115px!important}
  [data-testid="stMain"] .bb83-portrait img{width:115px!important;height:115px!important}
  [data-testid="stMain"] .bb83-identity h2{font-size:22px!important;white-space:normal!important}
  .bb83-rate-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important}
  .bb90-mini-card{min-height:125px!important}
  .st-key-bb90-footer [data-testid="stHorizontalBlock"]{flex-wrap:wrap!important}
  .st-key-bb90-footer [data-testid="stHorizontalBlock"]>[data-testid="column"]{
    flex:1 1 47%!important;min-width:47%!important;
  }
}
@media (prefers-reduced-motion:reduce){
  .st-key-bb83_search,
  [data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"],
  .bb83-split-card.accent,
  .bb83-take:before,.bb90-empty-take:before,
  [data-testid="stMain"] .bb83-hero,.bb90-empty-hero,
  .bb83-rate-card:hover{
    animation:none!important;
  }
  *,*:before,*:after{
    scroll-behavior:auto!important;
    transition-duration:.01ms!important;
  }
}

/* Two subtle reference-header indicators, informational until account work exists. */
.bb91-header-icons{
  position:fixed;z-index:200;
  top:9px;right:16px;
  display:flex;align-items:center;gap:10px;
  pointer-events:none;
}
.bb91-header-icons>span{
  display:grid;place-items:center;
  width:35px;height:35px;position:relative;
  border-radius:50%;border:1px solid #537da0;
  color:#e2f5ff;font-size:19px;
  background:linear-gradient(130deg,#0b1d35,#071427);
  box-shadow:0 0 9px rgba(0,152,243,.1);
}
.bb91-header-icons i{
  position:absolute;width:6px;height:6px;top:4px;right:4px;border-radius:50%;
  background:#ff8737;box-shadow:0 0 8px rgba(255,131,42,.72);
}
@media(min-width:1650px){
  [data-testid="stMain"] .bb83-portrait{
    flex-basis:12.7vw!important;
  }
  [data-testid="stMain"] .bb83-portrait img{
    width:12.7vw!important;
  }
  [data-testid="stMain"] .bb83-identity h2{
    font-size:2.28vw!important;
  }
  .bb91-header-icons{
    top:.65vw;right:1.15vw;gap:.75vw;
  }
  .bb91-header-icons>span{
    width:2.5vw;height:2.5vw;font-size:1.4vw;
  }
}
@media(max-width:700px){
  .bb91-header-icons{display:none!important}
}

</style>
"""
def apply_reference_fx():
    st.markdown(REFERENCE_FX_CSS, unsafe_allow_html=True)
