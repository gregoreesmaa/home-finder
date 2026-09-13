# Overturn hunt log — G8 flood polygons per-parcel join (issue #239)

> Time-boxed source hunt for Group 8 no-map set (parameters3.md §5.8):
> p46/p112/p117, p118/p182, p371/p372, p377/p378/p429
> (p69/p255/p333/p334/p336/p447 already ship as proxies and are
> untouched).
> Hunted 2026-09-13 (~40 min). **Verdict: PARTIAL overturn** — the
> KAUR/EELIS WFS carries exactly one open flood polygon layer with
> a verified schema and polite BBOX-filtered ingest, so **p112 gains
> the honest per-parcel zone-JOIN shape** (proven on fixtures in
> `services/scoring/dims_overturn_flood.py`, pinned by
> `services/scoring/tests/test_dims_overturn_flood.py`); the other
> nine params **KEEP the NULL** with dated reasons. Production
> Tallinn joins are empty (zero polygons in-market, no T-bands), so
> no GROUP08 verdict flips until a T-band feed appears in-snapshot.
> Re-check the WFS layer list and CEMS gating no later than
> **2027-03-13**.

## Verdict

**One open feed, narrowly scoped.** `eelis:kr_yleujutusohuga_ala`
is a 16-feature OBJECT register (ministerial list of water bodies
with large flood areas), not T10–T1000 hazard polygons: the schema
carries no return-period or band attribute, and the Tallinn market
window holds zero of its polygons. That supports a per-parcel
zone-MEMBERSHIP join for p112 (inside a named polygon vs
outside/unknown — a choropleth fact, never a gradient), and nothing
else. EFAS/GloFAS stay a dated negative (registration-gated CEMS
app, no anonymous bulk).

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

