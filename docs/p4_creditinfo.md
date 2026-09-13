# P4 creditinfo verdict note — Creditinfo/Krediidiinfo (P4-007 + P4-020 slice)

> Dated-negative verdict for issues #259 (demo) and #340 (coverage).
> Checked 2026-09-13. Both params are documented no-map NULL dims
> (OTA PR #131 precedent); scorers live in
> `services/scoring/dims_p4_creditinfo.py`, pinned by
> `services/scoring/tests/test_dims_p4_creditinfo.py`.

## Verdict

**No open feed — both dims stay NULL with Estonian reasons.** The two
Creditinfo inputs (P4-007 source 3: KÜ maksehäired cross-check;
P4-020 source 4: Tallinn developer scores) are account-gated
("Minu Creditinfo" self-service) and contract-gated B2B products
(sales department, lender KYC/debt-management solutions). There is
no public API to poll politely, so there is no ingestion to cache,
no TTL to state, and no honest district band to paint.

## Openness evidence (one polite check, 2026-09-13, no scraping, no auth)

Two header-only `HEAD`s plus one `GET` of the landing page with a
labelled one-off user-agent (response headers + keyword scope read
of visible text only):

| Check | Observed | Meaning |
|---|---|---|
| `https://www.creditinfo.ee/` → 301 to `https://creditinfo.ee/` | Bare-www redirect, Cloudflare-fronted | Canonical host is creditinfo.ee |
| `https://www.krediidiinfo.ee/` → 301 to `https://creditinfo.ee/` | Krediidiinfo brand redirects to the same host (nginx) | One vendor, one storefront: Krediidiinfo is folded into Creditinfo Eesti |
| `https://creditinfo.ee/` → 200, ~123 KB | Storefront copy: "Minu Creditinfo" (oma maksehäirete vaatamine), "Krediidiraportid", "Maksehäired", B2B "Tutvu võimalustega" + müügiosakond (KYC, võlahaldus, kliendiandmete lahendused laenuandjatele/võlausaldajatele) | Payment-default data and scores are sold products behind self-service accounts and sales contracts — not a public feed |
| Keyword sweep of landing text: avaandmed / tasuta alla / X-tee / X-Road / developer / Dokumentatsioon | All absent | No open-data page, no developer portal, no X-tee service advertised |

Judgment call: the check stopped at landing-page level on purpose —
no endpoint enumeration, no account creation, no session flows.
Deeper probing (signing up, driving the self-service flow) is
exactly the scraping this repo refuses (AGENTS.md §5).

## What stays open (overturn paths, not wired here)

- **P4-007 main slice:** e-Äriregister KÜ majandusaasta aruanded
  (XBRL bulk) carry the loan/remondifond/küte €/m² fields themselves
  (parameters4.md source 1) — openly pullable in principle. But that
  is a separate Äriregister ingestion, not the Creditinfo slice this
  verdict covers; wiring it belongs to its own demo, not to this
  NULL module. A challenge must bring that ingestion, not a
  Creditinfo screen-scrape.
- **P4-020 open slices:** Ametlikud Teadaanded pankroti-/täiteteated
  are already scored (open, cap 75) in `dims_p4_ata.py`; the
  kohtutäitur register and Maa-amet kitsendused (arest/keelumärge)
  stay unjoined in both modules.
- **Full overturn:** Creditinfo publishes an open per-entity API
  (or X-tee service) → re-open #259, build the polite cached
  ingestion, and graduate these dims to per-entity joins.

## Why demo + coverage share one PR

The coverage body (#340) states it extends the demo ingestion
(#259). With the demo verdict dated-negative there is no ingestion
to extend, so P4-020's Creditinfo slice lands in the same verdict
module instead of a second file importing a pipeline that does not
exist. One module, one test file, one verdict note — no edits to
shared files.

Note: P4-020 already has a scored AT-notice slice in
`dims_p4_ata.py` (#254/#335); the slice here is disjoint (bureau
developer scores, NULL), the same split-slice precedent as P4-021
(EHR builder history vs AT developer notices).
