# P4 POI meta-register verdict: audit SHIPS, layers GATED (issue #549)

Closes #549 — huvipunktid WFS cross-check + long-tail amenity upgrade.

Code: `services/scoring/dims_p4_poi.py` (agreement audit + 3 gated
long-tail dims); tests:
`services/scoring/tests/test_dims_p4_poi.py` (hermetic, fixture
counts/distances, no network).

## 1. Polite probe (2026-09-16, UA `home-finder-idea-probe/1.0`)

GetCapabilities only (no feature pull — per-type pulls belong to the
licence-day bulk job):

| Check | Result |
|---|---|
| URL | `https://gsavalik.envir.ee/geoserver/huvipunkt/wfs?service=WFS&request=GetCapabilities` |
| Result | **OPEN.** HTTP 200, 191 963 B, ~0.09 s. No 429, no key. |
| Feature types | **98** `huvipunkt:*` (full inventory in `HUVIPUNKT_TYPES`, names only — no points vendored): perearst/haigla/kiirabi, haridusasutus, raamatukogu, muuseum/teater/kino, ujula/supluskoht/spordihoone/staadion/tenniseplats, toitlustus, buss/rong/tramm/troll-peatused + terminalid, parkla, politsei/paastekomando, **ohtlik_ettevote**, **varjumiskoht**, hudrant/veevotukoht, kalmistu/kirik, sadam, matkarajad/terviserajad, post/pank, tervisekaubad… |
| CRS | EPSG:3301. updateSequence 1980. |
| Licence | **NONE confirmed** (no statement in capabilities; none in catalogue). **Gate holds: counts only, no points.** |

Harjumaa counts for 10 key types, per-type update stamps and CRS
validation of actual features need GetFeature pulls — deferred to the
licence-day job (single-probe budget spent; `agreement_audit()` ships
here so the job feeds counts straight into it).

## 2. Agreement-audit table: SHIPPED as a pure function

`agreement_audit()` maps caller-supplied {type, osm_n, reg_n} rows to
{verdict: register-rikkam / sarnane / osm-rikkam / võrdlus puudub} at
ratio edges 1.5 / 0.67 (pinned by test). The Harjumaa count table
itself is NOT pasted here — no feature pull was made, and inventing
counts would be fake precision. First bulk-job run pastes it into
this doc.

## 3. Long-tail shortlist (≥3, dense, no dedicated issue)

`raamatukogu` (libraries), `post` (post), `tervisekaubad`
(pharmacy-ish) — all in the observed 98, none owned by
#527/#528/#530/#531/#532. Walk bands ≤300/600/1000 m, NULL-beyond.
Dedicated split enforced by test (`DEDICATED_SPLIT`: perearst→#532,
haridusasutus→#530, spordihoone/staadion/ujula/tenniseplats/
supluskoht→#531, ohtlik_ettevote→#527, varjumiskoht/paastekomando→#528
— scored dims refuse these types with a "topeltarvestust pole"
reason).

## 4. Staleness note

Monthly intermediate layer ("vahekiht") over source registers of
varying vintage — every reason says so. Per-type staleness table is
licence-day work (first pulls record per-type stamps).

## 5. DoD evidence

```text
python3 -m pytest services/scoring/tests/test_dims_p4_poi.py -q
# → 9 passed (observed 2026-09-16, worktree 549-poi-register)
python3 -m pytest services/scoring/tests -q
# → full suite green, no regressions (see PR checks)
```

## 6. Licence-day addendum #612 (2026-09-16, UA `home-finder-research`)

Licence gate OPENED: the GetCapabilities Abstract applies the Maa-
ja Ruumiamet open spatial-data licence
(`https://geoportaal.maaamet.ee/avaandmete-litsents`, Fees/
AccessConstraints "puudub", no per-layer override) — scorer
`LICENCE_OK` flipped True, reasons stamp the licence (§5 tests
updated). The portal catalogue page is a JS shell (no readable
licence field), so the capabilities Abstract is the dated evidence.

Bulk pulls (type-bounded GetFeature + `mk='Harju maakond'` CQL, 2 s
pacing, raw XML in `/tmp/hf-612-poi/` only): raamatukogu 124,
post 536, tervisekaubad 187 — all plotted, zero coordless, zero
dropped. Builder `scripts/build/batch_poi.py` (monthly TTL) emits
`poi/poi-points.json` (lat/lon/slice only — names/addresses never
leave the builder). Map slices `poi_library` / `poi_post` /
`poi_pharmacy` reuse the dbands kernel with the exact scorer table
(≤300 m → 85, ≤600 m → 70, ≤1 km → 55, NULL-beyond).

Agreement audit (Harjumaa: OSM 2026-09-12 snapshot vs register
2026-09-16 — snapshot bbox runs slightly wider, so OSM counts are
upper bounds):

| type | OSM n | register n | ratio | verdict |
|---|---|---|---|---|
| raamatukogu | 86 (`derived-libraries`) | 124 | 1.44 | sarnane |
| post | 418 (`derived-postal`, boxes + offices + lockers mixed) | 536 (521 pakiautomaat + 12 kontor + 3 punkt) | 1.28 | sarnane |
| tervisekaubad | 180 (`derived-lastshop` amenity=pharmacy) | 187 | 1.04 | sarnane |

All three agree within the similar band — the OSM legs stay
trustworthy; the register adds coverage (libraries +44%). No layer
follows for dedicated-split types (split table enforced by test).

Staleness table (per-feature `andmeseis`, feed-level):

| type | stamps | source registers |
|---|---|---|
| raamatukogu | 03.11.2025 ×85, 17.11.2025 ×37, 21.11.2024 ×2 | Eesti Rahvusraamatukogu ×124 |
| post | 06.04.2026 ×159, 05.02.2024 ×126, 01.02.2024 ×120, 11.01.2024 ×75, 16.01.2024 ×49, older ×7 | Omniva ×159, DPD ×129, Maa-amet Internet ×128, SmartPOST ×120 |
| tervisekaubad | 04.09.2026 ×187 | Ravimiamet Apteegid ×187 |

Post-flip judgment (#612 title): post INCLUDES pakiautomaat —
lockers are the dominant postal access (521/536); offices-only
would fake scarcity. Stated in the legend + source note.
