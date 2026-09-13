# P4 EELIS: Estonian Nature Information System verdict note (issues #287 + #360)

Demo (#287) implements the EELIS ingestion + P4-015 end-to-end;
coverage (#360) wires P4-024 / P4-030 / P4-053 off the same
ingestion. One PR closes both because the #360 body states coverage
"extends the demoed ingestion" with "no new plumbing expected": the
habitat/felling/emitter tables are same-snapshot extra tables
(P4-024 source (5), P4-030 source (6), P4-053 source (5)), not new
sources.

Scope guard: sibling legs stay out — P4-015 PPA theft stats,
insurer tariffs, Maa-amet surge layers, Päästeamet fire density;
P4-024 Terviseamet/PRIA/complaint legs; P4-030 NDVI/satellite/
raieloa legs; P4-053 Ilmateenistus wind-rose/complaint/harbour legs
(`livability.py`, WEIGHTS, all shared/group files unmodified;
3 new files only, `_eelis`-suffixed keys, no double-scoring).

## Openness verdict: POSITIVE (2026-09-13)

EELIS serves a public, keyless WFS documented at
https://keskkonnaagentuur.ee/eelis ("Avalik WMS/WFS teenus";
cat I/II species + habitats withheld by design). Polite evidence,
14 tiny requests total (custom UA, no scrape):

```
HEAD eelis.ee/                        -> 404 (Kestrel; app root, no data)
GET  keskkonnaagentuur.ee/eelis        -> HTTP 200, 97 242 B (names the WFS)
GET  .../geoserver/eelis/ows?...GetCapabilities
                                       -> HTTP 200, 186 232 B, 104 types
resultType=hits, Tallinn BBOX (lat 59.35-59.65, lon 24.55-24.95):
  kr_yleujutusohuga_ala  -> 0   (16 nationwide: flood leg wired, Tallinn-empty)
  kr_kaitseala           -> 33
  niidud                 -> 44
  kaadamisalad           -> 1
  kr_puhasti             -> 33
  kr_jaakreostus         -> 38
GET count=1 GeoJSON sample (srsName=EPSG:4326) -> HTTP 200, 834 B:
  server reprojects L-EST97 -> WGS84 itself (no coord math in ingestion)
```

Raw headers/pages: `/tmp/eelis-open/` (one-off PR record, not committed).
Pull contract: max 1 pull (6 small GETs) / 365 d per cache dir
(`EELIS_TTL_S = 31536000`, parameters4.md P4-015 TTL annual; the
coverage legs ride the same annual ticket — zones, meadows,
fellings and emitter registers change on planning/permitting
cadence, not weekly), single GETs, no retries — HTTP 429/errors
are a stop signal. Failed layers store empty tables + `layer_ok:
false` (transport errors are never data); all-layers-fail caches
nothing.

## Honest shapes per param (checklist / bands, NULL stays NULL)

| Param | Dim key | Window | Scored shape | NULL when |
|---|---|---|---|---|
| P4-015 insurability (demo, EELIS leg) | `kindlustus_eelis` | flood ≤ 300 m, kaitse ≤ 500 m | flood→35 tariff + illiquidity flag, kaitse→55 restriction + illiquidity flag, measured clear→85 (prints flood-empty caveat) | no snapshot / no zone rows / beyond window |
| P4-024 habitat (EELIS leg) | `maaloodus_eelis` | habitat cell ≤ 500 m | near→55 tick-caution (proxy, never species claim), clear→80 | no snapshot / no habitat rows / beyond window |
| P4-030 change flag (EELIS leg) | `rohemuutus_eelis` | felling ≤ 500 m | hit→45 + register year when known, clear→80 | no snapshot / no felling rows / beyond window |
| P4-053 sector (EELIS leg) | `lohnasektor_eelis` | emitter ≤ 1500 m | ≤500 m→40, ≤1500 m→60, reason names emitter + liik + octant + distance + wind-unmeasured caveat; clear→80 | no snapshot / no emitter rows / beyond window |

Measured values score; missing joins stay NULL. Beyond-window is
unknown, never calm/clear/clean. Every scored reason says `hinnang`
with components; every NULL reason says `EI OLE` and names the
missing input. Zone rows join by nearest labelled centroid within
the window (point-in-polygon stays a future-adapter job, P4-023
precedent in `dims_p4_trans.py`) — distance gates, the LABEL scores.

## Judgment calls (for the reviewer)

1. Demo + coverage in one PR: #360 defines coverage as extending the
   demo ingestion — one snapshot, five tables, six WFS layers.
2. Flood leg wired but Tallinn-empty TODAY (0 hits in the verified
   BBOX, 16 nationwide): it scores nothing and the clear band says
   so instead of claiming flood-clear. If the layer gains Tallinn
   polygons, the dim scores them with zero code change.
3. No literal "rohevõrgustik" layer exists in the 104 served types,
   so P4-024 uses niidud polygons as the coarse tick-habitat proxy
   (cells only, "mitte liigiväide" in every hit reason).
4. P4-053 is sector + distance, never a rose: no wind-frequency or
   schedule data exists here, so there is no calendar leg yet and
   every hit reason states wind is unmeasured.
5. Bands (35/55/85, 55/80, 45/80, 40/60/80) and all four windows are
   first-cut judgments with no live calibration; MUST be
   recalibrated from a real Tallinn pull on reopen.
6. No Overpass fragment / tag mapping staged: OSM has no honest tag
   for EELIS zone ids or emitter registers (group20a no-map
   precedent).
7. No shared-file edits; central hook (snapshot feed + WEIGHTS
   rebalance) stays one joint change across all batches.

## Layer #488 (polygon overlay off this snapshot)

`eeliskaitse` (P4-015) + `eelisniit` (P4-024) + `eelisraie` (P4-030)
visualize the kaitse/habitat/felling tables as zone-membership
choropleths (`apps/web/lib/layers_eelis.ts`, sidecar
`eelis/eelis-areas.json` via `scripts/build/batch_eelis_poly.py`):
inside-a-named-polygon vs outside/unknown, never a gradient, no score
field. The scorer above is untouched (NULLs stay NULL); the flood
table stays out (owned by the #487 floodzone overlay) and the emitter
register stays out (point locations, no honest polygon — the P4-053
sector dim stays scorer-side).

## Reopening checklist (when the map needs live data)

1. Re-run the probes above; paste fresh evidence.
2. Pull one snapshot (`fetch_eelis_snapshot`) and confirm the
   Tallinn counts per layer (esp. whether the flood layer gained
   Tallinn polygons).
3. Recalibrate bands + windows from the real pull.
4. Add the explicitly-flagged live integration test (not a unit run).
5. True point-in-polygon adapter (listing → containing zone at
   ingest) replaces the nearest-centroid gate.
