# Measured winter-maintenance layer (issue #536)

The P4-018 "first pull": replaces/audits the fixture codelist behind
`docs/p4_trans.md` `winter_road_class` with the Eesti teeregister WFS
register leg (Transpordiamet, CC_BY_4.0, DAILY feed).

## Source

- Public WFS: `https://teeregister.mnt.ee/290424/wfs`
  (`?service=WFS&version=2.0.0&request=GetCapabilities`; guide:
  `teeregister.mnt.ee/reet/docs/Teeregistri_avalik_WFS_teenus.docx`)
- INSPIRE WFS: `https://inspire.geoportaal.ee/geoserver/TN_teeregister/wfs`
  (named alternative, not harvested)
- Map app: `xgis.maaamet.ee/xgis2/page/app/teeregister`
- Harvest cadence: DAILY portal feed → pull at most weekly/monthly
  (roads change slowly; polite automation per AGENTS.md §7).

## Openness probe (2026-09-16, custom UA, one GET each, no 429)

| Probe | Result |
|---|---|
| Public GetCapabilities | **OPEN, keyless**: HTTP 200 text/xml, 80339 B, **60 feature types**, all DefaultCRS **EPSG:3301** (road classes Põhi/Tugi/Kõrvalmaantee + Ramp/Muutee, `ms:teeosa` segments, `n_kate` surfaces, `n_kiiruspiirang` speeds, `n_seisund_talvine/suvine`, `n_liiklussagedus`, `n_kergliiklustee`, `n_murasein`, …) |
| Winter DescribeFeatureType | `ms:n_seisund_talvine` attrs: `hoolklt_hoolklt_xv` (class CODE) + `hoolklt_hoolklt_val` (label), tee_number/tee_nimi, km range, oids — **hooldusklass IS carried, no pivot needed** |
| Harjumaa-window hits | **568** winter segments (native EPSG:3301 bbox 430000,6575000,600000,6630000 — WGS84 bboxes returned 0, this WFS does not reproject the filter) |
| INSPIRE GetCapabilities | HTTP 200, 116572 B (RoadLink/Road/RoadSurfaceCategory/Roadwidth/NumberOfLanes) — reachable, not harvested |

Raw probe files: one-off `/tmp` working copies, never committed.

## Fixture-codelist audit (row-for-row, old vs. new)

| Old (`roadclass_p4` fixture, dims_p4_trans) | New (`roadwinter_p4` measured, this module) | Verdict |
|---|---|---|
| `maint_class` "1" → 85 | `hoolklt_hoolklt_xv` position "1" → 85 | band kept |
| "2" → 65 | "2" → 65 | band kept |
| "3" → 45 | "3" → 45 | band kept |
| "4" → 30 | "4" → 30 | band kept |
| unknown/missing → NULL | unseen raw values → NULL (`remap_maintenance_class` fails closed) | stricter, honest |

Bands unchanged (reviewer call per the issue — no evidence demands a
change). The value census (`hoolklt_hoolklt_xv` real codes) waits on the
first full pull; until then the remap is provisional and fails closed.
The two POI kinds never cross-score (pinned by
`test_fixture_kind_never_cross_scores`).

## Honest shape (checklist / bands, NULL stays NULL)

| Dim key | Window | Scored shape | NULL when |
|---|---|---|---|---|
| `winter_road_class_measured` | ≤ 150 m | klass 1→85, 2→65, 3→45, 4→30 (`hinnang`, teeregister-named) | no segment / unknown class — never a default class |
| `audit_surface_against` | — (audit, never a score) | match/mismatch/unknown vs. OSM proxy (register wins) | either side missing → unknown |

No traffic-volume claims (counters are DATEX-gated — explicitly out).
No winter-service quality scoring (class ≠ ploughing punctuality —
the legend must say so). No Tark Tee DATEX key requests in this issue.

Legend must say: "talvine hooldusklass (mõõdetud liidestus, allikas:
teeregister, CC BY 4.0) — klass pole sahkamise täpsus".

## Judgment calls (for the reviewer)

1. No pivot to "attribute cross-check": hooldusklass is present, so the
   issue's fallback is documented but not taken; surfaces ship as an
   audit helper instead of a faked band.
2. Provisional remap fails closed: unseen codes NULL rather than guess.
3. INSPIRE leg named but not harvested — one join, not two.
4. No shared-file edits: 3 new files only (`dims_roadreg_winter.py`,
   `tests/test_dims_roadreg_winter.py`, this note). p4_trans Tark Tee
   legs, Group 12/13/18 OSM proxies untouched. "Screenshot if mapped"
   N/A (scoring-only until the first full pull projects EPSG:3301).

## First-full-pull / reopening checklist

1. Harvest `ms:n_seisund_talvine` (weekly TTL) into the cache dir;
   project L-EST97 → WGS84; census `hoolklt_hoolklt_xv` values and
   confirm/extend `remap_maintenance_class`.
2. Harvest `ms:n_kate` for the surface audit on the same pull.
3. Re-probe GetCapabilities on reopen (type count drift); paste fresh
   evidence. Add the explicitly-flagged live integration test on that
   reopen PR (not a unit run).
