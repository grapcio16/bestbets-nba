"""Responsive full-width BestBets preview (Streamlit Components V2).

This is a separate preview entrypoint. It deliberately does NOT change
app.py or the production Streamlit v1 component.

The premium appearance is retained in a normal CSS Grid/Flex layout.
No application viewBox, fixed aspect ratio or dashboard scaling. The
production NBA research and navigation handlers are reused.
"""
from __future__ import annotations

from pathlib import Path
import re
import streamlit as st

from bestbets_custom_screen import _cached_brand, _research

ROOT=Path(__file__).resolve().parent
FRONTEND=ROOT/"bestbets_reference_frontend"
SOURCE=FRONTEND/"index.html"


def _assets():
    raw=SOURCE.read_text(encoding="utf-8")
    css=(FRONTEND/"responsive.css").read_text(encoding="utf-8")
    body=raw.split("<body>",1)[1].split("<script>",1)[0].strip()
    script=raw.split("<script>",1)[1].split("</script>",1)[0].lstrip()
    original_header='(function(){\n"use strict";'
    assert script.startswith(original_header),"Unexpected upstream JS structure"
    script=script.replace(
        original_header,
        'export default function(component) {\n"use strict";\n'
        'const {parentElement,data,setTriggerValue}=component;\n'
        'const mounted=parentElement.__bestbetsV2;\n'
        'if(mounted && mounted.root===parentElement.querySelector("#stage")){\n'
        '  mounted.update(data,setTriggerValue);return mounted.watchChart();\n'
        '}\n'
        'const bridge={setTriggerValue};',
        1
    )
    old_lookup='const $=function(id){return document.getElementById(id)};'
    assert old_lookup in script
    script=script.replace(old_lookup,
        'const $=function(id){return parentElement.querySelector("#"+id)};',1
    )
    script=script.replace("document.querySelectorAll(", "parentElement.querySelectorAll(")
    script=script.replace("document.querySelector(", "parentElement.querySelector(")
    old_notify='''function notify(type,extra){
  window.parent.postMessage(Object.assign({isStreamlitMessage:true,type:type},extra||{}),"*");
}'''
    assert old_notify in script
    script=script.replace(old_notify,'''function notify(type,extra){
  // V2 triggers go directly to Python, without iframe/window messages.
  if(type==="streamlit:setComponentValue"){
    bridge.setTriggerValue("search",(extra||{}).value);
  }
}''',1)
    start=script.index("function resize(){")
    finish=script.index("const animatedMetrics=",start)
    script=script[:start]+script[finish:]
    script=script.replace('  resize();','')
    script=script.replace('window.addEventListener("resize",resize);','')
    script=script.replace('$("props-pane").style.display=active?"block":"none";',
                          '$("props-pane").style.display=active?"grid":"none";')
    script=script.replace('parentElement.querySelector(".suggestions").style.display=active?"flex":"none";',
                          'parentElement.querySelector(".suggestions").style.display=active?"grid":"none";')
    # Only the chart uses SVG. Its coordinates follow its real pixel size,
    # so wider panels contain wider plots without stretching the typography.
    script=script.replace('function chartMarkup(games){', '''function chartSize(){
  const svg=$("chart-svg");
  return {width:Math.max(1,svg.clientWidth),height:Math.max(1,svg.clientHeight)};
}
// Use a compact, centered bar group instead of stretching sparse L5/L10
// results across the full-width analytics panel. Preserve the full-width
// grid and baseline: only the actual bars / labels are positioned in the
// grouping. All positions follow real CSS pixels and remain responsive.
function chartBarGeometry(available,count){
  const plotSpan=Math.min(available,count*82,960);
  const step=plotSpan/count;
  const gap=Math.min(14,step*.22);
  const bar=Math.max(1,Math.min(68,step-gap));
  const start=(available-plotSpan)/2;
  return {plotSpan,step,bar,start};
}
function chartMarkup(games){''',1)
    script=script.replace('const w=581-padLeft-padRight,h=170-top-bottom;',
                          'const {width,height}=chartSize();\n  const w=width-padLeft-padRight,h=height-top-bottom;',1)
    script=script.replace(
        'const gap=n>15?4:n>10?6:8;\n  const bar=Math.min(46,(w-gap*(n-1))/n),step=w/n;',
        'const {step,bar,start}=chartBarGeometry(w,n);',1)
    script=script.replace(
        'x=padLeft+step*i+(step-bar)/2',
        'x=padLeft+start+step*i+(step-bar)/2',1)
    # The value and tick labels now scale to the available group width.
    script=script.replace(
        '''font-size="'+(n>15?9:11)+'"''',
        '''font-size="'+Math.min(13,Math.max(9,step*.17))+'"''',1)
    script=script.replace(
        '''font-size="'+(n>15?7:8.7)+'"''',
        '''font-size="'+Math.min(11,Math.max(8,step*.14))+'"''')
    assert 'const {step,bar,start}=chartBarGeometry(w,n);' in script
    assert 'x=padLeft+start+step*i+(step-bar)/2' in script
    script=script.replace('y="153"', 'y="\'+(height-17)+\'"')
    script=script.replace('y="163"', 'y="\'+(height-7)+\'"')
    script=script.replace('const svg=$("chart-svg"),placeholder=$("chart-placeholder");',
        '''const svg=$("chart-svg"),placeholder=$("chart-placeholder");
  const size=chartSize();
  svg.setAttribute("viewBox",`0 0 ${size.width} ${size.height}`);''',1)
    script=script.replace('placeholder.style.display="block"', 'placeholder.style.display="grid"')
    script=script.replace('placeholder.style.display=rows.length?"none":"block"',
                          'placeholder.style.display=rows.length?"none":"grid"')
    start=script.index('window.addEventListener("message",function(event){')
    script=script[:start]+'''function update(payload,trigger){
  bridge.setTriggerValue=trigger;
  // Keep local draft/error mutations separate from Streamlit's input data.
  state.payload={...(payload||{player:null,error:"",brand:""})};
  state.loading=false;
  const p=state.payload.player;
  if(p){
    const identity=[p.name,p.market,p.line,p.side].join("|");
    if(identity!==state.lastIdentity){
      state.market=p.market||"PTS";state.line=Number(p.line)||25.5;
      state.side=p.side==="UNDER"?"UNDER":"OVER";state.period="L10";
      state.lastIdentity=identity;
    }
  }
  render();
}
function watchChart(){
  // A data update may clean up the previous V2 invocation. Reconnect one
  // observer, with a cleanup bound only to that invocation's observer.
  const mounted=parentElement.__bestbetsV2;
  if(mounted.stopWatching)mounted.stopWatching();
  let lastSize="";
  const observer=new ResizeObserver(()=>{
    const size=chartSize(),key=size.width+"x"+size.height;
    if(key===lastSize)return;
    lastSize=key;
    if(state.page==="props")renderChart(state.payload.player);
  });
  observer.observe($("chart-svg"));
  mounted.stopWatching=()=>observer.disconnect();
  return mounted.stopWatching;
}
// V2 reruns JS when data changes but retains its DOM. Bind listeners once.
parentElement.__bestbetsV2={root,update,watchChart};
update(data,setTriggerValue);
return watchChart();
}'''
    # Keep each footer card and its navigation label together when the grid
    # wraps. All original IDs, text and route handlers are preserved.
    footer=body.split('<footer id="footer">',1)[1].split('</footer>',1)[0]
    tiles=re.findall(r'  <div class="preview".*?(?=\n  <div class="preview"|\n </div>)',footer,re.S)
    links=re.findall(r'<button data-page=.*?</button>',footer)
    assert len(tiles)==len(links)==6, "Unexpected footer structure"
    modules=''.join('<div class="module-slot">'+tile+
        '<nav class="footer-links">'+link+'</nav></div>' for tile,link in zip(tiles,links))
    body=body.replace(footer,'<div class="module-grid">'+modules+'</div>')
    body=body.replace('<div id="work">','<main id="work">',1)
    body=body.replace('</div>\n<footer id="footer">','</main>\n<footer id="footer">',1)
    return body,css,script