8 tiny requests total (single GETs/HEADs, labelled one-off
user-agent `home-finder KAUR-EFAS overturn check issue #239`,
paced ≥ 5 s, capabilities/storefront scope only, no form
submissions, no XHR probing, no login attempts). Raw bodies:
/tmp/hf-239/ (one-off PR record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `GET gsavalik.envir.ee/geoserver/eelis/wfs?service=WFS&request=GetCapabilities` → 200, 186 232 B, `application/xml` | 104 feature-type names; exactly one flood layer: `eelis:kr_yleujutusohuga_ala` ("KKR Üleujutusohuga ala"); zero names matching T10/T50/T100/T1000/surge/risk | No open T-band hazard polygons on the KAUR WFS |
| `DescribeFeatureType eelis:kr_yleujutusohuga_ala` → 200, 1751 B | Attributes: shape + sys_id + versioon + id + nimi + kr_kood + vveekogu/sveekogu + tyyp; geometry `gml:GeometryPropertyType` | No return-period/band field: every row carries the single constant tyyp "Suurte üleujutusaladega siseveekogu" |
| `GetFeature resultType=hits` (national) | `numberMatched="16" numberReturned="0"` | Object register: 16 water bodies nationally |
| `GetFeature count=2` sample → 712 176 B | `gml:Polygon` in EPSG:3301 (L-EST97); nimi "Mullutu-Suurlaht kogu kalda ulatuses" (Saaremaa), "Suur-Emajõgi koos vanajõgedega kogu ulatuses" (Tartumaa) | Water-body objects with heavyweight polygons (national pull is multi-MB — fetch defaults to the Tallinn BBOX) |
| `GetFeature resultType=hits&bbox=24.4,59.2,25.5,59.7,EPSG:4326` | `numberMatched="0"` | ZERO polygons intersect the Tallinn market window |
| `https://www.efas.eu/` → 301 → `https://european-flood.emergency.copernicus.eu/` → 200, 4034 B, visible text only "CEMS-Floods React" | JS-only SPA shell | Forecast grids/downloads live behind the registration-gated EFAS-IS app — no anonymous per-parcel bulk (polite stop) |
| `https://www.globalfloods.eu/` → 301 → `https://global-flood.emergency.copernicus.eu/` → 200, 4034 B, same shell | Same gating | GloFAS likewise a dated negative |
| `https://keskkonnaportaal.ee/et/avaandmed` → 200, 163 537 B | Documents EELIS + Geoserver WMS/WFS services (matches the #285/#359 reading) | Portal confirms the WFS route; no separate per-parcel bulk URL on the page |

Judgment call: the check stopped at storefront/capabilities level
on purpose — no EFAS-IS XHR probing, no download-form enumeration,
no blind guessing of further WFS typeNames (each miss is load on a
state GeoServer). Deeper probing is exactly the scraping this repo
refuses (AGENTS.md §5).

## What flipped vs stayed NULL

| Param | Verdict | Why |
|---|---|---|
| p112 flood history/elevation | JOIN SHAPE (`dim_floodzone_p112`): 25 inside a named polygon, NULL outside | Zone membership is the honest choropleth; fixtures prove the wiring |
| p46 environmental risks | NULL keeps | Object register is not an incident register |
| p117 sea level rise | NULL keeps | No DEM, no CMEMS/IPCC curve on the layer |
| p118 drought | NULL keeps | No soil attributes anywhere on the layer |
| p182 prevailing wind | NULL keeps (permanently unmappable) | Uniform regional SW flow; direction is not goodness |
| p371 burn scar | NULL keeps | Needs EFFIS perimeters, not flood objects |
| p372 buyout history | NULL keeps | Needs a payout register |
| p377 frost heave | NULL keeps | Needs a geotechnical survey |
| p378 saltwater intrusion | NULL keeps | Needs well-salinity series |
| p429 zone creep | NULL keeps | Single-version register; no time series |

Outside-every-polygon stays NULL, never "dry/clear": the layer is
an object register with zero Tallinn polygons, not a hazard model
(OTA PR #131 precedent). The scored reason says `hinnang` +
`tsooniliide` and names the zone (nimi + kr_kood); every NULL
reason says `EI OLE` and names the missing input + buyer check.

## Near-miss proxies considered and refused

- **Water proximity as flood risk** (re-skin of p50 drainage):
  refused — the scored reason states `mitte drenaaži-/
  tänavaproksi`, and distance plays no role (centre and edge of a
  polygon score alike, pinned by test).
- **Shore distance as sea-rise projection** (re-skin of p334/p340):
  refused — p117 stays NULL; coastline distance fakes projection
  precision (nomap.md §3 G8).
- **"Contractor/notice exists" or EFAS forecast presence as a zone**:
  refused — forecast grids are 5 km model output behind a login,
  not per-parcel zones.
- **Scoring Tallinn parcels off the 16 national polygons by
  nearness**: refused — nearest-object distance to a Saaremaa lake
  is not a Tallinn flood fact; only containment scores.

## Sibling split (no overlap, no double-scoring)

- `dims_p4_kaur.py` (#285/#359) owns the parameters4 P4-015
  insurability leg (`kaur_zone_p4` POIs, `_kaur` keys) — untouched,
  and this module uses distinct `flood_zone_overturn` POIs and
  `_overturn_flood` keys (kind-collision pinned by test).
- `dims_group08a-d.py` (#167–#170) own the G8 proxies + NULLs —
  untouched. `livability.py`, WEIGHTS, `parameters3.md`,
  `docs/nomap.md` untouched (final docs-index PR owns nomap.md).

## What stays open (overturn path, not wired here)

A T10–T1000 (or 10/50/100/1000-yr) polygon typeName appears in the
WFS capabilities (then one BBOX-filtered pull tests the join and
FLOOD_ZONE_SCORE is recalibrated per band), or CEMS opens an
anonymous per-parcel EFAS extract → re-open #239 and propose the
banded choropleth (bands + Tallinn histogram + master, per
docs/nomap.md §2). Re-check by RECHECK_AFTER (2027-03-13).
