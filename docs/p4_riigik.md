# P4 Riigikontroll verdict note — KOV auditid, P4-019 leg (issue #316 demo)

> Dated-negative verdict for issue #316 (demo). Checked 2026-09-13.
> Single-param demo: P4-019 is the only param naming this source, so
> no coverage follow-up is owed. The scorer lives in
> `services/scoring/dims_p4_riigik.py`, pinned by
> `services/scoring/tests/test_dims_p4_riigik.py`.

## Verdict

**No open machine feed — the dim stays NULL with an Estonian reason.**
Riigikontroll publishes audits as human report pages
(`riigikontroll.ee/auditiaruanded/koik`, topic filter "Eelarve,
rahandus, maksundus"): KOV audits exist as prose reports (e.g.
"Asutuste võrk ja kinnisvara kohalikes omavalitsustes pärast
haldusterritoriaalselt reformi" — "Kuidas on omavalitsustes
hallatavate asutuste võrku ... 2018–2024 korrastatud?"), but there
is no per-KOV finance table and no per-listing data to poll. There
is no ingestion to cache and no TTL beyond this one-off check:
re-probe yearly (the param's TTL is annual), or sooner if
riigikontroll.ee or Teabevärav gains a machine-readable KOV audit
table.

## Openness evidence (one polite round, 2026-09-13, no PDF download, no auth)

4 served requests total (single GETs, labelled one-off user-agent
`home-finder riigik openness-check #316 (one-off, single GETs, no
retry; contact via GitHub home-finder)`, `--max-time 25`, headers +
visible-text keyword scope read only). Raw bodies:
`/tmp/hf-riigik-probe/` (one-off PR record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://www.riigikontroll.ee/` → HTTP 200 (80747 bytes, ~4.9k visible chars, title "Avaleht \| Riigikontroll") | Audit topic present in prose (15 audit hits, "Eelarve, rahandus, maksundus" filter); sweep 0 for andmestik / masinloetav / avaandmed / open data (csv/json/rss raw hits are Drupal chrome: ajax-loader SVG markup, drupal-settings-json, feed-link tags) | Entry point confirmed, nothing KOV-machine-readable advertised |
| `https://www.riigikontroll.ee/auditid` (guessed) → HTTP 404 ("Lehte ei leitud", 60157 bytes) | Documented negative guess, not a real path — the listing lives at `/auditiaruanded/koik` | No trivial audit API path at the guessed URL |
| `https://www.riigikontroll.ee/en/audits` → HTTP 200 (166382 bytes, ~12.8k visible chars, 226 links) | Links the real Estonian listing `/auditiaruanded/koik` plus `/en/audits/all` and per-type filters — human navigation, no dataset endpoint | Audit index is browsable prose, not a feed |
| `https://www.riigikontroll.ee/auditiaruanded/koik` → HTTP 200 (173503 bytes, ~12.5k visible chars, 0 PDF hrefs on the listing) | Per-report pages (`/auditiaruanded/<slug>`); KOV audits exist as prose (haldusreform-järgne asutuste-võrgu aruanne, 8 omavalitsus hits); sweep 0 for xlsx / andmestik / masinloetav / avaandmed / open data | Reports are human pages, not a per-KOV table |

Judgment call: the check stopped at listing level on purpose — no
per-report PDF download, no full-text parsing, no site-search
crawling, no Teabevärav re-probe (andmed.eesti.ee/dataset is a JS
shell per the #301 precedent). Deeper probing is exactly the
enumeration this repo refuses (AGENTS.md §5).

## Honest shape per param (NULL until a feed appears)

| Param | Dim key | Honest shape when a feed lands | Buyer-side check meanwhile |
|---|---|---|---|
| P4-019 KOV fiscal health (demo) | `audit_riigik` | per-KOV table, annual (võlakoormus, investeeringud, maamaksu trend — the audit leg) | Read the KOV/Tallinn audit report page (riigikontroll.ee/auditiaruanded/koik); Tallinna eelarve + eelarvestrateegia (tallinn.ee); Statamet leg dims_p4_stat + EMTA leg dims_p4_emta + Rahandusministeeriumi leg dims_p4_rahmin + arengukava leg dims_p4_cityplans + overturn-#242 G16 tables |

Never 0 and never 100 would apply once scored (absence of an audit
finding is not proof of a healthy KOV); today the reason says
`EI OLE` and points at the concrete checks above. Every
scored-future reason must trace to a joined record.

## Judgment calls (for the reviewer)

1. Single-param demo, no coverage issue: P4-019 source (6) is the
   only parameters4.md line naming Riigikontroll, so one module, one
   test file, one verdict note — no second file importing a pipeline
   that does not exist (Sentinel-2 #305 precedent). The issue body's
   "remaining 0 params" line is taken literally.
2. Pairing rationale: the EMTA sibling (dims_p4_emta.py,
   `dim_fiscal_health`) and the Rahandusministeeriumi sibling
   (dims_p4_rahmin.py, `dim_fiscal_rahmin`) were read first; their
   P4-019 slices are named, never re-scored here, and
   dims_group16*.py is untouched. Same split-slice precedent as
   P4-020 (ATA notices in dims_p4_ata, bureau scores NULL in
   dims_p4_creditinfo).
3. Human report pages are not a table: the openly readable listing
   was deliberately NOT turned into a proxy score
   (report-exists-for-Tallinn would score every listing identically
   while claiming fiscal health).
4. No shared-file edits (livability.py, WEIGHTS, layers, layers.md,
   parameters4.md untouched): 3 new files only. Central hook (enrich
   join + WEIGHTS rebalance) stays one joint change across all
   batches.

## Reopening checklist (when a pollable feed appears)

1. Re-run the four probes above yearly (or sooner if
   riigikontroll.ee or Teabevärav gains a KOV audit dataset); paste
   fresh evidence in the reopen PR.
2. If a per-KOV audit table appears, transcribe one vintage into the
   cache dir and run it through a `parse_riigik_tables` + per-KOV
   join on fixtures first.
3. Graduate the dim to a per-KOV table ONLY from joined records;
   keep NULL-with-Estonian-reason for every missing leg.
4. Add the explicitly-flagged live integration test (not a unit run).
