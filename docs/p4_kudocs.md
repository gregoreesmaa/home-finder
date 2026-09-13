# P4 kudocs verdict note (issues #258 demo + #339 coverage)

Date: 2026-09-13. Scope: P4-007 (demo) plus the 1 coverage param in
#339 (P4-047 KÜ-kaebuste-logid slice), both consuming one per-KÜ
document-bundle ingestion (`services/scoring/dims_p4_kudocs.py`).
Sibling slices are owned elsewhere and untouched: OSM
leisure=noise (`dims_p4_osm.dim_horrors`, tag does not exist),
listing-text NLP (`dims_p4_own_store.dim_ku_loan`, mention noted
never scored), Äriregister XBRL bulk (source (1), separate pipeline).

## Openness verdict: PRIVATE-per-association (dated negative, no bulk)

Polite probes, one GET each, `home-finder verification` User-Agent,
cached to /tmp/hf-kudocs, 2026-09-13 ~13:37 UTC:

| Probe | Result |
|---|---|
| `curl https://ariregister.rik.ee/` | HTTP 200 → `/est`, 80541 bytes, title "Juriidilise isiku otsing \| e-Äriregister" — company search reachable, but KÜ üldkoosoleku protokollid/otsused are NOT filed with the register (only annual reports are) |
| `curl "https://andmed.eesti.ee/api/3/action/package_search?q=korteriyhistu"` | HTTP 404 "Cannot GET" — national portal has no CKAN API (same finding as EHR #249 probe); no KÜ-docs dataset |
| `curl https://avaandmed.rik.ee/` | HTTP 200 with Content-Length: 0 — empty shell, no usable bulk listing |

No anonymous public KÜ-document bulk exists: each KÜ keeps its own
gated management portal, and probing any single KÜ's portal without
a mandate would target a private association — politeness stops at
the public endpoints above. Dated negative keeps this verdict.
Consequence, kept honestly in code:

- `fetch_kudocs_csv` takes a caller-supplied URL (the KÜ's published
  bundle link, or a seller/buyer handoff file staged at a URL) with
  `KUDOCS_TTL_DAYS = 90` (quarterly re-check per parameters4.md
  P4-007 "annual + quarterly refresh"; decisions change at general
  meetings). Single polite GET, file cache; transport/HTTP errors
  RAISE and are never cached as data; HTTP 429 propagates.
- Every dim scores ONLY joined records; with no `ku_code` match both
  return NULL with an Estonian reason. No public bulk = no backfill
  = NULLs until a per-KÜ handoff is joined. That is the honest
  shape, not a gap to paper over.

## Honest-shape table (per-ku_code join / per-listing dims)

| Param | KÜ slice consumed | Shape when joined | When missing |
|---|---|---|---|
| P4-007 loan/fund/heat | has_loan + balances/fund/heat + decisions_open | 70 (no loan + fund) / 60 (thin file or loan unknown) / 35 (active loan); heating + open decisions echoed | NULL → müüja/KÜ protokoll |
| P4-047 horrors | complaints_12m (counts only) | 75 (0) / 60 (1–3) / 40 (4+); no dates → calendar capped | NULL → KÜ logi |

Pairing rationale (one PR for #258 + #339): #339 states it "extends
the demoed ingestion" with "no new plumbing expected" — both params
read disjoint slices of the SAME bundle, so splitting would ship a
one-consumer ingestion then re-touch every signature.
