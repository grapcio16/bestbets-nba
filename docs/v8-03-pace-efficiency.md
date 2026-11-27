# V8.03 — pace and efficiency research candidate

27 November 2026. The previously settled nine-game sample motivated this
experiment, but is not an independent test of this model and is not used
to choose a fixed correction. No retrospective shadow forecasts.

- Fit three targets jointly: common estimated possessions, home points
  per 100 possessions, away points per 100 possessions.
- Use chronological pregame features, a 15-minute lead and a conservative
  four-hour final-result availability delay. Purge the validation boundary
  of labels unavailable at its first forecast time.
- Estimate paired residuals in all three dimensions and sample jointly.
  Reuse V8.02's explicit overtime approximation and representative joint
  score scenario; keep the mean separate.
- Report pace error, score error and signed total bias. No lineup/injury
  features yet; bounded bootstrap tails and overtime remain assumptions.
- Keep V8.01 and V8.02 archives untouched. The existing worker only adds
  V8.03 forecasts when HOOPZARO_V803_ENABLED=true. Default is OFF.
  Storage already distinguishes game_id + model_id; no schema change.
- Before enabling: pass offline CI and isolated worker/storage integration,
  review runtime, source rights and data cutoff. Do not change public UI.
- Evaluate frozen forecasts on a shared prospective game cohort, separately
  reporting mean/scenario MAE, total bias, winner accuracy, Brier score and
  interval coverage. Use a predeclared minimum of 100 shared settled games
  as an initial review checkpoint, not proof of superiority. Report sample
  size and uncertainty; preserve all outcomes, including failed forecasts.

No production deployment, database write, or live forecast is authorized
by this draft. Historical fixtures test invariants, not real-world accuracy.
