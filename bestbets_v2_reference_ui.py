"""Reference-only HTML/JS decoration for Streamlit V2.

The public index.html is left unchanged. This module only transforms the
separate preview, maintaining all original input IDs and event handlers.
"""
from __future__ import annotations

from html import escape

# Inline self-contained line icons: no external icon font, iframe or dependency.
_PATHS = {
    "home": '<path d="m3 10 9-7 9 7"/><path d="M5 9v12h14V9"/><path d="M9 21v-7h6v7"/>',
    "bars": '<rect x="3" y="11" width="4" height="10" rx="1"/><rect x="10" y="6" width="4" height="15" rx="1"/><rect x="17" y="2" width="4" height="19" rx="1"/>',
    "calendar": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M3 10h18"/>',
    "layers": '<path d="m12 2-9 5 9 5 9-5-9-5Z"/><path d="m3 12 9 5 9-5M3 17l9 5 9-5"/>',
    "users": '<circle cx="9" cy="8" r="4"/><path d="M2 21v-3a7 7 0 0 1 14 0v3H2Z"/><path d="M17 4a4 4 0 0 1 0 8M17 15a6 6 0 0 1 5 6"/>',
    "shield": '<path d="m12 2 9 4v6c0 5-4 9-9 10-5-1-9-5-9-10V6l9-4Z"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M10 2h4l.7 2.6 2.1.9 2.4-1.3 2.8 2.8-1.3 2.4.9 2.1L24 12v4l-2.6.7-.9 2.1 1.3 2.4-2.8 2.8-2.4-1.3-2.1.9L14 26h-4l-.7-2.6-2.1-.9-2.4 1.3L2 21l1.3-2.4-.9-2.1L0 16v-4l2.6-.7.9-2.1L2 6.8 4.8 4l2.4 1.3 2.1-.9L10 2Z" transform="translate(3 3) scale(.75)"/>',
    "search": '<circle cx="10.7" cy="10.7" r="7.2"/><path d="m16 16 5.3 5.3"/>',
    "bell": '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21a2 2 0 0 0 4 0"/>',
    "user": '<circle cx="12" cy="7" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2Z"/>',
    "x": '<path d="M5 5 19 19M19 5 5 19"/>',
    "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1" fill="currentColor"/>',
    "plane": '<path d="m22 2-7 20-4-9-9-4 20-7Z"/><path d="M22 2 11 13"/>',
    "keyboard": '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="M6 8h1m3 0h1m3 0h1m3 0h1M6 12h1m3 0h1m3 0h1m3 0h1M7 16h10"/>',
    "basket": '<circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2v20M5 5c4 3 5 11 0 14M19 5c-4 3-5 11 0 14"/>',
}


def icon(name: str, cls: str = "") -> str:
    paths = _PATHS[name]
    # Decorative children have aria-hidden; surrounding labels are accessible.
    return (f'<svg class="{escape(cls,quote=True)}" aria-hidden="true" '
            'viewBox="0 0 24 24" width="24" height="24" fill="none" '
            'stroke="currentColor" stroke-width="1.9" '
            'stroke-linecap="round" stroke-linejoin="round">'
            f'{paths}</svg>')


