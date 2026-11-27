# Player Intelligence Engine — research v0.1

## Baseline audit (27 Nov 2026)
Existing eligible_roster uses latest log grouped by name and an injury lookup
by normalized name; recent histories can include a former team. The new
research contract is stable player ID + explicit current team + verified
point-in-time roster. Existing public model is not modified. In the tracker
V7.4 has 856 settled rows with observed minutes out of 1028 and V7.6 has
781 of 933; none of the observed minute rows equals zero. The tracker
cannot currently establish availability/DNP accuracy from those rows.
Shared-sample minutes MAE previously measured 4.47 / 4.46. Do not compare
a new complete-rotation cohort against those selected rows without matching.

## First module
- Regulation-only team minutes conserve 240; each player is capped at 48.
- Fresh verified OUT gets zero. No entry, stale status, questionable,
  doubtful and probable require explicit scenario assumptions; no invented
  probability or implicit healthy flag.
- Uses up to 15 prior active regulation games for the current club, with
  recency weighting and per-minute rates. At least 3 games and weighted
  exposure of 20 minutes; no fabricated rookie or missing-player stats.
- Uses explicit observation timestamps, strict 15-minute lead and 4-hour
  conservative historical final delay. Rejects duplicate evidence.
- Outputs conditional minutes, PTS/REB/AST/FG3M/PRA, no joint player draws.
  Redistributes minutes proportionally, not by position or coached lineup.
  Five active players is a physical boundary, not a realistic rotation.
- Freshness limits (24h roster, 6h availability) are conservative design
  assumptions, not empirically tuned. Availability status must be verified
  for this fixture by the future adapter. Source rights must be reviewed.

## Next research gates
1. Verify provider IDs, roster completeness, schedule identity, timestamped
   official availability and regulation/OT metadata. No name-only joins.
   Record actual DNP separately from missing boxscore or unverified result.
2. Collect prospective immutable snapshots in an isolated research store
   (no production database migration without separate permission).
3. Evaluate minutes MAE, active/inactive coverage, conditional PTS/REB/AST/PRA
   and all-roster error; report missingness and scenario assumptions.
4. Model positional substitutions, minute distributions and lineup impacts
   from observed data; use chronologically held-out calibration.
5. Link to V8 team forecasts only after proving independent incremental value
   and avoiding double counting team form. No public UI or payment changes.

Current scope: offline calculation and tests only, no live integration.

## 27 November — evidence adapter
Initial rotation CI on 9e5ab48 passed 10/10 tests, run 46029884335.
Added an offline NBA CDN regulation-final adapter. It requires independently
verified fixture IDs, explicit UTC timestamps, final status, four periods,
matching teams, score and tipoff, unique NBA person IDs, complete played
statistics, and reconciled player points and team minutes (10-second
rounding tolerance). Explicit played=0 may provide a DNP record; missing
played/minute fields do not become zero. Namespaced NBA IDs cannot be
joined directly with ESPN IDs. Availability must now carry the exact
fixture ID. No network request, write, source licensing approval, or
live-schema validation is implied by this synthetic contract. A strict
adapter may reject genuine records if source schemas differ or timestamps
are rescheduled; document rejection coverage rather than silently relaxing
validation. Need a real sample and roster/availability capture contract.
Latest offline tests require CI verification.
