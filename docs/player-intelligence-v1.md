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

## Pregame roster/report snapshot
Reviewed official NBA Injury Report 2026-11-23 01:15 AM, page 5:
https://official.nba.com/referee/injury/Injury-Report_2026-11-23_01_15AM.pdf
The report includes team sections not yet submitted and page continuations,
and displays names rather than stable player IDs. No missing row is treated
as a confirmed active player. Raw PDF ingestion is not implemented.

The normalized snapshot requires two independently verified rosters,
verified fixture identity and per-row NBA person IDs, separate publication
and capture timestamps, and source evidence references. Latest whole team
report supersedes earlier releases, including omissions and non-submission.
Stale publication cannot be refreshed by re-downloading. Reject conflicting
same-publication reports, mismatched fixture/roster IDs and cross-team
membership. Retain an SHA-256 digest of normalized inputs/output diagnostics,
not medical details; this is an integrity identifier, not source authentication.
Snapshot output is compatible with rotation inputs. Tests are synthetic;
live source resolution, verified ID crosswalk, complete roster coverage and
commercial rights are still outstanding. No writes to the production tracker.

## Batch research implementation — empirical rotations and evaluation
- V02 uses up to 30 complete, previously observed regulation rotations with
  explicit played flags. Same-absence pool requires at least three observed
  games in which each unavailable player explicitly did not play. Missing
  players are not DNP. Shrink empirical rotations toward V01 with eight
  prior pseudo-games; this fixed weight is uncalibrated.
- Sample 100–5000 complete rotation vectors (default 5000) and whole
  per-player rate vectors. Each draw conserves 240 minutes, caps each
  player at 48, and counts three-pointers within PTS. Report empirical
  quantiles and means; rates across players are independently sampled,
  so team scoring/rebound/assist totals are not jointly constrained.
- Absence audit is an unadjusted descriptive played/DNP points comparison;
  it never modifies V8, and is not a causal injury or defensive/pace effect.
- Pipeline prepares one explicit pregame scenario for both teams, records
  snapshot digest and model identity. Disposable SQLite archive keeps first
  model/team/game forecasts, rejects late/backdated/corrupted records,
  protects UPDATE/DELETE and has no production DB connectivity.
- Paired evaluator uses common game/team/player and pregame scenario,
  reports MAE, signed bias, empirical interval coverage and missingness,
  counts actual explicit DNP separately, and excludes multiple scenarios
  instead of selecting one after the result.
- Still required: real-source fixture/roster/report ingestion and identity
  crosswalk, licensed data verification, actual chronological calibration
  and all-roster coverage, matchup and position-aware rotation, joint team
  score coupling, adjusted impact estimates, prospective scheduling, and
  approved production integration. No claim of improved real NBA accuracy.
- Documented NBA CDN fields checked against nba_api live boxscore schema:
  https://github.com/swar/nba_api/blob/master/docs/nba_api/live/endpoints/boxscore.md
  Direct sample URL was inaccessible via web retrieval; live schema and
  provider availability remain unverified.

## Source and replay iteration — 27 Nov 2026
Read-only Neon baseline audit of 933 V7.6 player forecast rows across 82
game/team groups: 12 groups have settled minutes for every selected row;
none of 82 predicted minute sums is within 10 seconds of 240. Seven actual
sums match 240 within that tolerance; actual sums range 182–266 among
non-null groups, and OT/selection are not separated. All player IDs are
numeric but zero are NBA-namespaced, and none of the game IDs has the
NBA 002 regular-season format. No identity mapping is inferred.
On 781 matched V7.4/V7.6 player rows, minutes MAE by realized minutes:
0–9 (80): 8.70/8.47; 10–19 (174): 4.03/4.10;
20–29 (261): 3.73/3.79; 30+ (266): 4.22/4.14.
V7.6 signed minute error respectively +8.44, +2.16, -0.51, -3.19.
These are outcome-conditioned descriptive diagnostics, not pregame features
or a valid tuning target without a held-out cohort.

Added bounded read-only NBA CDN capture using fixed schedule and game
URLs, no redirects, finite timeout/size cap, observed timestamps and
content hashes. Collects up to 10 games per explicit diagnostic call;
CI checks at most 2. Schedule fixture and strict boxscore reconciliation
must agree. CI diagnostic success does not mean live data verified:
read the source_verified_in_this_run field and rejection reasons.
No commercial use permission, complete coverage, or actual source success
has been established. Current captures cannot reconstruct earlier
pregame availability or historical observation timestamps.

Added chronological replay of independently pre-captured cases, one
scenario per game, with historical evidence filtered before either model
runs. Replay clocks are simulated, not true issued forecasts; never
pool replay metrics with prospective metrics or insert replay envelopes
into the live archive. Cases are not inferred from postgame lineups.
Source and replay tests use synthetic fixtures. Latest CI pending.
