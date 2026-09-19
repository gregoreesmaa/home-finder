# Probe: Rail Baltica corridor holdings (#704, verify-then-build)

**Verdict (2026-09-19): NEGATIVE — dated negative with inventory.**
Real Rail Baltica planning activity verifies live, but nothing
Tallinn-joinable verifies, so no corridor layer ships (no nuisance
discs, no station premium — both would be invented). Verdict carrier:
`services/scoring/probe_railbaltic.py` (`RAILBALTIC_VERDICT`), guard:
`services/scoring/tests/test_probe_railbaltic.py`.

## §1 What the existing holdings already say (code-read, no requests)

| Holding | State 2026-09-19 | Meaning for #704 |
|---|---|---|
| `dims_p4_rb.py` (`RB_BULK_URL`) | `None` — dated negative since #281 | No machine-readable Ülemiste timetable; scorers NULL with EI OLE |
| `dims_p4_cityplans.py` (`CITYPLANS_BULK_URL`) | `None` — dated negative since #282 | No bulk plan endpoint for the corridor reservation leg |
| `dims_p4_notices.py` (AT miner) | Structured parcel linkage 0/total by design (no location fields in the notice schema) | AT notices cannot join to addresses over structured fields |

## §2 Live inventory (polite, /tmp only)

UA `home-finder-research/0.1`, paced ≥ 2 s, 429 = stop (none seen),
raw in `/tmp/hf704_at/`, never committed. Three requests: the AT
miner zoning slice (served zero rows — taxonomy gap, §3), one
`planeeringud` list GET that timed out at 25 s with 0 bytes
(transport non-answer, retried once), one retry serving
**200, 5 000 604 B, 1001 notice rows** (the 1000-result cap is live).

RB mentions in the window (body + provider sweep for
`rail baltica|railbaltica|raudtee|ülemiste` → 32 hits, classified):

- **2 literal Rail Baltic notices** (the only ones about the project):
  - `2541352` — Rae Vallavalitsus, "Lehmja küla Rail Baltica Assaku
    peatuse detailplaneeringu kehtestamine" (09.12.2025, ~2,7 ha,
    free-text katastritunnused `65301:001:5956` et al.).
  - `2490346` — Jõelähtme Vallavalitsus, "Uusküla Muuga sadama Rail
    Baltic hoonete detailplaneeringu algatamine" (17.07.2025, ~11 ha,
    tunnused `24501:001:2849` et al., juhtimiskeskus + veeremi
    hooldusdepoo).
- **1 corridor-touching notice**: `2510688` — MKM riigi eriplaneering
  (Tallinna piirkonna kõrgepingevõrk) whose extended plan area
  (~106 km², PDF map) explicitly includes the Rail Baltic corridor —
  a power-grid plan, not a corridor geometry, location lives in a PDF.
- The other 29 hits are street-name matches (`Raudtee tn`) or
  Ülemiste-as-place — not the project.
- **Tallinn RB-corridor notices in the window: 0.** No Ülemiste
  terminal works notice, no Tallinn corridor reservation row.

## §3 Why no build

1. The two RB notices sit outside Tallinn (Assaku, Muuga) — scoring
   Tallinn listings off them is dishonest scope.
2. Their locations are free-text tunnus strings, not structured
   fields — no machine join exists (the miner's `TUNNUS_RE` anticipates
   text mining, but the kataster join is unbuilt).
3. The corridor geometry (Ülemiste works footprint, station premium
   radius) verifies nowhere machine-readable: RB bulk None, cityplans
   bulk None, OSM per the standing `dims_p4_rb` judgment has no honest
   RB phase tag (not re-litigated here — out of the verify scope).
4. No new dims module: the P4-014/P4-006 RB slices are owned by
   `dims_p4_rb.py` — a second NULL module would double-score the same
   gap.

## §4 Findings for other owners (not fixed here — out of scope)

- **AT miner taxonomy gap** (`batch_at_notices.py` `SLICES["zoning"]`
  uses pealiik `planeering`, which served zero rows; the live list is
  `/ee/-/planeeringud` with 1001 rows). Re-verify the slice slugs
  before the next harvest.
- **Overturn path**: text-mine tunnus + kataster join for the two RB
  parcels (Rae/Muuga precedent), or a verified Ülemiste works
  footprint with expiry dating — then re-open #704 with the geometry
  pasted here.
