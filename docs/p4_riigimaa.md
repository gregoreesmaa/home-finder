# P4 riigimaa note — state-land adjacency + auction early-warning (#544)

> Shipped layer for issue #544. Checked 2026-09-16. Scorers live in
> `services/scoring/dims_p4_riigimaa.py`, pinned by
> `services/scoring/tests/test_dims_p4_riigimaa.py`.

## Verdict

**OPEN (CC BY 4.0) — both dims score from joined polygons.** KATRI
state-parcel + auction geometries carry the attributes the join needs
(class, manager, deadline, status, URL), proven on live bytes + one live
sample row. Daily feed → harvest weekly at most; attribution Maa- ja
Ruumiamet CC BY 4.0.

## Openness evidence (one polite round, 2026-09-16, no scraping, no auth)

5 single GETs total, 2 s pacing, `--max-time 30`, labelled one-off
user-agent `home-finder openness-check (one-off, few pages max, no
scrape)`. Raw bodies: `/tmp/hf-probes/` (one-off PR record, not
committed).

| Check | Observed | Meaning |
|---|---|---|
| KATRI `katri/wfs?…GetCapabilities` → HTTP 200, 162 KB | 30 types incl. `state_property_ownership`, `state_property_unreformed`, `state_property_usage_rights`; CRS EPSG:3301/3857/4326 | State-parcel family enumerated |
| `…DescribeFeatureType` (both state types) → HTTP 200, 3.7 KB | `katastritunnus`, `vara_liik`, `riigivara_valitseja`, `volitatud_asutus`, `nimetus`, `pindala` | Join attributes proven at schema level; `vara_liik` VALUES unprobed (no KATRI rows pulled) → forest split is provisional substring match |
| Auction `maaoksjon/wfs?…GetCapabilities` → HTTP 200, 109 KB | Exactly one type: `maaoksjon:auction` | Single-type service |
| `…DescribeFeatureType=maaoksjon:auction` → HTTP 200, 2.1 KB | `id`, `obj_id`, `purpose`, `organizer`, `offer_deadline`, `starting_price`, `status`, `url`, `note` + polygon | Expiry (`offer_deadline`) + open-status (`status`) both present |
| `…GetFeature count=1` → HTTP 200, 901 B | id 3244621, Müük, Maa- ja Ruumiamet, `offer_deadline "17.09.2026 kell 10:00"`, status `Avaldatud`, `totalFeatures` 272 | Join proven on live bytes |
| Harjumaa bbox pull (count=300) → HTTP 200 | 15 features: 8 Rent + 7 Müük, ALL `Avaldatud`, deadlines 17.09–21.10.2026 | Live discrimination in the buyer area |

## Honest shapes (polygons only, never gradients)

| Leg | Dim key | Bands | Outside → |
|---|---|---|---|
| State adjacency | `state_land_adjacency` | forest (RMK/mets) → 70, other → 60, capped hinnang (ownership can change) | NULL (teadmata) |
| Auction warning | `auction_warning` | active (`Avaldatud` + deadline ≥ today) within 50 m → flat 40, dated, date+ID+URL in reason | NULL (teadmata) |

Adjacency rule (reviewer call, documented in code): containment OR
nearest vertex ≤ 50 m — shared-boundary-only would miss true neighbours
on digitisation slivers. Expired/unknown-expiry auctions never score.
No bidding advice, no valuation, no RMK logging-plan claims.

## Judgment calls (for the reviewer)

1. Assurance caps at 70: bordering state forest is evidence, not a
   guarantee — the auction leg prices the residual sale risk.
2. Rent auctions flag too (purpose named in the reason for buyer
   weighting).
3. Forest split is provisional (`mets`/RMK substring; exact `vara_liik`
   codelist unprobed) — labelled in code + reopen item 1.
4. No shared-file edits: 3 new files only. No map screenshot: thin
   overlay deferred (auction geometries mappable — reopen item 3).

## Reopening checklist

1. Pull KATRI rows; pin the exact `vara_liik` forest codelist (replace
   the substring heuristic).
2. Weekly harvest at most (daily feed); never present assurance as a
   guarantee (legend says so).
3. Optional thin auction-geometry overlay once the join runs on cached
   polygons; expired auctions drop out of the cache.
