# Waste-site avoidance layer (issue #534)

Honest avoidance proxy (`hinnang`) off the INSPIRE US jäätmekäitluskohad
WFS (waste-treatment/disposal **sites** — not p54 collection points).

## Source

- WFS: `https://inspire.geoportaal.ee/geoserver/US_jaatmekaitlus/wfs`
  (`?service=WFS&version=2.0.0&request=GetCapabilities`)
- Publisher: Land and Spatial Administration. Licence **CC0_1.0**
  (attributed here + in the map legend all the same).
- Portal: https://andmed.eesti.ee/datasets/inspire-(us)-eesti-jaatmekaitluskohad-(wfs)
- Update: IRREG → annual re-probe, no live calls in the scoring path.
- Temporal coverage from 2020-10-12.

## Openness probe (2026-09-16, custom UA, one GET each, no 429)

| Probe | Result |
|---|---|
| GetCapabilities | **OPEN, keyless**: HTTP 200 application/xml, 108487 B. Title "INSPIRE (US) - Eesti jäätmekäitluskohad (WFS)" (KKR/Keskkonnaregister feed: collection, treatment, processing, storage) |
| Feature type | `US_jaatmekaitlus:US.EnvironmentalManagementFacility` ("Eesti jäätmekäitluskohad"), DefaultCRS **EPSG:3301** (L-EST97) |
| Harjumaa-window hits (`resultType=hits`) | **1301 sites** (bbox lat,lon 58.9,23.5,60.0,25.6 — window slightly larger than Harjumaa proper; first lon,lat attempt returned 0 — WFS 2.0 uses lat,lon order for EPSG:4326) |
| DescribeFeatureType | inspireId, `name`, `currentStatus` + `type` + function activity/input/output (INSPIRE codelist href+title pairs — **no flat site-type codelist**, so the scorer echoes a harvest-normalised `site_type` label verbatim instead of enumerating unseen values), thematicId, validFrom/validTo, geom |

Raw probe files: one-off `/tmp` working copies, never committed.

## p54 distinction

p54 (`layers_batch10c.ts`) maps waste **collection points** (~1531
neighbourhood containers, OSM `amenity=waste_disposal`/`recycling`, POI
kind `wastepoint`) — nearby containers are a *convenience*. This register
holds treatment/disposal **sites** (POI kind `wastesite`) — odour,
heavy-truck traffic, resale stigma. Different phenomenon and scale:
a `wastepoint` never scores as a `wastesite` (pinned by
`test_p54_distinction`).

## Honest shape (checklist / bands, NULL stays NULL)

| Dim key | Window | Scored shape | NULL when |
|---|---|---|---|---|
| `waste_site` | ≤ 2 km | ≤500 m→35, ≤1 km→55, ≤2 km→70 (`hinnang`, never measured odour; harvest `site_type` named when known) | beyond 2 km / no join — never "no smell"; NULL reason carries `EI OLE` + kohapealne vaatlus (tuul, lõhn) check |

Legend must say: "jäätmekäituskoha lähedus (hinnang, allikas: INSPIRE US
jäätmekäitluskohad, CC0) — kaugus pole lõhnamõõt".

## Judgment calls (for the reviewer)

1. Scoring-only, no web layer file: positions arrive via the WFS join
   (EPSG:3301 → WGS84 projection is an explicit integration step), not
   via snapshot tags — nothing honest to render yet. "Screenshot if
   mapped" therefore N/A; bands + NULL-beyond are pinned by tests.
2. Site-type values are echoed, not enumerated: the schema carries
   codelist hrefs, and inventing the value list would be fake precision.
3. The 1301 count is a window count, not a Harjumaa exact tally — stated
   as measured, not rounded into false exactness.
4. No shared-file edits: 3 new files only (`dims_waste_sites.py`,
   `tests/test_dims_waste_sites.py`, this note). Central hook
   (POI kind + WEIGHTS rebalance) stays one joint change across batches.

## First-full-pull / reopening checklist

1. Harvest the feature type into the cache dir (annual TTL); project
   L-EST97 → WGS84; normalise `type`/`function` codelist titles into the
   scorer-side `site_type` label.
2. Re-probe GetCapabilities annually; paste fresh evidence on the reopen PR.
3. Calibrate `WASTE_BANDS` from complaint-distance data if ever available
   (until then the bands are stated judgment, not measurement).
