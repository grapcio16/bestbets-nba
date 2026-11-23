# HOOPZARO — Simulation Lab Premium: release acceptance gate
**Prepared:** 2026-11-23 · **Scope:** stacked PR #173–#179 · **Target:** public Streamlit/hoopzaro.com **only after approval**

## Release status
**Candidate, not production.** The final branch contains all six Premium screens plus integrated browser acceptance tests. It does **not** change statistical model mathematics or settle the 2026-11-25 Tracker evaluation. Never call the product independently validated solely from browser screenshots or a successful CI run.

## What is planned for public navigation
| Premium screen | Purpose | Release semantics |
| --- | --- | --- |
| Results & Distributions | Monte Carlo output + manual O/U line | Experimental probabilities and mean from verified payload |
| Player Simulations | Upcoming-game projections and separate ESPN player history | Historical L5/L10/L15/Season is not a simulated probability distribution |
| Scenario Builder | User-controlled pace/offense assumptions | Hypothetical what-if, not verified player or team news |
| Match Intelligence | Real pretipoff evidence and documented factors | Show unavailable fields as em dash; V7.5 factor corrections only when verified |
| Team Comparison | Verified pregame L5/L10, home/away | NBA Advanced PACE/OFFRTG/DEFRTG only if data complete; never substitute PPG |
| Model & Backtest | On-demand bounded offline walk-forward (max 40 games) | Historical baseline analysis, **not** a full production V7.5 backtest or betting ROI |

The experimental **Flow meczu** panel is still hidden, disabled and route-guarded. Do not reactivate until quarter/momentum predictions have independent evidence.

## Automated technical release gate
The GitHub workflow `.github/workflows/simulation-lab-final-release-gate.yml` must show SUCCESS on the exact commit proposed for release. It includes:
- JavaScript and Python syntax checks, six tab IDs, one CSS reference per design, no external ESPN headshots, disabled Flow, and explicit lack of historical bookmaker ROI.
- Unit tests for verified Player Simulations historical data and regression Chromium suites from each of the six module PRs.
- Integrated Chromium run for **1672×941 desktop, 390×844 iPhone, 320×700 compact phone, 844×390 landscape**: one active tab, correct pane, navigation through all six, full vertical scroll where content is taller than viewport, no horizontal overflow, browser page errors, no historical metric carry-over between games or models, and no Premium data after entitlement revocation.
- Screenshots uploaded as workflow artifacts. QA fixture values exist exclusively in test scripts; screenshots are **not** real NBA forecasts.

If any step is red, release is blocked. Do not relax geometry or data assertions to make the job green; repair the actual interface.

## Manual sign-off gates — required before changing `main`
- [ ] **Design 1:1:** compare generated desktop/iPhone screenshots for each of the six screens with the exact approved concept; verify widths, typography, spacing, shadows, cyan/purple glow, modal position, chart proportions and overall density. CI alone cannot establish pixel-perfect fidelity.
- [ ] **Real mobile devices:** check iPhone Safari in portrait + landscape; vertical scroll, tab-strip horizontal swipe, filters, calendar, model picker and last cards above bottom nav. Chromium simulation is insufficient for claiming iOS Safari certification.
- [ ] **Real server payload:** test selected future NBA matchup, a second matchup and different dates; confirm ESPN history cutoff is strictly prior to tip-off, injury provenance/freshness is visible and unverified factors show '—'.
- [ ] **Premium and admin:** test real OIDC sessions (guest, FREE, PREMIUM, admin), server-side access control and revocation. Confirm administrator receives Premium without payment; synthetic browser QA does not authenticate real accounts.
- [ ] **Model acceptance after Tracker 2026-11-25:** compare V7.2/V7.4/V7.5 winner calibration (Brier), game total and team MAE, player props outcomes and sample coverage. Compare contemporaneous pregame forecasts against actual results, not retrospective reconstructions. Document known totals high-bias and avoid marketing any unverified 'accuracy'. No changes to algorithms before evaluation.
- [ ] **Rights/legal:** validate sources, image permissions (no unlicensed headshots/logos), terms and disclosures, paid account pricing/Stripe live readiness, refund and support workflows before a paid public launch.
- [ ] **Production smoke + rollback:** keep a known good `main` SHA and a rollback procedure; after approved deployment test all six views on hoopzaro.com as admin and guest, with production secrets and historical data access; monitor errors and backtest runtime.
- [ ] **User approval:** confirm screenshots and wording before publishing. Merging/delivery must be a separate explicit decision.

## GitHub integration plan (stacked changes)
1. Review and test PRs sequentially: #173 Match Intelligence → #174 Team Comparison → #175 Scenario Builder → #176 Player Simulations → #177 Results → #178 Backtest → #179 Final Release Gate. This branch includes the ancestor changes from all six.
2. Do not merge these as independent unordered PRs; later branches depend on earlier ones. Reconcile the stack after each ancestor merge (especially when squashing) and ensure all diffs against `main` are understood.
3. Re-run the **final integrated release gate** on the exact effective `main` merge candidate. The last passing test on a prior branch SHA is insufficient.
4. Deploy only after the manual gates and Tracker review. Stop on any mismatch or source-integrity issue; revert using the pre-merge SHA.

## Blockers not automatically closed by this PR
- Model prediction validation and totals bias pending Tracker evaluation **2026-11-25**.
- Final pixel-by-pixel acceptance against the approved six source mockups.
- Testing with real NBA/ESPN data, authenticated accounts and Safari hardware.
- Production deploy approval and payment/legal readiness.

**Release decision: HOLD until all items above are completed.**
