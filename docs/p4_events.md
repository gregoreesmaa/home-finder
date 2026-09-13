# P4 events verdict note — Tallinna event & fireworks calendars (P4-033 + P4-047 slice)

> Dated-negative verdict for issues #310 (demo) and #375 (coverage).
> Checked 2026-09-13. Both params are documented no-map NULL dims
> (OTA PR #131 precedent); scorers live in
> `services/scoring/dims_p4_events.py`, pinned by
> `services/scoring/tests/test_dims_p4_events.py`.

## Verdict

**No open machine feed — both dims stay NULL with Estonian reasons.**
Lauluväljak/Pirita event rows, church-bell/noise permits, fireworks
permits, and the festive calendar live on human-readable culture pages
(CMS institution links, a React app shell) or behind a misconfigured
domain. There is no public bulk feed to poll politely, so there is no
ingestion to cache, no TTL to state beyond this one-off check
(re-probe each spring before the outdoor-event season), and no honest
calendar band to paint.

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

6 single GETs plus 2 TLS-failed attempts total (labelled one-off
user-agent `home-finder events openness-check (one-off, few pages max,
no scrape)`, 2 s pacing, `--max-time 25`, headers + visible-text
keyword scope read only). Raw bodies: `/tmp/hf-p4-events/` (one-off PR
record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://www.lauluväljak.ee/` → TLS cert mismatch (curl 60); bare domain same | Transport error, never data; not retried (429/errors are a stop signal) | No calendar confirmed at the venue domain over HTTPS |
| `http://lauluväljak.ee/` → HTTP 400 (~8.8 KB) | Veebimajutus.ee parking page (582 visible chars; 0 for ilutulestik/luba/load/lauluväljak/laulupidu/kalender/üritus/sündmus/csv/json/api/avaandmed) | IDN domain serves hosting-placeholder HTML, not an event calendar |
| `https://kultuurikava.ee/` → HTTP 200 (1796 bytes) | React SPA shell (`/static/js/main.07d7e3b5.js`, "Sinu teejuht kultuurimaastikul"); no server-rendered event rows | Culture programme exists as an app shell — chasing its app API exceeds a polite probe budget |
| `https://www.rescue.ee/et` → HTTP 200 (~143 KB) | Päästeamet homepage (~3.8k visible chars); 0 for ilutulestik/luba/load/kalender | No fireworks-permit feed advertised at entry level |
| `https://andmed.eesti.ee/dataset?q=ilutulestik` → HTTP 200 (~75 KB) | 12 visible characters ("Teabevärav" JS shell) | No trivially pollable national-portal fireworks dataset (same shell as #264/#277/#284/#298) |
| `https://www.tallinn.ee/et/kultuur` → HTTP 200 (~83 KB) | CMS culture page (institution links, 2x Lauluväljak, 3x üritus, 2x sündmus); 0 for kalender/ilutulestik/load/csv/json/api/avaandmed | Institution links, never dated event rows — no calendar band is painted from them |

Judgment call: the check stopped at entry/shell level on purpose — no
form replay, no app-API chasing, no newsroom crawling. Replaying them
would be exactly the human-page harvesting this repo refuses (AGENTS.md
§5).

## Honest shapes per param (all NULL until a feed appears)

| Param | Dim key | Honest shape when a feed lands | Buyer-side check meanwhile |
|---|---|---|---|
| P4-033 nuisance calendar (demo) | `events_calendar` | calendar dims with dates, never gradient (dated Lauluväljak/Pirita rows off the calendar) | Lauluväljak + Pirita calendars, church-bell/noise permits, on-site listen at the Kesklinn/Pirita edge; cruise days in dims_p4_sadam; hunting notices in dims_p4_kesk |
| P4-047 small horrors (coverage) | `fireworks_calendar` | calendar dims with dates, never gradient (dated permit rows off the fireworks calendar) | organiser permits via the city/Päästeamet, on-site listen around jaanipäev + new year; noise complaints + ploughing in dims_p4_komun; KÜ logs in dims_p4_kudocs; event-traffic calendar in dims_p4_paaste |

Never 0 and never 100 would apply once scored (absence is not proof of
calm or disaster); today every reason says `EI OLE` and points at the
concrete check above. Every scored-future reason must trace to a joined
record.

## Judgment calls (for the reviewer)

1. Demo + coverage in one PR: #375 defines coverage as extending the
   demoed ingestion with "no new plumbing expected" — with a
   dated-negative demo there is no ingestion to extend, so the P4-047
   fireworks slice lands in the same verdict module (komun #290+#363,
   TLT #277+#351, elektrilevi #264+#344, Elron #284+#358, sadam
   #298+#368 precedent).
2. Pairing rationale: both params name this source family in their
   parameters4.md source lists — P4-033 sources (2) Lauluväljak/Pirita
   calendars + (3) bells/noise permits, P4-047 source (3) fireworks
   permits + festive calendar — so there is no weak link; each dim is
   the events leg and names the cousin slices that own the other legs.
3. Complements, not duplicates: the P4-033 reason names the sadam
   cruise leg (dims_p4_sadam) and the kesk hunting leg (dims_p4_kesk);
   P4-047 names the komun complaint/ploughing legs (dims_p4_komun),
   the KÜ log slice (dims_p4_kudocs), and the Päästeamet event-traffic
   calendar (dims_p4_paaste). Distinct dim keys throughout.
4. The live culture pages observed (tallinn.ee institution links,
   kultuurikava shell) prove activity, not openness: activity is not a
   feed. The parking page + TLS mismatch at lauluväljak.ee prove the
   venue domain cannot even be polled, let alone joined.
5. No shared-file edits (livability.py, WEIGHTS, layers, layers.md,
   parameters4.md untouched): 3 new files only. Central hook (enrich
   join + WEIGHTS rebalance) stays one joint change across all batches.

## Reopening checklist (when a pollable feed appears)

1. Re-run the six probes above each spring (event-season TTL: spring,
   before the outdoor season); paste fresh evidence in the reopen PR.
2. If a venue or the city exposes a pollable event/permit calendar
   (CSV/JSON/iCal arrival-permit feed), transcribe one week of dated
   rows into the cache dir and run them through a `parse_events_feed`
   + calendar join on fixtures first.
3. Graduate dims to bands ONLY from joined records (calendar per the
   table above); keep NULL-with-Estonian-reason for every missing leg.
4. Add the explicitly-flagged live integration test (not a unit run).
