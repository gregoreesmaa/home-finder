# P4 silly bundle — trivial & silly amenity layers (issue #711)

Twelve micro-layers from the OSM extract already held. One bundle PR
(`apps/web/lib/layers_p4_silly.ts` + test + this doc). Zero new pulls,
zero new sources. All layers are markers-only `pins`
(fixit #623 precedent): dots mark MAPPED objects (hinnang), never
quality, never completeness.

## Probe (2026-09-19, no network)

Local held extract `/private/tmp/estonia-260914.osm.pbf`, osmium
tags-filter + export. Tallinn bbox: lon 24.45–25.0, lat 59.35–59.5.

| Checkbox | OSM tags | Tallinn count | Verdict |
|---|---|---|---|
| kirikukellad | amenity=place_of_worship | 97 | SHIP |
| kajakad | landuse=harbour 5 + amenity=marketplace 27 + landuse=landfill 4 | 36 | SHIP (gull food-spot proxy — gulls themselves are not mapped) |
| mänguväljakud | leisure=playground | 1874 | SHIP |
| koertepargid | leisure=dog_park | 89 | SHIP |
| saunad | leisure=sauna (amenity=sauna: 0) | 34 | SHIP (leisure=sauna is the mapped vocabulary) |
| talisuplus | leisure=swimming_area 19 + sport=swimming 53 | 72 | SHIP with caveat (no winter-swimming tag exists — mapped swim spots, talvehooldus teadmata) |
| tänavasport | leisure=fitness_station 319 + sport=skateboard 53 + sport=disc_golf 6 | 378 | SHIP (informal street sport only — register halls/pools stay in layers_p4_sport #607) |
| suvevesi | amenity=fountain 88 + amenity=drinking_water 74 | 162 | SHIP |
| WC | amenity=toilets | 205 | SHIP |
| AED | emergency=defibrillator | 11 | SHIP (hõre kaardistus, mitte tegelikkus — stated in title/legend/source) |
| raamatukapid | amenity=public_bookcase | 18 | SHIP |
| kalmistu | landuse=cemetery | 30 | SHIP (green-quiet hinnang, dB unmeasured) |
| targad pingid | — | — | DROP — OSM-s pole nutipinkide märgendit (tavalisi amenity=bench pinke on 14 555, aga "tarkust" ei kaardistata). |
| SUve häirikute komposiit | — | — | DROP — sääskedel ja STR-il pole kaardistatud allikat; osaline komposiit täisnime all oleks feik-täpsus. |

Counts are locked in `SILLY_PROBE` (pinned by
`layers_p4_silly.test.ts`); fallbackPoints are real mapped points from
the same probe (2–3 central-Tallinn points per layer, never invented).

## Wiring

Shared files touch the bundle only through marked `SILLY-HOOK (#711)`
blocks: `lib/layers.ts` (import, id union, decay, defs, tags,
bonusSpecFor), `lib/overlays.ts` (12 registry-unique marker colors +
Estonian legends), `lib/server/snapshot.ts` (raster names + metro
prefixes, all intentionally never built — `SILLY_NO_RASTER` /
`SILLY_NO_METRO` — plus the pins sidecar loader), `app/api/layers`
(route serves the sidecar, 200 snapshot / honestly-empty) and
`app/layers/page.tsx` (status names the extract, never the fixit
default). `paramIds` stays `[]` everywhere (P4 namespace — the
layers.md 1..500 audit untouched).

Serving (issue #774 option A — the "no sidecar by decision" verdict
is REVERSED: sample markers misrepresent layers with thousands of
mapped objects, so all twelve serve real points):
`scripts/build/batch_silly.py` builds `silly/silly-points.json`
(10 617 points, vintage 2026-09-14) from the held
`estonia-260914.osm.pbf` via `osmium tags-filter` (18 vocabularies,
all object types) + `osmium export`. Nodes serve directly, ways
serve their bbox-centre centroid (one marker per mapped object);
relations are outside the export. Dual-tagged objects classify once
— the probe's talisuplus 72 double-counted 19 swim spots tagged both
ways, the sidecar correctly serves 53 distinct points. OSM relations
and unmapped export artefacts never become points.

Status: served points ride `sillySnapshotStatus()` (`OSM väljavõte
(Eesti 2026-09-14, hinnang)`); transport failures still fall back to
the defs' real sample markers under `sillyDemoStatus()`
(`DEMO-näidis (näidispunktid, mitte loendus)`). Genuine load failures
keep the `DEMO-varu (live ebaõnnestus)` label.

## Screenshot

`docs/p4_silly_tallinn.png`: `/layers` page with the `kajakad` layer
active in central Tallinn (Vanasadam + Keskturg + Pärnamäe markers),
the layer-button group showing the bundle's checkboxes, legend entry
visible. (Screenshot predates option A — markers now render from the
served sidecar: 36 real kajakad points in the Tallinn view, status
`OSM väljavõte (Eesti 2026-09-14, hinnang)`.)
