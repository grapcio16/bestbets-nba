"""Compact BestBets NBA matchup presentation, backed by existing simulation outputs.

Pure markup helpers have no Streamlit side effects. Context panels use only
verified completed games and actual ESPN entries. Never imply injuries,
home/away splits or rest are applied to the underlying 5,000-draw model.
"""
from __future__ import annotations

from html import escape
import math

import pandas as pd
import streamlit as st

from teams import TEAM_FULL
from match_context import matchup_schedule_context
from simulation_data_audit import matchup_audit, venue_research_candidate
from availability_context import matchup_injuries


def _safe_float(value):
    try:
        number=float(value)
        if math.isfinite(number):
            return number
    except (TypeError, ValueError):
        pass
    return None


def show_number(value,precision=1,suffix=""):
    number=_safe_float(value)
    return f"{number:.{precision}f}{suffix}" if number is not None else "—"


def _pct(value):
    number=_safe_float(value)
    return min(100.,max(0.,number)) if number is not None else 0.


def matchup_card_html(sim,date_text,logos,names):
    """Complete compact match card; no reliance on former app.py CSS rules."""
    away,home=sim["away"],sim["home"]
    pct_a=_pct(sim.get("away_win_pct"))
    pct_h=_pct(sim.get("home_win_pct"))
    if pct_a+pct_h:
        total=pct_a+pct_h
        pct_a=pct_a/total*100
        pct_h=100-pct_a
    away_name=escape(str(names.get(away,away)))
    home_name=escape(str(names.get(home,home)))
    favorite=escape(str(names.get(sim.get("winner"),sim.get("winner","—"))))
    logo_a=logos(away);logo_h=logos(home)
    return f"""
    <div class="bbm-sim-game">
      <div class="bbm-sim-game-top">
        <span><span class="bbm-live-dot"></span>{escape(str(date_text))}</span>
        <span class="bbm-sim-source">5,000 SIMULATIONS · PRE-GAME MODEL</span>
      </div>
      <div class="bbm-sim-game-grid">
        <div class="bbm-sim-matchup">
          <div class="bbm-sim-team">
            {logo_a}
            <div><div class="bbm-sim-abbr">{escape(str(away))} · AWAY</div>
            <strong>{away_name}</strong></div>
            <b class="bbm-sim-score bbm-orange">{show_number(sim.get('away_points'))}</b>
          </div>
          <div class="bbm-sim-versus">VS</div>
          <div class="bbm-sim-team">
            {logo_h}
            <div><div class="bbm-sim-abbr">{escape(str(home))} · HOME</div>
            <strong>{home_name}</strong></div>
            <b class="bbm-sim-score bbm-green">{show_number(sim.get('home_points'))}</b>
          </div>
        </div>
        <div class="bbm-sim-summary">
          <div class="bbm-sim-small">PROJECTED TOTAL</div>
          <div class="bbm-sim-total">{show_number(sim.get('total_points'))}</div>
          <div class="bbm-sim-small">Model favors <b>{favorite}</b></div>
        </div>
      </div>
      <div class="bbm-sim-winbar" role="img" aria-label="Away {pct_a:.1f} percent; home {pct_h:.1f} percent">
        <div style="width:{pct_a:.2f}%"></div>
        <div style="width:{pct_h:.2f}%"></div>
      </div>
      <div class="bbm-sim-winlabels">
        <span class="bbm-orange">{escape(str(away))} · {pct_a:.1f}%</span>
        <span class="bbm-green">{escape(str(home))} · {pct_h:.1f}%</span>
      </div>
    </div>
    """


def detail_hero_html(sim,logos,names):
    away,home=sim["away"],sim["home"]
    a,h=escape(str(names.get(away,away))),escape(str(names.get(home,home)))
    away_win=_pct(sim.get("away_win_pct"))
    home_win=_pct(sim.get("home_win_pct"))
    return f"""
    <div class="bbm-sim-detail-hero">
      <div class="bbm-sim-detail-kicker">MATCHUP INTELLIGENCE · 5,000 MONTE CARLO RUNS</div>
      <div class="bbm-sim-detail-match">
        <div class="bbm-sim-detail-side">{logos(away)}
          <div><span class="bbm-sim-detail-code">{escape(str(away))} · AWAY</span>
          <strong>{a}</strong><em class="bbm-orange">{away_win:.1f}% win share</em></div>
        </div>
        <div class="bbm-sim-detail-middle">
          <div class="bbm-sim-projected">{show_number(sim.get('away_points'))}<span>:</span>{show_number(sim.get('home_points'))}</div>
          <small>PROJECTED SCORE</small>
        </div>
        <div class="bbm-sim-detail-side right">{logos(home)}
          <div><span class="bbm-sim-detail-code">{escape(str(home))} · HOME</span>
          <strong>{h}</strong><em class="bbm-green">{home_win:.1f}% win share</em></div>
        </div>
      </div>
    </div>
    """


