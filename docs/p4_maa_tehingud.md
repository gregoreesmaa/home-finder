# P4 Maa-tehingud — openness verdict + demo/coverage note (issues #244, #328)

> Verdict date: 2026-09-13 (all probes single polite fetches, cached
> `/tmp/hf-p4-maa-tehingud/`, 3 s pacing, contact UA in headers).
> Code: `services/scoring/dims_p4_maa_tehingud.py` (demo P4-002 + 10 coverage
> params); tests: `services/scoring/tests/test_dims_p4_maa_tehingud.py`
> (hermetic, synthetic fixtures, no network).

## Verdict

| Source | Result | Evidence (2026-09-13) |
|---|---|---|
| Maa-amet **tehingute andmebaas** (per-address deals) | **RESTRICTED — dated negative for per-address bulk** | Landing page HTTP 200 (53 192 B): *"Tehingu andmetele on juurdepääs piiratud. Andmebaasi andmetega võib tutvuda ja saada nendest väljavõtteid ainult maa hindaja hindamise läbiviimiseks, …"* — licensed valuers / statistics producers / R&D bodies / supervised lenders only. No open building-level feed exists. |
| Maa-amet **kinnisvaraturu ülevaated** (market publications) | **OPEN** | Yearbook PDF HTTP 200, `content-type: application/pdf`, 7 878 623 B, `last-modified: 2026-02-13`, `cache-control: public, max-age=31536000`; monthly PDFs also published (e.g. 2026-03). |
| Statistikaamet **PX-Web API** (HH01/KK11 Tallinn tables) | **OPEN** | `GET https://andmed.stat.ee/api/v1/et` → HTTP 200, lists `stat`/`statsql` DBs. |
| HTRARU public stats query UI (aggregates) | OPEN (aggregates only) | Referenced by the market PDFs as source (`Allikas: Maa- ja Ruumiameti tehinguteandmebaas`); per-address detail stays behind the restricted DB. |

Consequence (honest shape): the per-address median join is implemented and
fixture-proven, but with the per-address bulk restricted, **production joins
stay NULL** with an Estonian reason pointing at the licensed-valuer extract
until an open feed appears. Re-probe quarterly; a newly opened bulk flips the
verdict without code changes (ingestion already caches with TTL).

## Pull policy (polite, cached, TTL-stated)

- One request per source per run; `User-Agent: home-finder-research/0.1`
  (polite quarterly bulk; issue 244); 25 s timeout; 3 s pacing between hosts.
- `fetch_cached(url, cache_dir, name, ttl_days)`: fresh cache wins (no
  request); transport errors are raised and **never cached as data**; HTTP 429
  raises immediately (stop signal, no retry).
- TTLs: tehingud bulk **91 d** (quarterly), market publications **30 d**
  (monthly PDFs; yearbook 365 d), Stat HH01/KK11 **91 d** (quarterly).

## Per-param wiring (all honest shapes = per-address median join or a named leg)

| Param | Wired leg (this ingestion) | Legs honestly missing (EI OLE, named not faked) |
|---|---|---|
| P4-002 micro-comps | building → street median; score = 100·median/asking | thin levels (< 3 deals) |
| P4-001 DOM history | stale (≥ 90 d / ≥ 2 cuts) × P4-002 anchor | adapter `first_seen` history |
| P4-021 developer track | same-developer resale median vs base | TTJA complaints, EHR history, broker stats |
| P4-025 micro-liquidity | asum deals / 2 latest quarters | REL2021 age/migration/vacancy, school plans |
| P4-028 demand exhaust | views/day + DOM + updates (adapter counters) | Maa-amet ask-vs-close calibration (→ P4-038) |
| P4-038 bargaining margin | area-type gap table (Land Board publication) | table itself when unpublished |
| P4-043 number-13 | 13-mark × street median (taste-match flag) | thin street comps |
| P4-044 herd front | asum newer-half vs older-half median drift | REL2021 occupation-mix grid |
| P4-050 permit glut | falling-price check (latest vs year-ago window) | EHR permit/completion counts |
| P4-052 turnover wave | ≥ 6 deals/building/12 mo → neutral 50, both readings | — (both readings in reason by design) |
| P4-061 last-shop tracker | manual checklist (shop/pharmacy/ATM + bus cuts) | Peatus GTFS diffs, OSM closure tracking |

Never a gradient: no distance weighting, no interpolation, exact-match joins
only; single deals never set a "median" (MIN_COMPS = 3); P4-052 ambiguity
scores neutral 50 so it cannot push the steal sort.
