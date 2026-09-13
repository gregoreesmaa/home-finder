# Overturn hunt log — MARU/Stat/ECB: G16 market aggregates per-KOV choropleth (issue #241)

> Time-boxed source hunt for Group 16 market-aggregate params
> (parameters3.md §5.16: Maa-amet medians, Statistikaamet HH01/KK11,
> ECB 6M Euribor). Probed 2026-09-13 (5 polite single GETs, labelled
> research user-agent `home-finder-research/0.1 (... issue 241)`,
> paced ≥ 4 s, raw bodies at `/tmp/hf-maru-241/`, never committed).
> **Verdict: 5 per-KOV dims FLIP to honest registry-table joins
> (p41/p149/p421/p43/p484); national series stay unmapped by
> construction; everything else stays NULL (dated).** The test-pinned
> dims live in `services/scoring/dims_overturn_maru.py`, pinned by
> `services/scoring/tests/test_dims_overturn_maru.py`.
> Re-check the dated negatives no later than **2027-03-13**.

## Verdict

| Param | Verdict | Shape (all exact per-KOV joins, never walk-gradients) |
|---|---|---|
| p41 historical appreciation | **FLIP** | MARU KOV median YoY% (same quarter a year apart): ≤−5%→75, <0→65, ≤+5%→50, ≤+10%→40, above→30 |
| p149 market liquidity | **FLIP** | MARU KOV quarterly deal count: ≥300→80, ≥100→65, ≥30→50, below→35 (first-cut Harju bands) |
| p421 appraisal gap risk | **FLIP** | asking €/m² vs MARU KOV median: ≤1.0×→80, ≤1.10×→60, ≤1.25×→45, above→30 — **this is where area-median-vs-listing-price lives, not in p1** |
| p43 resale appeal | **FLIP** | composite depth (p149 leg) + direction (p41 leg): 70/55/50/35; a missing leg NULLs (no half-comps) |
| p484 absorption rate | **FLIP (weak, cap 70)** | MARU deal-velocity QoQ only; months-of-supply needs the KV-adapter inventory leg (named EI OLE) |
| p6 mortgage rates (ECB 6M) | **STAYS UNMAPPED by construction** | euro-area constant (latest print 2026-08: 2.7133333% p.a.) — no per-KOV join exists; display-only accessor, never a score or map band |
| p156/p185 (KredEx/net-metering) | **STAY NULL** | national rules, owned by dims_group16a |
| p481 price ceiling | **STAYS NULL (dated)** | a KOV max cannot cap one street — refused proxy (see below); street ceilings need micro-comps |
| all other G16 (p2/p7/p8/…, p241/…, p363/…, p482/483/487, …) | **STAY NULL** | owned by dims_group16a/b — per-deal facts, US concepts with no EE register, tax/fiscal tables outside these three feeds |

No-map gradients stay invalid throughout: a county-wide Euribor
constant painted per-parcel would be one flat colour, not a map
(OTA PR #131 precedent); the flipped shapes are per-KOV choropleth
cells / per-listing registry joins only (nomap.md §3 G16 reasoning
unchanged — shared/group files untouched; the final docs-index PR
updates nomap.md).

## Openness evidence (one polite round, 2026-09-13)

| Check | Observed | Meaning |
|---|---|---|
| `https://www.maaamet.ee/kinnisvara/htraru/` | 200, 23 015 B, `<title>Real property price statistics</title>` | query env open, no auth, no key |
| same body: `DDMaakond` / `DDOmavalitsus` multi-selects | `Maakond` + `Omavalitsus` field labels with multi-select dropdowns | **per-KOV aggregation verified** — the flip's join grain exists |
| same env: form-driven JS postbacks | no anonymous bulk CSV contract found at landing level | quarterly KOV table = caller-supplied maintainer export (EHR gated-export precedent) — never scraped |
| `maaruum.ee/.../Eesti kinnisvaraturg 2025.pdf` (HEAD only) | 200, `application/pdf`, `content-length: 7878623` | annual report public; no bulk download pulled |
| `https://andmed.stat.ee/api/v1/et` | 200, 67 B: `stat` / `statsql` | PxWeb open (same as the #292/#365 probe) |
| `.../et/stat/majandus/hinnad` | 200, 4 262 B, 30 tables incl. IA027/IA028/IA0285/IA0286 dwelling-price index | HH01/KK11 substitutes open; literal HH01/KK11 stay the sibling's dated partial-negative (not re-traversed out of politeness) |
| ECB `FM/M.U2.EUR.RT.MM.EURIBOR6MD_.HSTA?format=csvdata&lastNObservations=3` | 200, 1 558 B; prints 2026-06: 2.5955, 2026-07: 2.6467391, 2026-08: 2.7133333 (% p.a.) | series open, monthly, national (`U2`, "Euro area (changing composition)") |

Total: 4 GETs + 1 HEAD, paced ≥ 4 s, one 429-free round. No scraping,
no auth, no bulk download, no form submissions.

## Pull policy (polite, cached, TTL-stated)

- One request per source per run; `User-Agent: home-finder-research/0.1`
  (polite MARU/Stat/ECB overturn harvest; issue 241); 25 s timeout.
- `fetch_cached(url, cache_dir, name, ttl_days)`: fresh cache wins (no
  request); transport errors are raised and **never cached as data**;
  HTTP 429 raises immediately (stop signal, no retry).
- TTLs: MARU quarterly KOV export **91 d**, Stat quarterly tables
  **91 d**, ECB 6M prints **7 d** (parameters3.md §5.16: weekly Euribor
  sync). Cache subdir `hf-overturn-maru` under the caller cache dir
  (`/tmp/hf-cache` in production, `/tmp/hf-maru-241/` was the one-off
  probe record).
- Refresh rhythm: MARU quarterly (maintainer pastes the query-env
  export into the `kov;quarter;median_eur_m2;deals` import schema),
  ECB weekly auto-pull, Stat quarterly auto-pull.

## Near-miss proxies considered and refused

- **Euribor as a map layer**: a euro-area constant has zero per-KOV
  variance — painting it per-parcel is the flat-colour fantasy
  nomap.md already refuses. Display-only accessor, never a dim.
- **KOV max as street ceiling (p481)**: a KOV maximum comes from
  luxury new-builds; capping one street's panel flats off it inverts
  the param's question. Street ceilings need micro-comps.
- **Adjacent-quarter annualisation (p41)**: seasonal new-build spikes
  would fake a trend — same-quarter year-apart pairs only.
- **Velocity as full absorption (p484)**: deals without inventory is
  half the formula — capped at 70 with the inventory leg named.
- **Cross-KOV smoothing / forward-fill**: KOVs update independently;
  a missing KOV row stays NULL even when Tallinn is fresh.

## What stays open (overturn path, not wired here)

A MARU anonymous bulk contract appears (then the maintainer export
becomes an auto-pull), literal HH01/KK11 codes resurface in PxWeb
(then the Stat leg upgrades from IA028-substitute), or street-grain
micro-comps open (then p481 flips) → re-open #241 and propose the
join. Shared/group files (`dims_group16*.py`, `dims_p4_stat.py`,
`dims_overturn_maa.py`, `livability.py`, WEIGHTS, `docs/nomap.md`,
p1) are deliberately untouched — the final docs-index PR updates
nomap.md. Overlap boundaries for the rebalance follow-up: P4-002
owns the fair/steal anchor, p421 owns the appraisal-gap band;
P4-038 owns QoQ heat, p41 owns YoY appreciation; Maa-WFS owns
parcels, this module owns market aggregates.
