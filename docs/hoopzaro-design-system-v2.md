# Hoopzaro Design System 2.0 — visual contract
Owner-approved direction, 2026-11-27. This is a specification; it does not change production CSS. Existing approved screens take precedence over any proposed token changes.

## 1. Source of truth
- Shared shell: bestbets_reference_frontend/hoopzaro.css (loaded after legacy inline CSS in index.html), current owner screenshots of Centrum, Zawodnicy, Drużyny.
- Brand: owner-supplied composite dated 2026-11-27; left web lockup, right mobile app icon. No generated replacement or color reinterpretation. Current hoopzaro.svg is a legacy asset until new source is reviewed.
- Teams: approved second Team Spotlight concept. Players: no final mockup selected.
- Keep original 175/1231 desktop sidebar width at reference stage, original navigation order, current responsive behavior unless separately tested.

## 2. Color tokens (actual existing shell)
| Token | Value | Usage |
|---|---|---|
| --hz-ink | #05091e | Background |
| --hz-panel | #0b1027 | Panel |
| --hz-cyan | #16e9fa | Primary interactive accent |
| --hz-teal | #07edcb | Secondary accent |
| --hz-violet | #9a4ff6 | Analytical emphasis |
| --hz-magenta | #dc32f7 | Limited atmospheric accent |
| --hz-coral | #ff675d | Error / risk |
| --hz-green | #05f68f | Success / favorable |
| stage | #04091d / #060b21 / #050518 | Existing 125deg gradient |
| primary text | #f4f8ff | Main text |
| muted text | #b9d1e9 | Secondary text |
| premium text | #f8dda0 | Premium/Admin only |
| premium edge | #deb77d | Premium/Admin only |

Active navigation: blue-to-purple gradient, #3178e6 edge and inset 3px cyan line. Never substitute orange or lime for primary brand accents. Team accents may vary inside team-specific identity cards, not navigation. Keep meaningful red/green states with text labels (not color alone).

## 3. Component rules
- Typography: existing Inter/Arial/Helvetica shell, bold title hierarchy; existing premium Space Grotesk/Sora/system fallback. Tabular numerals; no font download or new font dependency without evaluation.
- Panels: current 12–18px reference radius, thin blue/violet borders, restrained light and depth; no glossy stock photography, arbitrary mascots or excessive glow. Use CSS/SVG for implementable details.
- Inputs/buttons: persistent accessible labels, visible focus, clear disabled state, existing SVG icons; 44 CSS px mobile touch targets where practical.
- Charts: same axis/readability conventions, explicit units, season and sample; chronological game dates; no fabricated trend lines, no 3D, label H/A if supported. Actual and projections visually distinct.
- Identity: circular initial avatars for players, original abstract letter monograms for teams. No faces or official marks until rights are verified.
- Paywall: existing gold faceted gemstone, dark obsidian gradient, text identifying access. Free content remains usable; Admin bypass. No fake checkout, no payment changes in design work.
- State patterns: loading, missing, stale, locked, empty, error; never display a fake number to fill the design. Reduced-motion support, keyboard navigation, mobile overflow checks.
- Layout: each page optimized for its task, not identical template for all. Preserve approved Centrum, schedule and simulation layouts.

## 4. Brand asset preparation / acceptance
Source is 1536 x 1024 composite PNG (not vector). Extract actual pixels into separate web lockup and square icon; keep original dark backdrop and glow. Do not erase background or trace without owner review. Use native-resolution crop as master, optimize web display variants; mobile 1024 export is an upscale, not new detail. PWA 192/512, favicon 32/48 and optional ICO. Inspect at actual size. iOS/Android store packaging, mask-safe assets and background handling require separate QA. A cropped raster source is not equivalent to true SVG. 
No production path changes until references, assets, mobile manifest/link and favicon behavior are reviewed. Keep legacy SVG fallback until parity confirmed.

## 5. Review gates
- Screenshot current production/reference and candidate at 1231x691, 1672x941, 390x844, 844x390.
- Compare brand, spacing, clipping, typography and all states. Verify interactions, Free/Premium/Admin and keyboard/touch. Capture before/after Centrum to verify no layout change.
- Use test fixtures clearly marked synthetic; verify live data contracts separately.
- Owner approves new visual target; CI passes required checks; then consider merging. 
