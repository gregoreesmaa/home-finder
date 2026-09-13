# P4 rentcompl: short-rental complaints verdict note (issue #294, single-param demo)

Demo (#294) implements the Tallinna short-rental complaints ingestion
+ P4-003 end-to-end in Tallinn (parameters4.md P4-003 source (5):
"Tallinna Linnavalitsus lühiajalise üüri kaebused (where published)").
Single-param: no follow-up coverage issue uses this source (per the
#294 body, remaining 0 params).

Scope guard: sibling P4-003 legs are scored where they live —
untouched (`dims_p4_own_store.py` (`rent_reality`, NULL),
`dims_p4_rel2021.py` (`rent_reality_rel`, rental-share/vacancy grid
leg), `dims_p4_stat.py` (`rent_reality_stat`, Stat rent-table leg),
the KV-medians adapter store, the Inside-Airbnb-style density check;
`livability.py`, WEIGHTS, shared/group files all unmodified; 3 new
files only). This module scores ONLY the complaints leg
(`nuisance_rentcompl_hex`).

## Openness verdict: dated negative (2026-09-13, keeps per #294)

Tallinna lühiajalise üüri kaebused are NOT published as an open
dataset. Polite evidence, ~12 tiny requests total (custom UA,
>= 3 s pacing between same-host hits, headers + search-page weight
only, no scrape):

```
web search (no target load)   -> no published complaints dataset; MKM
  "Lühiajalise üüri turg Eestis" uses Airbnb/VRBO listing open data +
  Inside-Airbnb-style aggregators (density, not city complaints); EU
  hits are regulation prose, not a Tallinn feed
GET avaandmed.eesti.ee/api/3/action/package_search (x3)
                              -> HTTP 301 (162 B nginx) to andmed.eesti.ee
GET andmed.eesti.ee/api/3/action/package_search (x3, followed)
                              -> HTTP 404 `Cannot GET /3/action/...`
GET andmed.eesti.ee/api/3/action/status_show
                              -> HTTP 404 (new "Teabevärav" portal: no CKAN API)
GET andmed.eesti.ee/          -> HTTP 200 Teabevärav SPA shell (transport note)
GET tallinn.ee/et/search?q=lühiajaline üür kaebused
                              -> HTTP 301 to /et/otsing
GET tallinn.ee/et/otsing (followed) -> HTTP 200 city search page;
  only generic hits (Botaanikaaia room hire, general "Kaebused,
  ettepanekud" contact page, kindergarten room hire) — no complaints
  table, no CSV/XLSX/andmestik feed
```

Raw headers/pages: `/tmp/hf-p4-rentcompl/` (one-off PR record, not
committed). Pull contract: max 1 download / 30 d per cache dir
(`RENTCOMPL_TTL_S = 2592000`, parameters4.md P4-003 TTL
monthly/quarterly — monthly, complaints accumulate), single GET, no
retries — HTTP 429/errors are a stop signal. `RENTCOMPL_BULK_URL`
stays `None` until the checklist below names a verified bulk URL;
until then the fetcher performs no requests and the scorer stays NULL
with an Estonian EI OLE reason. The scored shape is proven on
fixtures only (hermetic tests).

## Honest shape (checklist / bands, NULL stays NULL)

| Param | Dim key | Window | Scored shape | NULL when |
|---|---|---|---|---|
| P4-003 nuisance, complaints leg (demo) | `nuisance_rentcompl_hex` | listing's own hex_id, exact match | count band: 0→85, 1→65, 2–4→45, ≥5→25 | no snapshot / hex not covered / hex_id missing |

Covered hex with 0 Tallinn complaints scores 85 (measured calm,
capped — one signal, never 100); missing join stays NULL.
Neighbour-hex counts never leak in. The scored reason says `hinnang`
with components (hex id, count); every NULL reason says `EI OLE`
and names the missing input plus the buyer-side check (KÜ/maakler,
kohapealne vaatlus). Yield, Airbnb density, KV-medians and the
REL2021 rental-share legs are named EI OLE, never faked.

## Judgment calls (for the reviewer)

1. Single-param demo, no coverage pairing: unlike demo+coverage
   pairs, the #294 body states the remaining 0 params need no
   follow-up issue for this source — one snapshot (`hexes` roster +
   `complaints` rows), one dim.
2. Hex-exact join, no buffer: "hex nuisance hinnang" joins the
   listing's own opaque hex_id only (rel2021 no-gradient precedent);
   the module never geocodes an address into a hex (central hook's
   job) — hex-less listings stay NULL, pinned by test.
3. ALL complaint kinds count (müra/prügi/muu, kind missing still
   counts): nuisance is nuisance for the "nuisance?" Buy Q; kind is
   kept on the row for the future adapter, pinned by test.
4. Periods informational, never filtered: freshness is the TTL /
   re-pull problem, not a scorer filter (no live table, so no latest
   period to pin).
5. Tallinn filter: national rows join only on a recognised Tallinn
   `kov` (`tallinn` / `tallinna linn`, case-insensitive); kov-less
   rows are skipped (unknown municipality is never assumed local),
   pinned by test.
6. Bands (85/65/45/25) are a first-cut judgment with no live
   calibration; the 85 cap marks the leg partial by construction.
   MUST be recalibrated from a real snapshot on reopen.
7. No shared-file edits; central hook (snapshot feed + WEIGHTS
   rebalance) stays one joint change across all batches.

## Reopening checklist (when Tallinn publishes complaint bulk data)

1. Re-run the portal + tallinn.ee probes; paste fresh evidence.
2. Set `RENTCOMPL_BULK_URL` to the verified bulk URL; pull one snapshot.
3. Verify the hex-id scheme + `kov` spellings + `kind` codelist against
   the live feed; adjust roster/row handling.
4. Recalibrate `NUISANCE_BANDS` from real histograms; resolve the
   complaints↔Airbnb-density overlap rule with the central hook.
5. Add the explicitly-flagged live integration test (not a unit run).
