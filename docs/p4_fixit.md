# P4 fix-it channels — Tallinna abiliin/e-teenused + Mupo/KÜ (P4-026 + P4-062)

> Graduated ingestion + joins for issues #301 (demo) and #370 (coverage).
> First verdict dated-negative 2026-09-13; §7.7 dig + graduation 2026-09-16.
> Scorers live in `services/scoring/dims_p4_fixit.py`, pinned by
> `services/scoring/tests/test_dims_p4_fixit.py`.

## Verdict

**Keyless pins API found and joined — both dims score off joined
records, thin windows stay NULL with Estonian reasons.** The
annateada.ee report map is backed by a keyless read endpoint
(`POST /cgi-bin/ask`, documented in the page's own `notify.js`
bundle): one daily bbox POST returns every public report pin of the
rolling ~19-day window with position, server category, timestamp,
municipality region, and a documented handled/unhandled state. The
P4-026 leg scores the handled/total window rate (n≥5); the P4-062
leg flags Heakord-category waste-discipline counts (n≥5, never
addresses). The captcha-gated write path is never touched; the Mupo
phone/e-post intake and the Tark Tee DATEX key gate stay as-is (see
boundaries below).

## Openness evidence

First round (2026-09-13, dated negative): 7 single GETs —
tallinn.ee storefront (301→200), `/et/abiliin` (404, no machine
page), annateada.ee (human report map), Mupo page (helpline 14410 /
661 9860 + e-post intake, no stats table), Tark Tee (JS shell),
Teabevärav `abiliin` (JS shell). Raw bodies: `/tmp/hf-fixit-probe/`
(one-off PR record, not committed).

