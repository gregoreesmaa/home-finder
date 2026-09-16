# P4 sport-facility verdict note — measured register layers (P4-048)

> LIVE verdict for issue #531 (checked 2026-09-16). Overturns
> `docs/p4_recre.md` (#312) for the *venue* slice only (timetables/prices
> stay human-page checks). Scorers live in
> `services/scoring/dims_p4_sportreg.py`, pinned by
> `services/scoring/tests/test_dims_p4_sportreg.py`.

## Verdict

**Two live registers — four proximity dims ship (hall / field / pool x2).**
Neither bulk was ever probed in #312 (tallinn.ee human pages + RMK +
Teabevärav JS shell only).

## Openness evidence (one polite round, 2026-09-16)

Custom UA `home-finder-research/0.1`, single GETs, 429 = stop. Raw bodies
parsed in memory, aggregates only — never committed (AGENTS.md §5).

| Check | Observed | Meaning |
|---|---|---|
| `https://www.spordiregister.ee/opendata/files/spordiehitised.json` (HTTP 200, 21 259 733 B) | 4157 venues; 1216 Harjumaa; ALL 1216 with WGS84 `kaart_laius`/`kaart_pikkus` (0 coord-less); ALL `ehstaatus` "Spordialases kasutuses"; newest `esitatudkuupaev` **2026-09-15** | FRESH — the catalogue `updated` = 2022-11-23 flag is a stale catalogue page, the bulk is live |
| `http://vtiav.sm.ee/index.php/opendata/ujulad.xml` (HTTP 200, 262 833 B) | 226 `<ujula>`; 101 Harju/Tallinn; 219 with L-EST97 `<x>/<y>` (7 without, counted); tyyp üldkasutatav 94 / lasteasutus 52 / kool 32 / väike 22 / tervishoiuasutus 17 / väli 3 / muu 1 / empty 5; inspections 2026 x9 … 2018 x20 | Second pool leg with inspection vintage; same vtiav family #494 proved |

Harju `liik` top (full file): Võimla/hall 282, Välispalliväljak 190, Muu
sportimiseks kasutatav objekt 181, Muu vabas õhus 145, Muu spordiplats
46, Siseujula-combos 37, Staadion-combos 64, Tenniseplats 23, püsirada 29+.

## Slices (pinned by tests)

hall = `Võimla`…; field = Välispalliväljak/Staadion/Tenniseplats/püsirada/
vabas õhus/spordiplats; pool = Siseujula… (combo venues yield one POI per
slice); ujulad = every coord-carrying vtiav row (any tyyp). Unsliced:
"Muu … objekt", abihoone, non-active status rows. Bands ≤500 m → 80,
≤1 km → 65, ≤2 km → 50, beyond → NULL (straight-line ⇒ `linnulennult`
hinnang label). Ujulad projection verified against pyproj to 4 decimals
(Endla tn 4 → 59.430533, 24.736377).

## Licence + harvest

CC BY-SA 3.0 on both bulks (Spordiregister/Kultuuriministeerium,
Terviseamet/vtiav): attribute + share-alike. Annual harvest is plenty
for venues (TTL 365 d in-module).

## What stays open (not wired here)

- Timetables, prices, lane availability — human-page buyer checks.
- Indoor pool WATER quality — not scored (outdoor bathing water is #494).
- Hobby-education quality claims (haridussilm HTML) — explicitly out.
- OSM `dim_rec_special` (group 11) stays the fallback cousin.
