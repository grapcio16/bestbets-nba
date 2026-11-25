# HOOPZARO V8 Shadow — automated prospective accuracy report

The scoring report is **read-only** and deliberately uses no fresh forecast
calculations. It evaluates frozen `hoopzaro_v8_shadow_forecasts` and
`bestbets_forecasts_by_model` rows only **after** final NBA settlement.

## Research protocol

- Discard an outcome unless its original forecast was archived at least
  15 minutes before tipoff and it has verified final scores and settlement.
- Do NOT count unsettled pregame forecasts as successes, and do NOT
  retrospectively recompute older games with a newer model.
- The NBA final cannot be tied: skip corrupt tied actuals. V8.1's tied
  *predicted scenario* remains in the archive and is counted separately.
- Compare V8.1, V8.2 and V7 versions only on the same ESPN game IDs with
  identical away/home teams and final results; a common sample is mandatory.
- Score separate MAE for predicted **means**, MAE for the representative
  **scenario**, total points MAE, signed point bias, winner accuracy and Brier.
- Compute observed coverage for previously archived 10th–90th percentile
  intervals, and show how many real games had usable intervals.
- Preserve exact pregame version IDs; where V8.1 and V8.2 were trained
  on different numbers of games (first archived 25 November: 79 vs 144),
  flag the comparison as confounded. An improved score is not attributable
  only to overtime resolution when the training sample also changed.
- No bankroll, sportsbook line, odds or bet settlement are archived here:
  **ROI, over/under betting accuracy and financial return are unavailable**.
- Low-n research metrics must never be marketed as proven win rates.

## Operation

`.github/workflows/v8-shadow-evaluation.yml` runs daily at 13:37 UTC
(GitHub schedule may be delayed), on approved manual dispatch, and once
when the workflow is introduced on main. It reads Neon with the existing
`TRACKER_DATABASE_URL` GitHub secret and publishes an aggregate JSON
artifact and summary. It never updates any database row or public Premium
component. Empty settlement outputs `waiting_for_settled_games`, not fake
performance numbers.

Test suite: `python -m unittest -v test_v8_shadow_evaluation`
and the integrated V8-only QA workflow.
