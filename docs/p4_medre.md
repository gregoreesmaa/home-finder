# P4 primary-care verdict note — measured register layers (P4-011 GP half)

> LIVE verdict for issue #532 (checked 2026-09-16). Direct overturn path
> for the GP half of `kindergarten_queue_gp` (`docs/p4_haridus.md` guessed
> a directory path and 404'd — this bulk was never probed). Scorers live
> in `services/scoring/dims_p4_medre.py`, pinned by
> `services/scoring/tests/test_dims_p4_medre.py`.

## Verdict

**Two live DAILY bulks — two proximity dims ship, status leg stays NULL.**
`medre.tehik.ee/open-data` is a React SPA shell (AGENTS.md §7.7: opened,
not filed — static bundle read named the keyless open-data endpoints, no
login/session flow touched). Both bulks carry same-day `hetk` timestamps.

## Openness evidence (one polite round, 2026-09-16)

Custom UA `home-finder-research/0.1`, single GETs, 429 = stop. Raw bodies
parsed in memory, aggregates only — never committed (AGENTS.md §5).

| Check | Observed | Meaning |
|---|---|---|
| `/open-data` page (HTTP 200, 1422 B) | React shell, `/assets/index-CEBE_YUb.js` (~4.8 MB) | No server data; bundle statically lists `/api-common/public/*/open-data` paths |
| `.../general-practitioner-lists/open-data` (HTTP 200, 3 591 143 B, hetk today) | 782 `<nimistu>`; 371 Harju / 289 Tallinn `<koht>` with `<adr_id>` + `<adr_tekst>`; tag set has NO avatud/suletud/capacity/patient column (full-file grep) | Proximity leg joinable via ADS id; **status leg closes as documented NULL** |
| `.../companies/open-data` (HTTP 200, 14 536 762 B, hetk today) | 1572 asutus (832 Harju); loaliik Eriarstiabi 1292 / Õendusabi 739 / Üldarstiabi 500 / Füsioteraapia 194 / Ämmaemandus 162; tegevuskohad plain-text `<aadress>` + `<teenused>` | Üldarstiabi sites = clinic leg; other kinds counted, never scored |
| `.../open-data/{companies,data,lists}/description` (HTTP 200, PDFs) | Data dictionaries served live | Licence per national catalogue below; rendered licence line needs JS (boundary) |

## Geocoding path (stated, counted)

Neither bulk ships coordinates: 0/371 Harju GP addresses, 0/832 Harju
provider addresses. GP rows carry ADS `<adr_id>`/`<adr_kood>` → adr→AKS
join (EHR #136 family); company rows are plain text → AKS text join.
`parse_*` readers extract join refs with `with_coords: 0` pinned by tests;
unjoined rows stay out. Proximity POIs are caller-supplied post-join
points until an adapter owns the join (monthly harvest at most, TTL 30 d).

## Slices (pinned by tests)

gp = nimistu vastuvõtukohad; gp_clinic = Üldarstiabi tegevuskohad;
gp_open_status = documented NULL (no bulk column; per-GP UI driving would
be directory scraping — explicitly out, Tervisekassa lookup named).
Bands ≤500 m → 80, ≤1 km → 65, ≤2 km → 50, beyond → NULL
(`linnulennult` hinnang label; proximity ≠ quality in every reason).

## Licence + privacy

CC BY-NC-SA 3.0 on both datasets (national catalogue; live description
PDFs served from the same host): attribute + share-alike + non-commercial
note on derived-data docs. Register metadata only — fixtures use
synthetic names; reasons never name a doctor.

## What stays open (not wired here)

- AKS join adapter (monthly) — proximity legs score caller POIs meanwhile.
- Eriarstiabi/specialist proximity — future source issue, not scored here.
- Terviseamet water/bathing verdicts (`p4_tervise.md`) — untouched.
- OSM health amenities (group 11) stay the fallback cousins.
