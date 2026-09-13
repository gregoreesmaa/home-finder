# P4 notar verdict note — notar.ee closing guidance (P4-004)

> Dated-negative verdict for issue #253 (demo, single-param, no
> coverage issue).
> Checked 2026-09-13. The param is a documented no-map NULL dim
> (OTA PR #131 precedent); the scorer lives in
> `services/scoring/dims_p4_notar.py`, pinned by
> `services/scoring/tests/test_dims_p4_notar.py`.

## Verdict

**No open machine feed — the dim stays NULL with an Estonian reason.**
Notarite Koda (notar.ee) publishes closing guidance as human prose:
the Kinnisvaratehingud page explains the real-estate transaction
steps in ~14.8k visible characters, but offers no export, download,
dataset, or API — the front page's only `api` hits are a Google-Fonts
stylesheet and a Drupal CSS module. There is no pollable
closing-guidance feed to pull politely, so there is no ingestion to
cache, no TTL to state beyond this one-off check (re-probe yearly, or
sooner if notar.ee/avaandmed or Teabevärav gains a notary dataset),
and no honest closing score to paint from a hand-read of the prose.

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

5 served requests + 1 headers-only HEAD total (labelled one-off
user-agent `home-finder openness probe #253 (one-off, single GETs;
contact via GitHub home-finder)`, 2 s pacing between GETs, headers +
visible-text keyword scope read only).
Raw bodies: `/tmp/hf-notar-probe/` (one-off PR record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://notar.ee/` → HTTP 301 (162 bytes, Location: https://www.notar.ee/) | Bare domain redirects to www | Transport note, not data |
| Guessed deep URL `/kinnisvara-ost-muuk-ja-urimine/` → HTTP 301 (162 bytes) | Dead guess, recorded not chased | No URL guessing campaign (AGENTS.md §5) |
| `https://www.notar.ee/et` → HTTP 200 (69607 bytes, ~3.5k visible chars, title "Notarite Koda") | 67 links; `api` hits are Google Fonts + Drupal date_api CSS only; sweep 0 for csv / xlsx / andmestik / masinloetav / avaandmed | Entry point confirmed, nothing machine-readable advertised |
| `https://www.notar.ee/et/teabekeskus/kinnisvara` → HTTP 200 (94832 bytes, ~14.8k visible chars, title "Kinnisvaratehingud \| Notarite Koda") | 70 links; sweep 0 for csv / xlsx / andmestik / masinloetav / avaandmed / open-data / api; `json` hits are jQuery cookie chrome, `xml` hits are xml:lang attributes | Closing guidance is human prose, not a feed |
| National-portal dataset search | Re-uses the #301 precedent (andmed.eesti.ee/dataset is a JS shell with no server-rendered results) — not re-hammered | No trivially pollable Teabevärav dataset check without JS rendering |

Judgment call: the check stopped at storefront + guidance-page level
on purpose — no site-search crawling, no deep-URL guessing beyond the
one recorded dead guess, no DOC/PDF parsing, no RIK/EMTA re-poll
(siblings own those slices). Deeper probing is exactly the enumeration
this repo refuses (AGENTS.md §5).

## Honest shape per param (NULL until a feed appears)

| Param | Dim key | Honest shape when a feed lands | Buyer-side check meanwhile |
|---|---|---|---|
| P4-004 Kinnistus süva + notary checkpoint (demo, notar.ee leg) | `notar_closing_guidance` | per-listing dim, weak-good capped (the guidance leg — stays NULL by construction: prose versions a checklist, never a score) | Read the notar.ee Kinnisvaratehingud page; compute the fee on the notari-tasu page; pull the RIK e-Kinnistusraamat extract; book the notary; scored P4-004 legs already joined (KKIS/kitsendused dims_p4_maa_kataster dim_kinnistus_syva, taitur dims_p4_taitur dim_kinnistus_checkpoint, AT dims_p4_ata dim_kinnistus_checkpoint, maksuvõlg dims_p4_emta dim_kinnistus_debt) + deal costs dims_group16a dim_closing_costs |

Never 0 and never 100 would apply once scored (absence is not proof
of a closable deal); today the reason says `EI OLE` and points at the
concrete check above. Every scored-future reason must trace to a
joined record.

## Judgment calls (for the reviewer)

1. Demo with NO coverage issue: #253 states the remaining 0 params
   using this source need the follow-up coverage issue "created after
   this demo" — but P4-004's non-guidance legs are already scored
   (taitur #336, ATA, EMTA, maa-kataster, all merged before this
   probe), so there is nothing left to cover and no follow-up issue
   is opened. The sibling legs are named, never re-scored (P4-020
   split-slice precedent: ATA notices in dims_p4_ata, bureau scores
   NULL in dims_p4_creditinfo).
2. Pairing rationale: P4-004 source 2 is the notar.ee checkpoint
   guidance leg (closing feasibility) — the demo slice. Sibling
   sources stay scored where they live: RIK paid flow (unjoined
   everywhere — named in every P4-004 NULL reason), taitur register
   (dims_p4_taitur), AT notices (dims_p4_ata), KKIS kitsenduste kaart
   (dims_p4_maa_kataster), EMTA maksuvõlg (dims_p4_emta).
3. (origin, pois) signature, not a join signature: with the
   dated-negative verdict there is no ingestion and hence no join
   input (rahmin #315/#377 precedent for dated-negative NULLs).
4. No shared-file edits (livability.py, WEIGHTS, layers, layers.md,
   parameters4.md untouched): 3 new files only. Central hook (enrich
   join + WEIGHTS rebalance) stays one joint change across all
   batches.

## Reopening checklist (when a pollable feed appears)

1. Re-run the probes above yearly (or sooner if notar.ee/avaandmed
   or Teabevärav gains a notary dataset); paste fresh evidence
   in the reopen PR.
2. If a machine-readable guidance export appears, version the
   checklist text from it on fixtures first — it still versions the
   checklist, never a per-listing score.
3. Graduate the dim ONLY from joined records; keep NULL-with-
   Estonian-reason for every missing leg.
4. Add the explicitly-flagged live integration test (not a unit run).
