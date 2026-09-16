# P4 ratings + price tiers — gated verdict + join-shape note (issue #556)

> Verdict date: 2026-09-16 (docs pages only — no scraping of any
> review/delivery surface; no live key in tests).
> Code: `services/scoring/dims_p4_ratings.py` (keyed harvester +
> 2 scorer legs); tests:
> `services/scoring/tests/test_dims_p4_ratings.py`
> (hermetic, fixture Nearby Search bodies, no network).

## Buyer question

Not just "is there food nearby" (owned: OSM amenity counts, #549
toitlustus) but "is it any good, and what does it cost".

## Probe (polite investigation only)

| Path | Result |
|---|---|
| Google Places API (New) usage-and-billing docs | **Key-gated, workable**: billing account required; FieldMask tier model — `rating` / `userRatingCount` / `priceLevel` are Atmosphere-tier data billed on top of the base Nearby Search / Text Search / Place Details SKU (Essentials/Pro/Enterprise tiers). Exact per-SKU dollars live on the pricing page and are NOT pinned here — re-check before keying |
| ToS cache/retention | **Limits apply** — re-pull, don't hoard. Harvester defaults to a 30 d TTL + monthly quota cap (`PLACES_MONTHLY_MAX_CALLS = 500`); the exact retention clause must be re-checked against the live Terms before the first keyed pull |
| Review platforms / delivery apps (scraping) | **Refused class** (AGENTS.md §5/§7) — never re-litigated, no stars scraped from any surface, ever |
| OSM `cuisine`/`shop`/price tags | Counts only, virtually no prices — stay proximity legs, never scored as quality |
| Minimum honest harvest that fits | One keyed Nearby Search per listing-area per month (DISTANCE rank, rating+price field mask), cache-first, quota-capped — covers Tallinn's café/restaurant stock on a small monthly budget; exact sizing re-checked against live SKU dollars at keying time |

## Join path (place ↔ huvipunkt/OSM linkage + mismatch handling)

`link_places_to_records`: a keyed place links to a register/OSM
record within **50 m** with normalised-name agreement (containment
either way). A place matching nothing, or two places claiming one
record, stays **unmatched** (ignored, never force-joined — a wrong
star is worse than none).

## Honest shapes (scorer dims only, never a raster)

| Leg | Dim key | Window | Scored shape | NULL when |
|---|---|---|---|---|
| Dining delight | `dining_delight` | rated places ≤ 500 m | rating ≥ 4.3 with `userRatingCount` ≥ 10 nearby → 70 (capped taste-match, no editorial ranking) | no keyed pull (buyer check, never a guess); nothing above floor (unrated ≠ bad) |
| Price character | `price_character` | tiered places ≤ 500 m | cheapest `priceLevel` nearby: 0→75, 1→65, 2→55, 3→40, 4→30 (cost character, never baskets) | no keyed pull; no tiered places |

Review-count floors are load-bearing (`RATING_MIN_N = 10`): a 5.0
with 3 reviews is ignored, never scored. No review text ingested
(scores/tiers only). Keys from env only
(`GOOGLE_PLACES_API_KEY`), never committed; transport/429 never
cached; 429 is a stop signal.

## Judgment calls (for the reviewer)

1. Gated-verdict close with a shippable harvester: the key model is
   the Mapillary/OpenCellID precedent, so `fetch_places` ships
   quota-capped behind it; production stays NULL until a key exists.
2. Unmatched/ambiguous links are silent NULLs on the unmatched side
   — surfaced here, not hidden.
3. No livability.WEIGHTS splice here (joint follow-up). 3 new files
   only, zero shared-file edits.
