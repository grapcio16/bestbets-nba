"""Experimental iframe-free BestBets canvas (Streamlit Components V2).

This is a separate preview entrypoint. It deliberately does NOT change
app.py or the production Streamlit v1 component.

The approved 1231×691 reference is fitted by an SVG viewBox before the
first paint. No JavaScript height negotiations, iframe resize feedback,
entry fade, or zoom animation. The production NBA research is reused.
"""
from __future__ import annotations

from pathlib import Path
import streamlit as st

from bestbets_custom_screen import _cached_brand, _research

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/"bestbets_reference_frontend"/"index.html"


def _assets():
    raw=SOURCE.read_text(encoding="utf-8")
    css=raw.split("<style>",1)[1].split("</style>",1)[0]
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
        '  mounted.update(data,setTriggerValue);return;\n'
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
    script=script[:start]+'''function resize(){
  // The SVG viewBox handles scaling natively on first paint.
  // Keeping this function makes upstream render() reusable.
}
'''+script[finish:]
    script=script.replace('window.addEventListener("resize",resize);','')
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
// V2 reruns JS when data changes but retains its DOM. Bind listeners once.
parentElement.__bestbetsV2={root,update};
update(data,setTriggerValue);
}'''
    # The v1 document's root rules must target the V2 shadow host. Without
    # this, Streamlit's font, line height and text color leak into the canvas.
    css=css.replace(":root{", ":host{")
    css=css.replace("html,body{", ":host{")
    css += """
:host{
  /* Streamlit's parent padding can settle AFTER the component mounts.
     This dedicated fullscreen entrypoint must fit the viewport immediately. */
  position:fixed;inset:0;z-index:1000;
  display:block;width:100%;height:100dvh;overflow:hidden;
  /* Full-bleed background extends the approved dashboard atmosphere
     beyond its 1231:691 aspect-ratio frame without cropping or distortion.
     It also appears before component JavaScript is initialized. */
  background:
    radial-gradient(ellipse 72% 90% at 50% 8%,rgba(0,105,180,.16),transparent 72%),
    radial-gradient(ellipse 25% 70% at 0% 55%,rgba(0,155,220,.075),transparent 80%),
    radial-gradient(ellipse 25% 70% at 100% 52%,rgba(0,155,220,.065),transparent 80%),
    linear-gradient(90deg,#061426 0%,#061426 30%,#020713 69%,#061426 100%);
  line-height:normal;text-align:left;letter-spacing:normal;
  font-weight:400;font-style:normal
}
#bb-v2-viewport{
  display:block;width:min(100vw,calc((100dvh - 4px) * 1231 / 691));
  height:auto;aspect-ratio:1231 / 691;margin:0 auto;
  overflow:hidden;background:#020713;color:var(--white)
}
#app-shell{margin:0;width:1231px;height:691px}
#stage{transform:none!important}
"""
    html=('''<svg xmlns="http://www.w3.org/2000/svg"
       id="bb-v2-viewport" viewBox="0 0 1231 691"
       preserveAspectRatio="xMidYMin meet"
       aria-label="BestBets NBA Intelligence">
       <foreignObject x="0" y="0" width="1231" height="691">'''
       +body+'''</foreignObject></svg>''')
    return html,css,script


HTML,CSS,JS=_assets()
CANVAS=st.components.v2.component(
    "bestbets_reference_without_iframe_v2",
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
    result=CANVAS(data=payload,key="bb_v2_canvas",on_search_change=lambda:None)
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
