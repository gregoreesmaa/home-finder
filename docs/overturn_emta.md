# Overturn hunt log — G16 EMTA/KOV tax-table params p2/p73/p151/p422/p423 (issue #242)

> Time-boxed source hunt for Group 16 tax-table params
> (parameters3.md §5.16). Hunted 2026-09-13 (~20 min).
> **Verdict: KEEP the NULLs (dated negative)** — the per-KOV
> rate tables are yearly human-readable PDFs behind Nextcloud
> share links with no machine-readable bulk feed, so no honest
> automated join exists. The test-pinned verdict dims live in
> `services/scoring/dims_overturn_emta.py`, pinned by
> `services/scoring/tests/test_dims_overturn_emta.py`.
> Re-probe the EMTA guide + yearly-table links no later than
> **2027-03-13**.

## Verdict

**No pollable rate table — all five stay NULL with Estonian
KOV-table reasons.** EMTA's public land-tax guide is openly
reachable and even states the 2026 statutory bands, but the
per-KOV numbers it points at are five yearly PDFs (2022–2026)
on Nextcloud shares: a human download, not a join. Colouring
KOVs from a hand-transcribed PDF would be invented data, and a
gradient of the national statutory bands would be one flat
colour (OTA PR #131 precedent; nomap.md §3 G16 anticipated
exactly this shape: "colouring KOVs without the table
in-snapshot is invented data"). Only p2 would flip on a future
machine-readable table; p73/p151/p422/p423 stay NULL
permanently (wrong record type — see below).

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

4 checks total (labelled one-off user-agent
`home-finder-242-probe/1.0 (one-off open-data check for G16
EMTA/KOV tax-table feasibility; contact via GitHub issue
#242)`, paced ≥ 4 s, headers + visible-text/link-scope read
only). Raw bodies: `/tmp/hf-emta242/` (one-off PR record, not
committed).

| Check | Observed | Meaning |
|---|---|---|
| `GET emta.ee/.../maamaks` → 200, 268124 bytes | Public guide: 2026 bands elamumaa + maatulundusmaa õuemaa 0,1–1%, maatulundusmaa 0,1–0,5%, muu sihtotstarve 0,1–2%; KOV-set rates; koduomaniku soodustus ISIKUPÕHINE (MaaMS § 11); vabastused MAAPÕHISED (MaaMS § 4) | Pages are open; bands are national law (flat colour, never a gradient); discounts/exemptions are per-person/per-parcel facts |
| Same page, link census | Yearly per-KOV tables 2022–2026 as `ncfailid.emta.ee` share links labelled "pdf" (8 hrefs); the ONLY machine-readable href on the page is the site RSS feed | No CSV/XLSX/JSON/XML table to join — PDF-only |
| `HEAD` 2026 share → 200, `text/html` | Nextcloud landing wrapper, not a direct file | The table needs interaction + PDF parsing, not a GET-and-join |
| `GET avaandmed.eesti.ee/api/3/action/package_search?q=maamaks` → 404 | No CKAN-style bulk API at the standard path | No open-data-portal back door observed |

Judgment call: probing stopped after the four documented
checks — no Nextcloud-share following, no PDF download/parse,
no Riigi Teataja määrus crawl. Deeper harvesting is the bulk
work (and the scraping) this repo refuses (AGENTS.md §§5, 7.4);
yearly tables converge over annual cron runs, not one session.

## Honest-shape table (per-KOV join, never a gradient)

| Joined record | Score | Reason names |
|---|---|---|
| No joined table row (today: always) | NULL | EI OLE hinnangut, dated probe (2026-09-13), buyer-side table/check |
| Future p2 row: exact (KOV, year) hit | (reopen PR bands) | KOV + year + rate, table source |
| Future p2 lookup: wrong KOV / wrong year / out-of-band 2026 row | NULL (never a neighbour's decree or another year's rate) | EI OLE, KOV-table check |
| p73/p151/p422/p423 under any table | NULL permanently | wrong-record reason (määrus text / law text / deal notice / missing register) |

The `parse_kov_row` / `build_kov_index` / `lookup_kov_rate`
helpers pin this contract today on synthetic fixtures: exact
(KOV, year) match, first wins, 2026 rows validated against the
observed statutory bands, other years year-stamped without band
coercion.

## Near-miss proxies considered and refused

- **Hand-transcribed PDF table as the join** (download the 2026
  PDF once, type the Tallinn row in): a transcription is
  invented data the repo cannot re-verify — the dim would state
  a fact no feed holds. Reopen only on a machine-readable EMTA
  publication.
- **Statutory-band gradient** (paint KOVs by 0,1–1% law range):
  one national range = one flat colour, not an area signal (OTA
  PR #131 precedent).
- **dims_p4_emta rate as the G16 answer** (reuse the P4-019
  fiscal-health slice for p2): different question — trend-based
  fiscal context vs the applicable rate for this listing. The
  modules share nothing by design (cycle precedent, batch B3).
- **Riigi Teataja määrus crawl for p73** (every KOV's tax decree
  exists as an act): per-KOV legal texts with no central table;
  crawling them is the scraping AGENTS.md §5 refuses.
- **Next-year-bill estimate for p422** (model the reassessment
  hit): Estonia has no supplemental-bill instrument — the number
  lives on the deal's own e-MTA notice, never in a table.

## What flipped vs stayed NULL

- FLIPPED: nothing scores yet — constrained-open pages, closed
  bulk. The join path (`parse`/`index`/`lookup` + p2 verdict
  dim) is pinned and fixture-tested for the reopen PR.
- STAYED NULL: p2 (PDF-only table, KOV-table check reason),
  p73 (KOV määrus-text reason), p151 (MaaMS law-text reason),
  p422 (deal-notice reason), p423 (missing-register reason) —
  `dims_group16a`/`dims_group16b` dims untouched, still owning
  the canonical NULLs.
- STAYS INVALID: any area gradient for all five — municipal
  decrees and deal facts are not place fields.

## What stays open (not wired here)

Feeding a future machine-readable table through `lookup_kov_rate`
into the p2 dim + rebalancing WEIGHTS is one joint change across
all batches (existing tests pin `set(WEIGHTS)` exactly). Updating
the GROUP16 verdict entry and `docs/nomap.md` stays with the final
docs-index PR. Shared/group files (`dims_group16a.py`,
`dims_group16b.py`, `dims_p4_emta.py`, `livability.py`, WEIGHTS,
`docs/nomap.md`) are deliberately untouched here.
