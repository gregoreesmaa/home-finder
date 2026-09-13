# P4 muinsus verdict note — Muinsuskaitseamet new uses (P4-005 leg + P4-041 corridor slice)

> Dated-negative verdict for issues #324 (demo) and #380 (coverage).
> Checked 2026-09-13. Both params are documented no-map NULL dims
> (OTA PR #131 precedent); scorers live in
> `services/scoring/dims_p4_muinsus.py`, pinned by
> `services/scoring/tests/test_dims_p4_muinsus.py`.

## Verdict

**No pollable registry endpoint — both dims stay NULL with Estonian reasons.**
The parameters3-documented registry hostname is dead (NXDOMAIN) and the
moved register answers HTTP 520, so neither the Vanalinna/miljööväärtus
protection query (P4-005 leg) nor the Vanalinna vaatekoridorid polygons
(P4-041 slice) can be pulled politely. There is no ingestion to cache, no
TTL to state beyond this one-off check (re-probe quarterly — a restored
register would graduate both dims), and no honest protection/corridor band
to paint.

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

5 single GETs total (labelled one-off user-agent `home-finder muinsus
openness-check #324 (one-off, single GETs, no retry; contact via GitHub
home-finder)`, ≥ 6 s pacing, `--max-time 25`, headers + visible-text scope
read only; the spaced 520 re-probe is a down-confirmation, not a retry
dare). Raw bodies: `/tmp/hf-muinsus-probe/` (one-off PR record, not
committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://register.muinsuskaitseamet.ee/` → DNS NXDOMAIN (curl exit 6) | `nslookup` confirms NXDOMAIN | parameters3 Group 6 documented registry hostname is dead — transport error, never data |
| `https://register.muinsuskaitseamet.ee/api/v1/` → DNS NXDOMAIN (curl exit 6) | same resolver, same verdict | documented REST path dies with its host — no API to chase there |
| `https://muinsuskaitseamet.ee/` → HTTP 200 (~158 KB) | agency front page; registry link published 5×, all pointing at `register.muinas.ee/` | register moved — a link, not a feed |
| `https://register.muinas.ee/` → HTTP 520 ("error code: 520", 16 bytes) | repeated 20+ s later, same 520 | origin down at check time — a 520ing page cannot be polled, let alone joined |

Judgment call: the check stopped at entry/shell level on purpose — no Maa-amet
WFS layer crawl, no Tallinn milieu-plan PDF harvest, no app-API chasing.
Harvesting human pages for registry verdicts would be exactly the scraping
this repo refuses (AGENTS.md §5); the Maa-amet `mka:*` mirror stays a
reopening lead, not a silent substitution.

## Honest shapes per param (all NULL until the register answers)

| Param | Dim key | Honest shape when the register answers | Buyer-side check meanwhile |
|---|---|---|---|
| P4-005 permits, heritage leg (demo) | `permit_heritage` | per-listing binary, never 0: listed monument / kaitsevöönd / miljööväärtus ala → coordination friction noted, clear → bankability-neutral | register desk / Muinsuskaitseamet + KOV miljöö-area plans before the renovation budget; permit existence in dims_p4_ehr; quarter feel in dims_group06 |
| P4-041 glimpse, corridor slice (coverage) | `glimpse_corridor` | per-listing view class, never vaade: inside a protected vaatekoridor → future-blockage shelter noted | Tallinna üldplaneering vaatekohtade register + on-site stand; floor-ratio glimpse class in dims_p4_ehr; LiDAR view-fan separately |

Never 0 and never 100 would apply once scored (a monument is friction, not a
failed deal; a corridor shelters the sliver, it does not measure it); today
every reason says `EI OLE` and points at the concrete check above. Every
scored-future reason must trace to a joined registry record.

## Judgment calls (for the reviewer)

1. Demo + coverage in one PR: #380 defines coverage as extending the demoed
   ingestion with "no new plumbing expected" — with a dated-negative demo
   there is no ingestion to extend, so the P4-041 corridor slice lands in the
   same verdict module (events #310+#375, komun #290+#363, TLT #277+#351,
   elektrilevi #264+#344, Elron #284+#358, sadam #298+#368 precedent).
2. Pairing rationale: both params name this source family in their
   parameters4.md source lists — P4-005 source (5) Muinsuskaitseamet päring
   for Vanalinna/miljööväärtus areas, P4-041 source (3) Muinsuskaitseamet
   Vanalinna vaatekoridorid — so there is no weak link; each dim is the
   muinsus leg and names the cousin slices that own the other legs.
3. Complements, not duplicates: dims_p4_ehr.py was READ first (P4-005 EHR
   permit leg, P4-041 EHR floor-ratio leg — different records, different
   questions) and is untouched; overturn #237 (parameters3 G6 muinas
   register, dims_group06*.py OSM heritage proxies) owns the district/craft
   params, a different family from these P4 bankability/view slices.
   Distinct dim keys (`permit_heritage`, `glimpse_corridor`) throughout.
4. The live agency page observed (registry link to register.muinas.ee)
   proves the register moved, not that it is open: a link is not a feed,
   and the target 520s. NXDOMAIN on the old host plus 520 on the new one
   is a full dated negative on the machine path.
5. No shared-file edits (dims_p4_ehr.py, dims_group06*.py, livability.py,
   WEIGHTS, layers, layers.md, parameters4.md untouched): 3 new files only.
   Central hook (enrich join + WEIGHTS rebalance) stays one joint change
   across all batches.

## Reopening checklist (when the register answers)

1. Re-run the four probes above quarterly (registry TTL: quarterly); paste
   fresh evidence in the reopen PR.
2. If register.muinas.ee serves a pollable monument/zone/corridor feed
   (WFS/REST/CSV) or the Maa-amet `mka:ehitis`/`mka:kaitsevoond` mirror
   proves pollable, transcribe one Tallinn week of dated rows into the cache
   dir and run them through a `parse_muinsus_feed` + per-listing join on
   fixtures first.
3. Graduate dims to bands ONLY from joined records (binary / view class per
   the table above); keep NULL-with-Estonian-reason for every missing leg.
4. Add the explicitly-flagged live integration test (not a unit run).
