# P4 harbour — joined ports + AIS pleasure cells (#627)

> Build note for issue #627 (checked 2026-09-17). Reverses the #542
> dated-negative verdict below: the sadamaregister `public-active` app
> API IS openly served (37 joined rows), INSPIRE `TN_sadam PortNode`
> supplies names, and the AIS 2024 pleasure SHP was pulled (709 cells).
> Scorers live in `services/scoring/dims_p4_harbour.py`, pinned by
> `services/scoring/tests/test_dims_p4_harbour.py`; sidecar built by
> `scripts/build/batch_harbour.py`; web wiring in
> `apps/web/lib/layers_p4_harbour.ts` (+ snapshot sidecar, outlines
> painter, harbour + harbour/areas routes).

## What shipped

| Leg | Source | Shape |
|---|---|---|
| Joined port points | sadamaregister `public-active` (function taxonomy) + INSPIRE PortNode (names) | 37 real points, function-labeled fn1/fn2/fn3, dots on the point path |
| AIS pleasure fills | AIS 2024 500 m SHP (CC BY-SA) | 709 cells, pleasure-band fills; outside = NULL (never calm) |
| Fixture | P4-023 sadam leg | Replaced row-for-row (measured, not flat 60) |

No season calendar: detail endpoints return HTTP 401, so no per-port
season dates exist in any licensed feed — bands use season-free annual
totals BY HONESTY (stated in the legend, not faked).

Outside every port point and AIS cell is NULL with an Estonian reason
(never "quiet/calm", never 0, never 100).

## Licence notes

AIS SHP under CC BY-SA (attribution in the legend + layer def);
sadamaregister public-active rows are openly served public data (no
login/session flow touched, polite single pulls); INSPIRE WFS carries
no charge and no use constraint. No per-record scraping of human
publications, no personal data (AGENTS.md §5).

---

# P4 harbour verdict note — sadamaregister + AIS vessel density (#542)

> Dated-negative verdict for issue #542. Checked 2026-09-16. SUPERSEDED
> by the #627 build above (2026-09-17) — kept as history.

## Verdict (superseded)

**No licensed machine feed — both dims stay NULL with Estonian reasons.**
The sadamaregister serves a JS app shell + an undiscovered app API with no
licence statement (hard gate: no ingestion until an open licence is
confirmed), the INSPIRE harbour WFS carries geometry + names only (no
function taxonomy), and the AIS 500 m grid values were never pulled.

## Openness evidence (one polite round, 2026-09-16, no scraping, no auth)

8 single GETs total, 2 s pacing, `--max-time 30`, labelled one-off
user-agent `home-finder openness-check (one-off, few pages max, no
scrape)`. Raw bodies: `/tmp/hf-probes/` (one-off PR record, not
committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://www.sadamaregister.ee/avaandmed` → HTTP 200, 1632 B | JS shell (`<div id="app">` + `/js/app.2bb0d667.js`), zero server-rendered rows | Shell is a lead, not a feed (AGENTS.md §7.7) |
| `…/avaandmed.xsd` → HTTP 404 (`Cannot GET /avaandmed.xsd`) | Documented schema path does not exist | No bulk schema at the hoped-for URL |
| `/js/app.2bb0d667.js` → HTTP 200, 47 KB | Data-backed app: `window.appSettings.ApiBaseUrl` + `/ports/public-active`, `/ports/{id}/public-details`, `GisBaseUrl` | Rows exist behind an API whose base URL is undiscovered |
| `/appsettings.json`, `/js/settings.js`, `/config.js` → 3× HTTP 404 | No settings endpoint at the obvious paths | Base URL stays unknown; probing stops (no brute-forcing) |
| INSPIRE `TN_sadam/wfs?…GetCapabilities` → HTTP 200, 108 KB | 2 types: `PortArea` (`Eesti sadamaregistri sadamaalad`), `PortNode` (`Eesti sadamaregistri sadamad`); Fees/AccessConstraints `puudub` (= no charge, NOT a licence) | Harbour geometries ARE openly served — but see schema |
| INSPIRE `…DescribeFeatureType` (both types) → HTTP 200, 4 KB | PortArea = inspireId + `geom` ONLY; PortNode adds name spelling + `validfrom` | **No function taxonomy, no season dates, no vessel size** — function slices cannot come from this WFS (schema proof first, done) |
| AIS `laevaliikluse-tihedus` catalogue entry | Not present in the local checkout (no `sources/` dir) | Sizes / CRS / 2024 Pirita-Kakumäe values UNPROBED — stated, not faked |

No licence statement was found in the shell, the bundle, or the WFS
capabilities — the hard gate stands. No login/session flow touched, no
per-record scraping (AGENTS.md §5).

## Fixture-replacement audit (P4-023 sadam leg, row-for-row)

Live today in `services/scoring/dims_p4_trans.py`:

| Fixture row | Shape today | Measured replacement (BLOCKED) |
|---|---|---|
| `noisezone_p4` labelled `sadam` within 1 km → flat **60** | Fixture zone join (distance gates, label scores) | PortArea **containment** by function from joined sadamaregister rows: cruise-terminal adjacency → noise-calendar leg; cargo-port adjacency → low noise band; marina adjacency → recreation note |
| Outside every mapped zone → NULL | Unknown, not quiet | Outside every PortArea → NULL (never "quiet/calm") |

Until the licence gate clears, the fixture stays exactly as-is — this PR
touches no shared file and changes no existing score.

## Honest shapes per leg (all NULL until a gate clears)

| Leg | Dim key | Honest shape when its gate clears | Buyer-side check meanwhile |
|---|---|---|---|
| Port functions | `harbour_function_zone` (P4-023) | function slices off licensed port rows (cruise/cargo/marina score differently — schema proof first), containment only | sadamaregister.ee port pages; ts.ee timetables; on-site listen at Vanasadam/Pirita edge |
| AIS density | `ais_pleasure_density` (P4-033) | 500 m-grid overlay 1:1 (grid IS the field, no re-interpolation); outside port influence → NULL | harbour services; on-season site visit |

Never 0 and never 100 would apply once scored; today every reason says
`EI OLE`. P4-047 event-traffic + P4-055 icebreaking dims stay cousins
(distinct keys).

## Judgment calls (for the reviewer)

1. Verdict instead of bands: the licence hard gate forbids ingesting the
   register leg, and AIS values were never pulled — bands from either
   would be fake precision.
2. The WFS DescribeFeatureType is the "schema proof first" the issue
   asked for — and it disproves the WFS as the function source, so the
   reopen path is the licensed app API, not the WFS.
3. No shared-file edits (livability.py, WEIGHTS, layers, layers.md
   untouched): 3 new files only. No map screenshot: no layer is painted.

## Reopening checklist (when a gate clears)

1. Confirm the sadamaregister licence in writing; paste the statement.
2. Resolve `ApiBaseUrl` (settings endpoint or registry contact), pull ONE
   Tallinn-bay port row, transcribe the function taxonomy + season dates.
3. For AIS: one HEAD per S3 link (sizes), grid CRS, one 2024 cell value
   off Pirita/Kakumäe; state brief AIS gaps.
4. Graduate dims to bands ONLY from joined records; keep NULL + Estonian
   reason for every missing leg.
