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

- Eriarstiabi/specialist proximity — future source issue, not scored here.
- Terviseamet water/bathing verdicts (`p4_tervise.md`) — untouched.
- OSM health amenities (group 11) stay the fallback cousins.

## Map graduation Step 1 (#609, 2026-09-16)

Two `/layers` overlays ship the P4-011 GP-half slices: `medre_gp`,
`medre_clinic` (`apps/web/lib/layers_p4_medre.ts`, paramIds [] +
paramLabel P4-011). Harvester `scripts/build/batch_medre.py` (monthly
TTL, polite, 429 = stop) pulls both DAILY bulks and builds the
snapshot sidecar `medre/medre-points.json`: 782 nimistu / 870 kohad
(378 Harju) + 1571 asutus (759 Harju) / 537 Üldarstiabi kohad tallied,
linkage_rate 0, points [] — no ADS join adapter is owned anywhere, so
the caller-joined set is EMPTY and the layers serve honestly-empty
(paaste precedent: EI OLE legend, "no data" render, zero markers —
never invented clinics). Kernels reuse the sport #607 dbands kind
(same band table as the scorer; DORMANT all-NaN until Step 2).
CC BY-NC-SA 3.0 scope (incl. non-commercial) rides the legends.
Step 2 (ADS adr_id→AKS join) fills joined points into the same
sidecar shape and bumps linkage_rate; the loader/kernel/route need no
changes. P4-011 is shared with the EHIS school slices (#608) by
scorer design — distinct slices, distinct dim keys, no double-score.

## Map graduation Step 2 (#660, 2026-09-19)

Adapter `scripts/build/batch_medre_ads.py` (stdlib only; network only
in the paced ADS fetch + `main`) joins both legs via the keyless
Maa-amet ADS gazetteer (single polite GETs, 1 s pace, 429 = abort
unwritten, 30 d TTL file cache): reception rows accept only the
exact-`adr_id` hit with `kaugus == 0`; clinic rows (plain-text
addresses, no id) accept only `kvaliteet == "tapne_taisaadress"` with
`kaugus == 0`. Hermetic fixture test
`scripts/build/test_batch_medre_ads.py` pins the 378/537 counts
(`python3 -m pytest scripts/build/test_batch_medre_ads.py -q` — the
`build/` dir is outside the default pytest recursion, explicit path).

Measured linkage on the 2026-09-16 bulks: **901/915 joined
(linkage_rate 0.9847)** — reception 378/378, clinic 523/537; the 14
unjoined clinic rows are counted in the sidecar note, never placed
(exact-text criterion refused, no fallback geocoding). Sidecar
`medre/medre-points.json` stays snapshot-only, never committed; the
wire still carries lat/lon/slice only (no GP names, no ADS codes).
Live proof: `medre_gp` serves 342 + `medre_clinic` 139 real points over
the Harjumaa window with provenance `snapshot`.

Share-alike scope (reviewable): the TEHIK register content stays
CC BY-NC-SA 3.0 — attribution + share-alike + non-commercial ride the
legends and this note, so any derived extract (including this
sidecar) inherits the NC-SA scope and is never commercialised;
coordinates are per-address ADS viitepunkt lookups (facts, no bulk
redistribution); fixtures use synthetic names; reasons never name a
doctor. The Step-2 harvester re-runs monthly at most (ADS TTL 30 d);
raw ADS bodies live in `/tmp` caches only.
