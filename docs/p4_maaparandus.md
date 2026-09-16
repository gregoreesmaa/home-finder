# P4 maaparandus verdict note (issue #551)

Date: 2026-09-16. Scope: drainage-duty + wetness joins from the
maaparandus GIS WFS (MSR register mirror). Module
`services/scoring/dims_p4_maaparandus.py`. No shared files touched.

## Openness verdict: OPEN — licence gate passes

Polite probes, custom `home-finder-probe` User-Agent:

| Probe | Result |
|---|---|
| `GET gsavalik.envir.ee/geoserver/pta/wfs?…GetCapabilities` | HTTP 200, 117048 bytes. 5 layers: `pta:msr_vork` (reguleeriva võrgu alad), `pta:msr_eesvool`, `pta:msr_riigieesvoolud` (state-maintained joint outflows), `pta:kehtetu_maaparandussysteem` (invalid systems), `pta:mpy_tegevuspiirkond` (co-op areas). Default CRS EPSG:3301 (+3857, +4326). Fees NONE, AccessConstraints NONE. |
| Licence (in the capabilities) | **CC-BY 4.0**, attribution to Kliimaministeerium as source, unless a layer states its own terms. Gate passes — ingestion allowed with attribution (`ATTRIBUTION`). Informative-data disclaimer noted (no guarantee). |
| `DescribeFeatureType pta:msr_vork` | HTTP 200, 2342 bytes. Attributes: `ms_kood` (13-digit system code), `ehitise_kood/nimi`, `nahtuse_liik` + `nahtuse_seletus_lyhi`, `vihm`, `pind_ha`, `aasta`, `vork_id`, `ms_url` (MSR link), timestamps. **No `seisund`/status attribute**; `nahtuse_liik` semantics unproven without value samples (out of probe budget). |
| `GetFeature resultType=hits`, Harjumaa bbox | `numberMatched="1916"` regulating-network areas (lat-lon axis order; the lon-lat order hits zero — axis-order artefact documented in `build_hits_url`). |

## Status-attribute finding (duty leg closes as NULL)

The duty leg needs a maintained-vs-derelict status to score duty; the
schema has none with proven semantics. `dim_drainage_duty` therefore
always returns NULL: with an `ms_kood` it names the code + the
MSR-register check; without a join it names the missing join. Reasons
point at the register, never assert duty. Overturn: value samples of
`nahtuse_liik` proving maintained/derelict semantics (harvest PR).

## Honest-shape table (per-parcel joins, never gradients)

| State | Shape |
|---|---|
| No joined WFS pull | NULL (`EI OLE`) |
| Inside `msr_vork` | 55 capped hinnang, `ms_kood` + status-unknown + MSR check named |
| Inside `kehtetu_maaparandussysteem` | 40 measured risk flag (wins over the inside band) |
| Outside network, eesvool ≤100 m | 45 dampness flag ("lähedus ei ole märg krunt") |
| Outside everything | NULL — never "dry" |

Split vs neighbours (reviewer note): #543 owns restriction *zones*;
p50 owns open-water proximity; `p4_maa_subsurface` owns
karst/peat/groundwater. This module owns *infrastructure* containment
+ the duty-side NULL. Harvest weekly at most; transport errors raise,
never cached; 429 propagates.

## Graduation: map overlay (issue #616, 2026-09-17)

Closes #616. One layer (`drainage`, `paramLabel P4-kuivendus`,
`paramIds []` — parameters4 namespace): regulating-network areas
(wetness blue, condition unproven) + invalid systems (derelict brown)
+ outflow centerlines (thin ditch blue, no buffer) as a class
choropleth with lines; outside every shape NULL (never dry). Duty
refused everywhere (no duty attributes exist — scorer parity).

* Harvest (polite one-off, 2026-09-17, UA `home-finder-research/0.1`,
  paced >= 3–5 s, `--max-time` 60–180, no 429): GeoServer WFS
  `pta:msr_vork` (**1916 features**, 4.9 MB) +
  `pta:kehtetu_maaparandussysteem` (**785**) + `pta:msr_eesvool`
  (**1595**, 1125 LineString + 470 MultiLineString) in the Harju
  window. Raw GeoJSON kept at `/tmp/hf-616-cache` (PR record, not
  committed). Gotchas recorded: (1) WFS 2.0.0 + lat-lon bbox returns
  HTTP 200 with zero features on this service — the working recipe is
  WFS 1.0.0 + `typeName` + lon-lat bbox + `,EPSG:4326` suffix (KATRI
  recipe); (2) WITHOUT the suffix the server likewise returns silent
  empty, not an error.
* Polygon sidecar: `scripts/build/batch_maaparandus.py --vork <cached>
  --kehtetu <cached> --eesvool <cached> --snap <snap>` →
  `<snap>/drainage/drainage-areas.json` (zone_id/nimi/cls/ms_kood/
  ms_url + GeoJSON [lon, lat] exterior rings (`r`) or centerlines
  (`l`) + prefilter box — service cache is EPSG:4326 already, NO axis
  flip, pinned by test). Offline, stdlib-only. Rebuild: **4296
  shapes, 0 skipped** (1916 network + 785 invalid + 1595 outflow).
  ~8 MB sidecar (full float precision kept, EELIS precedent); served
  whole per /areas precedent.
* No raster master by decision (`MAAPARANDUS_NO_RASTER`,
  `MAAPARANDUS_NO_METRO`): shapes ARE the field — the points endpoint
  answers honestly-empty, windows serve county.
* Wiring: `DRAINAGE-HOOK (#616)` blocks in layers.ts (import/union/
  DECAY/LAYERS/TAGS/bonusSpecFor/fetchWindow skip), overlays.ts
  (marker `#1c1917` + legend), outlines.ts (`applyMaaparandusPolygons`
  match-expression fills + outflow line layer + slot incl. a
  dedicated outflow source id), server/snapshot.ts
  (`loadMaaparandusAreas` + raster/metro absent names), route.ts
  (honestly-empty points branch), new `/api/layers/maaparandus/areas`,
  page.tsx (fetch/paint/status `Maaparandusvõrk + eesvoolud · N
  kujundit (väljaspool = teadmata, mitte kuiv)`), ValueHeatMap
  (`maaparandusAreas` prop). Registry now 125 layers.
* Scorer parity: `MAAPARANDUS_CLASS_SCORE` mirrors the scorer legs
  (network 55 / invalid 40 / outflow-near 45); the map paints class
  fills + centerlines, never numbers or bands.

DoD evidence: `vitest` (new `layers_p4_maaparandus.test.ts` + painter
tests in `outlines.test.ts` + `test_batch_maaparandus.py`), full suites
green, typecheck clean — pasted in the PR. Screenshot:
`/layers?layer=maaparandus` network fills + outflow lines.

## Judgment calls (for the reviewer)

1. Layer id is `maaparandus`, NOT `drainage`: `drainage` is taken by
   the G03 open-water proximity proxy (points + raster + p50 scorer —
   reusing it would corrupt that layer). The new id carries
   `paramLabel P4-kuivendus` for buyer readability.
2. Mauve 
 
...[truncated 911 chars]
