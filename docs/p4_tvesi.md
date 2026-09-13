# P4 tvesi: Tallinna Vesi verdict note (issues #263 + #343)

Demo (#263) implements the Tallinna Vesi ingestion + P4-017
end-to-end; coverage (#343) wires P4-008/P4-046/P4-051/P4-060 off the
same ingestion. One PR closes both because the #343 body states it
extends the demoed ingestion ("no new plumbing expected") — each
coverage param's parameters4.md source list names Tallinna Vesi,
i.e. the feed P4-017 demos. No new plumbing was needed.

## Openness verdict: tariff OPEN, per-parcel CLOSED (2026-09-13)

Six polite requests total (custom UA, short timeouts, no scraping,
no auth attempts; bodies to /tmp only):

```
HEAD https://tallinnavesi.ee/                                -> HTTP 301 to www (nginx)
HEAD https://www.tallinnavesi.ee/                            -> HTTP 200 (nginx, text/html)
HEAD .../eraasiakas/veeteenused/hinnakiri/                   -> HTTP 308 to canonical path
GET  .../eraasiakas/veeteenused/hinnakiri  (follow, 1x)      -> HTTP 200 (554 467 B)
HEAD .../veetarbijale/uhisveevark-ja-kanalisatsioon/         -> HTTP 308 (content page)
```

The hinnakiri page publishes the water/sewer tariff as page content:
"Kehtiv alates 01.07.2026", Tallinn ja Saue linn — vesi 1,48 €/m³
KM-ga, kanal RG1 1,39 / RG2 2,78 €/m³ (RG1 combined 2,87; RG2
combined 4,26), approved by Konkurentsiamet decision 26.05.2026 nr
9-3/2026-014. The tariff leg is OPEN (page table, transcribed into
the snapshot layout the parser reads).

Per-parcel connection reality is CLOSED as a feed: ÜVK/liitumise
pages are content pages; reality comes from a manual iseteenindus
technical-conditions request (2 weeks) — same finding as #248/#332.
Honest shape is the zone table; missing stays NULL with the check
named. Zero-flow aggregates per hex and stormwater-fee zone tables:
no published feed found (dated negative keeps the verdict) — those
dims score ONLY joined snapshot slices.

Pull contract: max 1 download / 30 d per cache dir (`TVESI_TTL_S =
2592000`; tariff-change driven per parameters4.md P4-008 — re-pull
on Konkurentsiamet decisions), single GET, no retries — HTTP
429/errors are a stop signal. Transport errors are never cached as
data; the scorers stay NULL with an Estonian EI OLE reason until a
join lands. Scored shapes are proven on fixtures only (hermetic
tests).

## Honest shapes per param (bands, NULL stays NULL)

| Param | Dim key | Joined slice | Scored shape | NULL when |
|---|---|---|---|---|
| P4-017 water+sewer (demo) | `water_sewer_zone` | parcel zone → ÜVK zone table | central/central → 85; central+omapuhasti → 60; well+central → 55; well+omapuhasti → 45; liitumiskohustus caps 40; halb kvaliteet caps 35 | zone missing / not in table / half leg |
| P4-008 tariff (coverage) | `water_tariff` | piirkond → hinnakiri table | RG1 combined ≤3,50 → 75 (Tallinna tase); ≤5,00 → 55; above → 35; kaugküte leg always named missing | piirkond missing / not in table / half leg |
| P4-046 dread (coverage) | `water_redundancy` | parcel city_water+well | both → 80; city only → 60; well only → 40; neither → 25; other legs named missing | either flag unknown |
| P4-051 zero-flow (coverage) | `zero_flow_hex` | hex aggregate | share ≥30% → 25; ≥15% → 45; below → 70 (cap named); thin cells (<5) NULL | slice missing / half / thin |
| P4-060 stormwater (coverage) | `stormwater_fee` | parcel zone → fee table | tasu applies → 45; not → 70 (cap named); queue leg named missing | zone missing / not in table |

Never 0 and never 100 (zone/tariff absence is not proof of calm or
disaster). Every scored reason says `registriandmed, mitte hinnang`
(or `koond`) with the joined record; every NULL reason says `EI OLE`
and points at the concrete check (iseteenindus tehnilised tingimused,
hinnakiri, EHR, KÜ aruanne, ÜVK-kaart).

## Judgment calls (for the reviewer)

1. Demo + coverage in one PR: #343 defines coverage as extending the
   demoed ingestion — splitting would ship an ingestion with one
   consumer, then re-touch every signature (EHR #249/#333, taitur
   #255/#336 precedent).
2. P4-017 vs `dims_p4_maa_subsurface.dim_water_sewer` (#332): same
   buyer question, COMPLEMENTARY legs, not a duplicate. Subsurface
   reads geology-side ÜVK facts (kaitseala/puurkaev constraints from
   cached WFS polygons); this dim reads the utility's own zone table
   + tariff-validity leg. Bands match deliberately; the JOINED SOURCE
   named in each reason differs (tsoonitabel vs WFS-kiht). The central
   hook joins one source per parcel later — one joint change.
3. Tariff bands calibrated 2026-09-13 against the live hinnakiri
   (RG1 2,87 = today's Tallinn residential level sits inside the 75
   band; RG2 4,26 sits inside the 55 band). Stated, not hidden.
4. P4-008 scores water/sewer only and always names the unjoined
   kaugküte leg — a water-only 75 must never read as a whole-bill
   calm.
5. P4-051 thin cells (<5 connections) stay NULL: a 1-of-2 "share" is
   noise and near-identifying. Hex only, never addresses.
6. No shared-file edits (livability.py, WEIGHTS, layers, layers.md,
   parameters4.md untouched): 3 new files only. Central hook
   (enrich join + WEIGHTS rebalance) stays one joint change across
   all batches.

## Reopening checklist (when a per-parcel feed appears)

1. Re-run the probes above; paste fresh evidence in the reopen PR.
2. Transcribe one tariff table into the cache dir; run it through
   `parse_tariffs` + `index_zones` on fixtures first.
3. Recalibrate the 75/55/35 bands against the new Konkurentsiamet
   decision (note otsus + kehtib_alates in the snapshot).
4. Add the explicitly-flagged live integration test (not a unit run).
