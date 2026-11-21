# HOOPZARO Simulation Lab 2.0 — rollout plan

This document tracks the six-phase Premium redesign. Use the approved HOOPZARO navy / cyan / violet visual language without replacing existing Player Props.

## Phase 1 — New shell (released in PR #137)

- Full-width matchup hero with team badges, model-derived score and simulated win probabilities.
- Accessible fixture picker (same selected fixture, same Polish date and model across modules).
- **Wyniki i rozkłady** continues using existing server-produced distributions: match, away and home, model-computed P10–P90, Monte Carlo score averages. No browser-generated projections.
- **Player Simulations** is a separate working view based on the verified PTS, REB and AST player estimates supplied by the current backend.
- Later modules are explicitly disabled and labeled `Wkrótce`, rather than presenting fake features.
- Server-validated Premium entitlement and admin access remain unchanged. Guest payload must never include premium arrays. Current Player Props limits and pages remain unchanged.

## Subsequent implementation stages

## Phase 2 — Player Simulations inspector (this PR)

- Player-focused Premium module: accessible team filters (both/away/home), live player-name search, clickable forecast rows, selected-player forecast inspector.
- PTS, REB and AST from the model's **existing server-side Premium projection**. PRA is **the arithmetic sum of those three mean projections** only when all three are present. It is **not** a separately simulated or calibrated distribution.
- V7.5 only: verified historical estimated minutes, supporting appearance count and current ESPN availability label with the existing caveats. V7.2/V7.4 must explicitly say minutes are not supported; never synthesize sample sizes or minutes.
- Verified ESPN Out: projected production is missing, not deceptively displayed as zero points, and source/model caveats remain visible.
- Filter server-side output to the selected matchup's two team IDs; preserve team identity when searching, changing fixture, or switching model.
- When Premium access is revoked, clear the inspector immediately alongside the existing chart and player list. No data caching in the browser, and no new network call.
- Historical L5/L10/L15 charts remain exclusively in Player Props.
- 3PM, player-specific empirical uncertainty, and directly simulated PRA probability must await trustworthy backend data. They are **not** asserted by the UI.

## Remaining implementation stages

2. Future player model validation: true player-specific distributions for PTS/REB/AST/PRA and 3PM if supported by reliable pregame model inputs and audited backtests.
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