HTML,CSS,JS=_assets()
DASHBOARD=st.components.v2.component(
    "bestbets_responsive_full_width_v2",
    html=HTML,css=CSS,js=JS
)


def main():
    st.markdown("""<style>
[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],
[data-testid="stHeader"],[data-testid="stToolbar"],
[data-testid="stDecoration"],footer{display:none!important}
[data-testid="stAppViewContainer"],[data-testid="stMain"]{
  background:#020713!important;min-height:100vh!important;
  overflow:hidden!important
}
[data-testid="stMainBlockContainer"],.block-container{
  max-width:100%!important;width:100%!important;
  padding:0!important;margin:0!important
}
[data-testid="stMain"] [data-testid="stVerticalBlock"]{gap:0!important}
.stApp{background:#020713!important}
</style>""",unsafe_allow_html=True)

    st.session_state.setdefault("bb_v2_payload",{"player":None,"error":""})
    payload={
        "brand":_cached_brand(),
        # Even two identical responses must finish two separate searches.
        "response_id":st.session_state.get("bb_v2_response_id",""),
        "player":st.session_state["bb_v2_payload"].get("player"),
        "error":st.session_state["bb_v2_payload"].get("error","")
    }
    result=DASHBOARD(data=payload,key="bb_v2_dashboard",on_search_change=lambda:None)
    event=result.search
    if not isinstance(event,dict) or event.get("type")!="search":
        return
    event_id=str(event.get("id") or "")
    if not event_id or event_id==st.session_state.get("bb_v2_response_id"):
        return
    st.session_state["bb_v2_response_id"]=event_id
    query=str(event.get("query") or "").strip()
    if not query:
        st.session_state["bb_v2_payload"]={"player":None,"error":"Wpisz zdarzenie do wyszukania."}
    elif len(query)>280:
        st.session_state["bb_v2_payload"]={"player":None,"error":"Zapytanie jest zbyt długie."}
    else:
        try:
            st.session_state["bb_v2_payload"]={"player":_research(query),"error":""}
        except (ValueError,KeyError,RuntimeError,TypeError,IndexError) as exc:
            st.session_state["bb_v2_payload"]={"player":None,"error":str(exc)[:280]}
    st.rerun()
