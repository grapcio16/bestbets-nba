"""BestBets v8.4 — visual-first reference reset.

Presentation overrides only. Existing Streamlit widgets, real NBA data,
simulations and routing remain unchanged and operational.
The 11 November approved screenshot governs sizing and presentation.
"""
from __future__ import annotations

import streamlit as st

PIXEL_CSS = r"""
<style>
/* BESTBETS V8.4 — REFERENCE LOCK, 11 NOV 2026 */
:root{
  --v84-navy:#030c19;
  --v84-navy-2:#07172a;
  --v84-panel:#07182d;
  --v84-blue:#00aeff;
  --v84-orange:#ff7623;
  --v84-green:#00ef76;
  --v84-red:#ff4d45;
  --v84-white:#f8fbff;
}
*,*::before,*::after{box-sizing:border-box}
[data-testid="stAppViewContainer"]:has(.bb83-page-marker){
  background:
    radial-gradient(ellipse 54% 39% at 103% 7%,rgba(0,90,214,.14),transparent),
    radial-gradient(ellipse 28% 28% at 11% 97%,rgba(252,101,24,.10),transparent),
    linear-gradient(120deg,#020711 0%,#041022 48%,#030914 100%)!important;
}
[data-testid="stAppViewContainer"]:has(.bb83-page-marker) [data-testid="stMain"]{
  width:100%!important;min-width:0!important;
  background:transparent!important;
}
[data-testid="stAppViewContainer"]:has(.bb83-page-marker) [data-testid="stMainBlockContainer"],
[data-testid="stAppViewContainer"]:has(.bb83-page-marker) .stMainBlockContainer,
[data-testid="stAppViewContainer"]:has(.bb83-page-marker) .block-container{
  width:100%!important;
  max-width:none!important;
  margin-left:0!important;margin-right:0!important;
  padding:11px 24px 26px!important;
  min-width:0!important;
}
[data-testid="stAppViewContainer"]:has(.bb83-page-marker) [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"]{
  width:100%!important;max-width:none!important;
}
[data-testid="stAppViewContainer"]:has(.bb83-page-marker) [data-testid="stMain"] [data-testid="stVerticalBlock"]{
  row-gap:5px;
}
[data-testid="stAppViewContainer"]:has(.bb83-page-marker) [data-testid="stMain"] [data-testid="stHorizontalBlock"]{
  min-width:0!important;
}
[data-testid="stAppViewContainer"]:has(.bb83-page-marker) [data-testid="stMain"] [data-testid="column"]{
  min-width:0!important;
}
@media(min-width:901px){
  [data-testid="stAppViewContainer"]:has(.bb83-page-marker) [data-testid="stHeader"]{
    height:0!important;min-height:0!important;display:none!important;
  }
  [data-testid="stAppViewContainer"]:has(.bb83-page-marker) [data-testid="stDecoration"]{
    display:none!important;
  }
}
/* Locked 11-Nov left navigation — tall logo, thin separators and orange active item. */
[data-testid="stAppViewContainer"]:has(.bb83-page-marker) [data-testid="stSidebar"]{
  width:207px!important;
  min-width:207px!important;
  background:
    radial-gradient(ellipse 85% 30% at -25% 100%,rgba(255,106,28,.28),transparent),
    linear-gradient(174deg,#020915 0%,#071429 60%,#06101d 100%)!important;
  border-right:1px solid #16416a!important;
  box-shadow:3px 0 22px rgba(0,0,0,.42)!important;
}
[data-testid="stAppViewContainer"]:has(.bb83-page-marker) [data-testid="stSidebarUserContent"]{
  padding:8px 12px 15px!important;
}
[data-testid="stAppViewContainer"]:has(.bb83-page-marker) [data-testid="stSidebar"] .stVerticalBlock{
  row-gap:2px!important;
}
[data-testid="stAppViewContainer"]:has(.bb83-page-marker) .bbm-brand{
  display:flex!important;align-items:center!important;gap:2px!important;
  margin:0 0 23px!important;padding:11px 0 12px!important;
  border-bottom:1px solid #1c3658!important;
  min-height:69px;
}
[data-testid="stAppViewContainer"]:has(.bb83-page-marker) .bbm-brand img{
  width:55px!important;height:55px!important;object-fit:contain!important;
  filter:drop-shadow(0 2px 5px rgba(253,109,28,.4));
}
[data-testid="stAppViewContainer"]:has(.bb83-page-marker) .bbm-brand b{
  font-size:20px!important;font-weight:1000!important;line-height:1!important;
  font-style:italic;letter-spacing:-.08em!important;text-shadow:0 2px 8px rgba(0,0,0,.4)
}
[data-testid="stAppViewContainer"]:has(.bb83-page-marker) .bbm-brand b span{
  color:#fc671b!important;
}
[data-testid="stAppViewContainer"]:has(.bb83-page-marker) .bbm-brand .bbm-eyebrow{
  font-size:7px!important;color:#8ac3fa!important;letter-spacing:.13em!important;
  margin:3px 0 0!important;
}
[data-testid="stAppViewContainer"]:has(.bb83-page-marker) [data-testid="stSidebar"] .stButton > button{
  width:100%!important;min-height:39px!important;
  border:1px solid transparent!important;
  padding:9px 11px!important;margin:1px 0!important;
  border-radius:9px!important;
  text-align:left!important;justify-content:flex-start!important;
  font-size:12px!important;font-weight:800!important;
  letter-spacing:-.015em!important;
  background:transparent!important;color:#c8d8ef!important;
  box-shadow:none!important;
}
[data-testid="stAppViewContainer"]:has(.bb83-page-marker) [data-testid="stSidebar"] .stButton > button p{
  text-align:left!important;white-space:normal!important;line-height:1.3!important;
}
[data-testid="stAppViewContainer"]:has(.bb83-page-marker) [data-testid="stSidebar"] .stButton > button[kind="primary"]{
  color:#fff!important;
  background:linear-gradient(105deg,rgba(242,100,25,.35),rgba(88,48,38,.38) 50%,rgba(8,30,54,.92))!important;
  border:1px solid #ff7c29!important;border-left:4px solid #ff9f33!important;
  box-shadow:0 0 12px rgba(255,116,25,.43),inset 0 0 16px rgba(248,99,30,.07)!important;
}
[data-testid="stAppViewContainer"]:has(.bb83-page-marker) [data-testid="stSidebar"] .stButton > button:hover{
  border-color:#245b9a!important;background:rgba(26,55,88,.65)!important;
}
[data-testid="stAppViewContainer"]:has(.bb83-page-marker) .bbm-sidebar-footer{
  font-size:9px!important;line-height:1.4!important;
  color:#6385a9!important;margin-top:9px!important;
}
/* Search: centered cyan glowing capsule + 4 short, evenly spaced presets. */
.st-key-bb83_search{
  width:73%!important;max-width:990px!important;margin:4px auto 6px!important;
  min-height:50px!important;padding:3px 7px 3px 15px!important;
  border:1.5px solid #2ad0ff!important;border-radius:999px!important;
  background:linear-gradient(90deg,#051122 0%,#071a34 70%,#142038 100%)!important;
  box-shadow:0 0 0 2px rgba(0,182,255,.14),0 0 19px rgba(4,169,255,.70),inset 0 0 12px rgba(0,125,238,.26)!important;
}
.st-key-bb83_search [data-testid="stForm"]{
  padding:0!important;background:transparent!important;border:0!important;
}
.st-key-bb83_search [data-testid="stForm"] [data-testid="stHorizontalBlock"]{
  align-items:center!important;gap:6px!important;
}
.st-key-bb83_search [data-testid="stTextInput"] input{
  height:38px!important;background:transparent!important;border:0!important;
  font-size:16px!important;font-weight:700!important;color:#f4faff!important;
  padding:0 9px!important;box-shadow:none!important;
}
.st-key-bb83_search [data-testid="stTextInput"] input::placeholder{color:#c6d6ec!important;opacity:1}
.st-key-bb83_search [data-testid="stTextInput"]>div,
.st-key-bb83_search [data-baseweb="input"]>div{
  background:transparent!important;border:0!important;box-shadow:none!important;
}
.st-key-bb83_search button[kind="primary"]{
  min-height:40px!important;height:40px!important;
  border-radius:99px!important;border:1px solid #ffbc68!important;
  background:linear-gradient(110deg,#ffa22f,#ff7516)!important;
  box-shadow:0 0 0 2px rgba(255,126,24,.17),0 0 16px rgba(255,134,30,.74)!important;
  color:#fff!important;font-size:18px!important;
}
.st-key-bb83-suggest{
  width:90%!important;margin:0 auto 11px!important;
}
.st-key-bb83-suggest [data-testid="stHorizontalBlock"]{gap:9px!important}
.st-key-bb83-suggest .stButton>button{
  width:100%!important;min-height:31px!important;
  border-radius:30px!important;padding:5px 7px!important;
  border:1px solid #375979!important;
  background:linear-gradient(180deg,#071b30,#0a1325)!important;
  color:#e0eafa!important;font-size:10px!important;font-weight:650!important;
  box-shadow:inset 0 1px rgba(147,195,241,.06)!important;
}
.st-key-bb83-suggest .stButton>button:hover{
  border-color:#00baff!important;box-shadow:0 0 12px rgba(0,167,255,.28)!important;
}
.st-key-bb83-suggest .stButton>button p{
  white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;
}
/* Hero: green logo halo, cut-out portrait, full-width unified data rail. */
.bb83-hero{
  width:100%!important;min-height:123px!important;margin:0 0 4px!important;
  align-items:stretch!important;gap:4px!important;
  border-radius:14px!important;border:1px solid #157a98!important;
  padding:0 8px 0 0!important;
  background:
    radial-gradient(ellipse 22% 87% at 9% 40%,rgba(0,207,113,.22),transparent 83%),
    radial-gradient(ellipse 37% 89% at 101% 100%,rgba(0,100,243,.29),transparent 71%),
    radial-gradient(ellipse 24% 85% at 94% -20%,rgba(248,89,22,.24),transparent 75%),
    linear-gradient(109deg,#062c27 0%,#06182a 32%,#040f1e 72%,#0e2440 100%)!important;
  box-shadow:inset 0 1px rgba(115,224,205,.17),0 0 10px rgba(3,155,218,.18)!important;
}
.bb83-portrait{
  flex:0 0 clamp(108px,13vw,179px)!important;
  min-height:123px!important;
  background:radial-gradient(ellipse 81% 79% at 45% 53%,rgba(14,207,132,.21),transparent 85%)!important;
}
.bb83-portrait img{
  height:131px!important;width:100%!important;object-fit:contain!important;
  object-position:center bottom!important;
}
.bb83-portrait .bb83-team-back{top:4px!important;left:5px!important;opacity:.43!important}
.bb83-team-back img{height:101px!important;width:101px!important;object-fit:contain!important}
.bb83-identity{
  flex:1 1 225px!important;min-width:168px!important;padding:11px 3px!important;
}
.bb83-identity h2{
  font-size:clamp(24px,2.6vw,38px)!important;
  letter-spacing:-.055em!important;line-height:1.04!important;
  margin:0 0 9px!important;font-weight:950!important;color:#f7fbff!important;
}
.bb83-identity-line{gap:8px!important;font-size:11px!important;color:#d6e2f2!important}
.bb83-team-badge{
  padding:3px 8px!important;border-color:#14dc77!important;
  background:#0e5035!important;color:#fff!important;
  box-shadow:0 0 7px rgba(15,241,116,.24)!important;
}
.bb83-identity small{font-size:9px!important;color:#99b4ca!important;margin-top:9px!important}
.bb83-hero-metrics{
  flex:0 0 auto!important;gap:0!important;align-items:center!important;padding:9px 0!important;
}
.bb83-hero-metric{
  min-width:clamp(73px,7.6vw,115px)!important;
  padding:5px 6px!important;border-left:1px solid #345676!important;
}
.bb83-hero-metric label{color:#bdcce1!important;font-size:10px!important;font-weight:900!important}
.bb83-hero-metric b{font-size:23px!important;color:#fff!important;line-height:1.2!important}
.bb83-hero-metric em{font-size:9px!important;color:#a2b5ce!important}
.bb83-grade{
  flex:0 0 clamp(86px,10vw,127px)!important;
  min-width:0!important;align-self:center!important;
  margin-left:3px!important;padding:9px 4px!important;border-radius:12px!important;
  border:1px solid #6696c1!important;
  background:radial-gradient(ellipse at 50% 100%,rgba(0,162,238,.17),transparent 68%),#071629!important;
  box-shadow:0 0 15px rgba(14,141,253,.24)!important;
}
.bb83-grade small{font-size:9px!important;color:#c4d3e9!important}
.bb83-grade b{font-size:32px!important;color:#15e982!important}
.bb83-grade em{font-size:9px!important}
/* Controls — row of compact, coherent market, line, side, tab and history widgets. */
.st-key-bb83-controls{
  margin:3px 0 8px!important;padding:0!important;
}
.st-key-bb83-controls [data-testid="stHorizontalBlock"]{
  gap:9px!important;align-items:flex-end!important;
}
.st-key-bb83-controls [data-testid="stVerticalBlock"]{gap:2px!important}
.st-key-bb83-controls label p{
  font-size:10px!important;font-weight:900!important;
  color:#9eb6d2!important;white-space:nowrap!important;
}
.st-key-bb83-controls [data-testid="stSelectbox"]>div,
.st-key-bb83-controls [data-testid="stNumberInput"]>div{
  margin:0!important;
}
.st-key-bb83-controls [data-baseweb="select"]>div,
.st-key-bb83-controls [data-baseweb="input"]>div,
.st-key-bb83-controls [data-testid="stNumberInput"] input{
  height:37px!important;min-height:37px!important;
  background:linear-gradient(135deg,#0d2035,#09182b)!important;
  color:#f3faff!important;
  border:1px solid #3a5d84!important;border-radius:9px!important;
  font-weight:850!important;
}
.st-key-bb83-controls [data-testid="stSegmentedControl"]{
  background:linear-gradient(145deg,#071a30,#071526)!important;
  border:1px solid #3e5b7d!important;border-radius:10px!important;
  min-height:37px!important;padding:2px!important;
}
.st-key-bb83-controls [data-testid="stSegmentedControl"] button{
  padding:6px 7px!important;min-height:31px!important;
  border-radius:8px!important;font-size:11px!important;
  font-weight:900!important;white-space:nowrap!important;
}
.st-key-bb83-controls [data-testid="stSegmentedControl"] button[aria-checked="true"]{
  background:linear-gradient(145deg,#0675cc,#082852)!important;
  border:1px solid #1fc4ff!important;color:#fff!important;
  box-shadow:0 0 9px rgba(0,164,255,.48)!important;
}
.st-key-bb83-controls [data-testid="stSegmentedControl"] [data-selected="true"]{
  background:#0574bc!important;box-shadow:0 0 10px rgba(0,164,255,.4)!important;
}
/* Main research grid: reference chart left, four hit-rate cards right. */
.st-key-bb83-research{
  width:100%!important;margin:0!important;
}
.st-key-bb83-research > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"]{
  align-items:flex-start!important;gap:13px!important;
}
.st-key-bb83-research [data-testid="stHorizontalBlock"] > [data-testid="column"]:first-child{
  min-width:0!important;
}
.st-key-bb83-research [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(2){
  min-width:0!important;
}
.bb83-chart-head{
  min-height:29px!important;padding:2px 3px 5px!important;margin:0!important;
}
.bb83-chart-head strong{
  font-size:16px!important;line-height:1.3!important;font-weight:950!important;
}
.bb83-chart-head strong span{color:#ff8529!important}
.bb83-chart-head small{color:#9cb8d9!important;font-size:10px!important}
.st-key-bb83-research [data-testid="stPlotlyChart"]{
  width:100%!important;
  background:
    radial-gradient(ellipse 52% 45% at 0% 0%,rgba(254,106,19,.10),transparent),
    linear-gradient(135deg,#071527,#051a32)!important;
  border:1px solid #126aa7!important;border-radius:13px!important;
  padding:2px 5px 0!important;
  box-shadow:inset 0 1px rgba(87,172,248,.12),0 0 10px rgba(0,111,203,.12)!important;
}
.st-key-bb83-research [data-testid="stPlotlyChart"]>div{width:100%!important}
.bb83-right-panel{gap:6px!important;padding-top:0!important}
.bb83-rate-grid{
  display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:7px!important;
}
.bb83-rate-card{
  text-align:center!important;
  padding:8px 4px 7px!important;min-height:71px!important;
  border:1px solid #285883!important;border-radius:10px!important;
  background:linear-gradient(140deg,#07192e,#051225)!important;
  box-shadow:inset 0 1px rgba(110,204,247,.15)!important;
}
.bb83-rate-card small{font-size:10px!important;line-height:1.25!important}
.bb83-rate-card b{font-size:24px!important;line-height:1.18!important;color:#04ea77!important;margin:4px 0 1px!important}
.bb83-rate-card b.under{color:#ff5555!important}
.bb83-rate-card em{font-size:9px!important}
.bb83-split-grid{grid-template-columns:repeat(3,minmax(0,1fr))!important;gap:7px!important}
.bb83-split-card{
  min-height:55px!important;padding:6px 3px!important;
  background:#091b31!important;border-radius:9px!important;border-color:#2c547c!important;
}
.bb83-split-card small{font-size:10px!important}
.bb83-split-card b{font-size:18px!important;line-height:1.3!important}
.bb83-split-card.accent{
  border-color:#2bc5ff!important;
  background:linear-gradient(110deg,rgba(0,90,180,.34),#092142)!important;
  box-shadow:0 0 13px rgba(0,155,255,.34),inset 0 0 9px rgba(0,128,218,.13)!important;
}
.bb83-defense{
  min-height:90px!important;padding:9px 11px!important;
  border-radius:12px!important;
  border-color:#f98832!important;
  background:
    radial-gradient(ellipse 44% 80% at 100% 0%,rgba(255,103,22,.32),transparent),
    linear-gradient(106deg,#0b1a2e,#071629)!important;
  box-shadow:0 0 11px rgba(251,105,28,.21)!important;
}
.bb83-defense h4{font-size:13px!important;margin:0 0 4px!important}
.bb83-defense h4 span{color:#ffa33c!important}
.bb83-defense-inner{gap:11px!important}
.bb83-defense-logo{flex-basis:47px!important}
.bb83-defense-logo img{width:45px!important;height:45px!important}
.bb83-defense-points{font-size:10px!important;line-height:1.6!important}
.bb83-defense-points div:before{color:#00ef74!important}
/* Full-width take panel, orange rail at left, cyan wave to the right. */
.bb83-take{
  position:relative!important;overflow:hidden!important;
  width:100%!important;min-height:46px!important;
  margin:6px 0 3px!important;padding:9px 14px!important;
  gap:14px!important;border-radius:11px!important;
  border:1px solid #ec8230!important;
  background:
    radial-gradient(ellipse 30% 95% at 98% 160%,rgba(0,205,255,.50),transparent 85%),
    radial-gradient(ellipse 25% 50% at 0% 0%,rgba(242,87,14,.25),transparent),
    linear-gradient(101deg,#111528,#07172d 65%,#05213f)!important;
  box-shadow:0 0 9px rgba(252,107,25,.20),inset 0 1px rgba(255,191,131,.07)!important;
}
.bb83-take:after{
  content:"";position:absolute;pointer-events:none;
  width:190px;height:48px;right:-12px;bottom:-38px;border-radius:50%;
  border-top:2px solid #04cfff;transform:rotate(-10deg);
  box-shadow:0 -3px 12px rgba(0,184,255,.24);
}
.bb83-take strong{
  position:relative;z-index:1;padding-right:15px!important;
  font-size:16px!important;white-space:nowrap!important;
}
.bb83-take strong span{color:#ff8123!important}
.bb83-take>span{position:relative;z-index:1;font-size:11px!important;color:#dbe6f4!important}
.bb83-take em{color:#04f37e!important;font-weight:900!important}
/* Footer — six bordered mini-panels all on one strip on desktop. */
.bb83-footer-heading{display:none!important}
.st-key-bb83-footer{
  width:100%!important;margin:8px 0 0!important;
}
.st-key-bb83-footer [data-testid="stHorizontalBlock"]{gap:8px!important;align-items:stretch!important}
.st-key-bb83-footer [data-testid="column"]{min-width:0!important}
.st-key-bb83-footer [data-testid="stVerticalBlockBorderWrapper"]{
  min-height:129px!important;max-height:151px!important;
  border:1px solid #1576b5!important;border-radius:12px!important;
  background:
    radial-gradient(ellipse 70% 49% at 100% 0%,rgba(0,117,215,.16),transparent),
    linear-gradient(142deg,#0a2038,#061426)!important;
  box-shadow:inset 0 1px rgba(100,190,244,.13),0 0 8px rgba(0,137,251,.14)!important;
}
.st-key-bb83-footer [data-testid="column"]:nth-child(2) [data-testid="stVerticalBlockBorderWrapper"],
.st-key-bb83-footer [data-testid="column"]:nth-child(4) [data-testid="stVerticalBlockBorderWrapper"],
.st-key-bb83-footer [data-testid="column"]:nth-child(6) [data-testid="stVerticalBlockBorderWrapper"]{
  border-color:#de7828!important;
  box-shadow:inset 0 1px rgba(254,149,52,.16),0 0 8px rgba(255,103,16,.16)!important;
}
.st-key-bb83-footer [data-testid="stVerticalBlockBorderWrapper"] > div{
  padding:8px!important;
}
.st-key-bb83-footer [data-testid="stVerticalBlock"]{
  gap:2px!important;
}
.bb83-mini-kicker{
  color:#ff9c3d!important;font-size:10px!important;font-weight:950!important;
  letter-spacing:.02em!important;white-space:normal!important;
}
.bb83-mini-title{
  color:#f7fcff!important;font-size:12px!important;font-weight:950!important;
  margin:4px 0!important;
}
.bb83-mini-body{color:#adcae5!important;font-size:10px!important;line-height:1.3!important;min-height:32px!important}
.bb83-mini-body b{color:#10f19b!important}
.st-key-bb83-footer .stButton>button{
  min-height:26px!important;padding:2px 6px!important;
  font-size:10px!important;border-radius:7px!important;
  border:1px solid #2d6898!important;background:#132842!important;
}
/* Expanded methodology stays after the take/footer, not inside the hero. */
[data-testid="stMain"]:has(.bb83-page-marker) [data-testid="stExpander"]{
  border-color:#233e5e!important;background:rgba(8,20,38,.30)!important;
}
[data-testid="stMain"]:has(.bb83-page-marker) [data-testid="stExpander"] summary{
  font-size:11px!important;min-height:30px!important;color:#9ebadb!important;
}
[data-testid="stMain"]:has(.bb83-page-marker) [data-testid="stBottomBlockContainer"]{display:none}
[data-testid="stMain"]:has(.bb83-page-marker) .bbm-ref-aux{display:none!important}
/* Graceful desktop/laptop/tablet scaling, no horizontal clipping. */
@media(max-width:1450px){
  [data-testid="stAppViewContainer"]:has(.bb83-page-marker) [data-testid="stMainBlockContainer"]{
    padding:10px 14px 23px!important;
  }
  .bb83-portrait{flex-basis:125px!important}
  .bb83-identity h2{font-size:27px!important}
  .bb83-hero-metric{min-width:67px!important}
  .bb83-hero-metric b{font-size:20px!important}
  .bb83-grade{flex-basis:89px!important}
  .bb83-rate-card b{font-size:20px!important}
  .st-key-bb83-footer [data-testid="stVerticalBlockBorderWrapper"]{min-height:136px!important}
}
@media(max-width:1150px){
  [data-testid="stAppViewContainer"]:has(.bb83-page-marker) [data-testid="stSidebar"]{
    width:183px!important;min-width:183px!important;
  }
  .bb83-hero{flex-wrap:wrap!important;justify-content:space-between!important}
  .bb83-identity{flex:1!important}
  .bb83-hero-metrics{flex:1 1 auto!important;justify-content:flex-end!important}
  .bb83-grade{margin-right:3px!important}
  .bb83-rate-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important}
  .bb83-split-grid{grid-template-columns:repeat(3,minmax(0,1fr))!important}
  .st-key-bb83-footer [data-testid="stHorizontalBlock"]{flex-wrap:wrap!important}
  .st-key-bb83-footer [data-testid="stHorizontalBlock"]>[data-testid="column"]{
    flex:1 1 30%!important;min-width:30%!important;
  }
}
@media(max-width:900px){
  [data-testid="stAppViewContainer"]:has(.bb83-page-marker) [data-testid="stMainBlockContainer"]{
    padding:13px 12px 22px!important;
  }
  .st-key-bb83_search{width:96%!important}
  .st-key-bb83-suggest{width:100%!important}
  .st-key-bb83-research [data-testid="stHorizontalBlock"]{flex-wrap:wrap!important}
  .st-key-bb83-research [data-testid="stHorizontalBlock"]>[data-testid="column"]{
    flex:1 1 100%!important;min-width:100%!important;
  }
  .bb83-rate-grid{grid-template-columns:repeat(4,minmax(0,1fr))!important}
  .st-key-bb83-controls [data-testid="stHorizontalBlock"]{flex-wrap:wrap!important}
  .st-key-bb83-controls [data-testid="stHorizontalBlock"]>[data-testid="column"]{
    flex:1 1 46%!important;min-width:46%!important;
  }
}
@media(max-width:620px){
  .st-key-bb83_search{width:100%!important;padding:2px 5px!important;min-height:45px!important}
  .st-key-bb83_search [data-testid="stTextInput"] input{font-size:12px!important}
  .st-key-bb83-suggest [data-testid="stHorizontalBlock"]{flex-wrap:wrap!important}
  .st-key-bb83-suggest [data-testid="stHorizontalBlock"]>[data-testid="column"]{
    flex:1 1 47%!important;min-width:47%!important;
  }
  .bb83-portrait{flex-basis:91px!important;min-height:100px!important}
  .bb83-portrait img{height:103px!important}
  .bb83-team-back img{width:77px!important;height:77px!important}
  .bb83-identity{min-width:140px!important}
  .bb83-identity h2{font-size:22px!important;white-space:normal!important}
  .bb83-identity-line{font-size:10px!important}
  .bb83-hero-metrics{width:100%!important;flex-wrap:wrap!important;justify-content:space-between!important}
  .bb83-hero-metric{flex:1 1 20%!important;min-width:65px!important}
  .bb83-grade{min-width:77px!important;margin:5px auto!important}
  .bb83-rate-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important}
  .bb83-rate-card b{font-size:21px!important}
  .bb83-take{display:block!important}
  .bb83-take strong{display:block!important;border-right:0!important;border-bottom:1px solid #375779!important;padding-bottom:6px!important;margin-bottom:6px!important}
  .st-key-bb83-footer [data-testid="stHorizontalBlock"]>[data-testid="column"]{
    flex:1 1 47%!important;min-width:47%!important;
  }
  .bb83-chart-head strong{font-size:13px!important}
}
</style>
"""

def apply_pixel_theme():
    st.markdown(PIXEL_CSS, unsafe_allow_html=True)
