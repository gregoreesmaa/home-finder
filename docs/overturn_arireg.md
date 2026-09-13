# Overturn log — G4 p361/p369 per-listing entity dims from free e-Äriregister bulk (issue #232)

> Group 4 params p361 (trust/LLC transferability) and p369 (co-op
> board approval), parameters3.md §5.4. Hunted + ingested
> 2026-09-13. **Verdict: PARTIAL overturn** — p361 flips to
> scored-or-None from the free bulk downloads (84.3% of entities
> score, 15.7% stay NULL); p369 stays NULL with a KÜ-identity
> echo (approval rule lives in the paid articles text). The
> test-pinned dims live in
> `services/scoring/dims_overturn_arireg.py`, pinned by
> `services/scoring/tests/test_dims_overturn_arireg.py`.
> Re-check the discovery surfaces no later than **2027-03-13**.

## Verdict

**Free bulk exists outside the contract API — p361 scores, p369
echoes.** The XML query API (`avaandmete API`) is contract-gated
(sibling #257 verdict, untouched), but the open-data **download
environment** at `avaandmed.ariregister.rik.ee` publishes 12
static datasets (licence-terms acceptance, no RIK contract),
most refreshed daily, carrying public rows only for statuses
registrisse kantud / likvideerimisel / pankrotis. Two of them
answer p361's party-shape question for real:

| File (HEAD-verified 2026-09-13, refreshed same day) | Rows / objects | Fields consumed |
|---|---|---|
| `ettevotja_rekvisiidid__lihtandmed.csv.zip` (18 511 171 B) | 377 730 entities | `ariregistri_kood`, `nimi`, `ettevotja_oiguslik_vorm` (+ subtype), `ettevotja_staatus` (R 368 331 / L 8 725 / N 673), first-entry date, normalised address + EHAK |
| `ettevotja_rekvisiidid__osanikud.json.zip` (33 854 442 B, 763 MB uncompressed) | 377 730 company objects | per-company `osanikud[]` (`isiku_tyyp` F/J, `isiku_roll` OSAN/O, `osaluse_omandiliik` L/Y/K/KY + `..._tekstina`, `osaluse_protsent`), `osapandid_tingimuslikud_voorandamised[]` presence |

Shareholder-count census (today's dump): 0: 84 910 / 1: 237 527
/ 2: 41 264 / 3: 8 521 / 4+: ~5k. Ownership: L=Ainuomand
382 270 / Y=Ühisomand 7 894 / K=Kaasomand 36 / KY=Kaasomandiosa
ühisomandis 2. Non-empty pledge/conditional arrays: 124
companies. Roles `O` (23 075) carry the same "Osanik" label as
`OSAN` and count as party rows (said in code).

End-to-end run of the shipped parsers + dims over the real
`/tmp` pulls (never committed): join coverage 1.000, p361
**318 538 scored (84.3%)** — 75: 212 946 / 65: 33 198 /
70: 42 858 (FIE) / 55–60: ~13k / 45: 1 767 / pledge-cap 40:
1 465 / L→20: 8 725 / N→10: 673 — and **59 192 NULL (15.7%)**,
dominated by KÜ (25 600, →p369), MTÜ 22 569, UÜ 3 494,
AS 1 919, TÜ 1 040, KOV bodies, SA, branches, plus 4 OÜ with
zero shareholder rows (register lag — absence is unknown).
p369: 377 730 NULL by design (identity echo only).

## Openness evidence (one polite round, 2026-09-13, no scraping)

12 requests total (labelled one-off UA
`home-finder-232-hunt/1.0`, paced ≥ 4 s, headers + visible-text
scope on HTML, two intended-use static-file GETs). Raw bodies:
`/tmp/arireg-bulk/` (one-off PR record, not committed).

```
ariregister.rik.ee/                  -> 303 -> /est, 200 (80 919 B)
  per-company search UI, no bulk link on front page
rik.ee/.../ariregistri-paringud      -> 200 (38 121 B)
  "laadides alla avaandmeid" + "Kõigi teiste juriidiliste isikute
   andmetega on võimalik tasuta tutvuda ... ilma sisse
   logimiseta või RIKiga lepingu sõlmimiseta"; links to the
   download env + API intro
avaandmed.ariregister.rik.ee/        -> 200 (19 554 B)
  "Avaleht | e-äriregistri avaandmed": nav lists
  Avaandmete allalaadimine / API / Üksikpäring; query catalogue
  incl. Usaldushalduste päring, Tegelike kasusaajate päring
andmed.eesti.ee/dataset?q=ariregister -> 200, JS-only Teabevärav
  shell (12 visible chars) - no pollable national-portal path
.../et/avaandmete-allalaadimine      -> 200 (46 927 B)
  THE PAGE: 12 datasets, "enamikke neist uuendatakse kord
  päevas", "Avaandmete allalaadimise eelduseks on nõustumine
  litsentsitingimustega", statuses R/L/N only, per-dataset field
  lists + direct /sites/default/files/avaandmed/*.zip links;
  "Alates 10. juuli 2026 ei avaldata avaandmetena enam tegelike
   kasusaajate andmeid"; "Alates 1.nov 2024 ei sisalda
   avaandmete failid ... isikukoodide infot"
.../ettevotja-rekvisiitide-faili-teenus -> 200 (contract SOAP API
  doc, username+password - NOT used; the static files above are)
HEAD x4 (no bodies): lihtandmed-csv 18 511 171 B, osanikud-json
  33 785 442 B, üldandmed-json 229 727 986 B (body NOT pulled -
  too big, p369 needs only its prose schema), kommertspandid-json
  951 642 B (exists, NOT consumed - see boundary below); all
  Last-Modified Sun 13 Sep 2026 (daily rhythm live)
GET x2 (single, intended-use): both zips above, byte counts
  match HEAD exactly; parsed + scored end-to-end (tallies above)
```

Pull contract: max 1 download / 7 d per file per cache dir
(`ARIREG_TTL_S = 604800`), single GET per stale file, no
retries — HTTP 429/errors are a stop signal. The 230 MB
üldandmed body stays un-pulled until a consumer needs it.

## Near-miss proxies considered and refused

- **Beneficial-owner shape as a scored input**: removed from
  open data 10.07.2026 (Rahandusministeerium notice) — scoring
  "no BO rows = clean" would read a redaction as purity.
  Unpublished-BO is a stated cap reason on every p361 score.
- **Trust administration (usaldushaldus) from bulk**: no
  download file exists, only the contract-API query — the facet
  stays NULL instead of being faked from the `Usaldusühing`
  legal form (a partnership form, not a trust).
- **Kommertspandid as a p361 input** (free 0.95 MB file,
  HEAD-verified): pledges answer encumbrance (p144/p248
  territory + KKIS), not party shape — deferred, named here.
- **AS scored from bulk**: the shareholder book lives at the
  securities centre, not in any download — NULL with the CSD
  pointer, never a legal-form guess.
- **p369 scored from KÜ existence/status**: "a KÜ exists" does
  not answer "does its articles require consent" — NULL-echo
  (P4-010 precedent), consent question to the board in writing.
- **Address→KÜ auto-join** (lihtandmed carries normalised
  addresses): a second join with its own false-match risk —
  recheck hook below, not half-built here.
- **Area raster for either param**: entity facts are not place
  fields — per-listing dims only, never a map (OTA PR #131).

## What stays open (overturn path, not wired here)

1. Ingest `kaardile-kantud-isikud` (free file) → partnerships
   (TÜ/UÜ, ~4.5k entities) flip from NULL to scored; reason
   already names the file.
2. Address→KÜ join (lihtandmed address+EHAK) → p369 echo
   resolves the building's KÜ without a seller-supplied code.
3. Listing schema carries the seller registry code → dims plug
   into livability scoring; WEIGHTS rebalance stays one joint
   change across all batches (existing tests pin `set(WEIGHTS)`
   exactly).
4. Recalibrate `SH_BANDS`/haircuts/caps from a joined listing
   sample (current bands are first-cut off the national
   census, median case 75 by construction).
5. Re-check by **2027-03-13**: BO redaction lifted? trust
   download file appears? KÜ articles text freed? — any yes
   re-opens the NULL facets.

Shared/group files (`dims_group04.py`, `livability.py`,
WEIGHTS, `docs/nomap.md`) are deliberately untouched here —
the final docs-index PR updates nomap.md G4 rows. Paid
extracts (kinnistusraamat, articles texts, CSD book, BO data)
stay NULL permanently.
