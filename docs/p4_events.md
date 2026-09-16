# P4 events verdict note — Tallinna event & fireworks calendars (P4-033 + P4-047 slice)

> Demo (#310) + coverage (#375) verdict, updated by the 2026-09-16
> §7.7 app-API dig. P4-033 is SCORED (city-grain season pulse off
> the kultuurikava app API); P4-047 stays a documented no-map NULL
> (OTA PR #131 precedent). Scorers live in
> `services/scoring/dims_p4_events.py`, pinned by
> `services/scoring/tests/test_dims_p4_events.py`.

## Verdict

**P4-033 OPEN (keyless app API, polite daily snapshot); P4-047
stays NULL with an Estonian reason.** The 2026-09-13 check stopped
at the kultuurikava.ee React shell; the 2026-09-16 dig (§7.7) read
the shipped bundle statically and found the site's own anonymous
read API (keyless embedded client token, no login): dated event
rows with venue names pour out of `api/?do=events` (1309 upcoming
Tallinn rows on 2026-09-16), so P4-033 graduates to a scored
Tallinn city-grain calendar (starts in the next 30 days; venue
grain refused — no places bulk, per-alias enumeration would be
scraping). Fireworks/dated-permit rows exist NOWHERE in that API
(25 cultural categories, no ilutulestik/permit field), so P4-047
keeps its NULL with the dig evidence in the reason.

## Openness evidence II (the §7.7 dig, 2026-09-16 — P4-033 OPEN)

6 tiny reads + 2 static-asset fetches total (labelled one-off
user-agent `home-finder events dig (issue #310, one-off, tiny reads,
no scrape)`, 2–4 s pacing, `--max-time 25–40`, headers +
visible-text + bundle-static scope read only, no scraping, no auth,
no retries; no HTTP 429 hit). Raw bodies: `/tmp/hf-dig-events/`
(one-off PR record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `GET https://kultuurikava.ee/` → HTTP 200 (1796 B) | SPA shell, bundle `/static/js/main.07d7e3b5.js` (same hash as 2026-09-13) | Shell confirmed, dig proceeds statically |
| `GET .../static/js/main.07d7e3b5.js` → HTTP 200 (1 458 747 B) | `REACT_APP_API_URL="https://www.kultuurikava.ee"`, published anonymous `REACT_APP_API_TOKEN="1499ddfb…294"` (full value in the module docstring); public read actions `api/?do=events\|getbyurl\|categories\|totalevents`, `utility/?do=notemptycounties`; login-gated `/auth`, `/myprofile`, `/extranet` + `:8443` admin edit link untouched | Keyless read API named; gated surface mapped and refused |
| `GET api/?do=categories&token=<public>&lang=nat&format=json` → HTTP 200 (1712 B) | 25 cultural categories (Teater/Muusika/Kino/Pidu & Klubi/Sport/…/Kirik/Rahvakultuur/…) — zero for fireworks/ilutulestik/permit | P4-047 coverage join has no feed leg: stays NULL |
| `GET api/?do=events&…&city=tallinn&order=starta&start=0&limit=2&format=json&…` → HTTP 200 (15 357 B) | envelope `{code,message,data:{total,events}}`, `data.total=1309`; row = `{id,name,start_time,end_time(unix),place_id,place_name,city,county,categories[],isfree,times[],ticketurl[],url}`; sample row is a 2019–2026 museum exhibition | Dated Tallinn calendar proven; scorer counts STARTS (season pulse), not active long-runs |
| `GET utility/?do=notemptycounties` → HTTP 200 (21 111 B) | Harjumaa (`harjumaa`) + valds (Anija/Jõelähtme/…) + Tallinn city; 17 counties country-wide | Harjumaa coverage proven (reopen graduate, not this PR) |
| `GET api/?do=getbyurl&type=place&url=<alias>` → HTTP 200 (4364 B) | place = `{address_nat, lat, lng, city{…}, events[]}`; full-URL form first failed `code -1 "Incorrect object 2"`, alias-slug form works; NO places bulk action exists | Venue coords exist per-alias only → venue-distance join would be enumeration (refused); city grain is the honest shape |

Refresh: rows carry `created`/`modified` unix timestamps (sample
`modified` = September 2026) — live and current. Pull contract:
single bounded GET (`city=tallinn`, `start=0`, `limit=500`) max
1 / 24 h per cache dir (`EVENTS_TTL_S = 86400`; the feed states no
cadence, so daily per AGENTS.md §5 polite-cron guidance); body
stored only on HTTP 200 + JSON; 429/errors stop and cache nothing.
If the site rotates the published token the pull degrades to None
(honest NULL), never to a guess.

## Openness evidence I (first round, 2026-09-13, no scraping, no auth)

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

## Honest shapes per param (P4-033 scored 2026-09-16; P4-047 NULL)

| Param | Dim key | Honest shape | Buyer-side check meanwhile |
|---|---|---|---|
| P4-033 nuisance calendar (demo) | `events_calendar` | SCORED Tallinn city-grain calendar: event STARTS in the next 30 days off the cached snapshot (0→85 … ≥200→30; never 100/never 0; first-cut bands, recalibrate on reopen). Every Tallinn listing shares the month value — temporal signal, no venue join (no places bulk). Windows run off the snapshot `fetched_at`, stated in every reason | Lauluväljak + Pirita calendars, church-bell/noise permits, on-site listen at the Kesklinn/Pirita edge; cruise days in dims_p4_sadam; hunting notices in dims_p4_kesk |
| P4-047 small horrors (coverage) | `fireworks_calendar` | NULL (EI OLE): no dated-permit feed anywhere in the API (25 categories, no ilutulestik; ticket links are commerce) | organiser permits via the city/Päästeamet, on-site listen around jaanipäev + new year; noise complaints + ploughing in dims_p4_komun; KÜ logs in dims_p4_kudocs; event-traffic calendar in dims_p4_paaste |

Never 100 and never 0 on the scored leg (calm is not guaranteed
silence; a busy month is not a disaster). Every scored reason traces
to the cached snapshot (count + soonest start + snapshot date).

## Judgment calls (for the reviewer)

1. Demo + coverage in one PR: #375 defines coverage as extending the
   demoed ingestion with "no new plumbing expected" — the P4-047
   fireworks slice IS the same snapshot read for permits (absent:
   25 categories, no ilutulestik — pinned NULL with that evidence),
   so it lands in the same module rather than a second file importing
   a pipeline that does not exist (komun #290+#363, TLT #277+#351,
   elektrilevi #264+#344, Elron #284+#358, sadam #298+#368 precedent).
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
   parameters4.md untouched): this dig edits only the 3 files the
   re-opened issues own (dims module + its test + this note).
   Central hook (enrich join + WEIGHTS rebalance) stays one joint
   change across all batches.

## Reopening checklist (post-dig)

1. Re-pull the Tallinn snapshot each spring before the outdoor season
   (daily TTL handles freshness; the spring check recalibrates
   `CALM_BANDS` from a real starts histogram — the current bands are
   first-cut with no live calibration).
2. Harjumaa/county graduation: `utility/?do=notemptycounties` proves
   county coverage; add per-county snapshots + listing-city routing
   (the scorer already NULLs non-Tallinn cities honestly).
3. Venue grain ONLY if a places bulk appears: per-alias `getbyurl`
   enumeration stays refused (scraping, not polling).
4. Fireworks permits (P4-047): needs a dated permit feed from the
   city/Päästeamet — kultuurikava categories prove nothing more to
   find here; re-check the category list yearly.
5. Add the explicitly-flagged live integration test (not a unit run).

## Update 2026-09-16 (issue #540): Piletimaailm feed is ALIVE

The reopening condition above is met for ONE leg. Polite probes, one
GET per endpoint, `home-finder-probe/1.0` User-Agent, `--max-time 25`,
raw files at /tmp/hf-probes/ (one-off PR record, never committed):

| Probe | Result |
|---|---|
| `GET https://www.piletimaailm.com/performances/feed.json` | HTTP 200, 5 087 134 bytes JSON — 397 events, 2026-09-16→2026-10-16 (~30-day forward window), 21-key schema (venue/hall/address/city/category/date, NO coords) |
| `GET .../downloads/yrituste_voog_api.pdf` | HTTP 404 — guide gone (site restructured); schema self-describing, nothing blocked |

Coverage: venue 100%, city 86%, category 99.5% (Teater 308, Kino 75);
Tallinn 88 events / 11 venue strings (~8 physical: Draamateater 44,
Theatrum 14, Mere 9, Noblessner/Kumu 7, Salme 5, Estonia/Süda 1).
NO Lauluväljak/stadium/Pirita rows — the P4-047 horrors leg stays
NULL; the feed serves the P4-045 evening-culture leg only.

New module `services/scoring/dims_p4_events_feed.py` (this issue's ONE
allowed shared-file edit is this note itself): per-venue 30-day
event-days → joined-0 = 80 (real calm), ≤5 = 60, above = 40, missing
join NULL (p4_trans precedent); horrors dim always NULL with the
sibling-leg buyer checks. `dims_p4_events.py` (#310/#375) is
untouched. Venue→coordinate join: manual feed-address table, coords
None until the harvest geocodes (never guessed) — reviewer call,
documented in the module. Licence CC BY-SA 3.0, annual harvest.
