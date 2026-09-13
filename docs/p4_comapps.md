# P4 comapps verdict note — Commercial delivery/ride APIs (P4-027 + P4-049)

> Dated-negative verdict for issues #302 (demo) and #371 (coverage).
> Checked 2026-09-13. Both params are documented no-map NULL dims
> (OTA PR #131 precedent); scorers live in
> `services/scoring/dims_p4_comapps.py`, pinned by
> `services/scoring/tests/test_dims_p4_comapps.py`.

## Verdict

**No open feed — both dims stay NULL with Estonian reasons.** The three
commercial inputs behind P4-027 (Wolt/Bolt Food coverage polygons,
Barbora/Selver delivery windows, Bolt ride-price probes) and the
findability probes behind P4-049 (consumer-app search hit-rate) are
partner-gated, session-gated, or ToS-protected consumer flows. There
is no public API to poll politely, so there is no ingestion to cache,
no TTL to state, and no honest district band to paint.

## Openness evidence (one polite check, 2026-09-13, no scraping, no auth)

Single `curl` per host with a labelled one-off user-agent, response
headers only (plus one scope read of Wolt's public developer landing
page):

| Check | Observed | Meaning |
|---|---|---|
| `https://developer.wolt.com/` → 200 | Portal exists, serves a merchant-integration landing page (order/menu API for signed-up partners) | No public coverage-polygon or delivery-window feed; merchant API needs a partner contract + auth |
| `https://bolt.eu/en/developers/` → 404 | No public developer portal at Bolt | Ride-price probes would mean automating the consumer app — ToS territory, out of scope per AGENTS.md §7.4 |
| `https://foodora.com/developers/` → 403 (gated) | Developer page exists but is access-gated | Partner-gated docs, no open feed |
| `https://barbora.ee/` → 200 storefront | JS e-store, delivery slots behind address/session flow | No documented open API for delivery windows; slot-scraping would be session-scraping, not a polite pull |

Judgment call: the check stopped at landing-page level on purpose —
one request per host, no endpoint enumeration, no session creation.
Deeper probing (creating accounts, driving session flows) is exactly
the scraping this repo refuses (AGENTS.md §5).

## What stays open (overturn paths, not wired here)

- **P4-027 slivers:** Tallinna ööbussid (TLT/Peatus.ee GTFS), OSM
  `shop=*` + `opening_hours` (Selver/Maxima/Rimi/Konsum), and
  Omniva/SmartPOST/DPD parcel-point lists are open — but they answer
  night-bus lines / shop hours / locker distance, NOT evening food
  coverage or ride prices. Wiring a cousin as the commercial feed
  would mislead; a challenge must bring a genuinely open
  coverage/price feed.
- **P4-049 slivers:** OSM `entrance=*`/`wheelchair=*` tags mark mapped
  doorways, not taxi findability or Sat-19:00 guest parking. The
  honest signal is an on-site guest test (taxi order probe at your
  address, KÜ enquiry on guest parking, entrance photo check).
- **Full overturn:** a vendor publishes an open coverage/price API
  (or GTFS-grade feed) → re-open #302, build the polite cached
  ingestion, and graduate these dims to district bands.

## Why demo + coverage share one PR

The coverage body (#371) states it extends the demo ingestion (#302).
With the demo verdict dated-negative there is no ingestion to extend,
so P4-049 lands in the same verdict module instead of a second file
importing a pipeline that does not exist. One module, one test file,
one verdict note — no edits to shared files.
