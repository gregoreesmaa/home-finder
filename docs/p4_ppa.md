# P4 ppa verdict: PPA open data (P4-012 demo + P4-015 coverage)

Closes #278 (demo) and #352 (coverage) — paired in one PR because the
coverage body states it extends the demo ingestion; no new plumbing was
needed beyond the demo's `coverage` argument (said here as required).

## 1. Openness verdict (2026-09-13, KEEP — positives and dated negatives)

Six polite single GETs (UA `home-finder-p4-ppa-probe/1.0`,
`--max-time 20`, no retries, ~2 s pacing), cached to `/tmp/hf-ppa-cache`
(scratch, never committed). Two HEADs + two 4 KB ranged peeks followed
to verify the machine feeds without a bulk pull.

| # | URL | Result |
|---|-----|--------|
| 1 | `https://www.politsei.ee/` | **OPEN, human HTML, no key.** `HTTP 200`, `text/html`, 64 793 bytes, title "Politsei- ja Piirivalveamet". No statistika link on the homepage; links on to `/et/liiklusinfo` and `/et/politseis-registreeritud-oeoepaeeva-suendmused`. |
| 2 | `https://www.politsei.ee/et/politseis-registreeritud-oeoepaeeva-suendmused` | **OPEN, human daily summaries, no key.** `HTTP 200`, 54 512 bytes. "Lühikokkuvõtted politseis möödunud ööpäeva jooksul registreeritud tõsisematest sündmustest" with dated sub-pages (10./09./08. september 2026). No machine feed — cited, not ingested. |
| 3 | `https://www.politsei.ee/et/statistika` | **OPEN hub, human HTML.** `HTTP 200`, 54 875 bytes, title "Statistika - Politsei- ja Piirivalveamet". Its own text redirects the official legs: crime stats to Justiitsministeerium (`kriminaalpoliitika.ee`), accident stats to Transpordiamet (Maanteeamet). Zero dataset-file hrefs (only `/et/manifest.json`, the PWA manifest). Links on to the open-data guide and `siseturvalisuse-votmenaeitajad`. |
| 4 | `https://www.politsei.ee/et/juhend/politseitoeoega-seotud-avaandmed` | **OPEN guide, human HTML.** `HTTP 200`, 55 506 bytes. "Siin lehel jagame politseitööga seotud masinloetavas formaadis avaandmeid", CC BY-SA 3.0, "uuendatakse kord nädalas - neljapäeval". Names per-dataset sub-pages incl. `liiklusjarelevalve-kaigus-avastatud-suuteod` and `varavastased-suuteod`. |
| 5 | `.../avaandmed/liiklusjarelevalve-kaigus-avastatud-suuteod` | **OPEN dataset page.** `HTTP 200`, 57 982 bytes. Links `liiklusjarelevalve_{1,2,3}.csv` + `.zip` on `opendata.smit.ee/ppa/`; "_1 = this + last year, _2 = last five years, _3 = previous five years". |
| 6 | `.../avaandmed/varavastased-suuteod` | **OPEN dataset page.** `HTTP 200`, 57 581 bytes. Links `vara_{1,2,3}.csv` + `.zip`, same windowing. |
| 7 | `HEAD opendata.smit.ee/ppa/csv/vara_1.csv` | **OPEN machine feed.** `HTTP 200`, `application/octet-stream`, 10 519 355 B, `Last-Modified: Thu, 10 Sep 2026` (matches the Thursday-refresh claim), `Accept-Ranges: bytes`. |
| 8 | `HEAD opendata.smit.ee/ppa/csv/liiklusjarelevalve_1.csv` | **OPEN machine feed.** `HTTP 200`, 56 012 549 B, `Last-Modified: Thu, 10 Sep 2026`. |
| 9 | `Range 0-4000 of both CSVs` | **Schema verified on live bytes** (`HTTP 206`, 4 KB each): TAB-separated quoted rows; theft header `JuhtumId ToimKpv ... SyndmusLiik ... MaakondNimetus ValdLinnNimetus KohtNimetus Lest_X Lest_Y ... SyyteoLiik`; traffic header adds `MntVoiTanav MntTanavNimetus KM ... RikkujaSugu RikkujaVanus`. Live rows show `KohtNimetus` = "Põhja-Tallinna linnaosa" / "Kesklinna linnaosa" / "Lasnamäe linnaosa", L-EST 500 m bins (`6589500-6589999`/`539500-539999`), fresh `ToimKpv` 2026-09-09. |
| 10 | JSON API / precinct polygons | **NOT located (dated negative, kept).** No extra hunting per polite-automation rules. Consequence: the linnaosa join runs on file _1 (current window), never on a live query. |

