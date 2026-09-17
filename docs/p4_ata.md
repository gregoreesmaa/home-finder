# P4 Ametlikud Teadaanded (new uses) verdict note (issues #254 demo + #335 coverage)

Date: 2026-09-13. Scope: P4-020 (demo) plus the 2 coverage params in
#335 (P4-004 restriction slice, P4-021 developer-notice slice), all
consuming one AT URI-scheme ingestion
(`services/scoring/dims_p4_ata.py`). Overturn #233 (parameters3 p362
probate, `dims_group04*.py`) is a separate pipeline — untouched.

## Openness verdict: OPEN (anonymous pulls verified)

Polite probes, one GET each, `home-finder verification` User-Agent,
cached to /tmp/hf-ata, 2026-09-13 ~13:28 UTC:

| Probe | Result |
|---|---|
| `curl https://www.ametlikudteadaanded.ee/` | HTTP 200, 92326 bytes — public homepage, no auth |
| `curl https://www.ametlikudteadaanded.ee/avalik/uriotsing` | HTTP 200, 152108 bytes — documents the URI reuse scheme `/ee/{andmeandja}/{pealiik}/{alaliik}/{aasta}/{kuu}/{paev}/{teate_number}/{xml,rdf}` with publisher/type/date filters |
| `curl .../ee/eesti-advokatuur/.../2019/06/13/1483034/xml` (the page's own documented example) | HTTP 200, text/xml, 4171 bytes — real teadaanne schema: `teate_number`, `liik/kood+nimi`, `mall`, `andmeandja`, `puudutatud_isik`, `avaldamise/arhiveerimise_kpv`, `kinnitatud_sisu`, `sisendid` |

Consequence, kept honestly in code:

- `fetch_notice_xml` targets that URI layout with
  `ATA_TTL_DAYS = 1` (daily: enforcement notices are time-sensitive
  and the 1000-result cap forces date-windowed re-pulls), single
  polite GET, file cache; transport/HTTP errors RAISE and are never
  cached as data; HTTP 429 propagates (stop signal).
- Every dim scores ONLY joined records; with no AT record all 3
  return NULL with an Estonian reason. No join = NULLs until a pull
  is joined. That is the honest shape, not a gap to paper over.
- NEVER commit real pulls: `puudutatud_isik` carries personal data
  (names, codes). Tests use synthetic fixtures only.

## Honest-shape table (per-entity join, weak-good cap 75)

| Param | AT slice consumed | Shape when joined | When missing |
|---|---|---|---|
| P4-020 enforcement | pankrot/täitemenetlus/arest + auction | 15 active / 45 auction / 55 archived-only / 75 clean | NULL → RIK/notar |
| P4-004 kinnistus | keelumärge/arest (+auction echo) | 20 active + notar / 50 auction + notar / 60 archived + notar / 75 clean + notar | NULL → notar.ee |
| P4-021 developer | developer pankrot/täit/arrest-auction | 20 active / 45 asset notice / 60 archived / 75 clean | NULL → TTJA/EHR |

Clean is capped at 75 everywhere (never 100): a clean AT window is
not proof of clear title / a trusted seller — each clean reason
says so and names the unjoined check (RIK/notar, notar.ee, TTJA+EHR).
Unknown notice types and unknown currency (archive date missing)
stay NULL with the type named.

## Pairing rationale (why one PR, why these bands)

- One PR closes #254+#335 because #335 states it "extends the
  demoed ingestion" — splitting would ship an ingestion with one
  consumer, then re-touch every dim signature (EHR #249+#333
  precedent).
- P4-021 has two disjoint source slices by design: `dims_p4_ehr`
  scores EHR builder completion (cap 80); this module scores AT
  developer notices (cap 75, weaker evidence). Neither claims the
  full param; TTJA complaints stay unjoined in both.
- P4-020 (15) vs P4-004 (20) on the same active notice: different
  buyer questions ("frozen deal?" vs "can this close + notary
  checkpoint?"), so the checkpoint param carries the notar.ee
  pointer and a softer band.
- Active never scores 0: a notice can be stale, mis-joined, or
  superseded — strong-bad, never "worthless".
- The `tallinn: False` → NULL gate keeps the Tallinn demo scope
  explicit; a missing flag defaults to relevant (absence ≠ evidence).

## #628 land linkage (linkage before flags)

AT records carry no coordinates, so flags need a proven parcel join:
`scripts/build/batch_at_notices.py` pulls type-sliced URI lists
(`/ee/-/{pealiik}`, one polite GET per slice, TTL cache, 429 stops),
mines free text for kataster tunnus signatures
(`\d{2,5}:\d{1,4}:\d{1,4}`), and measures `linkage_rate`
(linked notices / parsed). List rows carry title + Avaldamise
algus/lõpp + body + provider inline — no per-notice fetch needed.
Bodies may name persons (incl. isikukood): records keep tunnus
signatures ONLY, never notice text or person fields.

| slice | pealiik slug | dim band |
|---|---|---|
| quarry | `kaevandamisluba` (UNVERIFIED) | 35 |
| zoning | `planeering` (UNVERIFIED) | 55 |
| cadastre | `kinnistus` (UNVERIFIED) | 60 |
| felling | `metsateatis` (UNVERIFIED) | NULL (Metsaregister) |

Slug verdicts 2026-09-17 (polite probes, TTL cache):
- `/ee/-/advokatuur` (docs example) serves 1001 rows — the ONLY
  verified list enumeration. End-to-end proof: 1001 listed, 50 in
  2022-04, linkage_rate 0.000 (advokatuur carries no parcels, as
  expected), sidecar `at/at-notices.json` written, no person text
  persisted (leak-checked).
- Date segments (`/ee/-/{pealiik}/-/{y}/{m}`) serve empty shells
  anonymously even for the verified slug — the month window runs
  client-side on Avaldamise algus. The wide-open month list
  (`/ee/-/-/-/{y}/{m}`) times out server-side and is never requested.
- Family slugs above are provisional (lowercased display stems);
  each serves the empty shell today. `--pealiik` overrides any slice
  for proof runs; a zero-row pull on an unverified slug warns loud.
  Quarry subtypes show retired 2019 markers in the type table
  ("Avaldamine lõpetatud 30.10.2019") — the quarry slice may be
  historically thin; the miner reports honestly either way.

Dims (`P4_ATA_LINK_DIMS`, separate registry — the demo registry is
untouched): quarry 35 / zoning 55 / cadastre 60 on an ACTIVE family
notice whose mined tunnus matches the listing parcel; clean caps at
70 (never 100); missing listing tunnus → NULL (linkage unproven);
felling always NULL. Fixture-measured linkage_rate 0.5 (synthetic
2-row window); live land rate pending verified family slugs.
