# P4 DTM relief verdict note (issue #553)

Date: 2026-09-16. Scope: slope + relative elevation as area character
(klint, slopes, lowlands). Module
`services/scoring/dims_p4_relief.py`. No shared files touched.

## Openness verdict: OPEN service, provisional bands

Polite probes, custom `home-finder-probe` User-Agent, no 429s:

| Probe | Result |
|---|---|
| `GET teenus.maaamet.ee/ows/wcs-dtm?…GetCapabilities` | HTTP 200, 7376 bytes. Maa-amet, WCS 2.0.1, Fees/AccessConstraints none. Coverages `dtm-25`, `dtm-10`, `dtm-1` (no `dtm-5` — the issue's "1/5/10/25 m" list overstates the service). |
| `DescribeCoverage dtm-1` | HTTP 200, 2487 bytes. EPSG:3301, 1 m grid offsets, envelope N 6375000–6635000 / E 365000–740000, float32 GeoTIFF. No vertical datum stated (EH2000/BK77 conventional, UNVERIFIED — only relative differences + slope used). |
| One small window: `GetCoverage dtm-1 …SUBSET=y(6591000,6591200)&SUBSET=x(543800,544200)` (Lasnamäe klint edge, 400×200 m) | HTTP 200, 320664 bytes, valid uncompressed float32 TIFF — **all 80000 cells exactly 0.00, no voids**. Downtown-adjacent land cannot be uniformly 0 m: dtm-1 is void (0-filled) there or the window misses the patch. No second pull per budget. |

CAUTION: slope bands are PROVISIONAL until the harvest PR validates
windows against dtm-10/dtm-25 + tile layout and pastes Nõmme-slope and
Pirita-lowland histograms. Licence CC BY 4.0 (`ATTRIBUTION`); annual
vintage in every scored reason.

## Overlay-vs-leg split (no taste claim without a named taste)

| Shape | Content |
|---|---|
| Character overlay (`classify_character`, no score) | tasane / laanõlv / nõlv / järsak / klindiserv / madalik / kõrgendik |
| `dim_lowland_dampness` (flood-avoider, bad side) | flat + rel ≤ −2 m → 45 + flood-layer pointer |
| `dim_viewpoint` (view-seeker) | rel ≥ +15 m → 65, "näitab vaadet, mitte keeldu", no monetisation |
| `dim_cycling_effort` (cyclist) | ≥5° → 60, ≥10° → 45 + winter-slip note |
| `dim_klint_edge` (geotechnical check) | ≤200 m or steep+high → 50, "kuju, mitte keeldu" — never a ban |
| `dim_driveway_grade` (graduates the NULL) | measured slope → 50/65; kerbs/crowns stay buyer check |

Every steep reason states slope ≠ slide risk (no landslide scoring).
1 m resolves streets, not kerbs.

## p336 cross-check table (logic defined, live rate unmeasured)

`p336_agreement(osm_cliff_near, slope_deg)`: both-steep or
both-flat → `kokkulangevus`, else `lahknevus`, no slope →
`hindamata`. A log label for review, never a score. Harvest PR
measures the agreement rate over the klint edge before any p336
graduation merges.
