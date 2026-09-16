# P4 paaste static-register verdict (issue #523)

Closes #523.

## 1. Verdict (2026-09-16): PARTIAL — structured addresses, zero geometries

Two polite single GETs (UA `home-finder-p4-paaste-probe/1.0`,
`--max-time 20`, no retries, 3 s pacing), cached to `/tmp/hf-523-probe`
(one-off PR record, not committed):

| # | URL | Result |
|---|-----|--------|
| 1 | `https://www.rescue.ee/et/kontaktid` | **OPEN, human HTML org tree, no key.** `HTTP/2 200`, `content-type: text/html`, 131 740 bytes (byte-identical size to the 2026-09-13 probe), `<title>Kontaktid - Päästeamet</title>`. Links per päästekeskus (`pohja/laane/louna/ida_paastekeskus`), zero coordinates/geojson. Nuxt app shell (`/_nuxt/static/…/payload.js`). |
| 2 | `https://www.rescue.ee/_nuxt/static/1/et/kontaktid/pohja_paastekeskus/payload.js` | **OPEN static structured payload, no key.** `HTTP/2 200`, `application/javascript`, 7 700 bytes. 125 string literals: unit names + paths (`Päästeamet/Põhja päästekeskus/Päästetöö büroo`, `Harjumaa päästepiirkond`), street addresses (`Erika tn 3`, `üldkontaktid: Erika tn 3, Tallinn`, linnaosa `Põhja-Tallinna linnaosa`, locality `Tallinn`). **`komando` × 0, `latitude/longitude/geojson/coordinates` × 0.** |

Consequence: there is a static official register of *units with street
addresses*, but no static register of *komandod with coordinates*.
Addresses are not points — hand-geocoding `Erika tn 3` into a komando
marker would invent a station. The layer therefore stays honest-empty,
and the improved empty message (shipped in
`services/scoring/dims_p4_paaste_register.py`) now names the dated
register tally, what is missing (komando coordinates) and why
(addresses are not points), plus the buyer-side check.

Commands run (evidence):

```bash
mkdir -p /tmp/hf-523-probe && cd /tmp/hf-523-probe
UA="home-finder-p4-paaste-probe/1.0 (Estonia open-data openness check, single polite pull)"
curl -sS -A "$UA" --max-time 20 -D kontakt.headers -o kontakt.html \
  "https://www.rescue.ee/et/kontaktid"
# HTTP/2 200, 131740 bytes, title "Kontaktid - Päästeamet"
sleep 3
curl -sS -A "$UA" --max-time 20 -D payload.headers -o payload.js \
  "https://www.rescue.ee/_nuxt/static/1/et/kontaktid/pohja_paastekeskus/payload.js"
# HTTP/2 200, 7700 bytes, application/javascript, komando x0, coord tokens x0
```

## 2. Ingestion contract

`fetch_register_snapshot()` (polite, cache-first,
`PAASTE_REGISTER_TTL_S = 30 d`, default dir `/tmp/hf-paaste-register`)
→ `parse_register_payload()` (pure: unit rows + street addresses +
geometry signal, fixture-tested) → `tallinn_extract()` (dated
snapshot `{fetched, units, n_units, n_addresses, has_geometry}`)
→ `dim_station_register()` (always NULL; the reason IS the improved
empty message). Transport errors raise and never touch the cache;
HTTP 429 stops the run.

## 3. Judgment calls for the reviewer

1. New files only (`dims_p4_paaste_register.py`,
   `tests/test_dims_p4_paaste_register.py`, `docs/p4_paaste_register.md`).
   `dims_p4_paaste.py` and `apps/web/lib/layers_paaste.ts` untouched —
   the improved message lives here until the joint WEIGHTS change.
2. The dim scores None even with a fresh snapshot by design: a row
   without coordinates cannot join the 500 m / 5 km legs.
3. The address pattern under-matches on purpose (fail-closed); a
   missed address keeps the row address-less, still NULL either way.
4. Test fixtures are fully synthetic — real observed values appear
   only in §1 above, never as ingested data.

## 4. DoD evidence

```text
$ python3 -m pytest services/scoring/tests/test_dims_p4_paaste_register.py -q
...........                                                        [100%]
11 passed in 0.06s
```

Hermetic: suite makes zero network calls (cache-hit fetch test only).
Full suite output pasted in the PR body.

## 5. Reopening checklist

* rescue.ee publishes komando coordinates (Teabevärav dataset with
  geometry, or coordinate tokens in the kontakt payloads) →
  `has_geometry` flips true, add a `derived-paaste.json` sidecar,
  recalibrate the provisional 60-band, joint WEIGHTS rebalancing.
* Real routed response times appear → NEW param work; never backfill
  drive time from straight-line distance.
