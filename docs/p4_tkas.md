# P4 tkas verdict note — Tervisekassa GP lists (P4-011)

> Dated-negative verdict for issue #272 (demo, single-param, no
> coverage issue).
> Checked 2026-09-13. The param leg is a documented no-map NULL dim
> (OTA PR #131 precedent); the scorer lives in
> `services/scoring/dims_p4_tkas.py`, pinned by
> `services/scoring/tests/test_dims_p4_tkas.py`.

## Verdict

**No open per-linnaosa bulk — the dim stays NULL with an Estonian reason.**
Tervisekassa publishes the practising-GP list ("Kõik Eestis nimistuga
tegutsevad perearstid") as a PowerBI-embedded interactive report: the
directory page server-renders 628 visible characters of section nav
plus a feedback form — no table, no per-GP rows, no avatud/suletud
flags, no linnaosa split — and the list itself renders client-side
from `app.powerbi.com/reportEmbed` behind a page JWT. The storefront
and the Perearstiabi guidance page carry `nimistu` only as prose
navigation (31x) with zero bulk markers anywhere (csv / xlsx /
andmestik / masinloetav / avaandmed / api / json / allalaadi all 0,
`avatud` / `suletud` 0x). There is no pollable nimistu open/closed
feed to pull politely, so there is no ingestion to cache, no TTL to
state beyond this one-off check (re-probe yearly, or sooner if
Tervisekassa or Teabevärav gains a nimistu dataset), and no honest
per-linnaosa availability score to paint from a hand-read of the prose.

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

6 requests total (labelled one-off user-agent `home-finder openness
probe #272 (one-off, single GETs; contact via GitHub home-finder)`,
2 s pacing between GETs, headers + visible-text keyword scope read only).
Raw bodies: `/tmp/hf-tkas-probe/` (one-off PR record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://www.tervisekassa.ee/` → HTTP 301 (466 bytes, Location: https://tervisekassa.ee/) | Bare-domain redirect | Transport note, not data |
| `https://www.tervisekassa.ee/et` → HTTP 301 (465 bytes, Location: https://tervisekassa.ee/et) | Host canonicalization | Transport note, not data |
| `https://tervisekassa.ee/et` → HTTP 301 (250 bytes, "Redirecting to /", Drupal x-redirect-id 300) | Language-path canonicalization | Transport note, not data |
| `https://tervisekassa.ee/` → HTTP 200 (68 346 bytes, ~5.8k visible chars, title "Tervisekassa", 93 links, Drupal CMS) | Sweep 0 for csv / xlsx / andmestik / masinloetav / avaandmed / allalaadi / opendata; single `api` hit is page chrome | Entry point confirmed, nothing machine-readable advertised; one GP-care section link `/perearstiabi` |
| `https://tervisekassa.ee/perearstiabi` → HTTP 200 (97 301 bytes, ~14.8k visible chars, title "Perearstiabi \| Tervisekassa", 91 links) | `nimistu` 31x as prose nav; `avatud` / `suletud` 0x; sweep 0 for csv / xlsx / andmestik / masinloetav / avaandmed / api / json / allalaadi | Guidance prose, not a feed; one directory link `.../koik-eestis-nimistuga-tegutsevad-perearstid` |
| `.../koik-eestis-nimistuga-tegutsevad-perearstid` → HTTP 200 (70 495 bytes, `<main>` 628 visible chars) | No `<table>`, no per-GP rows, no `avatud` / `suletud` / `vaba`, no `linnaosa` / `tallinn`; list is a `paragraph--type--powerbi-report` embed (`powerbi.embed(... app.powerbi.com/reportEmbed ...)`, page JWT accessToken) | JS-rendered BI report, not a pollable table |

Judgment call: the check stopped at storefront + perearstiabi +
directory-page level on purpose — no PowerBI token reuse, no
report-API probing, no survey/form driving, no Teabevärav re-probe
(#301 precedent: national-portal dataset search is a JS shell with
no server-rendered results), no deeper URL guessing. Deeper probing
is exactly the app-internals enumeration this repo refuses (AGENTS.md §5).

## Honest shape per param (NULL until a bulk appears)

| Param | Dim key | Honest shape when a feed lands | Buyer-side check meanwhile |
|---|---|---|---|
| P4-011 Perearst nimistu open/closed (demo, Tervisekassa leg) | `gp_list_open` | per-linnaosa table (open lists per linnaosa; bands only from joined rows, NULL stays NULL with Estonian reason) | Check the Tervisekassa perearstiabi nimistuotsing; file the perearsti vahetusavaldus; ask on site; scored P4-011 legs already joined (school capacity dims_p4_ehis dim_school_pressure, 0–6 demand dims_p4_rel2021 dim_kindergarten_pressure_rel) + queue half NULL in dims_p4_haridus dim_kindergarten_queue_gp |

Never 0 and never 100 would apply once scored (absence of an open
list nearby is not proof of no care access); today the reason says
`EI OLE` and points at the concrete check above. Every scored-future
reason must trace to a joined row.

## Judgment calls (for the reviewer)

1. Demo with NO coverage issue: #272 states the remaining 0 params
   using this source need the follow-up coverage issue "created after
   this demo" — but P4-011's non-GP legs are already scored
   (EHIS capacity #271, REL2021 demand grid, both merged before this
   probe; Haridusamet queue half NULL in #270), so there is nothing
   left to cover and no follow-up issue is opened. The sibling legs
   are named, never re-scored (P4-020 split-slice precedent: ATA
   notices in dims_p4_ata, bureau scores NULL in dims_p4_creditinfo).
2. Pairing rationale: P4-011 source (3) is the Tervisekassa nimistu
   open/closed leg (family-services availability) — the demo slice.
   Sibling sources stay scored where they live: Haridusamet queue
   stats (#270, NULL), EHIS capacity (dims_p4_ehis), REL2021 0–6
   demand (dims_p4_rel2021). Note #270's `kindergarten_queue_gp`
   NULL already bundles the GP half and points at the same
   nimistuotsing — the two NULLs agree; this module gives the
   Tervisekassa source its own key so a future per-linnaosa nimistu
   bulk graduates exactly one dim.
3. (origin, pois) signature, not a join signature: with the
   dated-negative verdict there is no ingestion and hence no join
   input (haridus #270 + notar #253 precedent for dated-negative NULLs).
4. A PowerBI embed is unpollable by construction (token replay
   against app.powerbi.com on every pull = app-internals scraping),
   so even a readable embed never graduates this dim — only a
   first-party per-linnaosa bulk table or Teabevärav nimistu
   dataset does. The per-GP interactive lookup alone never
   qualifies without scraping.
5. No shared-file edits (livability.py, WEIGHTS, layers, layers.md,
   parameters4.md untouched): 3 new files only. Central hook (enrich
   join + WEIGHTS rebalance) stays one joint change across all
   batches.

## Reopening checklist (when a pollable bulk appears)

1. Re-run the probes above yearly (or sooner if Tervisekassa or
   Teabevärav gains a nimistu dataset); paste fresh evidence
   in the reopen PR.
2. Transcribe one per-linnaosa open/closed table into the cache dir;
   run it through a `parse_linnaosa_table` + `index_by_linnaosa`
   on fixtures first (EHIS #271 precedent).
3. Graduate the dim ONLY from joined rows; keep NULL-with-
   Estonian-reason for every missing leg.
4. Add the explicitly-flagged live integration test (not a unit run).
