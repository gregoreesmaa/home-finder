# P4 Veeteede verdict note — Tallinn Bay icebreaking without a machine feed (P4-055)

> Dated-negative verdict for issue #311 (single-param demo, no
> coverage issue — the issue states 0 remaining params use this
> source, so no follow-up coverage issue exists).
> Checked 2026-09-13. The single param is a documented no-map NULL
> dim (OTA PR #131 precedent); the scorer lives in
> `services/scoring/dims_p4_veeteede.py`, pinned by
> `services/scoring/tests/test_dims_p4_veeteede.py`.

## Verdict

**No verified keyless icebreaking-notice feed — the dim stays NULL with an
Estonian reason.** The old `veeteedeamet.ee` host is a 301 forwarder to
Transpordiamet (the successor since the 2021 merger). Transpordiamet's
`/jaamurre-ja-talvine-navigatsioon` topic page is a rich human guide
(fleet Tarmo / EVA-316 / Botnica, Gulf of Finland work area, served ports
including the Tallinna/Kopli/Muuga bays), but its dated notices are
PDF käskkirjad with month-year parentheticals (e.g. "Kopli, Tallinna ja
Muuga lahe sadamate 2026 veeb-nõuded") — human publications, never a
comparable machine vintage. The national Teabevärav catalogue is a JS app
shell with no server-rendered icebreaking dataset, and `baltice.org`
(the page's related link) is a reference, not a polled interface. There
is no polite pull to cache, no TTL to state beyond this one-off check
(re-probe yearly each autumn before the ice season, or sooner if a
pollable dated feed appears), and no honest calendar to paint without
joinable ISO dates — one PDF filename says nothing about tonight's
bay-edge rumble.

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

6 served requests total (single GETs, labelled one-off user-agent
`home-finder veeteede openness-check #311 (one-off, single GETs, file
cache for PR record; contact via GitHub home-finder)`, `--max-time 25`,
headers + visible-text keyword scope read only; 2–3 s pacing; no PDF
parsing, no RSS driving, no form driving, redirects not spidered beyond
the single canonical documented link). Raw bodies:
`/tmp/hf-p4-veeteede/` (one-off PR record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://www.veeteedeamet.ee/` → HTTP 301, 0 B, `location: https://www.transpordiamet.ee/` | Old Veeteede Amet host is a forwarder | Successor confirmed; the old host is not a feed |
| `https://transpordiamet.ee/` → HTTP 200, 227004 B, title "Transpordiamet \| Muretult kohale!" | Portal front; sweep (~12.5k visible chars): jäämur x2; 0 for avaandmed / open data / API / andmestik / masinloetav / csv / geojson / wfs / wms; links `/jaamurre-ja-talvine-navigatsioon`, `/jaateed` | Working host confirmed; icebreaking paths documented one click deeper, no machine feed on the landing |
| `https://transpordiamet.ee/jaamurre-ja-talvine-navigatsioon` → HTTP 200, 226301 B, main ~6084 visible chars | Human icebreaking guide (jäämur x37: Tarmo / EVA-316 / Botnica, Soome laht, Tallinna/Kopli/Muuga lahe sadamad); 0 for avaandmed / API / andmestik / masinloetav / csv / json / geojson / wfs / rss / kalender / graafik; dated notices are month-parenthetical PDF käskkirjad; only machine pointer in main is the site-wide `rss-feeds/rss.xml` | Dated notices exist as human PDFs, never a comparable machine vintage — the P4-055 icebreaking calendar cannot be measured |
| `https://transpordiamet.ee/jaateed` → HTTP 200, 205446 B (~11.1k visible chars) | Ice-road page (jääte x26), not the Tallinn Bay leg; same 0 for every machine format | Different buyer question (ice roads vs bay icebreaking); no feed either way |
| `https://andmed.eesti.ee/dataset?q=jäämurre` → HTTP 200, 75497 B, title "Teabevärav" | JS app shell, 12 visible characters, no server-rendered results | No trivially pollable national-portal icebreaking dataset (same shell as the #264/#277/#284 checks) |
| `https://baltice.org/` (page "Seotud viited" link) → HTTP 301, 232 B | Single documented-link probe, polite stop at the redirect, not followed | Reference link confirmed, not a polled interface |

Judgment call: the check stopped at storefront/page level on
purpose — no PDF parsing, no RSS driving, no Teabevärav JS-app
driving, no baltice.org redirect chasing (tervise #289 precedent).
Driving a news feed or a PDF set notice-by-notice would be scraping
human publications, not polling a feed — exactly what AGENTS.md §5
refuses.

## Honest shape (NULL until a pollable feed appears)

| Param | Dim key | Honest shape when a feed lands | Buyer-side check meanwhile |
|---|---|---|---|
| P4-055 Harbour/air timetable, Veeteede slice (demo) | `jaamurde_calendar` | calendar dim off joined dated Tallinn Bay icebreaking notices (flat exposure while a dated notice is in effect, e.g. the sibling 45 band; 2 km bay propagation gate, membership never gradient; never 0/100 on this leg alone — an active season hints at winter-night rumble on the bay edge, never a guarantee) | kuula jäähooajal kohapeal Tallinna lahe ääres + kontrolli sadamagraafikut ts.ee-st; scored cousins: EANS dims_p4_eans + Männiku dims_p4_kvagi; NULL cousins: Sadam dims_p4_sadam + Elron dims_p4_elron + komun-validation dims_p4_komun |

Every scored-future reason must trace to a joined dated notice
record; a month-parenthetical PDF filename must never score a parcel.

## Judgment calls (for the reviewer)

1. Single-param demo, no coverage issue: #311 states the remaining
   0 params using this source are covered by a follow-up created
   after this demo — with a dated-negative demo there is no ingestion
   to extend, so one dim in one module is the whole honest scope.
2. Split-slice contract: the Sadam foghorn/icebreaker slice
   (dims_p4_sadam dim_sadam_timetable, NULL), the EANS harbour/air
   slice (dims_p4_eans dim_harbour_air_calendar, SCORED), the Männiku
   weekend-pops slice (dims_p4_kvagi dim_manniku_weekend_calendar,
   SCORED), the Elron ööaknad slice (dims_p4_elron
   dim_elron_night_maintenance, NULL) and the komun validation slice
   (dims_p4_komun dim_schedulable_noise_calendar, NULL) stay where
   they live and are named, never re-scored here. Sibling modules
   were read first; parameters4.md untouched.
3. The dated PDF set is the reopen anchor, not today's verdict: a
   topic page attaching PDFs is not a verified feed URL. Parsing
   them today would be harvesting human publications.
4. No shared-file edits (livability.py, WEIGHTS, layers, layers.md,
   parameters4.md untouched): 3 new files only. Central hook
   (enrich join + WEIGHTS rebalance) stays one joint change across
   all batches.

## Reopening checklist (when a pollable feed appears)

1. Re-run the six probes above each autumn (ice-season TTL:
   autumn, before the freeze); paste fresh evidence in the reopen
   PR.
2. If Transpordiamet (or andmed.eesti.ee / baltice.org) exposes a
   pollable dated icebreaking feed (CSV/JSON arrival-departure or
   notice feed with ISO dates), transcribe one ice season into the
   cache dir and run it through a `parse_icebreaking_notices` +
   calendar join on fixtures first.
3. Graduate the dim to a flat calendar band ONLY from joined
   records; keep NULL-with-Estonian-reason for every missing leg.
4. Add the explicitly-flagged live integration test (not a unit run).
