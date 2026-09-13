# P4 Kohanimeregister verdict note — taxi/guest name test (P4-049 slice)

> Dated-negative verdict for issue #313 (demo, single-param).
> Checked 2026-09-13. The one param is a documented register-only NULL
> dim (OTA PR #131 precedent); the scorer lives in
> `services/scoring/dims_p4_kohanimi.py`, pinned by
> `services/scoring/tests/test_dims_p4_kohanimi.py`.

## Verdict

**Searchable but not joinable — the single dim stays NULL with an
Estonian reason.** The Maa- ja Ruumiamet AKS-Kohanimeregister (KNR)
is openly searchable by hand, but its only machine path is
authenticated X-Road, and — decisively — its records ARE names
(official + unofficial + former), while P4-049 asks whether a guest
can SAY and FIND the name (Õismäe vs Kadriorg guest test). Grading
"Õismäe = hard" off the register would be a linguistic worth
judgement on a neighbourhood name, not a per-listing usability
measurement. There is no ingestion to cache, no TTL to state beyond
this one-off check, and no honest guest-test band to paint.

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

5 single GETs total (labelled one-off user-agent `home-finder
kohanimi openness-check #313 (one-off, single GETs, no retry;
contact via GitHub home-finder)`, paced ≥ 4 s, `--max-time 25`,
headers + visible-text scope read only, no form submissions, no XHR
probing). Raw bodies: `/tmp/hf-kohanimi-probe/` (one-off PR record,
not committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://geoportaal.maaamet.ee/` → 200, 27567 B, "Avaleht \| Geoportaal \| Maa- ja Ruumiamet" | Advertises "Kohanimeregistri teenus (AKS) / Kohanimede otsing ning kuvamine kaardil" | Portal reachable; the register is framed as search + display on map, not a feed |
| `https://andmed.eesti.ee/dataset?q=kohanimi` → 200 JS "Teabevärav" shell | 12 visible chars, zero kohanimi hits | No trivially pollable national-portal dataset |
| `.../est/teenused/kohanimeregistri-teenus-aks-p133.html` ("Kohanimeregistri teenus (AKS)") → 200, 33093 B | Since 23.04.2025 the new AKS system is live; KNR aggregates official + unofficial + former names for everyone; public search "võimaldab otsida … huvipakkuvaid kohanimesid"; URL access needs a known KNR object ID (e.g. `.../aks/name/detail/NO003313428`); only machine path named is "KNR X-tee teenused"; zero masinloetav / avaandmed / csv / rest / json mentions | Human-searchable by design; machine access is authenticated X-Road, not open polling |
| `https://aks.geoportaal.ee/aks/search/placename` ("Kohanimede otsing (AKS)") → 200, 1571 B | JS app shell titled "AKS" (5 visible chars, 0 forms, 0 export / csv / api / download hits) | Interactive search only; driving app internals would be scraping (refused, X-GIS precedent #266) |
| `.../est/teenused/wms-wfs-wcs-teenused-p65.html` → 200, 55694 B | Zero kohanimi mentions; the single KNR hit is the nav link to "KNR X-tee teenused" | No open KNR WFS layer advertised |

Judgment call: the check stopped at storefront/app-shell level on
purpose — no AKS search-form submission, no XHR probing, no
record harvesting. A per-listing name harvest would be scraping,
and even harvested names would not answer the guest question.

## Sibling slices (owned elsewhere, untouched)

- **P4-049 Ads/DSM findability-probe slice** (Takso/Bolt search
  hit-rate): its own demo, not this source.
- **P4-049 Tallinna guest-parking-rules slice** (Sat 19:00 guest
  parking): its own demo, not this source.
- **P4-049 TLT/Peatus.ee guest-arrival slice:** its own demo, not
  this source.
- **P4-049 listing-photo entrance-tidiness slice** (P4-022/P4-029
  join): its own demo, not this source.
- **P4-049 OSM entrance/wheelchair-tags slice:** its own demo, not
  this source.

This source feeds only P4-049 (`grep -i 'kohanimi\|kohanimeregister\|knr'
parameters4.md` hits source (2) alone), so there is no follow-up
coverage issue (single-param, like #295).

## What stays open (overturn path, not wired here)

Maa- ja Ruumiamet publishes a pollable open KNR bulk feed (WFS /
REST / CSV download) AND the project agrees a name-derived
usability signal is honest (e.g. official-vs-unofficial name
conflict at the listing's address, not pronounceability grading) →
re-open #313, build the polite cached ingestion (quarterly TTL per
parameters4.md P4-049), and graduate `guest_name_test` to a
per-listing join. Until then the buyer-side check is: say the
address aloud to a guest / send it to a taxi driver, check Sat
19:00 guest parking, look at the entrance on site.
