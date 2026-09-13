# P4 libs: Tallinna libraries & culture-hours verdict note (issues #321 + #379)

Demo (#321) implements the Tallinna libraries & culture-hours source
openness check + P4-045 end-to-end; coverage (#379) wires P4-039 off
the same verdict. One PR closes both because the #379 body states it
extends the demoed ingestion with "no new plumbing expected" — and
with a dated-negative verdict there is no pipeline to extend, so all
three dims land in one verdict module (komun #290+#363, green
#300+#369 precedent).

## Openness verdict: dated negative (2026-09-13, 8 polite requests, labelled UA)

Raw bodies: `/tmp/hf-libs-probe/` (one-off PR record, not committed).
Seven single GETs + one header-only redirect check, 25 s timeout, no
retries, 2 s pacing; headers + visible-text keyword scope only.

| URL | Result | Verdict |
|---|---|---|
| `https://keskraamatukogu.ee/` (GET 302, 145 B, nginx) | bare domain is a redirect shell, not a feed | DATED NEGATIVE for a direct hours feed |
| header check on the same URL (no body) | `Location: https://tallinnaraamatukogud.ee` | redirect target confirmed |
| `https://tallinnaraamatukogud.ee/` (GET 200, ~176 KB, ~8.2k visible chars) | human CMS: branch list, "Kõik lahtiolekuajad" page, "Sündmuste kalender", newsletter; 0x csv/geojson/wfs/api/masinloetav/andmestik/avaandmed; "lahtioleku" 4x = nav prose, "külastus" 1x = cookie prose, "kalender" 2x = human event nav | DATED NEGATIVE for hours/visit tables |
| `https://www.tallinn.ee/et/kultuur` (GET 200, ~83 KB, ~4.6k visible chars) | institution link hub (Tallinna Raamatukogud, organiser-aid pages, newsletter); 0x csv/geojson/wfs/api/masinloetav/andmestik/avaandmed/lahtioleku | DATED NEGATIVE for the event feed |
| `https://kultuurikava.ee/` (GET 200, 1 796 B) | JS SPA shell ("You need to enable JavaScript"), no server-rendered feed | DATED NEGATIVE (same shell as #264/#277/#284/#290) |
| `https://andmed.eesti.ee/dataset?q=raamatukogu` (GET 200, ~75 KB, 10 visible chars) | "Teabevärav" JS shell | DATED NEGATIVE (same shell as #264/#277/#284/#290) |
| `https://www.tallinn.ee/et/otsing?search_api_fulltext=raamatukogude+külastatavus` (GET 200, ~148 KB, ~10.4k visible chars) | 22x raamatukogu = human content; 0x külastatavus/csv/geojson/wfs/masinloetav/andmestik/lahtioleku; 2x avaandmed + 4x statistika = footer/nav chrome | DATED NEGATIVE for visit statistics |

Pull contract: nothing pollable, so no `fetch_*` helper (a fetcher
around human CMS pages would be brittle scraping dressed as
ingestion). TTL = one-off check; re-probe politely if the city
publishes a machine-readable hours/event/visits feed.

## Honest shapes per param (per-listing dim; NULL stays NULL)

| Param | Dim key | Scored shape | NULL when |
|---|---|---|---|
| P4-045 third places, library slice | `library_evening_hours` | per-branch evening-hours join per linnaosa (Kõik lahtiolekuajad) | always (human CMS, no table) |
| P4-045 third places, events slice | `culture_evening_events` | per-asum evening-events calendar join | always (hub links + JS shell + human CMS) |
| P4-039 civic capital, civic-use leg | `civic_use_visits` | library/youth-centre visits per linnaosa (taste-match only, never ethnic/wealth proxy) | always (no visit table) |

Every NULL reason says `hinnang` + `EI OLE` with the concrete buyer
check (Kõik lahtiolekuajad + õhtune jalutusring, kultuuriinfo
uudiskiri + Sündmuste kalender, raamatukogu/noortekeskuse
külastuspäring).

## Judgment calls (for the reviewer)

1. Demo + coverage in one PR: #379 defines coverage as extending the
   demo ingestion — with a dated-negative verdict there is no
   pipeline, so one verdict module holds all three dims.
2. P4-045 is two dims (different honest shapes: branch-hours join vs
   asum-events calendar), each with its own buyer check; P4-039 gets
   its one civic-use leg (leg 6 of its parameters4.md source list).
3. Slice boundary (no double-scoring): OSM owns mapped third-place
   density (dim_thirdplace, genuinely scores TASTE-match), peatus/TLT
   own evening access, rel2021 owns belonging demand, the keeper
   leg (e-Äriregister >10 yr independents) has no scorer in this
   repo; OSM owns the freshness NULL (dim_civic), arireg owns the
   fondikogumise echo NULL (dim_commons_echo); turnout / kaasav
   eelarve / Teeme Ära legs stay gaps. This module owns ONLY the
   three libraries-feed legs above, under distinct dim keys.
4. No shared-file edits (WEIGHTS/Overpass rebalance stays one joint
   change); 3 new files only.

## Refresh checklist (city publishes a machine-readable feed)

1. Re-run the 7 polite probes above; confirm HTTP 200 + feed keywords.
2. Add a `fetch_libs` pull + reviewed snapshot table in a new PR
   (human-reviewed facts, never an HTML scrape).
3. Score the three dims off the snapshot; keep NULL-with-reason for
   missing joins (unknown branch != closed).
