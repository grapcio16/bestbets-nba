"""Presentation-only components for the administration dashboard."""
from html import escape

CSS = """
<style>
.stApp {background:radial-gradient(ellipse at 90% 0%,#202849 0%,#111b30 35%,#0c1220 72%);color:#edf2fa;}
[data-testid="stHeader"]{background:#0c1220;}
[data-testid="stMainBlockContainer"]{width:100%;max-width:1640px;padding:3.9rem 2.2rem 2.5rem;}
[data-testid="stSidebar"]{background:#111a2b;border-right:1px solid #273448;}
[data-testid="stSidebar"] [data-testid="stSidebarContent"]{padding:.6rem .45rem;}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"]{gap:.35rem;}
.hz-admin-brand{display:flex;align-items:center;gap:12px;padding:10px 4px 19px;border-bottom:1px solid #29354a;margin-bottom:8px}
.hz-admin-mark{display:grid;place-items:center;width:42px;height:42px;flex:none;border-radius:11px;background:linear-gradient(145deg,#416dd1,#7457c7);color:#fff;font-size:17px;font-weight:800;letter-spacing:-1px}
.hz-admin-name{font-size:18px;font-weight:750;color:#f2f5ff;letter-spacing:.025em;line-height:1.25}
.hz-admin-role{font-size:13px;color:#9fb0c7;line-height:1.4}
[data-testid="stSidebar"] [data-testid="stButton"] button{width:100%;min-height:44px;justify-content:flex-start;padding:8px 13px;border-radius:8px;box-shadow:none;}
[data-testid="stSidebar"] [data-testid="stButton"] button p{font-size:16px!important;font-weight:600!important;}
[data-testid="stSidebar"] [data-testid="stButton"] button[kind="secondary"]{color:#b9c7db;background:transparent;border:1px solid transparent;}
[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"]{color:#f0f4ff;background:linear-gradient(100deg,#3d3569,#253952);border:1px solid #6c60ad;box-shadow:inset 3px 0 #ae96ff;}
[data-testid="stSidebar"] [data-testid="stButton"] button:hover{background:#25334a;border-color:#52678b;color:white;}
[data-testid="stMainBlockContainer"] h1{font-size:34px!important;line-height:1.15;letter-spacing:-.025em;color:#f1f5ff;margin:0 0 .4rem;}
[data-testid="stMainBlockContainer"] h2,[data-testid="stMainBlockContainer"] h3{font-size:21px!important;line-height:1.25;font-weight:650;color:#edf2fa;margin:.1rem 0;}
[data-testid="stMainBlockContainer"] [data-testid="stMarkdownContainer"] p{color:#b9c7da;font-size:15px;line-height:1.5}
.hz-kpi-grid{display:grid;grid-template-columns:repeat(var(--hz-cols,3),minmax(0,1fr));gap:14px;margin:0 0 4px}
.hz-kpi{box-sizing:border-box;min-width:0;min-height:104px;display:flex;flex-direction:column;justify-content:space-between;gap:12px;padding:17px 18px;background:#151f30;border:1px solid #2a394e;border-radius:11px;}
.hz-kpi-label{font-size:15px!important;font-weight:550!important;color:#b8c5d8!important;line-height:1.35;overflow-wrap:anywhere}
.hz-kpi-value{font-size:32px!important;font-weight:750!important;font-variant-numeric:tabular-nums;letter-spacing:-.035em;line-height:1.14;color:#f0f4fc!important;overflow-wrap:anywhere}
.hz-kpi.is-empty .hz-kpi-value{font-size:26px!important;color:#8fa1bb!important;}
.hz-kpi-state{font-size:13px!important;color:#9eabc0!important;line-height:1.2;}
.hz-health{display:flex;align-items:center;gap:9px;padding:12px 15px;background:#151f30;border:1px solid #2a394e;border-radius:9px;color:#e6edf8;font-size:15px;line-height:1.4}
.hz-dot{width:9px;height:9px;flex:none;border-radius:50%;background:#e5b46c;}
.hz-health.is-ok .hz-dot{background:#5cc49c;}
.hz-health.is-bad .hz-dot{background:#ed8594;}
.hz-health strong{color:#ecf1fa;}
[data-testid="stDataFrame"],[data-testid="stExpander"],[data-testid="stForm"],[data-testid="stVegaLiteChart"]{border:1px solid #2a394e;border-radius:10px;overflow:hidden;background:#151f30}
[data-testid="stAlert"]{border-radius:9px;border:1px solid #35465d;}
[data-testid="stMainBlockContainer"] [data-testid="stButton"] button,[data-testid="stFormSubmitButton"] button{min-height:42px;border:1px solid #536989;border-radius:8px;background:#283957;color:#edf3ff;font-weight:600;}
[data-testid="stMainBlockContainer"] hr{border-color:#29364a;margin:.9rem 0;}
@media(max-width:1150px){.hz-kpi-grid{grid-template-columns:repeat(2,minmax(0,1fr));}[data-testid="stMainBlockContainer"]{padding:3.6rem 1.4rem 2rem;}}
@media(max-width:650px){.hz-kpi-grid{grid-template-columns:1fr;gap:9px;}.hz-kpi{min-height:88px;padding:14px;}.hz-kpi-value{font-size:27px!important;}[data-testid="stMainBlockContainer"]{padding:3.6rem 1rem 2rem;}}
.hz-kpi{--hz-accent:#94a9e7;--hz-icon-bg:#293957;position:relative;border-top:2px solid var(--hz-accent);background:linear-gradient(145deg,#1b2940,#151e30);box-shadow:0 5px 15px #0002;}
.hz-kpi.tone-users{--hz-accent:#8daaff;--hz-icon-bg:#293e68;}
.hz-kpi.tone-activity{--hz-accent:#52cfc0;--hz-icon-bg:#1e4248;}
.hz-kpi.tone-finance{--hz-accent:#e7bf75;--hz-icon-bg:#473d31;}
.hz-kpi.tone-engine{--hz-accent:#b5a0f7;--hz-icon-bg:#3d335b;}
.hz-kpi.tone-alert{--hz-accent:#efab89;--hz-icon-bg:#49362f;}
.hz-kpi-label{max-width:calc(100% - 36px);}
.hz-kpi.is-empty .hz-kpi-value{color:var(--hz-accent)!important;}
.hz-kpi-icon{position:absolute;top:12px;right:12px;display:grid;place-items:center;width:30px;height:30px;border-radius:8px;color:var(--hz-accent);background:var(--hz-icon-bg);}
.hz-kpi-icon svg{width:17px;height:17px;display:block;}
.hz-health{background:linear-gradient(90deg,#1c293c,#151f30);}
[data-testid="stSidebar"] [data-testid="stButton"] button:focus-visible{outline:2px solid #b5a0f7;outline-offset:2px;}
</style>
"""

