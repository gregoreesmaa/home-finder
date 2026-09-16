# Soil/garden suitability scorer (issue #535)

Documented per-parcel join scorer dim first (G3 cadastre family) off the
Maa-amet mullastiku kaart WFS — the soil DB whose absence `docs/nomap.md`
§G3 verified ("p68 soil — no soil DB"). Direct, named overturn probe.

## Source

- INSPIRE WFS: `https://inspire.geoportaal.ee/geoserver/SO_pinnas/wfs`
  (`?service=WFS&version=2.0.0&request=GetCapabilities`)
- Memoir: `geoportaal.maaamet.ee/docs/muld/mullakaardi_seletuskiri.pdf`
  (Tallinn 2001, 46 pages)
- Publisher: Land and Spatial Administration. Licence **CC BY 4.0**
  (attributed here + in the legend).
- Update: IRREG → annual re-probe, no live calls in the scoring path.

## Openness probe (2026-09-16, custom UA, one GET each, no 429)

| Probe | Result |
|---|---|
| GetCapabilities | **OPEN, keyless**: HTTP 200 application/xml, 106411 B |
| Feature type | `SO_pinnas:SO.SoilBody` ("Eesti mullastiku kaart"), DefaultCRS **EPSG:3301** (L-EST97) |
| DescribeFeatureType | inspireId, `soilBodyLabel` (the šifr), beginLifespanVersion, isDescribedBy, geom — **no texture/humus/stoniness columns**: texture is decoded from the šifr via the memoir legend (lisa 3), offline at harvest |
| Harjumaa-window hits | **86474** polygons (lat,lon 58.9,23.5,60.0,25.6) — dense + discriminating rural coverage |
| Tallinn-bbox city-gap | **2226** intersecting polygons (59.35,24.55,59.50,24.95) — NONZERO fringe spill, so the gap is parcel-level (Kesklinn core unmapped, city soil is fill), not a bbox claim |
| Memoir PDF | HTTP 200 application/pdf, 843914 B — §V Tabel 1 (pdf lk 9, Kačinski texture classes), legend lisa 3 (pdf lk 46) |

Raw probe files: one-off `/tmp` working copies, never committed.

## Honest verdict

For detached-house / garden-plot buyers outside the city (Viimsi, Harku,
Saku, Kiili): drainage, foundation, gardening soil. Inside Tallinn the
map is not valid by construction — urban joins stay NULL (never zero).
No Tallinn soil map exists; the gap IS part of the finding. A
walk-graph raster is NOT shipped (rural-parcel phenomenon; OTA PR #131).
A rural-only proxy overlay waits on harvest density proof — not claimed
here.

## Class→band mapping (stated hinnang, memoir-calibrated)

| Family (harvest-decoded) | Score | Memoir ground |
|---|---|---|
| saviliiv (sl, 10–20% savi) | 85 | balanced garden + foundation |
| liiv (l/pl/tl, 0–10%) | 70 | free-draining, droughty |
| liivsavi (ls1/ls2, 20–40%) | 65 | workable, drainage care |
| leede (L) | 55 | acidic forest sand |
| paepealne/rähkne (Kh/Kr) | 50 | thin on limestone |
| savi (s, 40–85%+) | 40 | shrink-swell, kuivendus vajalik |
| glei (G) | 30 | waterlogged |
| turvas (T) | 25 | settlement risk |

Unknown/absent family → NULL (never guessed). No agronomic-yield claims,
no contamination claims (KIK/E-KIK territory).

## Honest shape (checklist / bands, NULL stays NULL)

| Dim key | Window | Scored shape | NULL when |
|---|---|---|---|---|
| `soil_suitability` | ≤ 300 m | family bands above (`hinnang`, 1:10 000; raw šifr named) | no join / urban-flagged / unknown family — never 0; NULL reason carries `EI OLE` + mullakaardi check |

Legend must say: "mulla sobivus (hinnang, 1:10 000, allikas: Maa-amet
mullakaart, CC BY 4.0) — servatäpsus piiratud, linnas ei kehti".

## Judgment calls (for the reviewer)

1. The scorer reads a harvest-decoded `family`, never raw šifrid —
   parsing codes here would fake legend knowledge (lisa 3 decoding is
   an explicit harvest step).
2. NULL-in-cities is a conservative design rule (fill soil + scale), not
   a "zero polygons" claim — the measured 2226 fringe intersects are
   stated, not hidden.
3. No shared-file edits: 3 new files only (`dims_soil_map.py`,
   `tests/test_dims_soil_map.py`, this note). p50 / p332 / p340 cousins
   untouched. Central hook + projection stay one joint change.

## First-full-pull / reopening checklist

1. Harvest SO.SoilBody into the cache dir (annual TTL); project
   L-EST97 → WGS84; decode šifr → `family` via legend lisa 3; apply the
   city mask → `urban` flag.
2. Re-probe GetCapabilities annually; paste fresh evidence on reopen.
3. Recalibrate bands from foundation-claim/drainage data if ever joined
   (until then: stated judgment, not measurement).
