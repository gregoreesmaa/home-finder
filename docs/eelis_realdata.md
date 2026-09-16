# EELIS real-data verdict (issue #517)

Buyer report: all three EELIS layers (raiealad, niiduelupaigad,
kaitsealad) read empty. The builder snapshot
`/tmp/hf-488-snap/eelis/eelis-areas.json` holds exactly 3 zones,
ALL explicitly fictitious (`Pirita joeoru maastikukaitseala
(fiktiivne)`, `Fixture niit (fiktiivne)`, `Fixture raie
(fiktiivne)` — re-read 2026-09-16). Nothing is installed in the
default snapshot, so users see honest-empty.

## Verdict: REAL HARVEST, not honest-empty

Re-verdict 2026-09-16 (7 tiny WFS metadata/hits requests, labelled
one-off UA, paced ≥ 5 s, ≤ ~1 kB bodies, no scrape, no bulk pull;
HTTP 429 never seen):

| Check | Observed | Meaning |
|---|---|---|
| `GetFeature resultType=hits`, Tallinn BBOX (lat 59.35–59.65, lon 24.55–24.95) × 3 layers | HTTP 200 on `kr_kaitseala`, `niidud`, `kaadamisalad` | liveness re-confirmed today |
| Per-layer Tallinn counts | 33 / 44 / 1 (verified 2026-09-13, `dims_p4_eelis.PULL_PLAN`, same BBOX) | real polygons exist behind the WFS |
| Builder snapshot | 3/3 zones `(fiktiivne)` | fiction, never installed |

The empty map is a **missing harvest, not a missing source**: the
real path (`fetch_eelis_snapshot` → `batch_eelis_poly.py` →
`eelis-areas.json` sidecar) is open. No layer is converted to
honest-empty; the flood table stays out (owned by #487).

## What ships (3 new files, no shared edits)

* `services/scoring/dims_eelis_realdata.py` — install-time guard
  (`scrub_fictitious` / `installable_sidecar`: ANY fictitious zone
  refuses the whole candidate; empty stays honest-empty; only a
  non-empty fiction-free list is installable) + dated coverage
  record (`coverage_note`, `verdict_summary`). No network in the
  module — the pull stays in `dims_p4_eelis`.
* `services/scoring/tests/test_dims_eelis_realdata.py` — 14
  hermetic tests (fiction gate incl. an unenumerated mixed-case
  variant, scrub parity, install refusals/acceptance, dated copy).
* This note.

## Judgment calls (for the reviewer)

1. The fiction guard fails closed on markers (`fiktiivne`,
   `fixture`, `demo`, `näidis`, …) matched case-insensitively over
   all name fields; non-dict rows fail closed too. Real register
   names never carry these markers — documented in the module.
2. Counts rest on the 2026-09-13 verified pull plan (same BBOX);
   today re-confirmed liveness only, to keep the probe to 7 tiny
   metadata requests. A full re-pull is the harvester's job, not
   this verdict's.

## Reopening checklist

1. Run one real harvest (`fetch_eelis_snapshot` + sidecar build);
   confirm Tallinn counts per layer.
2. Gate the install with `installable_sidecar`; paste the refusal
   log (must show 0 dropped on a real pull).
3. Recalibrate `dims_p4_eelis` bands from the real pull if counts
   drifted. Re-check no later than **2027-03-16**.