def enhance_reference_body(body: str) -> str:
    original_brand = ('<div class="brand"><img id="brand-img" alt="" src="">'
                      '<div class="wordmark">BEST<b>BETS</b></div></div>')
    assert original_brand in body, "Reference brand markup changed unexpectedly"
    brand = ('<div class="brand"><img id="brand-img" alt="" src="">'
             '<div class="brand-lockup"><div class="wordmark">BEST<b>BETS</b></div>'
             '<div class="brand-kicker">NBA ANALYTICS</div></div></div>')
    body = body.replace(original_brand, brand, 1)

    # Replace ambiguous unicode symbols with consistent vector pictograms.
    for char, name in [('⌂','home'),('▥','bars'),('▣','calendar'),
                       ('◈','layers'),('♧','users'),('⬡','shield'),
                       ('⚙','settings')]:
        original=f'<span class="ic">{char}</span>'
        assert original in body, f"Missing sidebar {name}"
        body=body.replace(original,f'<span class="ic">{icon(name)}</span>',1)

    old_search = ('<form class="topsearch" id="search-form"><span class="glass">⌕</span>'
                  '<input id="query" autocomplete="off" placeholder="Jayson Tatum over 25.5 points" '
                  'aria-label="Wyszukaj zawodnika, linię i rynek"><button id="search-btn" type="submit">⌕</button></form>')
    assert old_search in body, "Search markup changed unexpectedly"
    new_search = (
        '<form class="topsearch" id="search-form">'
        f'<span class="glass">{icon("search")}</span>'
        '<input id="query" autocomplete="off" placeholder="Jayson Tatum over 25.5 points" '
        'aria-label="Wyszukaj zawodnika, linię i rynek">'
        f'<button class="clear-query" type="button" id="clear-query" aria-label="Wyczyść wyszukiwanie">{icon("x")}</button>'
        f'<button id="search-btn" type="submit" aria-label="Wyszukaj">{icon("search")}</button></form>'
    )
    body=body.replace(old_search,new_search,1)
    old_utility='<div class="utility"><span title="Powiadomienia">♧<i class="dot"></i></span><span title="Profil">♙</span></div>'
    assert old_utility in body
    body=body.replace(old_utility,
        f'<div class="utility"><span title="Powiadomienia">{icon("bell")}<i class="dot"></i></span>'
        f'<span title="Profil">{icon("user")}</span></div>',1)
    body=body.replace('<span class="searchsymbol">⌕</span>',
                      f'<span class="searchsymbol">{icon("search")}</span>')
    body=body.replace('<span class="orange-bars">▥</span>',
                      f'<span class="orange-bars">{icon("bars")}</span>',1)
    body=body.replace('<span class="target-icon">◎</span>',
                      f'<span class="target-icon">{icon("target")}</span>',1)
    body=body.replace('<span class="shield">⬡</span>',
                      f'<span class="shield">{icon("shield")}</span>',1)
    body=body.replace('<small>⌂ Home</small>',
                      f'<small>{icon("home")} Home AVG</small>')
    body=body.replace('<small>➤ Away</small>',
                      f'<small>{icon("plane")} Away AVG</small>')

    # Live recap card: show data of the selected player instead of fabricating
    # a "Top Tip of the Day" value. Styling still matches the visual reference.
    existing='<span>🏀</span><span>Centrum NBA<small>Otwórz podsumowanie</small></span>'
    replacement=(
        f'<span class="home-player-mark">{icon("basket")}</span>'
        '<img class="mini-avatar" id="home-player-avatar" alt="" hidden>'
        '<span class="home-player-copy"><span id="home-selected-name">Centrum NBA</span>'
        '<small id="home-selected-meta">Otwórz podsumowanie</small></span>'
    )
    assert existing in body
    body=body.replace(existing,replacement,1)
    # Use existing locally bundled/cached team badges from BestBets, not
    # hotlinked ESPN images (browser certificate failures) or fake emblems.
    from team_logos import logo_data_uri
    for code,label in [('BOS','Boston Celtics'),('NYK','New York Knicks'),('PHI','Philadelphia 76ers')]:
        old=f'<span class="mini-ball">◉</span><span class="mini-name">{label}</span>'
        src=logo_data_uri(code)
        badge=(f'<img src="{src}" alt="" loading="lazy">' if src
               else f'<span>{code[:1]}</span>')
        updated=(f'<span class="mini-ball team-mark team-{code}">{badge}</span>'
                 f'<span class="mini-name">{label}</span>')
        assert old in body
        body=body.replace(old,updated,1)
    # Distinguish functional example icons in games, players and footer nav.
    body=body.replace('<span class="mini-ball">♙</span>',
                      f'<span class="mini-ball">{icon("user")}</span>')
    body=body.replace('<span class="mini-ball">◉</span>',
                      f'<span class="mini-ball">{icon("basket")}</span>')
    # No modification of data-page, data-market, id or search IDs.
    assert all(f'id="{name}"' in body for name in
               ('query','search-btn','stage','hero','chart-svg','take','footer'))
    return body


def enhance_reference_script(script: str) -> str:
    # Correct hit/miss colors for UNDER too (the original colors assumed OVER).
    old='const color=over?"#00ec79":under?"#ff514b":"#ffac41";'
    new=('const color=state.side==="UNDER"'
         '?(under?"#00ec79":over?"#ff514b":"#ffac41")'
         ':(over?"#00ec79":under?"#ff514b":"#ffac41");')
    assert old in script, "Chart color hook missing"
    script=script.replace(old,new,1)

    # A fixed screenshot can show 10 games at any time; the real product must
    # still respect L5/L10/Season and actual stats.
    old_update='  render();\n}\nfunction watchChart(){'
    assert old_update in script, "V2 update hook missing"
    new_update='''  render();
  const selected=$("home-selected-name"),meta=$("home-selected-meta"),
        avatar=$("home-player-avatar"),mark=parentElement.querySelector(".home-player-mark");
  if(selected && meta) {
    selected.textContent=p?p.name:"Centrum NBA";
    meta.textContent=p
      ?("Wybrany zawodnik · "+(p.team||"NBA"))
      :"Otwórz podsumowanie";
  }
  if(avatar && mark) {
    if(p&&p.photo) {
      setImage("home-player-avatar",p.photo,p.name);
      mark.style.display=avatar.hidden?"inline-flex":"none";
    } else {
      avatar.hidden=true;avatar.removeAttribute("src");
      mark.style.display="inline-flex";
    }
  }
}
function watchChart(){'''
    script=script.replace(old_update,new_update,1)

    old_init='parentElement.__bestbetsV2={root,update,watchChart};'
    assert old_init in script, "V2 init hook missing"
    script=script.replace(old_init,'''const clearButton=$("clear-query");
if(clearButton) clearButton.addEventListener("click",function(){
  const field=$("query");
  if(field){field.value="";state.query="";field.focus();}
});
parentElement.__bestbetsV2={root,update,watchChart};''',1)
    return script
