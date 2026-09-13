# P4 opmaps verdict note — Telia/Elisa/Tele2 levikaardid (P4-009 operator leg)

> Dated-negative verdict for issue #267 (demo only — P4-009 is the
> only param using this source, so there is no coverage follow-up).
> Checked 2026-09-13. Single param is a documented no-map NULL dim
> (OTA PR #131 precedent); the scorer lives in
> `services/scoring/dims_p4_opmaps.py`, pinned by
> `services/scoring/tests/test_dims_p4_opmaps.py`.

## Verdict

**No pollable operator bulk feed — the dim stays NULL with an Estonian reason.**
All three operators publish coverage as interactive marketing map apps
behind JS storefronts, with no bulk download, no API, and no
machine-use licence advertised anywhere. There is no ingestion to
cache, no TTL to state beyond this one-off check, and no honest
per-address coverage band to paint.

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

6 single GETs total (labelled one-off user-agent `home-finder opmaps
openness-check #267 (one-off, single GETs, no retry; contact via GitHub
home-finder)`, ≥ 6 s pacing, `--max-time 25`, headers + visible-text/link
scope read only). Raw bodies: `/tmp/hf-opmaps-probe/` (one-off PR record,
not committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://www.telia.ee/` → 302 to `/era` | locale-split gate, 20 bytes | storefront entry, not a data portal |
| `https://www.telia.ee/era` → HTTP 200 (360 921 bytes, 3 829 visible chars, 10 script tags) | leviala / levikaart / coverage 0×; avaandmed / open data / developer / download / andmestik / masinloetav all 0; single "arendaja" hit is the "Ehitajale, arendajale" construction-developer footer, "Sideettevõtjale" is the wholesale/carrier footer | no open-data surface, no developer portal — footers are construction/wholesale, not data |
| `https://www.elisa.ee/` → HTTP 200 (97 646 bytes, 5 793 visible chars, 11 script tags) | no leviala link or mention anywhere in served HTML; no open-data terms; same construction ("Ehitajale, arendajale") + "For carriers" footers | storefront only — the map lives behind JS nav, no feed advertised |
| `https://www.tele2.ee/` → 301 to apex `https://tele2.ee/` → HTTP 200 (408 501 bytes, 3 496 visible chars, 32 script tags) | nav/footer link "Tele2 leviala" → `/leviala`, `/internet/leviala`, device-support page; no open-data terms (visible-text "api" 1× is a shop-menu substring, context-checked) | coverage page confirmed to exist — and it is a page, not a feed |
| `https://tele2.ee/leviala` → HTTP 200 (269 826 bytes, 4 522 visible chars, 31 script tags, no `<title>`) | "Tele2 levikaart" heading on a JS map-app shell (< 2% visible text); csv / geojson / wfs / download / andmestik / masinloetav all 0; "Tingimused" is the generic service-terms footer link | marketing-grade interactive map: no bulk endpoint, no machine feed |

Judgment call: the check stopped at storefront/shell level on purpose —
no tile harvesting, no map-app API chasing, no session flows. Driving a
marketing map to extract coverage would be exactly the scraping this repo
refuses (AGENTS.md §5). ToS got a scope-read only: generic "Tingimused"
service-terms footers on all three, no open-data/API licence anywhere —
with no bulk feed to licence, clause-level ToS reading answers nothing.

## Honest shape (NULL until an operator opens a feed)

| Param | Dim key | Honest shape when a feed answers | Buyer-side check meanwhile |
|---|---|---|---|
| P4-009 reliability, operator leg (demo) | `operator_coverage` | per-address band from joined operator rows only, never a screenshot grade | mobile coverage TTJA netikaardilt, speed Ookla avaandmetest, mast density OpenCellID-st, power cuts rikkekaardilt |

Sibling P4-009 slices keep their owners (untouched): Elektrilevi feeder
SAIDI (`dims_p4_elektrilevi`, NULL), Elering system series
(`dims_p4_elering`, NULL per-address), TTJA netikaart / Ookla tiles /
OpenCellID masts (their own demos).

## Judgment calls (for the reviewer)

1. Single-param demo, no coverage issue: P4-009 is the only param naming
   this source family (parameters4.md source (4)
   "Telia/Elisa/Tele2 levikaardid Tallinn (verify ToS, cache)") — one
   module, one test file, one verdict note.
2. The confirmed Tele2 map page carries the verdict for the source
   family: all three storefronts advertise no open-data surface, and the
   one reachable map is a JS shell with zero machine markers. A second
   and third app-shell fetch would add bytes, not information.
3. No shared-file edits (livability.py, WEIGHTS, layers, layers.md,
   parameters4.md untouched): 3 new files only. Central hook (enrich
   join + WEIGHTS rebalance) stays one joint change across all batches.

## Reopening checklist (when an operator opens a feed)

1. Re-run the probes above on demand (a feed announcement, not a cron —
   there is no ingestion to refresh); paste fresh evidence in the reopen PR.
2. If any operator publishes a pollable bulk coverage feed (CSV/GeoJSON/
   WFS/API with a machine-use licence), transcribe one Tallinn week of
   dated rows into the cache dir and run them through a parser + per-address
   join on fixtures first.
3. Graduate the dim to a band ONLY from joined rows (coarse raster
   hinnang per parameters4.md); keep NULL-with-Estonian-reason for every
   missing leg.
4. Add the explicitly-flagged live integration test (not a unit run).
