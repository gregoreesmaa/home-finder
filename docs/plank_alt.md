# PLANK/TPR alternative-source verdict (issue #519)

Buyer report: designated-use polygons show nothing; the route
header documents a dated NULL (PLANK WFS gone, TPR has no bulk).
Honest but useless.

## Verdict: NULL FORMALLY ACCEPTED + improved empty UX (branch 2)

Alternative-source probe 2026-09-16 (2 tiny metadata requests,
labelled one-off UA `home-finder-519-plank-alt/1.0`, short
timeouts, no scrape, no bulk pull, no form submissions; HTTP 429
never seen):

| Check | Observed | Meaning |
|---|---|---|
| `GET geoportaal.maaamet.ee/.../Avalik-WMS-teenus-p65.html` | names `aks.geoportaal.ee/aks-ogc` as the current public WMS | probe target resolved from the supplier's own docs |
| `GET aks.geoportaal.ee/aks-ogc?service=wms&1.3.0&GetCapabilities` | HTTP 200, 151 251 B; `<Name>` families `ads_*` / `knr_*` / `poi_*` only | ZERO planning layers — no planeering/detailpl/kehtiv/Katerina/TPR/sihtotstarbe name in the whole document |

The Maa-amet public WMS is a **dated negative** as a
designated-use source (addresses + cadastre + POIs, never
decrees). With the standing sibling verdicts (PLANK WFS 301 →
E-ehitus SPA, no GetCapabilities; TPR SPA shell, no bulk link —
2026-09-13), no open per-parcel designated-use bulk exists today.
No invented polygons under any circumstance — there is no polygon
builder in this change at all.

## What ships (3 new files, no shared edits)

* `services/scoring/dims_plank_alt.py` — verdict record:
  `empty_ux_copy` (Estonian title/body/source explaining what is
  missing and why + `polygons: ""` pinned empty);
  `probe_aks_capabilities` / `has_planning_layer` (one-query 2027
  re-check; errors → None, never cached).
* `services/scoring/tests/test_dims_plank_alt.py` — 11 hermetic
  tests (stubbed probe incl. error paths; marker scan incl.
  unenumerated variants; copy pins PLANK+TPR+AKS+EI OLE+date).
* This note.

Wiring the copy into the planktpr overlay stays an explicit
follow-up (shared-file edit, out of scope here).

## Judgment calls (for the reviewer)

1. `plank`/`tpr` are deliberately short markers (fail toward the
   NULL: only a marker hit flips the verdict; unknown input is
   False). A future real planning layer named without any of the
   seven markers would need a marker update — flagged here, not
   hidden.
2. The E-ehitus SPA bundle (§7.7) and the Katerina/municipal
   mirror URLs were NOT probed (login-gated platform / no local
   mirror copy to resolve URLs from) — recorded as the next step,
   not claimed.

## Reopening checklist

1. Reverse-engineer the planeeringud.ee SPA bundle (§7.7);
   resolve the Katerina WMS / municipal kehtivad-planeeringud URLs.
2. Re-run `probe_aks_capabilities`; on a marker hit, verify the
   layer serves per-parcel designated-use polygons (not a WMS
   picture) before any harvest.
3. Wire `empty_ux_copy` into the planktpr overlay. Re-check no
   later than **2027-03-16**.
