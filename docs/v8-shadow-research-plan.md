# HOOPZARO — V8 Shadow research protocol (2026-11-24)

## Research only — never show V8 in Premium until prospectively validated

Independent files in `v8_shadow/` implement original model mathematics. Existing
V7.2/V7.4/V7.5/V7.6 simulation code, Premium UI, tracker workflows and baseline
tables remain untouched. The worker has a *separate* GitHub Actions schedule
and only writes two new tables whose names begin with `hoopzaro_v8_`.

### 1. Observed source features and their evidentiary status

| Field | Expected provider | Validity / contract |
|---|---|---|
| ESPN game ID, teams, actual final, UTC tipoff | Existing ESPN season schedule, shared only as external transport | Completed only, exact IDs, immutable score |
| FGA, FTA, offensive rebounds, turnovers by both teams | ESPN final game-summary team boxscore | All four observed, exact fixture and score, no mock filling |
| Estimated game possessions | Derived from observed stats | FGA − OREB + TOV + 0.44×FTA; approximate, **not** official possession count |
| Raw pace proxy | Average both teams' derived possessions | Overtime games excluded until 48-minute normalization validated |
| OffRtg, DefRtg | Team points scored/allowed per observed estimated possessions | Research estimate; not labelled as verified official NBA rating |
| Last 5/25 form, rest, venue | Only strictly earlier verified final games | No post-tipoff/revised injury data |
| Player injury/rotation | No historical pretipoff snapshots in V8 yet | Deliberately **not used**; cannot reconstruct from later injury reports |
| League-adjusted shooting/lineups | Pending reliable, licensed feed | Missing, NOT silently imputed |
| Betting lines and odds | Pending separately licensed data | Not available; never manufacture a return-on-investment estimate |

Provider options researched: NBA Stats (`nba_api`, Pace/OffRtg/DefRtg),
ESPN game summary (`hoopR` reference schema), pbpstats (possession histories),
BALLDONTLIE (advanced endpoint, plan-dependent). GitHub and Neon are already
connected. Optuna/MLflow can be installed as Python tooling in the next
calibration iteration; neither requires a new ChatGPT integration.

**Commercial rights:** public endpoints and open-source client libraries do not
grant HOOPZARO a commercial data license. Before any user-facing V8 deployment,
review NBA, ESPN, pbpstats upstream and future providers' licenses.

### 2. Scoring engine and 5,000 simulations

- Chronological rolling team data: pace, scoring efficiency, conceded efficiency,
  scoring trend, venue splits, rest; feature rows for each completed training
  game are calculated from games with an earlier tipoff only.
- A new standardized ridge model learns two team point targets jointly from
  observed game-level outcomes. Fixed initial regularization is *not*
  optimized until a separate rolling validation stage.
- Last 24% of chronological examples (min 16) is held out for prelaunch
  residual diagnostics. Train the final model on all earlier matches; no
  hindsight in forthcoming fixtures.
- Draw 5,000 correlated (home,away) results by resampling paired out-of-time
  residuals plus small covariance-proportional jitter. This is a *research
  empirical uncertainty model*, pending coverage calibration.
- Output (a) one observed-data-conditioned joint high-density 5×5 point-bin
  scenario, (b) two distinct mean team points, (c) win probability based on
  all draws with regulation ties split, (d) 10th/50th/90th quantiles, and
  (e) validation diagnostics and sample size. A scenario is NOT an
  exact-result guarantee and is never presented publicly.

### 3. Archive and no-leakage gates

1. Game evidence must pass exact same-team, game ID, final score and physical
   stats checks. Unknown or conflicting boxscores are rejected.
2. No completed match may enter the pregame feature set if it started after
   the forecast was issued. Same-tipoff events are trained together.
3. Forecasts require a minimum number of observed games and at least
   15-minute pretipoff lead. There is NO invented fallback forecast.
4. Model and data evidence tables have insert-only semantics for predictions,
   with `(game_id, model_id)` uniqueness and no revision of original forecasts.
5. V7 tables and equations are not modified. V8 data are isolated on a
   shadow research workflow and not rendered in public Streamlit Premium.
6. Postgame settlement fills actuals once; do not treat a retrospective
   recomputation as an archived pregame prediction.

### 4. Validation criteria after November 27

Only compare common games with all models' *pregame* forecasts, and report
coverage. Compare winner accuracy, Brier, mean home/away point MAE,
absolute total MAE, signed total bias, joint selected scenario MAE, and
empirical 80% interval coverage. Audit low-score/high-score tails.
**A more varied-looking scoreboard is not itself an improvement.**

Evaluate performance separately for regulation-only and OT games; for V8 v0.1,
OT training is excluded. Minimum 60 comparable pregame matches recommended
before any tentative preference, and materially more for public performance
claims. No backtest uses data from after each historical prediction timestamp.

### 5. Operating

- Draft PR holds changes until unit + real schema smoke are reviewed.
- `.github/workflows/v8-shadow-collector.yml` installs research dependencies,
  connects only through existing GitHub Actions secret `TRACKER_DATABASE_URL`,
  ingests max 18 missing final game boxscores per run and freezes eligible
  future predictions with sufficient historical evidence.
- Stored raw evidence is **per-game numeric summary**, not full ESPN JSON or
  protected user information. The archive is only accessible in Neon.
- Missing provider availability must result in less training evidence,
  **never** in fabricated PACE or ORtg/DefRtg.
- Historical season backfill is intentionally bounded. Current season
  sufficient coverage may take multiple collection cycles. No promises of
  next-day predictive quality before checking actual stored sample sizes.
