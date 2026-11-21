# HOOPZARO Simulation Lab 2.0 — rollout plan

This document tracks the six-phase Premium redesign. Use the approved HOOPZARO navy / cyan / violet visual language without replacing existing Player Props.

## Phase 1 — New shell (this PR)

- Full-width matchup hero with team badges, model-derived score and simulated win probabilities.
- Accessible fixture picker (same selected fixture, same Polish date and model across modules).
- **Wyniki i rozkłady** continues using existing server-produced distributions: match, away and home, model-computed P10–P90, Monte Carlo score averages. No browser-generated projections.
- **Player Simulations** is a separate working view based on the verified PTS, REB and AST player estimates supplied by the current backend.
- Later modules are explicitly disabled and labeled `Wkrótce`, rather than presenting fake features.
- Server-validated Premium entitlement and admin access remain unchanged. Guest payload must never include premium arrays. Current Player Props limits and pages remain unchanged.

## Subsequent implementation stages

2. Player Simulations: verify player minutes and model reliability, add real 3PM/PRA only with supported source data, and player-specific uncertainty; use the same game, date and model context.
3. Bidirectional Player Props ↔ Player Simulations deep links: preserve player identity, stat market, selected fixture and return navigation, respecting each module's subscription gate.
4. Scenario Builder: re-run the server-side model using explicit hypothetical constraints, retain the baseline, compare A/B projections, log assumptions; do not treat simulations as official injury news.
5. Match Intelligence / Team Comparison: verified pace, form, strength, injuries and schedule context; clear missing-data flags and transparent model factor attribution.
6. Model & Backtest: timestamp/store genuine pre-tipoff forecasts; use walk-forward evaluation, MAE, calibration, sample sizes and historical archived market prices where available. Never display invented ROI/win rates.

## Release guardrails

- Keep model versions `legacy_v72`, `research_form_v74`, `research_context_v75` independent in frontend identity checks and server cache.
- Never use actual postgame scores or later player performances to predict an earlier NBA fixture.
- Display retrospective runs as retrospective, not as recorded pregame forecasts.
- Prevent data and paywall leaks when switching tabs, model, date, game or identity.
- New frontend changes must pass `node test_simulations_canvas.js`, `python test_simulations_browser.py`, the existing Player Props/browser regressions and all repository PR workflows before squash merge to `main`.
- PR merge only; Streamlit Cloud deployment should be independently verified, not assumed from the GitHub commit.
