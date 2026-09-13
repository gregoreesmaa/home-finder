# P4 park: Tallinna parkimine verdict note (issues #279 + #353)

Demo (#279) implements the Tallinna parkimine source ingestion + P4-013
end-to-end; coverage (#353) wires P4-037 + P4-049 off the same
zone-facts snapshot. One PR closes both because the #353 body states it
extends the demoed ingestion with "no new plumbing expected".

## Openness verdict: mixed (2026-09-13, 8 polite requests, labelled UA)

Raw bodies: `/tmp/park-open/` (one-off PR record, not committed).

| URL | Result | Verdict |
|---|---|---|
| `https://www.tallinn.ee/et/liikuvus/parkimine` (hub, GET 200, ~101 KB) | 4-zone regime as readable text (fees, hours, passes) | OPEN (facts) |
| `https://www.riigiteataja.ee/akt/431122022063` (GET 200) | määrus text (T-numbered street lists) = legal basis | OPEN (basis) |
| `https://www.parkimine.ee/parkimisinfo/` (GET 200, ~133 KB; wp-json content EMPTY) | commercial lot directory (YT/F/P operator codes); 0x tasuline/elaniku/külalis/määrus | DATED NEGATIVE for the zone join |
| `https://parkimine.tallinn.ee/` (GET 200, ~165 KB) | JS login shell, 46 visible chars | DATED NEGATIVE for polling |
| gis.tallinn.ee veebikaart / Google My Map / kaardiotsing | interactive viewers only | DATED NEGATIVE for bulk polygons |

tallinn.ee HEAD probes 403 (Cloudflare) while the same URL GETs 200 —
HEAD status there proves nothing; the GET is the verdict.

Pull contract: one file per source under `hf-p4-park/`, re-pull only
after `TTL_PARK_DAYS = 365` (zones/fees change by regulation:
parameters4.md "on regulation change + annual"). Single GET, labelled
UA, 25 s timeout, no retries — 429/errors yield None and are never
cached as data.

## Live regime (hub page, 2026-09-13 — the snapshot's reviewed facts)

| Tsoon | Tasu | Aeg | Perioodipilet | Laupäev 19:00 |
|---|---|---|---|---|
| kesklinn | 0,025 €/min | E–R 7–19, L 8–15, P tasuta | 150 € | tasuta (paid only till 15:00) |
| südalinn | 0,08 €/min | 24/7 | 250 € | tasuline |
| vanalinn | 0,10 €/min | 24/7, eraldi määrus | 300 € | tasuline |
| pirita | 0,01 €/min | 15.05–15.09, 10–22 | — | hooajaline |
| tasuta ala | 0 | piiranguta | — | tasuta |

Also verified on the hub: first 15 min free with clock, PARGI.EE /
SMS-1902 / meter payment, 24h info 600 3055. Resident/guest permit
detail is NOT on the hub (portal/login-gated) — the NULL reasons point
at the iseteenindusportaal instead of faking it.

## Honest shapes per param (per-parcel join, NULL stays NULL)

| Param | Dim key | Scored shape | NULL when |
|---|---|---|---|
| P4-013 regime (fee/hours leg) | `parking_regime` | burden band on the verified fee ladder: vanalinn 35, südalinn 45, kesklinn 60, pirita 75, tasuta 80 | no katastritunnus, no/missing/unknown `tsoon` |
| P4-037 exposure (zone-cost slice) | `zone_cost` | 30/40/55/70/80; automaks bands + transit offset named missing | same join rule |
| P4-049 guest (Sat-19:00 slice) | `guest_parking` | 35/45/65/75/80; Pirita states the season caveat | same join rule |

Verified-free (tsoon None) scores — a real no-burden signal; missing
join stays NULL. Every scored reason says `hinnang` with components;
every NULL reason says `EI OLE` with the concrete check (Maainfo,
kaardiotsing, iseteenindus).

## Judgment calls (for the reviewer)

1. Demo + coverage in one PR: #353 defines coverage as extending the
   demo ingestion — all three dims ride the same snapshot.
2. Parcel-keyed shape (not the brief's group20a `(origin, pois)`
   pattern): a distance gradient from a zone centroid would be fake
   precision; parameters4.md + the kataster P4-013 precedent say
   per-parcel join.
3. Slice boundary: OSM owns mapped-bay/entrance proxies, kataster owns
   the A/B/C × courtyard join, peatus/TLT/trans own transit/arrival/
   restriction slices — this module owns ONLY the live-regime legs
   (fee/hours, zone-cost, Sat-evening guest cost), under distinct dim
   keys (`parking_regime`, `zone_cost`, `guest_parking`) so the central
   hook can weight slices independently (trans #408 precedent).
4. Zone naming follows the LIVE hub (kesklinn/südalinn/vanalinn/
   pirita), not kataster's A/B/C nor RT's T-numbering — both older
   schemes disagree with the live source. Flagged, not fixed (new
   files only): follow-up must reconcile `dim_parkimine_hoov`'s A/B/C
   input domain with the live 4-zone regime.
5. Bands are first-cut burden judgments on verified fees/hours;
   re-anchor centrally if tariffs move. No shared-file edits
   (WEIGHTS/Overpass rebalance stays one joint change).

## Refresh checklist (tariff/zone change)

1. Re-run `fetch_park` for the hub + RT act (one polite GET each);
   paste fresh evidence in the refresh PR.
2. Human-review the new zone facts; update `ZONE_FACTS` + bands here
   and in `dims_p4_park.py` (same PR, never scraped).
3. If polygons ever open: add a point-in-polygon join follow-up (the
   explicit-`tsoon` contract stays as fallback).