Commands run (evidence):

```bash
mkdir -p /tmp/hf-ppa-cache && cd /tmp/hf-ppa-cache
UA="home-finder-p4-ppa-probe/1.0 (Estonia open-data openness check, single polite pull)"
curl -sS -A "$UA" --max-time 20 -o home.html "https://www.politsei.ee/"
# HTTP:200 SIZE:64793 TYPE:text/html
curl -sS -A "$UA" --max-time 20 -o events.html \
  "https://www.politsei.ee/et/politseis-registreeritud-oeoepaeeva-suendmused"
# HTTP:200 SIZE:54512 TYPE:text/html
curl -sS -A "$UA" --max-time 20 -o statistika.html \
  "https://www.politsei.ee/et/statistika"
# HTTP:200 SIZE:54875 TYPE:text/html ("Ametlikku kuritegevuse statistikat
# avaldab Justiitsministeerium. Ametlikku liiklusõnnetuste statistikat
# väljastab Maanteeamet.")
curl -sS -A "$UA" --max-time 20 -o avaandmed.html \
  "https://www.politsei.ee/et/juhend/politseitoeoega-seotud-avaandmed"
# HTTP:200 SIZE:55506 TYPE:text/html (CC BY-SA 3.0, weekly Thursday refresh)
sleep 2; curl -sS -A "$UA" --max-time 20 -o traffic.html ".../liiklusjarelevalve-kaigus-avastatud-suuteod"
# HTTP:200 SIZE:57982 (links liiklusjarelevalve_{1,2,3}.csv + .zip)
sleep 2; curl -sS -A "$UA" --max-time 20 -o theft.html ".../varavastased-suuteod"
# HTTP:200 SIZE:57581 (links vara_{1,2,3}.csv + .zip)
curl -sS -A "$UA" --max-time 20 -I "https://opendata.smit.ee/ppa/csv/vara_1.csv"
# HTTP/1.1 200, 10519355 bytes, Last-Modified: Thu, 10 Sep 2026
curl -sS -A "$UA" --max-time 20 -I "https://opendata.smit.ee/ppa/csv/liiklusjarelevalve_1.csv"
# HTTP/1.1 200, 56012549 bytes, Last-Modified: Thu, 10 Sep 2026
curl -sS -A "$UA" --max-time 20 -H "Range: bytes=0-4000" <each csv>  # HTTP 206, TSV schema peek
```

## 2. Ingestion contract (what the demo implements end-to-end)

`services/scoring/dims_p4_ppa.py`: `fetch_ppa_snapshot(kind)`
(polite, cache-first, `PPA_CACHE_TTL_S = 7 d` — source refreshes
Thursdays, so at most one live pull/week; 30 s timeout, single attempt,
429 stops the run, bodies without the `KohtNimetus` header token are
refused and never cached) → `parse_ppa_snapshot()` (pure: TAB-separated
despite `.csv`, UTF-8, header-pinned `ValdLinnNimetus`/`KohtNimetus`,
Tallinn filter, `normalize_linnaosa()` genitive fixes, per-linnaosa
counts; empty payload reads empty, missing geo columns raise visibly)
→ the weekly archiver accumulates snapshots → `coverage` dict
(`linnaosa` + `ppa_traffic_counts` / `ppa_theft_counts` + window label)
→ the two dims. Transport errors raise and never touch the cache.
Cache files: `<cache-dir>/ppa-liiklusjarelevalve_1.csv`,
`<cache-dir>/ppa-vara_1.csv` (default dir `/tmp/hf-ppa-cache`).

