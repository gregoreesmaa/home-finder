# P4 green: Tallinna green-inventory verdict note (issues #300 + #369)

Demo (#300) implements the Tallinna green-inventory source openness
check + P4-048 end-to-end; coverage (#369) wires P4-042 + P4-056 off
the same verdict. One PR closes both because the #369 body states it
extends the demoed ingestion with "no new plumbing expected" — and
with a dated-negative verdict there is no pipeline to extend, so all
five dims land in one verdict module (komun #290+#363 precedent).

## Openness verdict: dated negative (2026-09-13, 12 polite requests, labelled UA)

Raw bodies: `/tmp/hf-green-probe/` (one-off PR record, not committed).
Single GETs, 25 s timeout, no retries, 2 s pacing; headers +
visible-text keyword scope only.

| URL | Result | Verdict |
|---|---|---|
| `https://www.tallinn.ee/et/keskkond` (GET 200, ~99 KB, ~5.9k visible chars) | Keskkonnaveeb landing (Keskkonnahoid / Linnaloodus); 0x csv/geojson/wfs/masinloetav/andmestik/haljasala/roheala/linnaaed/pink/vaatekoht | DATED NEGATIVE for the inventory feed |
| `https://www.tallinn.ee/et/otsing?search_api_fulltext=haljasala` (GET 200, ~147 KB, server-rendered) | 15x haljasala = human content only: korrashoid e-service, Kopliranna + Tedre/Kotka project pages, Purskkaevu/Pirita park pages; 0x csv/geojson/wfs/masinloetav; "pinkide" 1x = maintenance prose, not a register | DATED NEGATIVE for bench/inventory registers |
| `https://www.tallinn.ee/et/otsing?search_api_fulltext=linnaaed` (GET 200, ~144 KB) | only content hit = kindergarten photo album (Mustakivi linnaaed = lasteaia mänguaed); 0x järjekord/csv/geojson/wfs | DATED NEGATIVE for allotment-queue tables |
| `https://www.tallinn.ee/et/teenused/haljasalade-parkide-teede-ja-vaikeobjektide-korrashoid` (GET 200, ~148 KB; bare path 301s to /et/) | maintenance e-service description, not a dataset; 0x csv/geojson/wfs/masinloetav/andmestik/inventar/roheala/vaatekoht | DATED NEGATIVE for the inventory join |
| `https://gis.tallinn.ee/` (GET 200, 703 B, IIS default page) | viewer entry only, no endpoint at page level | DATED NEGATIVE for bulk polygons (no service enumeration — refused) |
| `https://andmed.eesti.ee/dataset?q=haljasala` (GET 200, ~75 KB, 12 visible chars) | "Teabevärav" JS shell | DATED NEGATIVE (same shell as #264/#277/#284/#290) |

Pull contract: nothing pollable, so no `fetch_*` helper (a fetcher
around human project pages would be brittle scraping dressed as
ingestion). TTL = one-off check; re-probe politely if the city
publishes a machine-readable inventory.

## Honest shapes per param (per-listing dim; NULL stays NULL)

| Param | Dim key | Scored shape | NULL when |
|---|---|---|---|
| P4-048 delights, bench slice | `bench_view_3min` | <3 min bench-view join (Kadriorg/Hirvepark/Pirita) | always (no register) |
| P4-048 delights, green slice | `delight_green_15min` | <15 min isochrone join (seenemets/ujula/gym/ice off rohealade kava) | always (kava = documents, not a feed) |
| P4-048 delights, queue slice | `allotment_queue` | annual queue table (Lillepi/Pelgu, queues = true demand) | always (no queue table) |
| P4-042 seasonality leg | `blossom_chorus_cells` | coarse hinnang cells (sirel/dawn-chorus, never doorway precision) | always (no inventory seasonality) |
| P4-056 green-deficit leg | `courtyard_green_deficit` | per-parcel courtyard green join | always (no parcel inventory) |

Every NULL reason says `hinnang` + `EI OLE` with the concrete buyer
check (3-minuti jalutusring, 15-minuti isokroon, aiandusühistu
päring, hommikune nuusutamine/kuulamine, hoovi-ülevaatus + KÜ päring).

## Judgment calls (for the reviewer)

1. Demo + coverage in one PR: #369 defines coverage as extending the
   demo ingestion — with a dated-negative verdict there is no
   pipeline, so one verdict module holds all five dims.
2. P4-048 is three dims (different honest shapes: <3 min join vs
   <15 min isochrone vs annual queue table), each with its own buyer
   check; P4-042/P4-056 get one green leg each.
3. Slice boundary (no double-scoring): EHR owns orientation
   breakfast-sun, peatus/TLT own <15 min access, OSM owns bakery
   anchors + the agreeing delights-NULL, paaste owns smoke cells,
   komun owns odour-complaint cells, kaur owns smoke episodes +
   fume validation, arireg owns emitter addresses, lidar owns the
   scoring enclosure index (+ilm/aerial/ehr legs). This module owns
   ONLY the five green-inventory legs above, under distinct dim keys.
4. No shared-file edits (WEIGHTS/Overpass rebalance stays one joint
   change); 3 new files only.

## Refresh checklist (city publishes a machine-readable inventory)

1. Re-run the 6 polite probes above; confirm HTTP 200 + feed keywords.
2. Add a `fetch_green` pull + reviewed snapshot table in a new PR
   (human-reviewed facts, never an HTML scrape).
3. Score the five dims off the snapshot; keep NULL-with-reason for
   missing joins (unknown parcel != green).
