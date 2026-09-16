# P4 density/urbanity grid — openness verdict + taste-leg note (issue #554)

> Verdict date: 2026-09-16 (4 polite GETs, custom UA
> `home-finder density-probe/0.1 (issue 554)`, /tmp only, no 429).
> Code: `services/scoring/dims_p4_density.py` (3 taste legs);
> tests: `services/scoring/tests/test_dims_p4_density.py`
> (hermetic, fixture GML in the live schema shape, no network).

## Source

- Catalogue: `sources/inspire-pd-eesti-rahvastiku-tihedus-1x1km-wfs-8bcebb4b.md`
  (+ WMS twin; NUTS3 sibling explicitly out).
- Portal: https://andmed.eesti.ee/datasets/inspire-(pd)-eesti-rahvastikutihedus-1x1km-(wfs)
- Publisher: Land and Spatial Administration (source: Statistikaamet).
  Licence CC0_1.0 — Statamet/Maa-amet attributed in every reason.

## Probe (one GetCapabilities + one DescribeFeatureType + one bbox pull)

| Probe | Result |
|---|---|
| GetCapabilities | **OPEN, keyless**: HTTP 200 XML, 111218 B. One feature type `PD_rahvastikutihedus:PD.StatisticalDistribution`, title "INSPIRE (PD) - Eesti rahvastiku tihedus 1x1km (WFS)" |
| DescribeFeatureType | **OPEN**: HTTP 200, 4742 B. Per-square schema: `inspireid_identifier_localid` (e.g. S-10040), `value_statisticalvalue_value` (unit "person", method "count", domain "demography"), masked squares read 0 **with** `value_statisticalvalue_specialvalue_*` = INSPIRE `notApplicable`, reference period `periodofreference_xlink_title` |
| Harjumaa bbox pull (24.5,59.35,25.0,59.55, count=10; first attempt 400 on `typeName`, retried once with WFS-2.0 `typeNames`) | **OPEN**: HTTP 200 GML, 20 features. Live values 11 / 64 / 25 / 7 / 8 / 9 / 244 plus masked 0-squares carrying the `notApplicable` flag. **Reference period on every row: 1.1.2024 – 31.12.2024** |
| CRS | Default EPSG:3035 (ETRS89-LAEA); EPSG:3301 + EPSG:4326 offered |

## Same-or-different verdict vs. the §4 dated-negative bulk

**DIFFERENT — proceed.** `docs/layers.md` §4 + `docs/p4_rel2021.md` date
the *census-2021-vintage* 1 km bulk (the REL2021 open tree has no grid
level at all). This WFS serves a **maintained annual series with a 2024
reference year** — not the same bulk in a new dress. What carries over:
the masked-zero rule (0 + `notApplicable` flag → scorer None, never
0/100) and the vintage warning (now "2024 people ≠ 2026 people —
Lasnamäe infill, Rae growth", riding in every reason).

## Honest shapes (taste axis, never goodness)

| Leg | Dim key | Window | Scored shape | NULL when |
|---|---|---|---|---|
| Urbanist delight | `urbanist_delight` | nearest cell ≤ 750 m | density = delight, capped 75: ≤50→30, ≤500→45, ≤2000→60, ≤6000→70, else 75 | no cell join; masked square (privaatsusmaskeeritud, never 0/100) |
| Quiet-seeker delight | `quiet_delight` | nearest cell ≤ 750 m | density = cost, capped 80: ≤50→80, ≤500→65, ≤2000→50, ≤6000→35, else 25 | same |
| Services viability | `services_viability` | nearest cell ≤ 750 m | density floor, capped 70: ≤50→30, ≤500→45, ≤2000→60, else 70 (viability, not quality) | same |

Character overlay first: `cell_character` (rahulik hajaasustus /
äärelinn / eeslinn / linnaline / tihe süda, masked → "maskeeritud
hajaasustus") carries no score field. Bands justified on the Harjumaa
distribution (bbox-fringe live samples 7–244, dormitory ring in the low
hundreds, Lasnamäe/Õismäe core in the several thousands, masked rural
0+flag) — recalibrate on the first full pull if the histogram
disagrees. Never interpolate between squares.

Pull contract: annual TTL (`DENSITY_TTL_S = 365 d`); cache hit within
TTL makes NO request; single GET, no retries — HTTP 429/errors are a
stop signal. Transport errors and short bodies are never cached as
data. Scorers are network-free (proven by tests with urlopen stubbed
to raise).

## Judgment calls (for the reviewer)

1. DIFFERENT verdict rests on the reference period read off live rows
   (1.1.2024–31.12.2024), not on catalogue cadence claims.
2. The 400 on the first pull was a client param error (`typeName` vs
   WFS-2.0 `typeNames`), not a feed refusal — one corrected retry,
   then stop.
3. No livability.WEIGHTS splice and no `/layers` overlay here: one
   joint change across batches later (existing tests pin
   set(WEIGHTS) exactly). 3 new files only, zero shared-file edits.