def _team_form(hist,team,asof):
    """Local import avoids a circular module import when used by simulation_view."""
    from simulation_view import team_form_diagnostics
    return team_form_diagnostics(hist,team,asof=asof)


def render_matchup_overview(sim,g,hist,advanced,injury_table,injury_meta,logo_html):
    away,home=sim["away"],sim["home"]
    names=TEAM_FULL
    from simulation_engine import advanced_ratings
    ratings=advanced_ratings(advanced)
    contexts=matchup_schedule_context(hist,g)
    forms={t:_team_form(hist,t,g.get("start_utc")) for t in (away,home)}

    st.markdown(
        '<div class="bbm-sim-section-title">TEAM FORM & MATCHUP '
        '<span>verified past results · descriptive only</span></div>',
        unsafe_allow_html=True)
    left,right=st.columns(2,gap="small")
    for col,team,css in ((left,away,"away"),(right,home,"home")):
        form=forms[team]
        ctx=contexts.get(css) or {}
        metric=f'{form["wins_last5"]}/{form["games_last5"]}' if form else "—"
        scored=show_number(form.get("scored_last5") if form else None)
        allowed=show_number(form.get("allowed_last5") if form else None)
        rest=str(ctx.get("rest_days"))+" days" if ctx.get("available") and ctx.get("rest_days") is not None else "—"
        with col:
            st.markdown(f"""
            <div class="bbm-sim-form-card {css}">
              <div class="bbm-sim-form-heading">
                {logo_html(team)}<div><small>{escape(team)} · {escape(css.upper())}</small>
                <strong>{escape(str(names.get(team,team)))}</strong></div>
              </div>
              <div class="bbm-sim-form-grid">
                <div><small>L5 WINS</small><b>{metric}</b></div>
                <div><small>L5 POINTS</small><b>{scored}</b></div>
                <div><small>L5 ALLOWED</small><b>{allowed}</b></div>
                <div><small>REST</small><b>{escape(rest)}</b></div>
              </div>
            </div>
            """,unsafe_allow_html=True)
    st.caption("Forma oraz odpoczynek są dodatkowymi informacjami. "
               "Na obecnym etapie nie korygują automatycznie 5000 symulacji.")

    st.markdown(
        '<div class="bbm-sim-section-title">MODEL CONTEXT '
        '<span>sample and defensive ratings</span></div>',
        unsafe_allow_html=True)
    m1,m2,m3=st.columns(3)
    m1.metric("TOTAL · średnia",show_number(sim.get("total_points"),1," pkt"))
    if "total_p10" in sim and "total_p90" in sim:
        m2.metric("80% symulacji",f'{show_number(sim.get("total_p10"),0)}–{show_number(sim.get("total_p90"),0)}')
    else:
        m2.metric("80% symulacji","—")
    m3.metric("Źródło", "NBA Advanced" if any(x in ratings for x in (away,home)) else "ESPN")
    with st.expander("Defensive / pace ratings",expanded=False):
        s1,s2=st.columns(2)
        for col,team in ((s1,away),(s2,home)):
            with col:
                st.markdown("**"+names.get(team,team)+"**")
                data=ratings.get(team)
                if data:
                    st.markdown(
                        f"PACE **{show_number(data.get('pace'))}** · "
                        f"OFF **{show_number(data.get('off'))}** · "
                        f"DEF **{show_number(data.get('def'))}**")
                else:
                    st.caption("NBA Advanced niedostępne; "
                               "nie estymujemy PACE i ratings z punktów.")

    report,metadata=matchup_injuries(injury_table,home,away,injury_meta)
    if not report.empty:
        st.markdown(
            '<div class="bbm-sim-section-title">INJURY WATCH '
            '<span>ESPN reports, not confirmed starting lineups</span></div>',
            unsafe_allow_html=True)
        shown=report.head(4)
        columns=st.columns(min(2,len(shown)))
        for i,(_,person) in enumerate(shown.iterrows()):
            name=escape(str(person.get("Zawodnik") or ""))
            team=escape(str(person.get("Drużyna") or ""))
            status=escape(str(person.get("Status ESPN") or "Unconfirmed"))
            with columns[i%len(columns)]:
                st.markdown(
                    f'<div class="bbm-sim-injury"><b>{name}</b>'
                    f'<span>{team} · {status}</span></div>',
                    unsafe_allow_html=True)
        if len(report)>4:
            st.caption(f"+{len(report)-4} kolejnych wpisów w zakładce Kontuzje.")
    if metadata.get("stale"):
        st.caption("Uwaga: raport ESPN może być nieaktualny.")
    st.markdown(
        '<div class="bbm-sim-take"><strong>✦ BESTBETS TAKE</strong>'
        '<span>Porównanie wynika z 5 000 przebiegów modelu, '
        'nie z potwierdzonego prawdopodobieństwa wygranej. '
        'Przed oceną zdarzenia sprawdź jakość danych, urazy i aktualne linie.</span></div>',
        unsafe_allow_html=True)


