# Overturn hunt log — p317 park upkeep quality / KOV haljastus contracts (issue #240)

> Time-boxed source hunt for Group 11 p317 (parameters3.md §5.11).
> Hunted 2026-09-13 (~25 min). **Verdict: KEEP the NULL** — no open
> machine-readable source for park upkeep quality / KOV haljastus
> contracts in Tallinn. The test-pinned verdict dim lives in
> `services/scoring/dims_overturn_p317.py`, pinned by
> `services/scoring/tests/test_dims_overturn_p317.py`.
> Re-check the three discovery surfaces no later than **2027-03-13**.

## Verdict

**No open feed — p317 stays NULL with an Estonian reason.** Park
upkeep quality lives in KOV maintenance contracts per park
polygon. No OSM tag family encodes it, the Tallinn open-data API
exposes no discoverable haljastus/hooldus table, the national
portal has no pollable dataset (and no CKAN API at all), and
riigihanked notices are per-procurement human documents with no
per-park polygon join. There is no ingestion to cache, no TTL to
state beyond this one-off check, and no honest per-park upkeep
band to paint. Scoring p317 off park density, a contractor's
name, or an `operator=` manager tag would be fake precision
(OTA PR #131 precedent; nomap.md §3 G11).

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

6 tiny requests total (single GETs, labelled one-off user-agent
`home-finder-p317-hunt/1.0 (one-off open-data check; contact via
GitHub issue #240)`, paced ≥ 4 s, headers + visible-text keyword
scope read only, no form submissions, no XHR probing). Raw
bodies: `/tmp/hf-p317/` (one-off PR record, not committed).
Local OSM checks ran zero network against
`~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf`.

| Check | Observed | Meaning |
|---|---|---|
| `osmium tags-count harjumaa-260911.osm.pbf maintenance cutting` → 1 `maintenance`, 13 `cutting` | The single `maintenance` object is relation 1175710, `maintenance=good` on the E11 European long distance path Scheveningen→Tallinn (verified via `osmium cat` XML: trail-condition tag on a trans-European hiking route) | Zero park-upkeep signal: the only upkeep-ish key county-wide describes a hiking trail, not a park |
| Same PBF: 13 `cutting` objects | All road/railway terrain cuttings (`cutting=yes/no` on `highway=residential`, `railway=abandoned`, footway) | Terrain term, not mowing — no signal |
| `osmium tags-count` → 294 `leisure=park`, 2155 `leisure=garden`, 7710 `operator` | Park polygons exist in the hundreds, but no upkeep-quality key family exists to join them against | Polygons without quality attributes cannot calibrate even a weak proxy |
| `https://andmed.eesti.ee/dataset?q=haljastus` → 200, 75497 B | JS-only "Teabevärav" shell, 12 visible chars, zero server-rendered hits | No trivially pollable national-portal dataset |
| `https://andmed.eesti.ee/api/3/action/package_search?q=haljastus` and `?q=pargi%20hooldus` → 404 `Cannot GET` (98 B / 104 B) | Not a CKAN platform — no package-search API at all | No machine fallback behind the JS shell |
| `https://avaandmed.tallinn.ee/` → 200, 1420 B | Real "Universal API for Tallinn city open data": `/data/?table=…&columns=&filters=&order_by=&page=&per_page=` (FastAPI 0.1.0 per `/openapi.json`, 1597 B, generic endpoint only) | Machine-readable API exists, but the table catalog lives in the JS portal and the schema enumerates no tables — no haljastus/hooldus table discoverable politely |
| `https://riigihanked.riik.ee/` → 200, 2606 B | AngularJS (`rhrApp`) shell; notices live behind the JS app | Tender/award notices are per-procurement human documents — no per-park polygon feed to join |

Judgment call: the check stopped at storefront level on purpose —
no RHR XHR probing, no tender-PDF enumeration, no blind guessing
of Tallinn `table=` names one by one (each miss is load on a city
API). Deeper probing is exactly the scraping this repo refuses
(AGENTS.md §5).

## Near-miss proxies considered and refused

- **Park density as upkeep** (`leisure=park` nearness): density
  measures supply, never mowing frequency or quality — refused
  (nomap.md §3 G11 states the fantasy explicitly).
- **`operator=` manager as quality**: names who manages the park
  (e.g. Kommunaalamet), never how well — relabelling management
  as upkeep is the refused proxy.
- **Award-notice contractor as quality**: a notice names a
  contractor and a lump area, never per-park quality polygons;
  "a contractor exists" inverts the param's question (presence
  of a contract ≠ quality of upkeep).

## What stays open (overturn path, not wired here)

A haljastus/hooldus table name surfaces in the Tallinn catalog
(then one `/data/` query tests the join), or a per-park upkeep
polygon feed appears in-snapshot → re-open #240 and propose the
per-park-polygon contract join (bands + Tallinn histogram +
master, per docs/nomap.md §2). Shared/group files
(`dims_group11*.py`, `livability.py`, WEIGHTS, `docs/nomap.md`)
are deliberately untouched here — the final docs-index PR
updates nomap.md.
