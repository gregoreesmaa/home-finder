# P4 microclimate-cells verdict note (issue #541)

Date: 2026-09-16. Scope: station-grain microclimate cells from the
Keskkonnaagentuur climate PostgREST (kliimaandmestik) — nearest-station
normals join (`services/scoring/dims_p4_kliima_stations.py`).

## Openness verdict: OPEN (keyless PostgREST JSON, CC BY 4.0)

Polite probes, one GET per endpoint, `home-finder-probe/1.0`
User-Agent, raw files at /tmp/hf-probes/ (one-off PR record, never
committed):

| Probe | Result |
|---|---|
| `GET .../f_kliima_jaam_vaatlus?limit=100` | HTTP 200, 54 050 bytes — station×element×period rows with `pikkuskraad`/`laiuskraad`/`korgus_merepinnast_m` |
| `GET .../f_kliima_jaam_vaatlus?select=jaam_kood,jaam_nimi,pikkuskraad,laiuskraad&limit=3000` | HTTP 200, 208 595 bytes — **25 distinct stations** nationwide (Harku … Võru) |
| `GET .../f_kliima_element?limit=200` | HTTP 200, 5 342 bytes — **25 elements** (daily DPA008/DPREC/DRH08/DRQS/DSDUR/DSND/DTAN/DTAX/DTA08/DWSX/DWS08; hourly PA0/PR1H/RH/SDUR1H/TA/TAN1H/TAX1H; 10-min WD10M/WD10MA/WSX1H/WS10M/WS10MA/WS10MX) |
| `GET .../f_kliima_kuu?aasta=eq.2023&kuu=eq.12&limit=10` | HTTP 200, 2 327 bytes — query pattern CONFIRMED (`jaam_kood`, `jaam_nimi`, `aasta`, `kuu`, `vaartus`, `element_kood`; sample Harku Dec-2023 DPREC 43.60 mm) |

Licence: CC BY 4.0 (catalogue). Attribution `CLIMATE_ATTRIBUTION`.
CONT feed → annual harvest (`CLIMATE_TTL_DAYS = 365`).

## Voronoi-vs-single-cell decision: CELLS (3 usable stations)

In/near Harjumaa: Tallinn-Harku (59.3981N 24.6029E, in), Pakri
(59.3895N 24.0401E, in), Kuusiku (58.9732N 24.7340E, Rapla ~8 km S of
the border, serving S-Harjumaa). 3 ≥ 3 → nearest-station cells, NO
interpolation (legend states it per score). Eastern Harjumaa falls to
the nearest of the three; Kunda stays out (Lääne-Viru). Normals window
1991–2020 (WMO).

## Honest-shape table (relative-rank dims on the joined distribution)

| Param | Climate slice consumed | Shape when joined (≥2 cells) | When missing |
|---|---|---|---|
| Winter mildness | frost-day 1991–2020 normals | mildest 70 / middle 55 / harshest 40 | NULL (EI OLE + ilmateenistus/ heating-bill check) |
| Wetness | annual-precip 1991–2020 normals | driest 70 / middle 55 / wettest 40 | NULL same |

No absolute cutoffs are hardcoded: 30-year normals need far more pulls
than a polite probe budget allows, so the harvest joins measured
normals and the dims rank them — bands justified ON the station
distribution, not beside it.

## Pairing rationale

- Normals vs nowcast: `dims_p4_ilm` (#308/#374, live Harku XML) stays
  the weather baseline; these dims are the climate-normals sibling.
  No double-score. `dims_p4_kliima` (strategy-PDF verdict) untouched.
- Never street-level, never forecasts (ilma­teeni­stus forecast
  products stay out); no heat-island tracing (human cross-check only).
- New files only, zero shared-file edits.

## Reopening checklist

1. Annual harvest: aggregate `f_kliima_kuu` 1991–2020 per station
   (frost days from DTAN, annual precip from DPREC) with paginated
   polite pulls; paste per-station normals in the harvest PR.
2. If a Harjumaa station goes silent (period end < harvest year),
   re-tally usable cells; <3 flips to single-row no-map per the issue.
3. Wind-rose stays owned by #308/#374 — do not re-derive here.
