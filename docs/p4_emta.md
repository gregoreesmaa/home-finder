# P4 EMTA (new uses) verdict note (issues #256 demo + #337 coverage)

Date: 2026-09-13. Scope: P4-019 (demo) plus the 2 coverage params in
#337 (P4-004 debt slice, P4-037 policy-exposure slice), all
consuming one EMTA ingestion
(`services/scoring/dims_p4_emta.py`). Overturn #242 (parameters3
G16 tax tables, `dims_group16*.py`) is a separate pipeline —
untouched.

## Openness verdict: MIXED / constrained-open (no bulk feed observed)

Polite probes, one GET each, `home-finder verification` User-Agent,
cached to /tmp/hf-emta, 2026-09-13 ~13:37–13:38 UTC:

| Probe | Result |
|---|---|
| `curl https://www.emta.ee/` | HTTP 200, 203803 bytes — public homepage, no auth |
| `curl .../eraklient/maksud-ja-tasumine/muud-maksud/maamaks` | HTTP 200, 267763 bytes — public land-tax guide: 2026 statutory bands (elamumaa 0,1–1%, maatulundusmaa 0,1–0,5%, muu 0,1–2%), KOV-set rates, koduomaniku soodustus (maamaksuseadus §11), yearly per-KOV rate PDFs referenced |
| `curl https://avalik.emta.ee/mootorsoidukimaks` | HTTP 200, 2155 bytes, JS SPA shell ("Laeme rakendust… JavaScript required") — public calculator app, anonymous GET fine, but content needs JS rendering: no server-side scrape |
| `curl .../registrid-paringud/avalikud-paringud` | HTTP 200, 164870 bytes — documents Võlapäring: public per-entity query by registrikood/isikukood; shows only sissenõutavaid tähtpäevaks tasumata nõudeid; does NOT show estimated interest or debts under 100 euros |
| `curl .../et/maksuvõlg` and `.../et/mootorsoidukimaks` (guessed) | HTTP 404 — documented negative guesses, not real paths |

Consequence, kept honestly in code:

- `fetch_emta_page` pulls info pages with
  `EMTA_TTL_DAYS = 30` (monthly: KOV tables refresh yearly, but
  page links/bands drift and debt guidance is per-deal), single
  polite GET, file cache; transport/HTTP errors RAISE and are never
  cached as data; HTTP 429 propagates (stop signal).
- `parse_maamaks_page` extracts only the page-level facts actually
  observed (statutory bands, KOV-table years, the 100-euro
  visibility floor); a reworded page yields Nones and the dims
  stay NULL — fail-closed, never guessed.
- Every dim scores ONLY joined rows; with no EMTA row all 3
  return NULL with an Estonian reason. The per-KOV rate-PDF bulk
  join is explicit future work — no join = NULLs until it lands.
  That is the honest shape, not a gap to paper over.
- NEVER commit real pulls: võlapäring answers carry personal data
  (registry codes, debt flags). Tests use synthetic fixtures only.

## Honest-shape table (joined rows only; caps named per dim)

| Param | EMTA slice consumed | Shape when joined | When missing |
|---|---|---|---|
| P4-019 fiscal health | maamaks rate level + trend (annual KOV row) | 70 stable low / 55 stable high / 45 rising | NULL → KOV määra-tabel / eelarve |
| P4-004 kinnistus | maksuvõlg per entity (võlapäring + notar.ee) | 20 active debt + notar / 75 clean + notar | NULL → võlapäring / notar.ee |
| P4-037 policy exposure | joined CO2 label + commute dependence | 70 car-free / 60 madal / 45 keskmine / 30 kõrge | NULL → avalik.emta.ee calculator |

Clean/good is capped everywhere (70/75/70, never 100): a stable
maamaks rate is not proof of fiscal health (võlakoormus unjoined),
a clean võlapäring hides sub-100-euro debts by documented rule,
and car-freedom does not pre-empt ummikumaks/autovaba-ala
decisions. Unknown trends, unknown debt currency, and unknown
CO2 labels stay NULL with the missing slice named.

## Pairing rationale (why one PR, why these bands)

- One PR closes #256+#337 because #337 states it "extends the
  demoed ingestion" — splitting would ship an ingestion with one
  consumer, then re-touch every dim signature (ATA #254+#335
  precedent).
- P4-019 caps at 70 (stricter than ATA's 75): the EMTA slice is
  rate + trend only, while võlakoormus/investments — the param's
  core per parameters4.md — need eelarve/Rahandusministeerium/
  Statamet rows this module never joins (#242 owns the G16 side).
- P4-004 reuses ATA's 20/75 bands on purpose: same param, EMTA
  slice instead of AT slice. The clean reason carries the
  100-euro caveat the võlapäring page itself documents — a buyer
  reading only the score cannot mistake it for clear title.
- P4-037 takes `co2_band` as a JOINED label from the buyer's own
  calculator run instead of computing it: the calculator is a JS
  app with no scraped API (probed 2026-09-13), so hard-coding CO2
  cutoffs from memory would be fake precision. Never scores 0 —
  a band is an estimate, not a verdict.
- The `tallinn: False` → NULL gate keeps the Tallinn demo scope
  explicit; a missing flag defaults to relevant (absence ≠ evidence).
