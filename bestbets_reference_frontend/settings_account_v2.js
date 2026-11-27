/* Settings v2: presentation only. Auth and consent remain server-owned. */
(function(){
"use strict";
const $=id=>document.getElementById(id);
const titles={profile:"Profil konta",plan:"Plan i dostęp",preferences:"Preferencje aplikacji",notifications:"Powiadomienia",privacy:"Prywatność i zgody",security:"Bezpieczeństwo",support:"Pomoc i wsparcie"};
let current="",identity="",returnFocus=null,callbacks={};
function txt(id,value){$(id).textContent=value;}
function close(){if($("hza-dialog").open)$("hza-dialog").close();}
function open(key,trigger){
 if(!Object.hasOwn(titles,key)||$("hz-account").hidden)return;
 const dialog=$("hza-dialog");
 if(!dialog.open){returnFocus=trigger;dialog.showModal();}
 current=key;txt("hza-title",titles[key]);
 dialog.querySelectorAll("[data-hza-panel]").forEach(p=>p.hidden=p.dataset.hzaPanel!==key);
 dialog.querySelectorAll("[data-hza-open]").forEach(b=>{if(b.dataset.hzaOpen===key)b.setAttribute("aria-current","page");else b.removeAttribute("aria-current");});
 $("hza-close").focus();
}
function render(visible,payload){
 const auth=payload?.auth||{},role=["admin","premium","free"].includes(auth.role)&&auth.logged_in===true?auth.role:"guest";
 const logged=role!=="guest",premium=role==="premium"||role==="admin";
 const next=String(auth.session_epoch??"")+":"+role+":"+String(auth.name??"");
 if(!visible||identity!==next)close();
 identity=next;
 const name=logged?String(auth.name||"Użytkownik"):"Gość";
 const initials=logged?name.trim().split(/\s+/).slice(0,2).map(w=>Array.from(w)[0]||"").join("").toUpperCase():"HZ";
 const label=role==="admin"?"ADMINISTRATOR · PREMIUM":premium?"PREMIUM":logged?"FREE":"GOŚĆ";
 txt("hza-avatar",initials||"HZ");txt("hza-profile-avatar",initials||"HZ");
 $("hz-account").dataset.role=role;txt("hza-modules",premium?"Aktywne":logged?"Free":"Publiczne");
 txt("hza-plan",premium?"Premium":logged?"Free":"Gość");
 txt("hza-access",role==="admin"?"Administrator":premium?"Pełny":"Podstawowy");
 txt("hza-profile-name",name);txt("hza-profile-email",logged?String(auth.email||"Brak zweryfikowanego adresu"):"—");txt("hza-profile-role",label);txt("hza-current-plan",label);
 txt("hza-plan-explanation",role==="admin"?"Bezpłatny dostęp administracyjny; nie wymaga subskrypcji.":premium?"Dostęp Premium potwierdzony przez serwer.":logged?"Konto podstawowe.":"Zaloguj się, aby sprawdzić uprawnienia.");
 txt("hza-summary-profile",name);txt("hza-summary-plan",premium?"Premium":logged?"Free":"Gość");
 txt("hza-preview-email",logged?String(auth.email||"Brak zweryfikowanego adresu"):"Zaloguj się do konta");txt("hza-preview-access",premium?"Pełny":logged?"Podstawowy":"Publiczny");
 txt("hza-summary-preferences","Polski · Dark");txt("hza-summary-notifications","W przygotowaniu");
 txt("hza-summary-privacy",payload?.usage_consent_available?(payload.usage_consent_granted?"Włączona":"Wyłączona"):"Informacje o danych");
 txt("hza-summary-security",logged?"Logowanie aktywne":"Nie zalogowano");txt("hza-summary-support","FAQ · kontakt");
 // Google links only when server explicitly identifies a verified Google issuer.
 const google=logged&&auth.provider==="google";
 $("hza-google-profile").hidden=!google;$("hza-google-security").hidden=!google;
 txt("hza-security-provider",google?"Google":logged?"Dostawca tożsamości":"Brak aktywnej sesji");txt("hza-preview-provider",google?"Konto Google":logged?"Konto Hoopzaro":"Gość");
 $("hza-privacy-unavailable").hidden=payload?.usage_consent_available===true;
 document.querySelectorAll("[data-hza-auth]").forEach(b=>b.hidden=!(auth.configured===true&&(b.dataset.hzaAuth==="login"?!logged:logged)));
}
function init(cb){
 callbacks=cb||{};
 document.addEventListener("click",e=>{
  const trigger=e.target.closest("[data-hza-open]");
  if(trigger){open(trigger.dataset.hzaOpen,trigger);return;}
  const auth=e.target.closest("[data-hza-auth]");
  if(auth&&!auth.hidden){close();callbacks.auth?.("auth_"+auth.dataset.hzaAuth);}
 });
 $("hza-close").addEventListener("click",close);$("hza-done").addEventListener("click",close);
 $("hza-dialog").addEventListener("click",e=>{if(e.target===$("hza-dialog")){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)close();}});
 $("hza-dialog").addEventListener("close",()=>{current="";if(returnFocus?.isConnected&&!$("hz-account").hidden)returnFocus.focus();returnFocus=null;});
}
window.HoopzaroAccount={init,render};
})();
