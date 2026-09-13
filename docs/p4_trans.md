# P4 trans: Transpordiamet verdict note (issues #275 + #349)

Demo (#275) implements the Transpordiamet accident ingestion + P4-012
end-to-end; coverage (#349) wires the remaining 7 params off the same
source family. One PR closes both because the #349 body states it
extends the demo ingestion with "no new plumbing expected" — the seven
coverage dims reuse `fetch_cached` plus the point-buffer / zone-join
shapes, each reading its own POI kind. No second source is pulled.

## Openness verdict (2026-09-13, 12 tiny requests, custom UA, /tmp cache)

| Feed | Probe | Result |
|---|---|---|
| Accident metadata API (`andmed.eesti.ee/api/datasets/slug/inimkannatanutega-liiklusonnetuste-andmed`) | single GET | **OPEN, keyless**: HTTP 200 JSON, 6783 B, access PUBLIC, accrual MONTHLY, CC_BY_3.0, org Transpordiamet (collection: PPA) |
| Accident CSV (`pilv.transpordiamet.ee … lo_2011_2026.csv`) | bytes 0–2500 range peek | **OPEN, keyless**: HTTP 206 text/csv, `;`-delimited; first row Tallinn / Põhja-Tallinn / Sepa tn → Tallinn (`Omavalitsus`) filter proven on live bytes |
| Old portal host (`avaandmed.eesti.ee…`) | HEAD | 301 → `andmed.eesti.ee`; catalogue page is a JS shell ("Teabevärav" only) — the API, not the HTML, is the honest entry point |
| Tark Tee incidents / restrictions / truck traffic | GET `tarktee.ee/` root | **Dated negative**: HTTP 200 but a 66 KB driver-app shell with zero api/datex/avaandmed/download/wfs/rest links |
| Legacy Tark Tee ArcGIS (`tarktee.mnt.ee/arcgis/rest/services/avalik`) | HEAD | 301 → `tarktee.transpordiamet.ee` (host moved; no keyless JSON shape re-probed, to stay polite). DATEX II SRTI feeds need a registered key per public consumer notes — legs stay NULL |
| Tallinn noise downloads | GET `tallinn.ee/en/map-applications` | **Dated negative**: HTTP 200, 141 KB, no müra/noise download named — strategic END maps are viewer pages, EANS zones are not an open feed; zone join proven on fixtures only |

Raw probe files: `/tmp/hf-p4-trans/` (one-off PR record, not committed).
Pull contract: accidents refresh monthly (`ACCIDENTS_TTL_S = 30 d`,
portal accrual MONTHLY); cache hit within TTL makes NO request; single
GET, no retries — HTTP 429/errors are a stop signal. Transport errors
and short bodies are never cached as data.

CRS caveat (verified on live bytes): `X/Y koordinaat` are **L-EST97
metres** (e.g. `6589196.459 / 568050.8757` on a 2025 Harju row), not
WGS84 — and older rows (the 2011 Tallinn/Sepa row) have **empty X/Y**.
The reader keeps raw x/y and skips rows without finite coordinates;
projection L-EST97 → WGS84 is an explicit integration step on the first
full pull (see checklist). Fixtures carry WGS84 directly.

## Honest shapes per param (checklist / bands, NULL stays NULL)

| Param | Dim key | Window | Scored shape | NULL when |
|---|---|---|---|---|
| P4-012 blackspots | `accident_blackspots` | 300 m buffer | severity sum (3/death + 1/injured): ≤1→65, ≤3→50, ≤6→35, else 20 | empty buffer (casualty-only register: unknown, never "safe"), no join; päästeaeg always liidestamata |
| P4-018 winter class | `winter_road_class` | ≤ 150 m | hooldusklass 1→85, 2→65, 3→45, 4→30 (fixture codelist, remap on first pull) | no segment / unknown class |
| P4-023 noise zones | `noise_zone_trans` | ≤ 1000 m (join gate only) | label only, never gradient: lennumüra→35, õppus→50, sadam→60 | outside mapped zones (unknown, not quiet) |
| P4-026 fix-it rate | `fixit_response` | ≤ 500 m | rate ≤0.5→40, ≤0.8→60, else 80; needs n ≥ 5 | thin hex / unpublished |
| P4-037 restrictions | `policy_restrictions` | ≤ 500 m | sulgemine→45, piirang→55, tasuline→60 (Transpordiamet leg only) | no restriction join (Tark Tee keyless feed gated) |
| P4-046 2nd exit | `dread_egress` | ≤ 300 m | exits 0→30, 1→55, 2+→85 (road-egress leg only) | no egress join |
| P4-047 event traffic | `horrors_events` | ≤ 500 m | days/yr 0→80, ≤5→60, else 40 (joined 0 = real calm: calendars exhaustive) | no calendar join |
| P4-054 truck routes | `quarry_trucks` | ≤ 1000 m | flat 45 in-buffer (blast timetable EI OLE: no seasonal band faked) | beyond buffer (unknown, not quiet) |

Measured zero vs missing join: a joined `days_per_year == 0` scores 80
(real calm signal); a missing join (`None`) stays NULL everywhere. Every
scored reason says `hinnang` with components; every NULL reason says
`EI OLE` and names the missing input.

## Judgment calls (for the reviewer)

1. Demo + coverage in one PR: #349 defines coverage as extending the
   demo ingestion — nothing here needs a second source.
2. Per-source slices, not full params: P4-037 keeps the EMTA automaks
   slice and the peatus GTFS offset; P4-046 keeps EHR heat + Elektrilevi
   backup-feed; P4-047 keeps the kudocs KÜ-complaint slice; P4-054 keeps
   the maa-subsurface deposit buffer; P4-018 keeps the OSM
   winter_service NULL; P4-023 keeps the EHR NULL; P4-026 keeps the
   arireg cost-echo NULL. Distinct dim keys so the central hook can
   weight slices independently.
3. Empty accident buffer is NULL, not "safe" — pinned by test.
4. No Overpass fragment staged: positions arrive via the CSV join, not
   snapshot tags — stated, not omitted.
5. No shared-file edits (livability.py, WEIGHTS, layers, layers.md,
   nomap.md, parameters4.md untouched): 3 new files only. L-EST97
   projection + central hook (POI kinds + WEIGHTS rebalance) stay one
   joint change across all batches.

## First-full-pull / reopening checklist

1. Pull `lo_2011_2026.csv` into the cache dir; project L-EST97 → WGS84;
   drop rows without X/Y (count + report them, never fake).
2. Remap `maint_class` 1–4 to the real teeregister/talihooldus codelist.
3. Recalibrate `BLACKSPOT_BANDS` / `FIXIT_BANDS` from real histograms.
4. Re-probe Tark Tee keyless shapes + noise-zone downloads; paste fresh
   evidence. Add the explicitly-flagged live integration test on that
   reopen PR (not a unit run).