## 3. Per-param honest shapes (choropleth tertile proxy, never a gradient)

| Param | Shape | No-input / missing-input behaviour |
|-------|-------|------------------------------------|
| P4-012 supervision (demo, PPA leg) | Linnaosa count tertile over the _1 window (madal→60, keskmine→50, kõrge→40 — compressed ±10, direction-ambiguous by design) | NULL naming the missing count table + Tark Tee check; Transpordiamet points and drive-time legs NOT joined; unknown linnaosa → NULL |
| P4-015 theft (coverage, PPA leg) | Linnaosa count tertile (madal→70, keskmine→50, kõrge→25, same scale as the paaste fire slice) + illiquidity flag on kõrge | NULL naming the missing table + insurer check; flood/tariff legs NOT joined; unknown class → NULL |

All reasons say `hinnang` and print count + rank + base size
(e.g. "100 avastatud rikkumist failiaknas (ülemine kolmandik,
7. koht 8 linnaosast …)"). All NULL reasons say `hinnang` + `EI OLE`
and name the buyer-side check. No Overpass fragment / tag mapping:
PPA data is not OSM data, and stuffing linnaosa tables into POIs would
abuse the POI channel. No WEIGHTS / livability / layers / docs changes
(joint rebalancing stays a joint change).

## 4. Judgment calls for the reviewer

1. Demo+coverage in ONE PR (AGENTS.md §3 says one issue per PR): the
   coverage issue body explicitly states it extends the demo ingestion,
   so splitting would review the same ingestion twice (trans #408 and
   paaste #406 precedent). Both issues close here.
2. Scorers take `(origin, pois, coverage=None)` — the optional third
   argument is the coverage-anticipated new plumbing: linnaosa count
   tables have no honest snapshot channel. `pois` is accepted for
   central-hook shape compatibility and ignored (stated in the module).
3. Relative tertiles, never absolute bands: only a 4 KB schema peek was
   pulled (never a full-file calibration — polite automation), so
   absolute thresholds would be fake precision. One-linnaosa tables
   score neutral keskmine with a "võrdlusbaas üks linnaosa" note.
4. P4-012 traffic bands are compressed (60/50/40) because the direction
   is ambiguous (busier roads vs stricter enforcement); P4-015 theft
   bands (70/50/25) mirror the paaste fire slice — same param scale.
5. Per-source slices with distinct keys (`traffic_supervision`,
   `theft_tariff`; `ppa_`-prefixed coverage keys): P4-012 keeps the
   trans casualty-buffer and paaste komando slices; P4-015 keeps the
   paaste fire slice. The central hook can weight slices independently.
6. Only the two observed genitives are mapped; other `KohtNimetus`
   stems pass through and MUST be revisited on the first full pull.
   The 56 MB traffic file is pulled whole by the weekly cron;
   streaming-parse is a noted first-pull optimisation.
7. Test place names, counts, and ranks are synthetic fixtures (clearly
   labelled) — real observed values appear only in §1 above, never as
   ingested data.

## 5. DoD evidence (observed 2026-09-13, worktree `278-p4-ppa`)

```text
$ python3 -m pytest services/scoring/tests/test_dims_p4_ppa.py -q
.......................s                                               [100%]
23 passed, 1 skipped in 0.14s

$ python3 -m pytest services/scoring/tests -q
........................................................................ [ 89%]
........s............................................................... [ 94%]
........................................................................ [ 99%]
...                                                                      [100%]
1439 passed, 4 skipped in 10.58s
```

- Hermetic: default suite makes zero network calls; fetch is proven
  via `file://` URLs (live/cache/garbage/stale) and the single real
  pull runs only with `HF_LIVE_PPA=1` (env-gated, skipped otherwise —
  the 1 skip above).
- New files only: `services/scoring/dims_p4_ppa.py`,
  `services/scoring/tests/test_dims_p4_ppa.py`, `docs/p4_ppa.md`.
  No edits to shared files (`livability.py`, WEIGHTS, layers,
  `docs/layers.md`, `docs/nomap.md`, `parameters4.md` — untouched).
