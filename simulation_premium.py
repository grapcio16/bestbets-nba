"""BestBets v8.1 — dense, colorful simulation and matchup presentation.

Only real observed team history and pregame model summaries are displayed.
The model itself and its calibration are not changed by these UI helpers.
"""
from __future__ import annotations

from html import escape
from math import isfinite


def _safe(value):
    return escape(str(value),quote=True)


def _numeric(value, decimals=1, suffix=""):
    try:
        number=float(value)
        return f"{number:.{decimals}f}{suffix}" if isfinite(number) else "—"
    except (ValueError,TypeError):
        return "—"


def _team_html(code, name, logo, score, win, side):
    return (
        '<div class="bb81-team">'
        '<div class="bb81-team-label">'+("AWAY" if side=="away" else "HOME")+'</div>'
        '<div class="bb81-team-logo">'+logo+'</div>'
        '<div class="bb81-team-name">'+_safe(name)+'</div>'
        '<div class="bb81-team-short">'+_safe(code)+'</div>'
        '<div class="bb81-team-score">'+_numeric(score,1)+'</div>'
        '<div class="bb81-team-prob '+side+'">'+_numeric(win,1,"%")+
        ' <span>sim wins</span></div></div>'
    )


def game_tile_html(sim, game, names, away_logo, home_logo, date_label):
    """Compact two-club scorecard suitable for a 2-column desktop grid."""
    a,h=str(sim["away"]),str(sim["home"])
    wa=float(sim["away_win_pct"]);wh=float(sim["home_win_pct"])
    wa=max(0.,min(100.,wa));wh=max(0.,min(100.,wh))
    score=_numeric(sim.get("total_points"),1)
    confident = h if wh>=wa else a
    return (
        '<div class="bb81-game-tile">'
        '<div class="bb81-game-top"><span class="bb81-game-date">🏀 '+
        _safe(date_label)+'</span><span class="bb81-game-batch">'
        '5,000 RUNS</span></div>'
        '<div class="bb81-game-match">'
        +_team_html(a,names.get(a,a),away_logo,sim.get("away_points"),wa,"away")
        +'<div class="bb81-vs">VS</div>'
        +_team_html(h,names.get(h,h),home_logo,sim.get("home_points"),wh,"home")
        +'</div>'
        '<div class="bb81-chances"><span style="width:'+f"{wa:.1f}"+
        '%"></span><span style="width:'+f"{wh:.1f}"+
        '%"></span></div>'
        '<div class="bb81-prob-labels"><b>'+_numeric(wa,1,"%")+
        ' <small>'+_safe(a)+'</small></b><b>'+_numeric(wh,1,"%")+
        ' <small>'+_safe(h)+'</small></b></div>'
        '<div class="bb81-game-footer">'
        '<div><small>PROJECTED TOTAL</small><strong>'+score+
        '</strong></div>'
        '<div><small>MODEL LEADER</small><strong>'+
        _safe(names.get(confident,confident))+'</strong></div>'
        '</div>'
        '</div>'
    )


def matchup_hero_html(sim, game, names, away_logo, home_logo, date_label):
    """Above-the-fold, width-bounded hero; never implies a real scoreboard."""
    a,h=str(sim["away"]),str(sim["home"])
    aw=float(sim["away_win_pct"]);hw=float(sim["home_win_pct"])
    away_name=names.get(a,a);home_name=names.get(h,h)
    return (
        '<div class="bb81-matchup-hero">'
        '<div class="bb81-eyebrow">NBA GAME INTELLIGENCE'
        '<span>'+_safe(date_label)+' · 5,000 SIMULATIONS</span></div>'
        '<div class="bb81-matchup-head">'
        '<div class="bb81-matchup-team">'+away_logo+'<span>'+
        _safe(away_name)+'</span><small>AWAY · '+_safe(a)+'</small></div>'
        '<div class="bb81-matchup-score">'
        '<small>PROJECTED SCORE</small><strong>'+
        _numeric(sim["away_points"],1)+
        '<em>:</em>'+_numeric(sim["home_points"],1)+'</strong>'
        '<span>SIMULATION AVERAGES · NOT LIVE</span></div>'
        '<div class="bb81-matchup-team">'+home_logo+'<span>'+
        _safe(home_name)+'</span><small>HOME · '+_safe(h)+'</small></div>'
        '</div>'
        '<div class="bb81-matchup-probs"><div><b>'+
        _numeric(aw,1,"%")+'</b><small>'+_safe(a)+'</small></div>'
        '<div class="bb81-chances"><span style="width:'+
        f"{max(0,min(100,aw)):.1f}"+'%"></span><span style="width:'+
        f"{max(0,min(100,hw)):.1f}"+'%"></span></div>'
        '<div><b>'+_numeric(hw,1,"%")+'</b><small>'+_safe(h)+'</small></div>'
        '</div>'
        '</div>'
    )


def matchup_metrics_html(sim):
    """Small inline KPI tiles, including a clearly named simulated 80% interval."""
    tiles=[
        ("TOTAL POINTS",_numeric(sim.get("total_points"),1),
         "mean of simulation"),
        ("80% RANGE",_numeric(sim.get("total_p10"),0)+"–"+
         _numeric(sim.get("total_p90"),0),
         "simulated totals, P10–P90"),
        ("5,000", "RUNS", "per game"),
    ]
    return ('<div class="bb81-matchup-kpis">'
            +''.join(
                '<div class="bb81-inline-kpi"><small>'+_safe(k)+'</small>'
                '<b>'+_safe(v)+'</b><span>'+_safe(note)+'</span></div>'
                for k,v,note in tiles)
            +'</div>')


