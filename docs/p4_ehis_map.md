# P4 EHIS school-proximity verdict note — measured register layer (P4-011)

> LIVE verdict for issue #530 (checked 2026-09-16). Overturns the
> dated-negative of `docs/p4_ehis.md` for the *proximity* question only
> (the per-linnaosa capacity table there stays missing). Scorers live in
> `services/scoring/dims_p4_ehis_map.py`, pinned by
> `services/scoring/tests/test_dims_p4_ehis_map.py`.

## Verdict

**Live measured register — three proximity dims ship.**
The EHIS buildings bulk endpoint serves every school building with an
address, an EHR code, an ADS address id, AND L-EST97 coordinates; the
institutions bulk serves the type classifier (`<tyyp>`) and the
active/closed flag (`<staatus>`). 95.1% of Harjumaa building rows place
as-is; the rest stay out with counts. No map wiring here (batch
convention: scorer + tests + note, zero shared-file edits); a future
harvest job feeds caller POIs from `parse_hooned_xml`.

## Openness evidence (one polite round, 2026-09-16)

Custom UA `home-finder-research/0.1`, single GETs, 429 = stop. Raw bodies
parsed in memory, aggregates only — never committed (AGENTS.md §5).

| Check | Observed | Meaning |
|---|---|---|
| `http://enda.ehis.ee/avaandmed/rest/hooned` (HTTP 200, text/xml, 1 093 076 B, `vastuseLoomiseAeg` 2026-09-16) | 2180 `<hoone>` rows; 739 Harju; 703 with `<koordinaatX/Y>` (x = northing, y = easting); every row has `<ehrKood>`, `<adsOid>`, `<adsAdrId>`, `<aadress>`; `peahoone` jah 935 / ei 1245; `tegevusloaAsukoht` jah 987 / ei 1193 | 95.1% of Harjumaa rows placeable as-is; 36 coord-less rows excluded + counted |
| `.../rest/oppeasutused/-/-/-/-/-/-/-/-/-/-/0/0/XML` (HTTP 200, text/xml, 12 628 175 B, same-day vintage) | 5689 institutions; `<staatus>` Registreeritud 3976 / Suletud 2217; ZERO `oppekeel`/`keel` tags in 12.6 MB | Type classifier + active filter joinable; **language slices impossible** — documented, never guessed |

Type distribution (`<tyyp>`, full file): täienduskoolitusasutus 2516,
huvikool 1231, põhikool või gümnaasium 804, lasteaed 405, koolieelne
lasteasutus 238, lastehoid 118, noortelaager 116, kutseõppeasutus 114,
filiaal 88, rakenduskõrgkool 38, ülikool 16, Määramata 5.

## Slices (pinned by tests)

| Slice | tyyp values | Note |
|---|---|---|
| school | põhikool või gümnaasium | incl. lasteaed-põhikool alamTyyp rows |
| kindergarten | lasteaed, koolieelne lasteasutus, lastehoid | queue stays a Haridusamet buyer check |
| hobby | huvikool | incl. 444 spordikool + 173 muusika- ja kunstikool rows — SCHOOLS, not #531 venues |
| unsliced (never scored) | täienduskoolitus, kutseõpe, kõrgkoolid, noortelaager, filiaal, Määramata + every Suletud row | adult/seasonal/closed ≠ family-buyer proximity |

Bands (straight-line haversine ⇒ reasons say `hinnang (linnulennult,
mitte marsruut)`): ≤500 m → 80, ≤1 km → 65, ≤2 km → 50, beyond → NULL
(never "bad school", only distance). Projection: local stdlib
inverse-LCC copy of `scripts/build/batch_tervise.py`, verified against
pyproj EPSG:3301→EPSG:4326 to 6 decimals on probe rows
(Nõmme tee 49 → 59.415698, 24.719748); GRS80~WGS84 ~1 m gap stamped.

## Licence + harvest

CC BY-SA 3.0 (EHIS / Haridus- ja Teadusministeerium): attribute +
share-alike on derived-data notes. CONT feed — quarterly harvest is
plenty for buildings (TTL 90 d in-module).

## What stays open (not wired here)

- Per-linnaosa capacity table (`docs/p4_ehis.md`) — still missing.
- Haridusamet queue legs (`docs/p4_haridus.md`) — untouched.
- Language-of-instruction slices — impossible until EHIS publishes a
  language column; re-probe the institutions bulk, then slice.
- OSM school layers (group 15: p12, p123, p130, p314, p386) stay the
  fallback cousins; this register measures them once harvested.

## Map graduation (#608, 2026-09-16)

Three `/layers` overlays ship the slices: `ehis_school`,
`ehis_kindergarten`, `ehis_hobby` (`apps/web/lib/layers_p4_ehis.ts`,
paramIds [] + paramLabel P4-011). Harvester
`scripts/build/batch_ehis.py` (quarterly TTL, polite, 429 = stop)
joins hooned rows to institution slices via `<oppeasutusId>` and
builds the snapshot sidecar `ehis/ehis-points.json`: 618 Harjumaa
points (school 239 / kindergarten 369 / hobby 10 — the hobby slice is
thin: huvikool institutions without their own coord-carrying Harju
building place nowhere, stated on the legend); dropped 1179
other-county + 355 closed/unsliced-institution + 28 coordless, all
counted (zero closed-institution buildings in the Harju set; every
`<oppeasutusId>` resolved). Harjumaa membership = `<aadress>` naming
Harju maakond (the feed's own county label — 738 rows, matching the
verdict's 739 within one row). Kernels are the exact scorer bands
(≤500 m → 80, ≤1 km → 65, ≤2 km → 50, beyond NULL — straight-line
`linnulennult` hinnang, no smoothing, no raster master by documented
decision, sport #607 dbands kernel reused). The OSM `schools` layer
keeps its own tuning (never re-tuned here); Spordiregister venues
(#607) stay a separate signal (schools ≠ venues — no double-score).