BRAND = """<div class="hz-admin-brand"><div class="hz-admin-mark" aria-hidden="true">HZ</div><div><div class="hz-admin-name">HOOPZARO</div><div class="hz-admin-role">Panel administratora</div></div></div>"""

# Static icons and semantic accents are presentation only.
ICONS = {
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.9M16 3.2a4 4 0 0 1 0 7.6"/>',
    "activity": '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
    "finance": '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="M3 10h18m-14 5h3"/>',
    "engine": '<rect x="6" y="6" width="12" height="12" rx="2"/><rect x="9" y="9" width="6" height="6" rx="1"/><path d="M9 3v3m6-3v3M9 18v3m6-3v3M3 9h3m-3 6h3m12-6h3m-3 6h3"/>',
    "alert": '<path d="m12 3 10 18H2L12 3Z"/><path d="M12 9v4m0 4h.01"/>',
    "default": '<path d="M3 3v18h18M7 16v-4m5 4V7m5 9v-7"/>',
}

def metric_tone(label):
    word = str(label).casefold()
    if any(x in word for x in ("przych", "subskryb", "rentown", "operacyj", "płatn")):
        return "finance"
    if any(x in word for x in ("odrzucon", "powielon")):
        return "alert"
    if any(x in word for x in ("aktywn", "analizy", "połączen", "zapytan", "łącznie")):
        return "activity"
    if any(x in word for x in ("konta", "admin", "użytkown")):
        return "users"
    if any(x in word for x in ("mecze", "trening", "prognoz", "mae")):
        return "engine"
    return "default"

def metric_markup(label, value, help=None):
    """Escape every dynamic field before inserting presentation markup."""
    tone = metric_tone(label)
    icon = f'<span class="hz-kpi-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{ICONS[tone]}</svg></span>'
    label = escape(str(label), quote=True)
    text = str(value) if value is not None else "Brak danych"
    missing = text in ("Brak danych", "Nie podłączono", "Niedostępne")
    title = f' title="{escape(str(help), quote=True)}"' if help else ""
    display = "—" if missing else escape(text)
    state = f'<div class="hz-kpi-state">{escape(text)}</div>' if missing else ""
    kind = " is-empty" if missing else ""
    return (f'<div class="hz-kpi tone-{tone}{kind}"{title}>{icon}<div class="hz-kpi-label">{label}</div>'
            f'<div><div class="hz-kpi-value">{display}</div>{state}</div></div>')

def grid_markup(items, columns=3):
    cols = max(1, min(4, int(columns)))
    return f'<div class="hz-kpi-grid" style="--hz-cols:{cols}">' + "".join(
        metric_markup(*item) for item in items) + "</div>"

def health_markup(label, status, kind="warn"):
    kind = kind if kind in ("ok","bad") else "warn"
    return (f'<div class="hz-health is-{kind}"><span class="hz-dot" aria-hidden="true"></span>'
            f'<strong>{escape(str(label))}</strong><span>{escape(str(status))}</span></div>')
