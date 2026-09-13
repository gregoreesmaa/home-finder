# P4 kesk verdict note — Keskkonnaamet national feed (P4-017 + 3 slices)

> Dated-partial verdict for issues #291 (demo) and #364 (coverage).
> Checked 2026-09-13. The national feed EXISTS and is pollable, but
> serves none of the four legs — all four params are documented
> no-map NULL dims (OTA PR #131 precedent); scorers live in
> `services/scoring/dims_p4_kesk.py`, pinned by
> `services/scoring/tests/test_dims_p4_kesk.py`.

## Verdict

**Open feed, unservable legs — all four dims stay NULL with Estonian
reasons.** KOTKAS avaandmed publishes keyless bulk JSON (permits,
registrations, applications, documents, monitoring reports, 4 xlsx
registers), but the schema carries no water-abstraction, hunting,
mining, blast-schedule, or solid-fuel subtype, and geography is
linnaosa free text with no coordinates and no parcel link. A
linnaosa permit-count band would score "paperwork near you", not
drinking-water reality, hunting season, blast Tuesdays, or stove
law — so no ingestion is staged (unused ingestion would be fake
progress) and every dim returns None with a buyer-side check.

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

8 requests total with labelled one-off user-agent
`home-finder openness-check (one-off, no scrape; issues #291/#364)`,
`--max-time 20/30`, single attempts, 1–2 s pacing. Raw bodies:
`/tmp/kesk-open/` (one-off PR record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://keskkonnaamet.ee/` (HTTP 200, 182 674 B) | Visible text ~9 960 chars; sweep 0 for avaandmed / open data / API / masinloetav / andmestik | No open-data surface on the storefront; permits live behind named e-service registers (KOTKAS submission, VEKA borehole search, FOKA, SPIM — access application needed) |
| `https://andmed.eesti.ee/dataset?q=keskkonnaamet` (HTTP 200, 75 497 B) | 10 visible chars ("Teabevärav" JS shell), no server-rendered results | No trivially pollable national-portal dataset (same shell as the #264/#277/#284 checks) |
| `https://kotkas.envir.ee/` (HTTP 200, 28 452 B) | JS-required app (AVE v2.13.64), "Sisene" login for self-service, public `/opendata` page linked | Register door is keyless for open data, gated for self-service |
| `https://kotkas.envir.ee/opendata` (HTTP 200, 26 570 B) | Taotlused .json 10.2 MB, Keskkonnaload .json 6.1 MB, Registreeringud .json 2.6 MB, Dokumendid .json 30.7 MB, Seirearuanded .json 22.6 MB + 4 xlsx; no licence stated | The open feed family (licence not claimed); page carries no refresh date (app internal version 2026-09-02 at check time) |
| `permits.json` (HEAD 200, application/json, 6 385 555 B; one full pull — server ignores Range) | 13 120 records; permit_type only KL (12 338) / KKL (782); status Kehtiv 4 227 / Arhiveeritud 8 892; geography linnaosa free text (503 Kehtiv Tallinn rows) | No water/mining/air subtype, no coordinates, no parcel link — P4-017 per-parcel join and P4-054 timetable+buffer impossible |
| `registrations.json` (HTTP 200, 2 734 673 B) | 5 320 records; permit_type only RE.JÄ (3 769) / RE.VT (981) / PHRR (550) / OLRR (20) | Waste/dredging-type registrations only — no servable leg |
| object_name free-text scan (observed, NOT used) | "vee" 77 Kehtiv rows (offshore-wind sea use, mine dewatering), "puurkaev" 13, "kaevand" 9, "paekivi" 1 (Väo remediation) | Keyword NLP would be fake precision: "vee erikasutus" never means drinking-water quality; names carry no dates/coords |
| `…/jahipidamine/kuttimisandmed` (HTTP 200, 192 575 B) | Human HTML page | Hunting figures are human publications; no hunting, blast-schedule, or solid-fuel dataset in the avaandmed list |

Judgment call: the check stopped at page + schema level on
purpose — no subscription-flow driving, no JS-app scraping, no
KOTKAS self-service login. Parsing human hunting pages would be
scraping publications, not polling a feed — exactly what this repo
refuses (AGENTS.md §5).

## What stays open (overturn paths, not wired here)

- **P4-017 water leg:** Tallinna Vesi ÜVK kaart, Terviseameti
  joogivee seire, and EHR veevarustuse liik stay the buyer checks
  (future Terviseamet / Tallinna Vesi / EHR source issues). A
  KOTKAS water-abstraction subtype with parcel geography would
  graduate only the kesk leg here.
- **P4-033 hunting leg:** keskkonnaamet.ee jahipidamise teated +
  Kaitseväe õppuste teated stay the checks. A hunting-notice
  dataset would graduate only the kesk leg.
- **P4-054 blast leg:** Maa-ameti maardlate register
  (Maardu/Harku paekivi) + Tark Tee truck info + kohapealne
  teisipäeva-hommiku vaatlus stay the checks. A mining subtype
  with blast dates + coordinates would graduate only the kesk
  leg.
- **P4-059 stove leg:** Tallinna Keskkonnaameti tahkekütte
  teated, EHR kütte liik, Päästeameti korstnateated stay the
  checks. A solid-fuel-zone dataset would graduate only the kesk
  leg.
- **Full overturn:** re-open #291, build the polite cached
  ingestion off the exact `/opendata/download_opendata?type=…`
  URLs (TTL: re-check annually — the page states no refresh
  cadence), and graduate the servable dim to a per-parcel rule
  join / calendar.

## Why demo + coverage share one PR

The coverage body (#364) states it extends the demoed ingestion
(#291). The ingestion exists (KOTKAS avaandmed) but serves no
leg, so the three coverage slices (P4-033, P4-054, P4-059) land
in the same verdict module instead of a second file importing a
pipeline none of the four dims can consume. One module, one test
file, one verdict note — no edits to shared files (same
precedent as Elron #284+#358, TLT #277+#351, and RB #281+#355).
