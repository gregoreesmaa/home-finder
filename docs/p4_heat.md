# P4 heat: heat-tariff verdict note (issues #261 + #342)

Demo (#261) implements the heat-tariff ingestion + P4-008
end-to-end; coverage (#342) wires P4-036's return-temp bonus slice
off the same ingestion. One PR closes both because the #342 body
states it extends the demoed ingestion — P4-036's source list names
the Utilitas return-temp bonus as source (6), i.e. the same operator
feed P4-008 demos. No new plumbing.

## Openness verdict: dated negative (2026-09-13, keeps per #261)

Eight polite requests total (custom UA, 25 s timeout, paced ≥4 s,
cached `/tmp/hf-p4-heat/`, no scraping, no auth attempts, redirects
not spidered):

```
HEAD https://www.utilitas.ee/  -> 301 to apex (WordPress)
GET  https://utilitas.ee/      -> HTTP 200, 103 154 B ("Avaleht - Utilitas")
HEAD https://konkurentsiamet.ee/ -> 302 to www (Cloudflare)
GET  https://www.konkurentsiamet.ee/ -> HTTP 200, 120 078 B
GET  .../soojus/kooskolastatud-hinnad -> HTTP 200, 114 278 B ("Kooskõlastatud hinnad")
GET  https://tallinnavesi.ee/  -> 301 to www (nginx)
GET  https://www.tallinnavesi.ee/ -> HTTP 200, 363 912 B ("Tallinna Vesi")
GET  https://adven.com/        -> HTTP 200 (corporate WordPress)
GET  https://www.elektrilevi.ee/ -> HTTP 302, empty body (not followed)
```

What each page actually carries:

- Utilitas front page: kaugküte marketing (`Kaugküte on ... parim
  lahendus tiheasustusega piirkondade soojusega varustamiseks`);
  ZERO `hinnakiri`/`tariif`/`võrk`/`kaart` hrefs — no anonymous
  per-address tariff feed on the front page.
- Konkurentsiamet hub links to
  `/elekter-gaas-soojus-ja-vesi/soojus/kooskolastatud-hinnad`, a
  decision hub (accordion `#esitatud-soojuse-hin...` + HAI e-teenus
  `Hindade arvutamise infosüsteem`). Decisions are published as
  documents/e-service, with no anonymous per-address bulk endpoint.
- Tallinna Vesi front page links to `/teenused/hinnakiri`: a
  price-list page, not a per-address machine feed.
- Adven root: English corporate marketing (`Adven – The leading
  partner in the energy transition`), no local katlamaja tariffs.
- Tallinna Küte: no verified domain, not probed (polite stop).
- Elektrilevi root redirects with an empty body (not followed):
  the võrgutasu cross-check leg stays unverified.

Dated negative keeps the verdict: no anonymous per-address
heat-tariff machine feed verified 2026-09-13. Konkurentsiamet stays
the re-pull TRIGGER (its decisions move tariffs); the dims score
ONLY joined snapshot slices and stay NULL otherwise.

Pull contract: max 1 download / 30 d per cache dir (`HEAT_TTL_S =
2592000`; tariffs move on KA decisions, which additionally trigger
an out-of-band re-pull), single GET, no retries — HTTP 429/errors
are a stop signal. Transport errors are never cached as data; the
scorers stay NULL with an Estonian EI OLE reason until a join
lands. Scored shapes are proven on fixtures only (hermetic tests).

## Honest shapes per param (bands, NULL stays NULL)

| Param | Dim key | Joined slice | Scored shape | NULL when |
|---|---|---|---|---|
| P4-008 heating tariff (demo) | `heating_tariff` | per-address zone record | kehtiv tariff in known operator zone → 60 (January budgetable, cap named); operator known but tariff pending/unset → 45 (weak predictability) | record missing/non-dict, or joined-but-empty (no operator, no tariff) |
| P4-036 roof income (coverage) | `roof_bonus` | same record, bonus cell | return-temp bonus applicable → 65 (yield kicker, solar/mast/ad legs named as unjoined) | bonus absent/unknown; reason names the unjoined LiDAR/EHR/export legs |

Never 0 (the table alone never prices a January bill — building
consumption dominates) and never 100 (partial coverage by
construction — absence of a joined record is not proof of cheap
heat or zero roof income). P4-008 scores bill PREDICTABILITY, not
cheapness: ranking zones by €/MWh without consumption data would be
fake precision. Every scored reason says `registriandmed, mitte
hinnang` with the joined operator/tariff/bonus; every NULL reason
says `EI OLE` and points at the KÜ January-bill check (P4-008) or
the KÜ roof-plan check (P4-036).

## Judgment calls (for the reviewer)

1. Demo + coverage in one PR: #342 defines coverage as extending the
   demoed ingestion — splitting would ship an ingestion with one
   consumer, then re-touch every signature (taitur #255/#336
   precedent).
2. Cap 60 on P4-008 (not the taitur 70): a known tariff only makes
   January budgetable — the euros come from consumption the table
   cannot see, so the ceiling sits a band lower. Stated, not hidden.
3. Cap 65 on P4-036: the bonus is a real yield kicker but only one
   of four P4-036 legs — solar/mast/ad need LiDAR/EHR joins that do
   not exist here.
4. Joined-but-empty reads as NULL (not 45): a zone record carrying
   neither operator nor tariff proves coverage of nothing. This
   replaces the taitur None-vs-[] distinction, which has no meaning
   for a single-record join.
5. `katlamaja` is a first-class operator token (local boiler houses
   are explicit P4-008 sources); unknown operators read as None,
   never as `katlamaja`.
6. Unparseable tariffs read as None, never zero — zero would fake
   free heat. Comma decimals parse (Estonian CSV convention).
7. No shared-file edits (livability.py, WEIGHTS, layers, layers.md,
   parameters4.md untouched): 3 new files only. Central hook
   (enrich join + WEIGHTS rebalance) stays one joint change across
   all batches.

## Reopening checklist (when a per-address feed appears)

1. Re-run the probes above; paste fresh evidence in the reopen PR.
2. Pull one snapshot into the cache dir; run it through
   `parse_heat_zones` + `index_by_zone` on fixtures first.
3. Recalibrate the 45/60/65 bands against real tariff spreads.
4. Add the explicitly-flagged live integration test (not a unit run).
