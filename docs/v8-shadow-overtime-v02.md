# HOOPZARO V8.2 Shadow — final-score research upgrade (2026-11-25)

The first **nine real V8.1 pregame forecasts** were archived before the NBA
fixtures of 25 November. They are **not** overwritten, recalculated or removed.

## Observed issue

The representative V8.1 PHX at HOU scenario was `117:117`, a possible
regulation-time draw but **not** a legal NBA final score. V8.1 also split
regulation-tie probability 50/50 without modelling actual overtime points.

## V8.2 research-only correction

- Frozen independent model ID `v8_possessions_shadow_v02`; V8.1 remains a
  separate `(game_id,model_id)` archive entry in Neon.
- Sample 5,000 **regulation** trajectories from the V8 two-team correlated
  joint residual model. For trajectories tied after 48 minutes, simulate
  independent team scoring over one or more 5-minute overtime periods with
  a shared random pace factor.
- Explicit scoring assumption: the expected 5-minute points for each team
  are `pregame_regulation_mean * 5 / 48`, varied by a shared factor, then
  drawn from a Poisson distribution. **This is an UNCALIBRATED approximate
  model**, not an empirical assertion about actual overtime efficiency.
- If a trajectory remains tied after a bounded number of extra periods,
  reject the forecast rather than invent a coin-toss winner or display a
  tied NBA final.
- All final-score scenarios are sampled from **untied final trajectories**,
  not produced by manipulating a previously selected tied representative.
- Full-game means/quantiles/win probabilities are calculated from these
  same final-score trajectories. Raw regulation mean remains separately
  recorded. The probability of overtime and maximum simulated periods
  are also recorded for audit.
- No change to V7, existing V8.1 forecasts, public Premium or baseline
  Tracker. The same 56-example chronological gate continues to apply.

## Assessment after real results

Evaluate V8.1 and V8.2 **side-by-side on matching games issued before
tipoff**. Do not mistake the replacement of a tied scenario for evidence of
better expected-point accuracy. Track MAE of both selected scenario scores
and full-game means, win probabilities, overtime frequency and interval
coverage, alongside accuracy against V7 baseline records.

Unverified injury/lineup inputs remain **excluded** from V8; do not silently
infer player availability. Research provider commercial rights remain
unconfirmed and must be cleared before any public Premium exposure.
