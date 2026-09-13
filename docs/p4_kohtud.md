# P4 kohtud verdict note — Kohtute infosüsteem published decisions (P4-020 leg)

> Dated-negative verdict for issue #317 (demo only — P4-020 is the
> only param naming this source, so there is no coverage follow-up;
> P4-020's sibling legs keep their owners, see below).
> Checked 2026-09-13. Single param is a documented no-map NULL dim
> (OTA PR #131 precedent); the scorer lives in
> `services/scoring/dims_p4_kohtud.py`, pinned by
> `services/scoring/tests/test_dims_p4_kohtud.py`.

## Verdict

**No open per-entity decisions feed — the dim stays NULL with an Estonian reason.**
Published court decisions are reachable through the browser search UI
(Riigi Teataja `kohtulahendid` search) and the authenticated e-toimik
case-file system — both linked from the public `kohus.ee` portal. Neither
is a machine-readable per-property/per-developer feed, and no open-data
page, developer portal, X-tee service, or bulk download is advertised.
Case-level records are proceedings involving named parties, so joining
them to listings would mean handling personal data — which this repo
refuses (AGENTS.md §5; no scraping or storing of personal data per #317).
There is no ingestion to cache, no TTL to state beyond this one-off check,
and no honest enforcement flag to paint from a portal landing page.

## Openness evidence (1 polite check, 2026-09-13, no decision download, no auth)

Exactly 1 request with the labelled one-off user-agent
`home-finder kohtud openness-check #317 (one-off, single GET, no retry;
contact via GitHub home-finder)`, `--max-time 25`, headers +
visible-text scope read only. Raw body: `/tmp/hf-kohtud-body.html` (one-off
PR record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `GET https://www.kohus.ee/` → HTTP 200 (46 633 bytes, 0.26 s) | Cloudflare-fronted RIK/Drupal portal, `content-language: et`; visible text (~5.4k chars) with "Kohtulahendid" (6 hits) and "Otsi"/"otsing" (2 hits) | portal reachable; decisions path is the browser UI, not a data feed |
| Decision href targets in the same body | `https://www.riigiteataja.ee/et/otsing/kohtulahendid`, `https://www.riigiteataja.ee/kohtulahendid/koik_menetlused.html`, `https://etoimik.rik.ee/` | published decisions live behind the Riigi Teataja search UI and the authenticated e-toimik case files |
| Keyword sweep of the same visible text: avaandmed / API / X-tee / X-Road / allalaad / REST / masinloetav | All absent | no open-data page, no developer portal, no X-tee service, no bulk download, no machine-readable property/developer filter |

Judgment call: the check stopped at portal-landing level on purpose —
one GET showing the decisions path is the browser search UI plus the
authenticated e-toimik carries the verdict for the source family.
Per-entity joins all need the same non-existent machine feed by
construction. Enumerating search endpoints, driving session flows, or
reading decisions to join parties to listings would be exactly the
personal-data scraping this repo refuses (AGENTS.md §5).

## Honest shape (NULL until an open per-entity feed appears)

| Param | Dim key | Honest shape when the feed answers | Buyer-side check meanwhile |
|---|---|---|---|
| P4-020 enforcement, Kohtute infosüsteem leg (demo) | `enforcement_kohtud` | per-entity flag from joined published-decision rows with a property/developer filter only (case reference + court + date, never party personal data) | Ametlike Teadaannete pankroti-/täiteteated, notarikontroll (notar.ee), kohtuvaidluse kahtluse korral KÜ/omaniku päring |

Sibling P4-020 slices keep their owners (untouched): AT notices
(`dims_p4_ata` `dim_enforcement`, cap 75), kohtutäiturite register
(`dims_p4_taitur` `dim_enforcement`, 15/40/70), e-Äriregister
maksehäired/aruandevõlad (`dims_p4_arireg` `dim_enforcement_arireg`),
Maa-amet kitsendused (`dims_p4_maa_kataster` `dim_enforcement`), and the
Creditinfo bureau slice (`dims_p4_creditinfo` `dim_enforcement_ci`, NULL)
— not faked here.

## Judgment calls (for the reviewer)

1. Single-param demo, no coverage issue: "kohtute infosüsteem" appears
   exactly once in parameters4.md (P4-020 source (5)) — one module, one test
   file, one verdict note.
2. The dated negative keeps the verdict: a future challenge must bring an
   open per-entity machine feed (or X-tee service) with a property/developer
   filter — not a screen-scrape of the search UI or e-toimik, and never
   party personal data.
3. No shared-file edits (livability.py, WEIGHTS, layers, layers.md,
   parameters4.md, sibling dims untouched): 3 new files only. Central hook
   (enrich join + WEIGHTS rebalance) stays one joint change across all
   batches.

## Reopening checklist (when an open per-entity feed appears)

1. Re-run the probe above on demand (a feed announcement, not a cron —
   there is no ingestion to refresh); paste fresh evidence in the reopen PR.
2. If RIK (or an attributed mirror) serves a keyless per-entity decisions
   feed with a property/developer filter, transcribe one Tallinn week of
   dated rows (case reference + court + date, no party data) into the cache
   dir and run them through a parser + join on fixtures first.
3. Graduate the dim to a per-entity flag ONLY from joined rows; keep
   NULL-with-Estonian-reason for every missing leg.
4. Add the explicitly-flagged live integration test (not a unit run).
