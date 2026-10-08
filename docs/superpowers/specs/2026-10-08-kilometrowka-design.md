# Kilometrówka — Design

**Date:** 2026-10-08
**Status:** Approved (design presented in chat; user approved 2026-10-08)
**Parent spec:** [2026-10-08-side-income-apps-design.md](2026-10-08-side-income-apps-design.md) (Product 1, first build)

## 1. Purpose

A free, no-account, client-side Polish "ewidencja przebiegu pojazdu" (mileage log) web tool — the first product of the Polish document suite. Target buyer: sole proprietors (JDG) and employees who must log business trips in a private car. Monetization: one-time Pro unlock (79 zł ≈ $19) via Lemon Squeezy license key.

Why this niche (from keyword research, 2026-10-08): strongest PL tool-intent volume (~10–30K searches/mo, January peaks when rates refresh); incumbents are Excel template downloads and subscription apps; the language moat (diacritics, "kwota słownie" declension, Polish SEO) blocks the global tool farms flooding English SERPs.

## 2. Constraints

- **Client-side only** — no server, no backend, no account, no uploads. Hosted on Cloudflare Pages (free tier).
- **Polish-language UI** and content.
- **Vanilla JS + Vite + Vitest** (user-approved stack; TDD per repo convention).
- **Legal positioning:** informational tool with disclaimer ("nie zastępuje programu księgowego/doradcy podatkowego"); no compliance promises.
- Lives in **this repo**: `projects/kilometrowka/`, same workflow as the todo project (spec → plan → TDD → review).

## 3. Rates (verified 2026-10-08)

Current statutory rates, unchanged since 17 Jan 2023 (Rozporządzenie Ministra Infrastruktury z 25.03.2002, Dz.U. 2023 poz. 5 § 2):

| Vehicle | Rate per km | Monthly limit |
|---|---|---|
| Car ≤ 900 cm³ | 0,89 zł | 6 000 km |
| Car > 900 cm³ | 1,15 zł | 6 000 km |
| Motorcycle | 0,69 zł | 7 500 km |
| Moped | 0,42 zł | 7 500 km |

Notes: capacity class comes from the registration document, not fuel type (EVs settle per >900 cm³ rate). A draft regulation (engine-power-based rates, EVs/hybrids separate) is pending but NOT in force; when enacted, new rates are added to the rate table as a dated option. The app must therefore keep rates **data-driven, versioned, and editable by release**, never hardcoded logic.

