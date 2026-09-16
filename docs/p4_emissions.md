# P4 air-emission verdict note — honest avoidance proxy (P4-042 source side)

> LIVE verdict for issue #533 (checked 2026-09-16). The geocoded sibling
> `docs/p4_kesk.md` waited for: KOTKAS avaandmed JSON has permits but no
> coordinates — this INSPIRE WFS serves the same register WITH geometry.
> Scorers live in `services/scoring/dims_p4_emissions.py`, pinned by
> `services/scoring/tests/test_dims_p4_emissions.py`.

## Verdict

**Live WFS — one avoidance dim ships (inverted bands, hinnang).**
2804 Harjumaa emission points with L-EST97 geometry; no pollutant/fuel/
capacity columns exist, so no subtype slices (documented, never invented).

## Openness evidence (one polite round, 2026-09-16)

Custom UA `home-finder-research/0.1`, single GETs, 429 = stop.

| Check | Observed | Meaning |
|---|---|---|
| GetCapabilities (HTTP 200) | Title "INSPIRE (PF) - Eesti heiteallikad õhku (WFS)"; publisher Maa- ja Ruumiamet; CC0; one type `PF_heiteallikad:PF.ProductionInstallation` | Clean licence, single layer |
| DescribeFeatureType (HTTP 200) | inspireId localId/namespace/versionId, name, thematicId identifier+scheme, void status, geom — nothing else | **No pollutant/fuel/capacity** → no subtype slices |
| GetFeature resultType=hits (HTTP 200; `typeNames` plural — singular `typeName` 400s) | numberMatched 8220 EE-wide; 2804 with Harjumaa bbox (srsName EPSG:4326 required — native-bbox queries match 0) | Far above the <10-point no-map branch |
| GetFeature count=1 json (HTTP 200) | "Katlamaja" HEIT0000008, Point [616911.00, 6538107.99] EPSG:3301, "Last update: 2026-07-13" | Fresh IRREG vintage; native-CRS reader + stdlib LCC |

## Bands (inverted on purpose — near = avoid)

≤500 m → 35, ≤1 km → 50, ≤2 km → 65, beyond → NULL (never "clean air";
NULL reasons carry EI OLE + the #524 station check + kohapealne
jalutuskäik). Reasons name the nearest source (name + KOTKAS id).

## Licence + harvest

CC0 1.0 — Maa-amet/KOTKAS still attributed in legend + docs. Annual
harvest is plenty (TTL 365 d in-module).

## What stays open (not wired here)

- Measured exposure (#524 stations) — the complement, untouched.
- P4-042 chimney-smoke leg (dims_p4_paaste) — split-slice, untouched.
- KOTKAS login flows, permit-text NLP — explicitly out.
- Group 7 air proxies (p61/p62) stay fallback cousins.