Second round — §7.7 dig (2026-09-16, 3 requests total: page GET +
bundle GET + one Tallinn-bbox ask POST, paced, labelled one-off
user-agent `home-finder-openness-check`, 25 s timeout, no retries,
no 429). Raw bodies: `/tmp/hf-dig/annateada/` (one-off PR record,
not committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://annateada.ee/` → HTTP 200 (~24 KB, Apache, ~4.1k visible chars) | Server-rendered intake page; scripts under `/notify/js/` | Not a shell — bundle readable |
| `/notify/js/notify.js` (28 KB, static read) | `ask_url="/cgi-bin/ask"` read path (bbox POST, static client constants) + `send_url="/cgi-bin/send"` write path (reCAPTCHA-gated, contact data required) | Keyless read API exists; write path refused (form driving behind captcha) |
| ONE `POST /cgi-bin/ask` (Tallinn bbox 59.30–59.55 / 24.45–25.15) → HTTP 200 (~130 KB JSON) | `{"messages": 294 pins, "instid", "adminabi", "heatava", "abi", ...}`; Tallinn slice 170 pins; stat 107×`1` / 187×`0` bbox-wide; dtime 2026-08-27…2026-09-15 | Live feed verified; rolling ~19-day window; municipality-grain region |

Pin schema (per `messages[]` entry): `id` (server int), `lat`/`lng`
(WGS84 strings), `msg` (free text — DROPPED at parse), `dtime`
(ISO), `ts` (epoch), `stat` (`'1'` green / `'0'` red), `region`
(municipality: Tallinn/Saue vald/Viimsi vald/…), `category`
(server taxonomy), `comm` (handler note — DROPPED), `photo`
(report-photo URL — DROPPED). Server taxonomy observed: Teed ja
tänavad, Heakord, Ohtlik objekt, Haljastus, Valesti parkimine,
Muu, Valgustus, Surnud loom/lind.

stat semantics are documented, not guessed: the ask-returned `abi`
help text states green = authority acknowledged / handling /
resolved, red = currently unhandled (`käsitlemata`), with an
automatic authority re-notice after a red week. So `stat=='1'` =
handled and handled/total is the P4-026 responsiveness rate.

## Honest shapes per param

| Param | Dim key | Honest shape | Buyer-side check meanwhile |
|---|---|---|---|
| P4-026 fix-it responsiveness (demo) | `fixit_channel_responsiveness` | 500 m window handled/total rate over the rolling window, n≥5, bands (0.5→40, 0.8→60, else 80, trans precedent) | thin windows: 14410 / 661 9860 helpline; ask the linnaosa for removal lag; KÜ stairwell accounts; dims_p4_komun heakorra leg + dims_p4_osm fixme cross-check + dims_p4_arireg cost echo |
| P4-062 rat/ice hex (coverage) | `rat_icefall_channel_flags` | Heakord-count operational flag per 500 m window, n≥5 (5–9→55, 10+→35, first calibration), never addresses | thin windows: on-site waste-house check; KÜ waste costs; ice leg has no taxonomy entry — dims_p4_paaste ice warnings + dims_p4_komun rotikaebused leg + dims_p4_osm waste cross-check + dims_p4_arireg waste echo |

Ingestion: `fetch_annateada_snapshot` (one bbox POST/day max,
24 h TTL, cache-hit = no request, transport errors never cached),
`parse_annateada_snapshot` (human content dropped at parse),
`build_annateada_pins` (Tallinn-filtered `annateada_pin_p4` POIs).
Never 0/100 by absence: thin windows stay NULL.

## Judgment calls (for the reviewer)

1. Demo + coverage in one PR: #370 defines coverage as extending the
   demoed ingestion — both slices read the same pins, so they land
   in the same module (Terviseamet #289+#362, TLT #277+#351,
   elektrilevi #264+#344, Elron #284+#358 precedent).
2. Window rate, not per-linnaosa stats: the `region` field carries
   municipality grain only (every Tallinn pin says
   region=Tallinn), so per-linnaosa aggregation is NOT honestly
   possible from this feed alone. The 500 m / n≥5 geometry mirrors
   the dims_p4_trans fixithex_p4 consumer so the rebalance can
   unify both legs. Named follow-up (not built here): keyless
   Linnaosad_asumid polygons inventoried in the #304 dig
   (`https://gis.tallinn.ee/arcgis/rest/services/Linnaosad_asumid/FeatureServer`,
   layers 0=Asumid, 1=Linnaosad) — one cached polygon pull plus a
   local point-in-polygon graduates this to per-linnaosa.
3. Pairing rationale: P4-026 source 1 is the abiliin/e-teenused
   reports leg (this join); P4-062 source 4 is the explicit P4-026
   join (this join's Heakord slice). Remaining P4-026/P4-062 legs
   stay scored where they live and are named, never re-scored
   (komun heakorra + rotikaebused legs, OSM fixme/waste
   cross-checks, Paasteamet ice warnings, Äriregister KÜ cost
   echos).
4. Complements, not duplicates: P4-026 (fix-it RATE) vs P4-062
   (waste COUNT flag) read the same pins differently — no
   double-scoring by construction (pinned by the aggregator test).
5. Stays refused: send/write path (captcha-gated form driving),
   Tark Tee DATEX key gate (registered key — separate decision),
   Mupo phone/e-post intake (human channel, never scraped),
   per-record photo/contact retention (dropped at parse).
6. No shared-file edits (livability.py, WEIGHTS, layers, layers.md,
   parameters4.md untouched): pair's own module + test + doc only.
   Central hook (snapshot→POI wiring + WEIGHTS rebalance) stays one
   joint change across all batches.

## Reopening checklist (what is still open)

1. Linnaosa-polygon join (Linnaosad_asumid URL above) for true
   per-linnaosa stats.
2. Winter re-probe: check whether the ask taxonomy gains an ice
   category (then graduate the P4-062 ice leg off joined records).
3. Re-run the ask probe if the bundle's client constants change
   (`instid`/`version`/`uuid`/`code` are bundle-pinned).
4. Add the explicitly-flagged live integration test (not a unit run).

## Layer verdict #623 (2026-09-17, polite, labelled UA)

Per maintainer decision the map shows the report PINS with
reporting-bias labeling — complaints measure reporting activity,
not place quality. Re-verified live: one JSON ask POST (Tallinn
bbox 59.30-59.55 / 24.45-25.15) → HTTP 200, 132 653 B, 300 pins,
2026-08-28 → 2026-09-17 = 19-day rolling window (173 Tallinn: 139
unhandled red-stat + 34 handled green-stat; neighbours Saue/Harku/
Viimsi/Rae/Saku vald). Same schema as the scorer probe (now with
`ts` epoch + `photo`; parser ignores extras). No licence/terms page
exists; the pins are public by publication.

Daily harvest (`scripts/build/batch_fixit.py`, 24 h TTL, 429 =
stop; parser + pin builder REUSED from dims_p4_fixit.py): 300 pins,
120 handled / 180 unhandled, 0 timeless dropped. Sidecar
`fixit/fixit-points.json` carries lat/lon/handled/ts ONLY —
category/msg/photo/region never leave the builder (report text can
identify people). #623 added the `ts` carry to the scorer's parse +
pin dicts (scorer never reads it; key-set tests updated).

Map: ONE `fixit` layer, new `pins` kernel (markers only — the field
stays unknown everywhere BY DECISION; ValueHeatMap clears it so no
red wash). Expiry enforced at serve time (ts within 19 days of
now): a stale sidecar degrades to honestly-empty (pinned: fresh
served, 25-day-old dropped, all-stale → []). Legend states the bias
caveat (density = reporting, empty map ≠ tidy street) + the rolling
window + the pull vintage. docs/layers.md row added.
