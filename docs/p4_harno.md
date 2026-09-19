# School quality: Harno exam results per school (issue #687)

> Code: `scripts/build/batch_harno.py`; tests:
> `services/scoring/tests/test_batch_harno.py` (hermetic).
> Scorer: `services/scoring/dims_harno.py` + `tests/test_dims_harno.py`
> (static-pending NULL, OTA PR #131 precedent).
> Overlay: `apps/web/lib/layers_p4_harno.ts` + `.test.ts`
> (honest-empty qbands, tervise #494 precedent).

## Buyer question

"Kas lähedal on hea kool?" — per-school quality from
riigieksamite averages for the family segment. (Distance is
already scored; this layer adds QUALITY.)

## §6 Source verdict (STEP ZERO — static-pending, 2026-09-19)

**NO bulk machine-readable per-school exam export exists — the
annual table arrives as an operator-verified snapshot, never
scraped, never polled.** Polite one-off round, UA
`home-finder-research/0.1`, `--max-time` 25, paced, raw in
`/tmp/hf_harno_*` (one-off PR record, never committed).

| Check | Observed | Meaning |
|---|---|---|
| `GET haridussilm.ee/ee` → 301 → `haridussilm.ee/ee` → 200, 41 186 B | JS SPA shell; zero CSV/XLS/API/download surface in the markup | Visual portal, no bulk export |
| `GET haridussilm.ee/main-*.js` → 200, 541 369 B | `/v1/comparison-view/` serves strategic-plan docs; data layer is PowerBI (`powerbi-report-fetch`) | Internal API serves plans + BI embeds, not per-school scores |
| `GET haridussilm.ee/tulemuslikkus/oppeasutuste-tulemusnaitajad/skeem` → 200, same 41 kB shell | SPA route, data loads at runtime from BI | No stable per-school JSON |
| EIS exam records | Behind school accounts | Not anonymously pollable — no account minting (AGENTS.md §5) |
| Yearly media koolide-edetabel graphics | Tables as news graphics, not stable URLs | Not a refreshable source — hand transcription would be unverifiable |

Judgment call: probing stopped at the BI wall on purpose — no
PowerBI reverse-engineering, no runtime-API spelunking beyond the
bundle read (AGENTS.md §7.4).

## Snapshot shape (vintage + per-school linkage)

Annual drop (operator-verified, EHIS ids as join keys):

```json
{"vintage": "2025", "source": "…",
 "schools": [{"ehis_id": "…", "name": "…",
   "lat": 59.43, "lon": 24.74,
   "avg_estonian": 82.5, "avg_math": 78.0, "avg_foreign": 88.0,
   "n_graduates": 60}]}
```

Linkage rules (pinned by `batch_harno.py` + test):
- `ehis_id` (EHIS registry) is the join key — names alone never join;
- coordinates verified at snapshot time against the held OSM
  extract (amenity=school name match checked against the EHIS
  street address — never hand-geocoded, paaste #493 rule);
- thin cohorts (`n_graduates` < 10) never plot;
- quality band = mean of the three subject means → 80/70/60/45/30
  (cap 80 — an exam mean is never a whole school; parity between
  `batch_harno.py quality_band` and `layers_p4_harno.ts
  HARNO_BANDS` is a drift bug if broken).

`batch_harno.py --build --cache-dir DIR --snapshot file.json`
validates then prints `{"total", "vintage"}`; without `--snapshot`
it honestly refuses (exit 2).

## Pole wiring (intentionally ABSENT)

Static annual refresh per the issue (no pole polling by default):
no `bin/run-harno.sh`, no cron, no `pole/api.py` entry. When the
first verified snapshot lands, it ships as a vintage-stamped
derived table per the linkage rules above (never raw dumps, never
personal data) — re-open #687 to graduate the dims + layer.

## Buyer-side check (until the first snapshot)

Vaata kooli näitajaid Haridussilma kooli-lehelt ja käi kool
kohapeal läbi.
