# P4 RIK e-Kinnistusraamat verdict note — paid per-section extracts (P4-004)

> Dated-negative verdict for issue #252 (single-param demo, no
> coverage issue — the issue states 0 remaining params use this
> source, so no follow-up coverage issue exists).
> Checked 2026-09-13. The single param is a documented no-map NULL
> dim (OTA PR #131 precedent); the scorer lives in
> `services/scoring/dims_p4_rik.py`, pinned by
> `services/scoring/tests/test_dims_p4_rik.py`.

## Verdict

**Paid flow, no open bulk — the dim stays NULL with an Estonian
reason.** RIK sells e-Kinnistusraamat extracts per register
section: I jao kanne 2 €, II jao kanne 2 €, III ja IV jao kanded
kokku 2 €, terve registriosa 6 € (prices exclude VAT; a bought
extract stays re-viewable for 24 h). Bulk-shaped access (XML
teenus) sits behind Lepinguinfo — a contract, not an anonymous
endpoint. There is no per-parcel extract feed to poll politely,
so there is no ingestion to cache, no TTL to state beyond this
one-off check (re-probe yearly, or sooner if rik.ee/avaandmed or
Teabevärav gains an open kinnistusraamat dataset), and no honest
keelumärge/hüpoteek summary to paint without the buyer's own paid
extract + notary reading.

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

4 served requests total (single GETs, labelled one-off user-agent
`home-finder openness probe #252 (one-off, single GETs; contact via
GitHub home-finder)`, headers + visible-text keyword scope read
only). Raw bodies: `/tmp/hf-rik-probe/` (one-off PR record, not
committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://www.rik.ee/et/kinnistusraamat` (guessed) → HTTP 404, 26552 bytes, title "Lehekülge ei leitud" | Documented negative guess, not a real path | Same precedent as the EMTA #256 guessed-URL 404s |
| `https://www.rik.ee/` → HTTP 301 → `/et` | Transport note, not data | Working host confirmed |
| `https://www.rik.ee/et` → HTTP 200, 36293 bytes, title "Avaleht \| Registrite ja Infosüsteemide Keskus" | Nav advertises the portal tree only: "E-kinnistusraamatu portaal", "Päringud", "Teenuste hinnad", "Lepinguinfo", "XML teenus", "Korteriühistu väljavõte", "Kinnistuportaal" | Queries live behind the portal's contract/pricing wall, not as linked open data |
| `https://www.rik.ee/et/e-kinnistusraamat/e-kinnistusraamatu-portaal/teenuste-hinnad` → HTTP 200, 32893 bytes (~2.8k visible chars) | Price table verbatim: "Teenuste hinnad: Teenus / Hind — I jao kanne 2 €, II jao kanne 2 €, III ja IV jao kanne kokku 2 €, Terve registriosa 6 €. *Hindadele ei lisandu käibemaksu. *Ostetud andmetega saab 24 tunni jooksul korduvalt tutvuda, tehes päringut" | Per-section extracts are paid; bulk XML needs a contract |

Judgment call: the check stopped at storefront/price-list level on
purpose — no portal login attempts, no query-form driving, no
XML-teenus contract probing, no per-parcel pulls (each costs 2–6 €
and needs a contract/identity). Chasing the paid flow with real
queries is exactly the spend + enumeration this repo refuses
(AGENTS.md §5).

## Honest shape (NULL until an open feed appears)

| Param | Dim key | Honest shape when a feed lands | Buyer-side check meanwhile |
|---|---|---|---|
| P4-004 Kinnistus süva (demo) | `rik_extract` | per-listing dim, weak-good capped (registriosa I–IV jaod per parcel + notary checkpoint — the RIK paid-extract leg) | Tasuline väljavõte (kinnistusraamat.rik.ee) + notari kontroll (notar.ee); scored cousins: KKIS leg dims_p4_maa_kataster + AT leg dims_p4_ata + EMTA leg dims_p4_emta + täituri leg dims_p4_taitur |

Never 0 and never 100 would apply once scored (a paid extract
still needs the notary's reading; this leg alone never zeroes a
flat); today the reason says `EI OLE` and points at the
väljavõte + notari kontroll above. Every scored-future reason
must trace to a joined extract record.

## Judgment calls (for the reviewer)

1. Single-param demo, no coverage issue: #252 states the remaining
   0 params using this source need only a follow-up created after
   this demo — with a dated-negative demo there is no ingestion to
   extend, so one dim in one module is the whole honest scope.
2. Split-slice contract: the KKIS public-layer slice
   (dims_p4_maa_kataster dim_kinnistus_syva), the AT notice slice
   (dims_p4_ata dim_kinnistus_checkpoint), the EMTA debt slice
   (dims_p4_emta dim_kinnistus_debt) and the täitur slice
   (dims_p4_taitur dim_kinnistus_checkpoint) stay scored where they
   live and are named, never re-scored here. Sibling modules were
   read first; dims_group04 / parameters4.md untouched.
3. No shared-file edits (livability.py, WEIGHTS, layers, layers.md,
   parameters4.md untouched): 3 new files only. Central hook
   (enrich join + WEIGHTS rebalance) stays one joint change across
   all batches.

## Reopening checklist (when an open feed appears)

1. Re-run the four probes above yearly (or sooner if rik.ee/avaandmed
   or Teabevärav gains an open kinnistusraamat dataset); paste fresh
   evidence in the reopen PR.
2. If a per-parcel extract feed appears, transcribe one vintage into
   the cache dir and run it through a `parse_rik_extract` + parcel
   join on fixtures first (never commit real extracts — they carry
   personal/paid data).
3. Graduate the dim to the per-listing weak-good-capped shape ONLY
   from joined extract records; keep NULL-with-Estonian-reason for
   every missing leg.
4. Add the explicitly-flagged live integration test (not a unit run).
