# P4 Rahandusministeerium verdict note — KOV finantsandmed + automaksu laekumine (P4-019 + P4-037)

> Dated-negative verdict for issues #315 (demo) and #377 (coverage).
> Checked 2026-09-13. Both params are documented no-map NULL dims
> (OTA PR #131 precedent); scorers live in
> `services/scoring/dims_p4_rahmin.py`, pinned by
> `services/scoring/tests/test_dims_p4_rahmin.py`.

## Verdict

**No open machine feed — both dims stay NULL with Estonian reasons.**
The ministry site (fin.ee) publishes tax policy as human prose: the
automaks page lists M1/N1 categories, the 50-euro base part and the
CO2 component, but no Tallinn revenue table; the statistics page has
no KOV finance section at all; and the one sentence that mentions
KOV budget data ("Andmed kohalike omavalitsuste eelarve kohta on
leitavad järgnevalt leheküljelt") carries no hyperlink — a dead
reference. There is no per-KOV finance table and no automaks-revenue
feed to poll politely, so there is no ingestion to cache, no TTL to
state beyond this one-off check (re-probe yearly, or sooner if
fin.ee/avaandmed or Teabevärav gains a KOV finance dataset), and no
honest fiscal table or revenue calibration to paint.

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

4 served requests total (four single GETs, labelled one-off user-agent
`home-finder openness probe #315 (one-off, single GETs; contact via
GitHub home-finder)`, headers + visible-text keyword scope read only).
Plus one transport note: `https://www.rahandusministeerium.ee/` timed
out from the probe host (not data — fin.ee is the working host).
Raw bodies: `/tmp/hf-rahmin-probe/` (one-off PR record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://www.fin.ee/` → HTTP 200 (195440 bytes, ~10.4k visible chars, title "Avaleht \| Rahandusministeerium") | No KOV/omavalitsus section links in 320 links; sweep 0 for csv / xlsx / andmestik / masinloetav | Entry point confirmed, nothing KOV-machine-readable advertised |
| `https://www.fin.ee/.../uuringud-ja-analuusid/statistika` → HTTP 200 (179939 bytes, ~7.9k visible chars) | 0 hits for kohalik/omavalitsus/KOV/võlakoormus; the two avaandmed hits are site-nav chrome + a pointer at EMTA open data and Statistikaamet (sibling dims_p4_emta / dims_p4_stat territory); sweep 0 for csv / xlsx / andmestik / masinloetav | No ministry KOV finance section; open-data pointers belong to siblings |
| `https://www.fin.ee/riigi-rahandus-ja-maksud/maksu-ja-tollipoliitika/maksud` → HTTP 200 (237385 bytes, ~36.5k visible chars) | Automaks is rate prose (M1/N1 categories, baasosa 50 eurot, CO2 component, e-MTA payment); 0 hits for maksulaekumine; "Andmed kohalike omavalitsuste eelarve kohta on leitavad järgnevalt leheküljelt" has NO `<a>` hyperlink; sweep 0 for csv / xlsx / andmestik / masinloetav | Policy text, not a revenue feed; the KOV-budget reference is unlinked prose |
| National-portal dataset search | Re-uses the #301 precedent (andmed.eesti.ee/dataset is a JS shell with no server-rendered results) — not re-hammered | No trivially pollable Teabevärav dataset check without JS rendering |

Judgment call: the check stopped at storefront/page level on
purpose — no site-search crawling, no deep-URL guessing, no DOC/PDF
parsing, no EMTA-open-data re-poll (sibling dims_p4_emta owns that
slice). Deeper probing is exactly the enumeration this repo refuses
(AGENTS.md §5).

## Honest shapes per param (all NULL until a feed appears)

| Param | Dim key | Honest shape when a feed lands | Buyer-side check meanwhile |
|---|---|---|---|
| P4-019 KOV fiscal health (demo) | `fiscal_rahmin` | per-KOV table, annual (võlakoormus, investeeringud, maamaksu trend — the ministry leg) | Tallinna eelarve + eelarvestrateegia (tallinn.ee); Statamet leg dims_p4_stat + EMTA leg dims_p4_emta + arengukava leg dims_p4_cityplans + overturn-#242 G16 tables |
| P4-037 policy exposure (coverage) | `automaks_revenue` | per-KOV revenue calibration feeding the per-listing exposure band (the ministry leg) | Own car figure via EMTA kalkulaator (avalik.emta.ee); commute alternative via TLT/Peatus.ee; EMTA/park/trans/cityplans/peatus/tlt exposure legs |

Never 0 and never 100 would apply once scored (absence is not proof
of a healthy KOV or a car-free-proof address); today every reason says
`EI OLE` and points at the concrete check above. Every scored-future
reason must trace to a joined record.

## Judgment calls (for the reviewer)

1. Demo + coverage in one PR: #377 defines coverage as extending the
   demoed ingestion — with a dated-negative demo there is no
   ingestion to extend, so the coverage slice lands in the same
   verdict module (fix-it #301+#370, Terviseamet #289+#362, TLT
   #277+#351, Elron #284+#358 precedent).
2. Pairing rationale: P4-019 source 2 is the Rahandusministeerium KOV
   finantsandmed leg; P4-037 source 6 is the Rahandusministeerium
   automaksu laekumine Tallinn leg — see the module docstring for the
   per-param leg mapping. The remaining P4-019/P4-037 legs stay
   scored where they live and are named, never re-scored (stat KOV
   leg, EMTA maamaks + CO2 legs, arengukava investment leg, park
   zone-cost leg, trans restriction leg, cityplans planned-zone leg,
   peatus/tlt alternative legs, overturn-#242 G16 tables).
3. Complements, not duplicates: P4-019 (per-KOV fiscal TABLE) vs
   P4-037 (per-KOV revenue CALIBRATION) are different honest shapes —
   no double-scoring by construction, both NULL. The EMTA sibling
   (dims_p4_emta.py) was read first; its P4-019/P4-037 slices are
   named, never re-scored here, and dims_group16*.py is untouched.
4. No shared-file edits (livability.py, WEIGHTS, layers, layers.md,
   parameters4.md untouched): 3 new files only. Central hook (enrich
   join + WEIGHTS rebalance) stays one joint change across all
   batches.

## Reopening checklist (when a pollable feed appears)

1. Re-run the four probes above yearly (or sooner if fin.ee/avaandmed
   or Teabevärav gains a KOV finance dataset); paste fresh evidence
   in the reopen PR.
2. If a per-KOV finance table or automaks-revenue feed appears,
   transcribe one vintage into the cache dir and run it through a
   `parse_rahmin_tables` + per-KOV join on fixtures first.
3. Graduate dims to a per-KOV table (P4-019) / revenue calibration
   (P4-037) ONLY from joined records; keep NULL-with-Estonian-reason
   for every missing leg.
4. Add the explicitly-flagged live integration test (not a unit run).