Sources: [poradnikprzedsiebiorcy.pl](https://poradnikprzedsiebiorcy.pl/-stawka-za-1-km-przebiegu-pojazdu-jaki-limit#0-Kwota-limitu-za-1-km-przebiegu-pojazdu---2026-rok), [firmove.pl](https://firmove.pl/aktualnosci/biznes/prowadzenie-firmy/kilometrowka-jakie-stawki?utm_source=aleo.com&utm_medium=link&utm_campaign=mainpage-publications-section).

## 4. Product Scope

### 4.1 Free tier

- Unlimited trip entries: date, route start/end, purpose (cel podróży), km, vehicle.
- One vehicle profile.
- Automatic rate application per capacity class; monthly km × stawka totals.
- Monthly limit warning (6 000 / 7 500 km), not a block.
- Monthly report PDF (print-ready).
- Data stored in localStorage only, with an explicit "dane nie opuszczają Twojej przeglądarki" note (privacy is a selling point vs. server-side competitors).

### 4.2 Pro tier (one-time 79 zł ≈ $19, Lemon Squeezy license key)

- Multi-vehicle profiles.
- Year archive (all months retained, browsable).
- XLSX export of trips and monthly summaries.
- Per-purpose (cel podróży) breakdown in summaries.
- Ryczałt mode: fixed monthly settlement entry (per art. 23 PIT rules) alongside per-km entries.
- Custom logo on the PDF report.
- Backup/restore of saved data (JSON export/import).

## 5. Architecture

```
projects/kilometrowka/
  index.html            # app shell (SPA, no router)
  src/
    main.js             # entry, wiring
    rates.js            # versioned rate table + calculation (pure)
    store.js            # localStorage persistence + versioned migration
    km.js               # trip model, monthly aggregation, limits (pure)
    xlsx.js             # Pro: XLSX export
    license.js          # Pro: Lemon Squeezy license key validation
    ui/                 # components: trip form, trip list, month view, summary, settings
    pdf/                # PDF generation (embedded Unicode font)
  tests/                # Vitest unit tests
  vite.config.js
  package.json
  README.md
```

**Boundaries (same discipline as todo's cli.py/store.py, in JS):** `rates.js`, `km.js`, and `store.js` are pure logic with no DOM or PDF knowledge — unit-testable in isolation. UI components consume them; `pdf/` and `xlsx.js` consume data structures only. `license.js` calls the Lemon Squeezy license API from the browser (public validation endpoint, no secret).

## 6. Data Model

```
vehicle = { id, name, plate, capacityClass }        # capacityClass: "<=900" | ">900" | "motorcycle" | "moped"
trip    = { id, date, start, end, purpose, km, vehicleId }
storage = { version: 1, vehicles: [...], trips: [...] }
```

Single localStorage key (e.g. `kilometrowka.v1`), JSON. `version` field enables future migrations (doc-suite additions must not corrupt existing data).

## 7. PDF Report

- **Library:** pdf-lib with an **embedded Noto Sans subset** — standard PDF fonts do not render Polish diacritics (ą/ę/ł/ż/ź/ć/ń/ó); broken diacritics are why several competing Polish tools look amateur. Font files loaded from own origin.
- **Layout:** header (seller name/address — Pro: logo), vehicle + month, trip table (date, route, purpose, km), totals (km, stawka, kwota), **"kwota słownie"** with correct Polish declension (tysiąc/tysiące/tysięcy, złoty/złote/złotych), signature line, footer disclaimer.
- Report reflects the currently selected month and vehicle; Pro adds year-archive export.

## 8. SEO & Marketing

- **Landing page = the tool itself**, on the shared product domain, targeted at the researched keyword set: "kilometrówka 2026 kalkulator", "kilometrówka kalkulator", "ewidencja przebiegu pojazdu wzór", "kilometrówka stawka za 1 km", "kilometrówka wzór pdf", "kilometrówka excel". Page title/description/headings in Polish with the primary keyword.
- **Content sections** on the same page (SEO + user trust): current rates table, how-to-use steps, FAQ ("czy kilometrówka wymaga ewidencji?", "limit 6000 km", "samochód elektryczny"), all linking the tool.
- **Yearly January refresh:** update rates/year references when the new regulation is enacted — the January rate-change searches are the volume peak.
- **Launch:** Wykop post, answer the existing forum.gofin.pl kilometrówka threads genuinely (tool mention where allowed), JDG/księgowe Facebook groups — no link dropping; help first.
- **Later:** cross-promote from the doc-suite's other landing pages (rachunek, WZ, pokwitowanie) once they ship; link to the Allegro extension project when it launches.

## 9. Testing (TDD, Vitest)

- `rates.js`: rate lookup per capacity class, calculation, monthly limits, future versioned-rate behavior.
- `km.js`: monthly aggregation, per-purpose breakdown, ryczałt mode totals, limit warnings.
- `store.js`: save/load round-trip, version migration, corrupt-data handling.
- `pdf/`: text extraction from generated PDFs — diacritics render correctly, "kwota słownie" declension cases (1 złoty / 2 złote / 5 złotych / 1 tysiąc / 2 tysiące / 5 tysięcy).
- `license.js`: activation flow states (valid/invalid/expired) — mocked API responses.

## 10. Milestones

1. Scaffold: Vite project, Vitest, package.json, README; `rates.js` + tests (TDD).
2. `store.js` + `km.js` aggregation + tests.
3. UI: trip form, list, month view, summary; wire storage.
4. PDF report + diacritics tests.
5. Landing page content + SEO + Polish copy.
6. Pro: `license.js` + Lemon Squeezy setup + XLSX export.
7. Deploy to Cloudflare Pages (subdirectory deploy), smoke-test, launch steps (§8).

## 11. Success Criteria

- A Polish user can log trips for a month and print a correctly-formatted, diacritics-correct monthly report without creating an account.
- Vitest suite green; rates and aggregation verified against the statutory table.
- Pro activation works end-to-end against a real Lemon Squeezy test license.
- Landing page live on the shared domain with the primary keywords in Polish.
- Launch checklist (§8) executed; first sales tracked against the portfolio spec's checkpoint (3 months post-launch: reassess if $0).

## 12. Risks

| Risk | Mitigation |
|---|---|
| Draft regulation changes rates | Data-driven, versioned rate table; yearly refresh ritual |
| Nobody searches (volume estimate wrong) | Keyword set verified via autocomplete; cheap to pivot to the next suite doc (rachunek/WZ/pokwitowanie share the engine) |
| PDF diacritics breakage | Embedded Noto Sans subset + text-extraction tests from day one |
| License-key friction on the free tier | Free tier is fully usable without an account; Pro gate only on clearly Pro features |