def render_injuries(injury_table,injury_meta,away,home):
    report,meta=matchup_injuries(injury_table,home,away,injury_meta)
    st.markdown("#### Injury watch")
    st.caption("Źródło: ESPN (nieoficjalne). Brak wpisu nie dowodzi "
               "dostępności zawodnika, status wymaga weryfikacji.")
    if report.empty:
        st.info("Brak potwierdzonych informacji o absencjach obu drużyn.")
    else:
        for team in (away,home):
            subset=report[report["Drużyna"]==team] if "Drużyna" in report else pd.DataFrame()
            if subset.empty:
                st.caption(f"{team}: brak wpisów w bieżącej odpowiedzi.")
                continue
            st.markdown("**"+escape(str(TEAM_FULL.get(team,team)))+"**")
            for _,record in subset.head(12).iterrows():
                name=escape(str(record.get("Zawodnik") or "—"))
                status=escape(str(record.get("Status ESPN") or "—"))
                info=escape(str(record.get("Informacja") or ""))
                st.markdown(
                    f'<div class="bbm-sim-injury"><b>{name}</b>'
                    f'<span>{status}{" · "+info if info else ""}</span></div>',
                    unsafe_allow_html=True)
    if meta.get("stale"):st.warning("Raport ESPN pochodzi z nieaktualnej kopii.")
    if meta.get("warning"):st.caption(str(meta["warning"]))


def render_model_audit(sim,g,hist,advanced):
    from simulation_view import team_scoring_history
    st.markdown("#### Data quality & research")
    st.caption("Liczby historyczne pochodzą wyłącznie z zakończonych meczów "
               "przed terminem spotkania. Nie są automatycznymi korektami modelu.")
    checks=sim.get("quality_check") or {}
    if checks.get("alerts"):
        for text in checks["alerts"][:5]:st.warning(str(text))
    away,home=sim["away"],sim["home"]
    a,h=st.columns(2)
    for col,team in ((a,away),(h,home)):
        hist_data=team_scoring_history(hist,team)
        with col:
            st.markdown("**"+escape(str(TEAM_FULL.get(team,team)))+"**")
            st.metric("Historyczne PTS · ostatnie 10",
                      show_number(hist_data.get("mean") if hist_data else None,1))
            st.caption(str(hist_data.get("games") if hist_data else 0)+" rozegranych meczów")
    with st.expander("Audyt próby 5/10/20, home/away, tempo",expanded=False):
        rows,flags=matchup_audit(hist,g,advanced)
        st.dataframe(rows,hide_index=True,use_container_width=True)
        for text in flags[:5]:st.caption("⚠ "+str(text))
        candidate=venue_research_candidate(hist,g)
        if candidate:
            st.caption(
                "Hipoteza badawcza dom/wyjazd (nie wpływa na model): "
                f"{candidate['away']:.1f} : {candidate['home']:.1f}.")
        else:
            st.caption("Brak wystarczających danych do osobnej hipotezy home/away.")
    if checks.get("alternate_available"):
        st.markdown("#### Wrażliwość na wariant modelu")
        a,b,c=st.columns(3)
        a.metric("Inny model · away",show_number(checks.get("alternate_away")))
        b.metric("Inny model · home",show_number(checks.get("alternate_home")))
        c.metric("Różnica handicapów",show_number(checks.get("margin_disagreement"),1," pkt"))
    st.caption("Źródło modelu: "+str(sim.get("source") or "nieokreślone"))
    st.caption(str(sim.get("warning") or ""))
