# HOOPZARO — Master project brief
Updated: 2026-11-27. Owner-approved visual modernization plan. Repository: grapcio16/bestbets-nba. Public service: hoopzaro.streamlit.app; intended branded address: hoopzaro.com. Treat this document as the project baseline, not proof of deployment. Refresh GitHub/CI/data status before changing code.

## Product and non-negotiables
Global NBA analytics, PL/EN, Free + Premium USD 9.99/month (Stripe test mode until commercial readiness). Admin bypasses paywall. Historical analytics and future projections must remain clearly separated. Never invent statistics, team identity, injury status, samples, forecast performance, or working controls. Show missing/unverified/stale data explicitly. Never label a research candidate as proven. No official team marks or player likenesses without appropriate permission; use original letter monograms and initials only. Commercial data rights remain an open release gate. Never commit secrets or live payment credentials.

## Visual baseline
The owner supplied a two-part brand reference on 2026-11-27: left = web HZ hexagon + italic HOOP (white) ZARO (cyan) wordmark + spaced NBA ANALYTICS; right = mobile HZ emblem inside a rounded square with cyan-to-magenta border. Preserve the artwork and proportions; no invented logo, palette substitution, athlete portraits or mascot logos. The supplied composite is a raster source, not an approved vector master. Extract separate assets without redesign; verify tiny-size legibility and safe area. Do not claim traced artwork is pixel-identical.
Existing shared shell is protected: original sidebar order and icons, blue/cyan active state, deep navy background and purple arcs, gold gemstone Premium/Admin CTA. Current CSS reference: bestbets_reference_frontend/hoopzaro.css and index.html; do not use obsolete orange inline defaults as the visual reference. See docs/hoopzaro-design-system-v2.md.

## Owner-approved scope and order
1. Document baseline, prepare logo assets and shared design system.
2. Players (Zawodnicy): design from scratch, no existing rejected mockup is approved. Explore usable desktop/mobile compositions with real frontend components. Show an actual visual preview for owner selection before implementing the final layout. Catalog/search, player profile, verified season metrics and historical games, links to existing Player Props and projections where supported. Avoid duplicate analysis and invented splits/usage/league rankings.
3. Teams (Drużyny): owner selected the second Team Spotlight mockup from conversation 2026-11-27: full-width team profile, record and form, advanced metrics/chart, direct analysis CTA, searchable compact grid with distinct team accents, abbreviated monograms, favorites. No unverified extra season/division filters. Keep free basic records and Premium advanced analytics, as currently implemented. Visual review before deployment.
4. Player Props: preserve approved design; refine consistency only. Historical L5/L10/L15/season, ALL/HOME/AWAY, daily free quota when verified, Premium beyond quota. 
5. Simulation Lab: preserve approved subpages. Verify data and charts, injury/minutes assumptions, model labels and result semantics. Do not revive inaccurate Flow timeline without evidence. V8 remains research-only until release gates.
6. Terminarz: preserve layout, factual schedule, H2H and standings.
7. Settings & Account 2.0: review consistency and real functionality. No fake billing, alerts or settings.
8. Premium/paywall: refine access presentation and safe test checkout only.
9. Mobile QA, accessibility, performance, full regression, owner review.
Centrum: **no redesign**. Only explicitly approved shared brand asset replacement and necessary verified bug fixes; do not alter its layout or presentation. Shared changes require Centrum regression screenshots.

## Technical workflow
Use dedicated branches and draft PRs. Check current main and overlapping branches before each change. Do not overwrite other work. Use Figma/Product Design in appropriate supported environment for UI exploration, Codex or GitHub for implementation, Playwright for desktop and mobile visual/functional QA, Neon for read-only evidence and isolated test data, GitHub Actions for CI. Build from actual CSS/HTML/JS, not image-only screens. Establish before/after screenshots (1231x691, 1672x941, 390x844, 844x390), compare against owner-approved reference. Verify navigation, keyboard focus, touch, scroll, no horizontal clipping, reduced motion, correct permissions, missing states and performance. Preserve existing backend contracts. Synthetic data only in labeled test fixtures. Do not merge/deploy failed or unreviewed UI. Never turn on production flags, payments or database writes as a visual change.
Keep progress reports concise: commits, files, tests with head SHA, actual evidence, blockers and next step. Don't count checking metadata as implementation.

## Technical snapshot (last verified during conversation, 2026-11-27)
- #189 Control Center: draft, 17 successful and 9 failed visible workflow runs; no production rollout.
- #205 V8.03: draft research, 14/8.
- #206 Utah identity: draft, 13/9.
- #207 Player Intelligence: draft research, 15/8.
- #208 UI test harness: draft, 15/7.
- #209 Settings & Account 2.0 merged; #210 next verified game fallback merged.
- #211 directory V5: draft, 15/10; not approved as final player design; compare to main and salvage tested fixes only. Do not merge or treat as reference.
These numbers describe workflow runs, not individual test cases; refresh before release.
Active separate automations: technical development and PR189 monitoring. Coordinate work and avoid overlapping writes.
