# P4 fix-it channels verdict note — Tallinna abiliin/e-teenused + Mupo/KÜ (P4-026 + P4-062)

> Dated-negative verdict for issues #301 (demo) and #370 (coverage).
> Checked 2026-09-13. Both params are documented no-map NULL dims
> (OTA PR #131 precedent); scorers live in
> `services/scoring/dims_p4_fixit.py`, pinned by
> `services/scoring/tests/test_dims_p4_fixit.py`.

## Verdict

**No open machine feed — both dims stay NULL with Estonian reasons.**
Fix-it intake (valgustus, augud, lumi, grafiti) lives on the 14410 /
661 9860 helpline, on Mupo e-post (weekend letters are treated as
call-outs, not answered), and in the human annateada.ee report-map
app. Tark Tee serves a JS shell with no server-rendered incident
feed; the national Teabevärav has no pollable abiliin/fix-it
dataset. There is no public lag table or per-linnaosa complaint-stats
feed to poll politely, so there is no ingestion to cache, no TTL to
state beyond this one-off check (re-probe yearly, or sooner if
tallinn.ee/avaandmed or Teabevärav gains a dataset), and no honest
hex responsiveness rate or hex operational flag to paint.

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

7 tiny requests total (seven single GETs, labelled one-off user-agent
`home-finder openness probe #301 (one-off, single GETs, file cache for
PR record; contact via GitHub home-finder)`, headers + visible-text
keyword scope read only). Raw bodies: `/tmp/hf-fixit-probe/` (one-off
PR record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://www.tallinn.ee/` → HTTP 301 (162 bytes), followed once → HTTP 200 (~138 KB, cloudflare, ~8.3k visible chars) | Storefront links the Mupo page, `/avaandmed/`, `/et/lumi`, the geoportal; sweep 0 for csv / geojson / wfs / api / andmestik / masinloetav | Entry points confirmed, nothing machine-readable advertised |
| `https://www.tallinn.ee/et/abiliin` → HTTP 404 (~123 KB, "Lehekülge ei leitud" shell) | No dedicated abiliin machine page | Intake is the helpline, not a feed |
| `https://annateada.ee/` → HTTP 200 (~24 KB, ~4.1k visible chars) | Human reporting app ("Teavita heakorraprobleemist, Märgi koht kaardil", Andmevara/Maanteeamet marks, mobile-app links); no API/docs/data endpoint at page level | Reports exist as human map pins, never a comparable machine vintage — the P4-026 lag join cannot be measured |
| `https://www.tallinn.ee/et/tallinna-munitsipaalpolitsei-amet` → HTTP 200 (~159 KB, ~14.5k visible chars) | Intake is phone 14410 / 661 9860 (24/7 helpline, 7 hits) + e-post (weekend letters treated as call-outs, not answered); kaebus hits (4x) are a DOC-form + e-post address; avaandmed (3x) / statistika (5x) hits are site-nav chrome, not a feed; sweep 0 for csv / geojson / json / wfs / api / andmestik / masinloetav | No per-linnaosa complaint-stats table, no machine feed |
| `https://tarktee.ee/` → HTTP 200 (~66 KB) | 18 visible characters ("Tark Tee 37.26.8.2"): JS shell, no server-rendered incidents | Interactive app, not a pollable response-time feed |
| `https://andmed.eesti.ee/dataset?q=abiliin` → HTTP 200 (~75 KB) | 10 visible characters ("Teabevärav" JS shell), no server-rendered results | No trivially pollable national-portal abiliin/fix-it dataset (same shell as #264/#277/#284) |

Judgment call: the check stopped at storefront/page/shell level on
purpose — no annateada form driving, no Tark Tee service
enumeration, no DOC-form parsing, no complaint-form probing. Deeper
probing is exactly the scraping this repo refuses (AGENTS.md §5).

## Honest shapes per param (all NULL until a feed appears)

| Param | Dim key | Honest shape when a feed lands | Buyer-side check meanwhile |
|---|---|---|---|
| P4-026 fix-it responsiveness (demo) | `fixit_channel_responsiveness` | hex responsiveness rate (abiliin/e-teenused + Mupo/KÜ stats leg) | 14410 / 661 9860 helpline; ask the linnaosa for removal lag; KÜ stairwell accounts; dims_p4_komun heakorra leg + dims_p4_osm fixme cross-check + dims_p4_arireg cost echo |
| P4-062 rat/ice hex (coverage) | `rat_icefall_channel_flags` | hex operational flags, never addresses (P4-026-join + waste/ice channel legs) | on-site waste-house check; KÜ waste costs; dims_p4_paaste ice warnings + dims_p4_komun rotikaebused leg + dims_p4_osm waste cross-check + dims_p4_arireg waste echo |

Never 0 and never 100 would apply once scored (absence is not proof
of a fixed street or a neglected block); today every reason says
`EI OLE` and points at the concrete check above. Every scored-future
reason must trace to a joined record.

## Judgment calls (for the reviewer)

1. Demo + coverage in one PR: #370 defines coverage as extending the
   demoed ingestion — with a dated-negative demo there is no
   ingestion to extend, so the coverage slice lands in the same
   verdict module (Terviseamet #289+#362, TLT #277+#351,
   elektrilevi #264+#344, Elron #284+#358 precedent).
2. Pairing rationale: P4-026 source 1 is the abiliin/e-teenused
   reports leg and source 3 the Mupo/KÜ stats leg; P4-062 source 4
   is the explicit P4-026 join — see the module docstring for the
   per-param leg mapping. The remaining P4-026/P4-062 legs stay
   scored where they live and are named, never re-scored (komun
   heakorra legs, OSM fixme/waste cross-checks, Paasteamet ice
   warnings, Äriregister KÜ cost echos).
3. Complements, not duplicates: P4-026 (fix-it LAG rate) vs P4-062
   (complaint COUNT flags) are different honest shapes (hex rate vs
   hex flags) — no double-scoring by construction, both NULL.
4. No shared-file edits (livability.py, WEIGHTS, layers, layers.md,
   parameters4.md untouched): 3 new files only. Central hook (enrich
   join + WEIGHTS rebalance) stays one joint change across all
   batches.

## Reopening checklist (when a pollable feed appears)

1. Re-run the seven probes above yearly (or sooner if
   tallinn.ee/avaandmed or Teabevärav gains an abiliin/fix-it
   dataset); paste fresh evidence in the reopen PR.
2. If a machine lag table or per-linnaosa stats feed appears,
   transcribe one vintage into the cache dir and run it through a
   `parse_fixit_reports` + hex join on fixtures first.
3. Graduate dims to a hex rate (P4-026) / hex flags (P4-062) ONLY
   from joined records; keep NULL-with-Estonian-reason for every
   missing leg.
4. Add the explicitly-flagged live integration test (not a unit run).
