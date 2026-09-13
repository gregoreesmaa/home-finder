# P4 taitur: Kohtutäiturite register verdict note (issues #255 + #336)

Demo (#255) implements the Kohtutäiturite register ingestion + P4-020
end-to-end; coverage (#336) wires P4-004's taitur slice off the same
ingestion. One PR closes both because the #336 body states it extends
the demoed ingestion — P4-004's source list names the kohtutäiturite
register (active täitemenetlus, Tallinn properties) as source (4),
i.e. the same feed P4-020 demos. No new plumbing.

## Openness verdict: dated negative (2026-09-13, keeps per #255)

Two HEAD probes total (custom UA, short timeout, no scraping, no auth
attempts):

```
HEAD https://kpkoda.ee/                -> HTTP 200 (Apache, WordPress)
HEAD https://www.ametlikudteadaanded.ee/ -> HTTP 405 (Cloudflare RIK JS app)
```

The Chamber's public site carries the bailiff contact directory
(pages, not a data feed); Ametlikud Teadaanded notices are searchable
in the browser UI with no anonymous bulk/search endpoint. No anonymous
per-property/per-developer active-täitemenetlus feed verified
2026-09-13. Dated negative keeps the verdict: the register stays
CLOSED for the per-entity active-proceedings purpose, so the dims
score ONLY joined snapshot slices and stay NULL otherwise. Personal
data is never fetched or stored — the snapshot layout has no debtor
name / personal-code columns, and the parser skips any row carrying
them (pinned by test).

Pull contract: max 1 download / 24 h per cache dir (`TAITUR_TTL_S =
86400`; enforcement actions and auction notices appear daily),
single GET, no retries — HTTP 429/errors are a stop signal. Transport
errors are never cached as data; the scorers stay NULL with an
Estonian EI OLE reason until a join lands. Scored shapes are proven
on fixtures only (hermetic tests).

## Honest shapes per param (bands, NULL stays NULL)

| Param | Dim key | Joined slice | Scored shape | NULL when |
|---|---|---|---|---|
| P4-020 enforcement (demo) | `enforcement` | per-subject case list | active arest/keelumärge/oksjon on kinnistu → 15 (frozen deal); active developer-side case → 40 (clouded); resolved-only / empty slice → 70 (weak-good, cap named) | subject not in index (`cases is None`) |
| P4-004 kinnistus checkpoint (coverage) | `kinnistus_checkpoint` | same slice | property freeze → 20 (deal won't close); developer-side → 50 (notar asks more); clear slice → 70 (still needs väljavõte) | same; reason names the unjoined RIK paid flow |

Never 0 (the register slice alone does not zero a flat) and never
100 (coverage is partial by construction — absence of a joined case
is not proof of clean title). Weak-good cap 70 on both. Every scored
reason says `registriandmed, mitte hinnang` with the joined
stage/subject; every NULL reason says `EI OLE` and points at the
e-Kinnistusraamat extract + notary check.

## Judgment calls (for the reviewer)

1. Demo + coverage in one PR: #336 defines coverage as extending the
   demoed ingestion — splitting would ship an ingestion with one
   consumer, then re-touch every signature (EHR #249/#333 precedent).
2. Cap 70 (not the EHR 80): title risk is binary at closing — a
   "clean" slice is worth less than a standing kasutusluba, so the
   ceiling sits one band lower. Stated, not hidden.
3. `None` (unknown, EI OLE) vs `[]` (joined-empty, weak-good 70):
   the index lookup proves coverage, so only indexed emptiness
   scores. An unindexed subject must never read as clean.
4. Resolved-only history scores like empty (70): past cases do not
   discount the price — only active proceedings move the needle.
5. Property freeze outranks developer cases in both dims (pinned by
   test): arest on THIS kinnistu kills closing; pankrot on the
   developer's other entity only clouds it.
6. No shared-file edits (livability.py, WEIGHTS, layers, layers.md,
   parameters4.md untouched): 3 new files only. Central hook
   (enrich join + WEIGHTS rebalance) stays one joint change across
   all batches.

## Reopening checklist (when a per-entity feed appears)

1. Re-run the HEAD probes; paste fresh evidence in the reopen PR.
2. Pull one snapshot into the cache dir; run it through
   `parse_taitur_cases` + `index_by_subject` on fixtures first.
3. Recalibrate the 15/40/70 bands against real stage frequencies.
4. Add the explicitly-flagged live integration test (not a unit run).
