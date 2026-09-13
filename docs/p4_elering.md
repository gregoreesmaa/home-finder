# P4 Elering verdict note (issues #265 demo + #345 coverage)

Date: 2026-09-13. Scope: P4-009 (demo) plus the 2 coverage params in
#345 (P4-036, P4-046), each restricted to its Elering slice in
`services/scoring/dims_p4_elering.py`. Sibling slices are owned
elsewhere and untouched: Elektrilevi feeder SAIDI / liitumiskaart /
Elektrilevi backup-feed half (`dims_p4_elektrilevi`, all NULL),
EHR roof-type upside + heat/fireplace redundancy
(`dims_p4_ehr.dim_roof_income` SCORED floor 50 + P4-046 heat slice
SCORED), Tallinna Vesi well+city-water redundancy (`dims_p4_tvesi`
SCORED), TTJA/Ookla/OpenCellID broadband slices (their own demos).

## Openness verdict: MIXED (machine-open national series, no address layer)

Polite probes, one GET each, `home-finder` verification User-Agent,
cached to /tmp/hf-elering, 2026-09-13 ~16:48–16:52 UTC:

| Probe | Result |
|---|---|
| `curl https://elering.ee/` | HTTP 200, 253401 bytes, title "Avaleht \| Elering" — TSO portal reachable; connection terms on human pages (110/330 kV liitumine), no open-data/dev portal advertised |
| `curl https://dashboard.elering.ee/` | HTTP 200, 4486 bytes, "Elering Live" JS app shell — no key on the landing |
| `curl https://dashboard.elering.ee/api/system/with-plan` | HTTP 200, 34003 bytes, `{"success":true,"data":{"real":[64 pts],"plan":[68 pts]}}`, 15-min steps 2026-09-12T21:00Z→2026-09-13T12:45Z — MACHINE-OPEN, no key. Point fields: timestamp, production, consumption, losses (null), frequency, system_balance, ac_balance, production_renewable, solar_energy_production (null across the window) |
| `curl https://elering.ee/en/article/renewable-energy-subsidy-applications-become-significantly-easier` | HTTP 200, 135739 bytes human HTML (subsidy-via-data-hub explainer); only `application/json` on the page is the Drupal settings blob — NO machine feed-in-rules feed |

What this means per slice:

- P4-009 Elering slice (system open data): machine-open as a
  NATIONAL aggregate — the payload has no geographic key at all
  (no feeder, no address). A national surplus says nothing about
  whether your street goes dark (distribution-level outages), so
  the per-address dim stays NULL; the snapshot is echoed in the
  reason as traceable context, never a score.
- P4-036 Elering slice (feed-in rules + mikrotootja terms): rules
  are human-pages-only (no machine feed found in the dated probes);
  rooftop connection capacity is Elektrilevi's distribution map
  (sibling slice). No per-building export signal exists at Elering,
  so the upside dim stays empty (None = no evidenced upside, not a
  negative).
- P4-046 Elering slice (backup-feed "where published"): neither
  half publishes per-address backup-feed info (dated: this probe +
  elektrilevi #264 verdict), so the "where published" condition is
  unmet and the dim stays NULL.

Consequence, kept honestly in code:

- `fetch_elering_system` pulls the national series with
  `ELERING_TTL_DAYS = 30` (monthly re-pull per parameters4.md
  P4-009 "TTL: monthly"; ~12 GETs/year). Single polite GET, file
  cache; transport/HTTP errors RAISE and are never cached as data;
  HTTP 429 propagates.
- `parse_elering_system` / `summarize_elering_system` turn the
  envelope into canonical points + snapshot (nulls stay None, never
  0; timestamp-less rows skipped; success:false/non-JSON → []).
- Every dim takes `(origin, pois, elering=None)` and returns NULL
  for every input, with "hinnang" + "EI OLE" + "ära feigi" markers
  and the concrete buyer-side check.

## Honest-shape table (national snapshot in / per-listing NULLs out)

| Param | Elering slice consumed | Shape | When missing |
|---|---|---|---|
| P4-009 system adequacy | national production/balance series | NULL per-address; reason echoes N points + avg balance as system context | NULL → rikkekaart + TTJA netikaart |
| P4-036 feed-in rules | human-only rules + national solar context | NULL upside (empty, not negative) | NULL → EHR katus + Elektrilevi liitumiskaart |
| P4-046 grid backup | published-backup absence (both halves) | NULL redundancy | NULL → kamin/kaev/2. väljapääs + KÜ |

Pairing rationale (one PR for #265 + #345): #345 states it
"extends the demoed ingestion" with "no new plumbing expected" —
all three params read disjoint slices of the SAME national
snapshot, so splitting would ship a one-consumer ingestion then
re-touch every signature (same precedent as elektrilevi #264+#344
and creditinfo #259+#340).
