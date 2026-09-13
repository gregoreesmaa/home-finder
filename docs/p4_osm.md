# P4 OSM (Tallinn extracts) — demo #280 + coverage #354 verdict note

Source demoed: OpenStreetMap Tallinn/Harjumaa extracts via Overpass
(no live calls in the map path; network lives in
`livability.fetch_pois`, cached 30 d).

## 1. Openness (#280 AC1) — POSITIVE, dated 2026-09-13

OpenStreetMap data is open under the ODbL. Verbatim from
https://www.openstreetmap.org/copyright (fetched 2026-09-13, HTTP 200):

> "OpenStreetMap is *open* data, licensed under the Open Data Commons
> Open Database License (ODbL) … You are free to copy, distribute,
> transmit and adapt our data, as long as you credit OpenStreetMap and
> its contributors."

No dated negative — the demo proceeds on OSM extracts. (The P4-029
primaries Mapillary/KartaView stay out of the snapshot: token-gated
imagery is crossed only via the OSM sidewalk/surface ground-truth
check, stated in every P4-029/P4-040 reason.)

## 2. Polite pulls + cache + TTL (#280 AC2)

Reused unchanged from `livability.py` (no new network code in
`dims_p4_osm.py`, asserted by test):

- Mirrors: 3 Overpass endpoints with per-mirror timeout
  (`OVERPASS_URLS`, `livability.py:48-53`).
- Politeness: 1.2 s gap after calls per the Overpass usage policy
  (`livability.py:541`); query `timeout:25`.
- Cache: 30-day POI cache (`OVERPASS_TTL_S = 30*24*3600`,
  `livability.py:45`); transport errors are never cached as data
  (`_Transient`, `livability.py:549-556`).
- New fragment `P4_OSM_OVERPASS_FRAGMENT` uses the same `{lat}/{lon}`
  placeholders and inherits the same TTL on integration.

## 3. Extract tag verification (osmium, Harjumaa 2026-09-11 PBF, 2026-09-13)

| tag | objects | verdict for |
| --- | --- | --- |
| highway=crossing 12 348; traffic_calming 4 860 | viable | P4-012 proxy |
| amenity=parking 78 071 | viable | P4-013 proxy |
| lit=yes 145 725; sidewalk key 16 846; highway=footway 166 990; surface=asphalt 303 336 | viable | P4-029/P4-035/P4-040 proxies |
| entrance 4 973; wheelchair 22 305 | viable | P4-049 proxy |
| shop=bakery 70; tourism=gallery 81 / museum 601; amenity=cafe 705 / library 175; leisure=sauna 143; amenity=atm 224; shop=supermarket 1 199 / convenience 1 099; amenity=pharmacy 294 | sparse but real (caps + caveats) | P4-027/P4-032/P4-042/P4-044/P4-045/P4-061 proxies |
| winter_service **0** county-wide | no signal → NULL | P4-018 |
| leisure=noise **0 globally** (taginfo API, data_until 2026-09-13) | tag does not exist → NULL | P4-047 |
| fixme 5 781 | carried, consumed by none (backlog ≠ rate/virtue) | P4-026/P4-039 NULL |

Counts are Harjumaa-wide; Tallinn subsets are smaller. Presence
establishes proxy viability; the single zero establishes P4-018.

## 4. Per-param verdicts (19)

Proxies (12, capped, "hinnang", never measured): P4-029 block observer
(footway/sidewalk/surface/lit ≤500 m), P4-012 blackspots
(cornerfurn+calming ≤500 m), P4-013 parking (bays+lots ≤800 m),
P4-027 grocery (≤1 km + known-late anchor), P4-032 activity density
(≤400 m, usage-not-safety), P4-035 darkness (lit ≤500 m), P4-040
arrival (≤200 m, peak-end, no safety claim), P4-042 smell (bakery
≤800 m, coarse), P4-044 herd (culture ≤1 km, taste-match ≤75),
P4-045 third places (≤800 m + evening anchor), P4-049 taxi
(entrance ≤300 m, weak-good ≤80), P4-061 last-shop (≤1.5 km,
absence = 35 warning).

Documented no-map NULLs (7, "EI OLE" + Estonian reason): P4-018
(winter_service 0 objects), P4-026 (fixme count ≠ response rate),
P4-031 (bus shelters ≠ balcony facts), P4-039 (fixme density points
the wrong way for civic virtue), P4-047 (leisure=noise does not
exist; calendars need dates), P4-048 (queues/registers absent),
P4-062 (bin mapping ≠ complaint rate).

Machine-checkable invariant (pinned by tests): "EI OLE" appears only
in NULL reasons, never in proxy reasons.

## 5. Judgment calls (AGENTS.md §7.5)

- Demo + coverage paired in ONE PR because the coverage issue body
  states it "extends the demoed ingestion" — two PRs would re-verify
  the same fragment.
- Shared kinds consumed, never re-mapped (cornerfurn, calming,
  street_parking, lit_street/lit_area, supermarket, convenience,
  pharmacy); new kinds only where no live owner exists. P4 walkway
  rows must precede the G18c street catch-all (fail-safe direction).
- Evening hours via optional "hours" passthrough (live parse keeps
  kind/lat/lon only); unknown hours are stated unknown, never closed.
- Absent-POI fallbacks 35–55 (unmapped ≠ absent); presence caps
  64–85 (mapped ≠ measured).
- No WEIGHTS / livability / layers / docs edits — integration and
  rebalancing stay one joint follow-up (existing tests pin WEIGHTS).