def compact_team_context_html(away, home, names, forms, contexts, advanced, logos):
    """Parallel side-by-side team boxes. All missing data show dashes."""
    def team_box(code,slot):
        form=forms.get(slot) or {}
        context=contexts.get(slot) or {}
        ratings=(advanced or {}).get(code) or {}
        if not context.get("available"):
            rest="—"
            b2b="brak danych"
        else:
            rest=str(context.get("rest_days","—"))
            b2b="TAK" if context.get("back_to_back") else "NIE"
        gp=form.get("games_last5") or 0
        label=names.get(code,code)
        stats=[
            ("LAST 5",f'{form.get("wins_last5",0)}/{gp}' if gp else "—"),
            ("POINTS / GAME",_numeric(form.get("scored_last5"),1)),
            ("ALLOWED / GAME",_numeric(form.get("allowed_last5"),1)),
            ("REST DAYS",_safe(rest)),
        ]
        extras=(
            '<span>BACK-TO-BACK <b>'+_safe(b2b)+'</b></span>'
            '<span>PACE <b>'+_numeric(ratings.get("pace"),1)+'</b></span>'
            '<span>OFF / DEF <b>'+_numeric(ratings.get("off"),1)+' / '+
            _numeric(ratings.get("def"),1)+'</b></span>'
        )
        return (
            '<div class="bb81-context-team">'
            '<div class="bb81-context-head">'+logos[code]+'<div><b>'+
            _safe(label)+'</b><small>'+_safe(slot.upper())+'</small></div></div>'
            '<div class="bb81-context-grid">'
            +''.join(
                '<div><small>'+_safe(k)+'</small><strong>'+
                _safe(v)+'</strong></div>' for k,v in stats
            )+'</div><div class="bb81-context-extras">'+extras+'</div></div>'
        )
    return (
        '<div class="bb81-section-label"><span>TEAM FORM & REST</span>'
        '<small>real games before tipoff</small></div>'
        '<div class="bb81-context-pair">'+team_box(away,"away")+
        team_box(home,"home")+'</div>'
    )


def injury_preview_html(report, metadata):
    """Count ESPN statuses, do not equate missing rows with full availability."""
    if report is None or report.empty:
        return (
            '<div class="bb81-health-strip"><b>🩺 Injury report</b>'
            '<span>No confirmed ESPN entries for this matchup. '
            'Roster availability has NOT been verified.</span></div>'
        )
    count=len(report)
    unavailable=bool((metadata or {}).get("stale"))
    tail=' · cache may be stale' if unavailable else ''
    return (
        '<div class="bb81-health-strip"><b>🩺 Injury report</b>'
        '<span>'+str(count)+' entries in ESPN injury data'+tail+
        ' · see player statuses below</span></div>'
    )



def player_previews_html(team_code,team_name,table):
    """Summarize up to five actual player projections. Never fabricate blanks."""
    import pandas as pd
    title=_safe(team_name)
    header=(
        '<div class="bb81-players-head"><b>'+title+'</b>'
        '<span>HISTORICAL PLAYER PROJECTIONS</span></div>'
    )
    if table is None or not isinstance(table,pd.DataFrame) or table.empty:
        return (header+'<div class="bb81-player-empty">'
                'No verified player projection available.</div>')
    required=["Zawodnik","PTS","REB","AST","3PM","Minuty"]
    if not set(required).issubset(table.columns):
        return (header+'<div class="bb81-player-empty">'
                'Player statistics unavailable in source.</div>')
    players=table.copy()
    for field in ["PTS","REB","AST","3PM","Minuty"]:
        players[field]=pd.to_numeric(players[field],errors="coerce")
    players=players.dropna(subset=["PTS"])
    if players.empty:
        return (header+'<div class="bb81-player-empty">'
                'Insufficient game logs for player projections.</div>')
    players=players.sort_values("PTS",ascending=False).head(5)
    parts=[header]
    parts.append(
        '<div class="bb81-player-row bb81-player-heading">'
        '<span>PLAYER</span><span>PTS</span><span>REB</span>'
        '<span>AST</span><span>3PM</span><span>MIN</span></div>'
    )
    for record in players.to_dict("records"):
        raw_status=str(record.get("Status ESPN") or "").strip()
        warning=raw_status.lower() not in ("","nan","none","healthy","available")
        label=str(record["Zawodnik"])
        parts.append(
            '<div class="bb81-player-row"><span><strong>'+_safe(label)+
            '</strong>'+
            ('<small class="bb81-status-warning">'+_safe(raw_status)+'</small>'
             if warning else '')+'</span>'+
            ''.join(
                '<span>'+_numeric(record.get(k),1)+'</span>'
                for k in ["PTS","REB","AST","3PM","Minuty"]
            )+'</div>'
        )
    parts.append('<div class="bb81-player-disclaimer">'
                 'Means inferred from observed games; not confirmed starters or minutes.'
                 '</div>')
    return ''.join(parts)
