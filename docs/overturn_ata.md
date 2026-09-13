# Overturn note — p362 probate and estate sale delays via Ametlikud Teadaanded URI (issue #233)

> Group 4 p362 (parameters3.md §5.4). Probed 2026-09-13 (2 polite
> GETs). **Verdict: PARTIAL OVERTURN** — the free public AT feed
> carries a joinable per-estate probate signal, so a scored-or-None
> per-listing dim ships in `services/scoring/dims_overturn_ata.py`
> (pinned by `services/scoring/tests/test_dims_overturn_ata.py`).
> Paid e-Kinnistusraamat extract facts stay NULL (owned by the
> untouched `dims_group04` dims), and area gradients stay invalid
> even then (per-estate signal, never a place field).
> Re-check the AT URI scheme + probate volume no later than
> **2027-03-13**.

## Verdict

**The NULL is overturned for the AT slice, kept for the paid slice.**
`Pärimismenetluse algatamise teade` notices are public, anonymous,
URI-addressable by notary publisher + probate type + month/day
window, and downloadable as XML lists — exactly the query shape the
issue asked for. The new `dim_probate_delay_overturn` scores joined
windows (20 active / 60 archived-only / 75 clean-capped) and stays
NULL wherever the join is missing, drifted, or undated, with
notary-check reasons. What the feed cannot answer — who owns the
parcel, what encumbrances sit on it — still needs the paid
e-Kinnistusraamat extract + notary title audit, so those NULLs
stand. No raster follows: 417 initiation notices in 13 days name
deceased estates, not parcels, so there is nothing county-wide to
paint (OTA PR #131 precedent; nomap.md §3 G4 anticipated exactly
this shape: "Ametlikud Teadaanded for p362 ... area gradients stay
invalid even then").

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

2 successful GETs total (labelled one-off user-agent
`home-finder-233-probe/1.0 (one-off open-data check for p362
probate URI feasibility; contact via GitHub issue #233)`, paced ≥
4 s, headers + visible-text/element-name scope read only; one
transient read timeout on the 2.6 MB pull, retried once politely).
Raw bodies: `/tmp/hf-ata233/` (one-off PR record, not committed —
real pulls carry personal data).

| Check | Observed | Meaning |
|---|---|---|
| `GET /avalik/uriotsing` → 200, 152469 bytes | Documents `/ee/{andmeandja}/{pealiik}/{alaliik}/{aasta}/{kuu}/{paev}/{teate_number}/{xml,rdf,txt}`; trailing components droppable; `-` wildcard for publisher/type mid-URI opens a matching notice LIST; list download by appending `xml`; cap "Otsingus kuvatakse vaid 1000 esimest tulemust!"; privacy carve-out covers only individually-served + archived notices | The issue's assumed query scheme is real and documented |
| Same page, `Pärimisteated` group | pealiik slug `parimisteated` with alaliik slugs `parimismenetluse-algatamine`, `parijate-valjaselgitamise-yleskutsemen`, `parimismenetluse-algat-ja-parijate-valjaselgitamise-yleskutsemen`, plus certificate/annulment subtypes | The p362 delay signal has a stable type address |
| `GET /ee/-/parimisteated/parimismenetluse-algatamine/2026/9/xml` → 200, text/xml, 2672862 bytes | 417 `<teadaanne>` records, ALL liik `Pärimismenetluse algatamise teade`, publishers 417/417 starting with `Notar` (per-notary andmeandja, percent-encoded in notice URLs) | Wildcard-publisher + type + month-window list-XML works; notary-publisher filter is real |
| Element census of that window (names only) | `teate_number`, `url`, `liik` (kood+nimi), `andmeandja`, `avaldamise_kpv` + `arhiveerimise_kpv` on every notice, `kinnitatud_sisu`, `sisendid` rows `parandaja_surmakuupaev` / `parandaja_sunnikuupaev` / `toestamise_tahtpaev` / `toestamise_kuupaev` / `parandaja_endine_nimi` / `testamendi_info` / `muude` | Currency is joinable per notice; estate join keys exist |
| Same census, what is ABSENT | No address / kinnistu / katastritunnus field anywhere in the 417 records | The feed resolves per ESTATE (deceased), never per parcel — the listing→estate join needs the deceased identity; without it the dim stays NULL |
| Volume math | 417 notices in Sept 1–13 alone → a full month can approach the 1000-result cap | Month windows with day-level splitting (`needs_split` at ≥ 1000) are required, as the issue specified |

Judgment call: probing stopped after the two documented GETs — no
per-notary enumeration, no day-window sweep, no notice-body mining.
Deeper pulling is bulk work that should converge over weekly cron
runs, not hammer through in one session (AGENTS.md §7.4).

## Honest-shape table (per-estate join, weak-good cap 75)

| Joined window | Score | Reason names |
|---|---|---|
| Active initiation notice(s) | 20 (strong-bad, never 0 — stale/mis-joined possible) | type + number + publication date, `avaldaja: notar` role when verified, notary checkpoint |
| Only archived initiation notices | 60 (history known, no active delay) | count, notary confirmation of current state |
| Queried window, zero notices | 75 capped (never 100) | "nõrk hea teadaandeakna põhjal", EI OLE puhta tiitli tõend, notar check |
| No joined record / no list returned | NULL | EI OLE hinnangut, AT URI search + notar check |
| Window with zero probate-typed notices | NULL (type drift) | count, EI OLE, notar check |
| Probate notice, archive date missing | NULL (unknown currency) | notice description, EI OLE |

Clean is capped at 75 everywhere (never 100): a clean AT window is
not proof of clear title — each clean reason says so and names the
unjoined check (notar). Reasons echo NEVER a person name, code, or
estate date (runtime-only join keys). Paid-fact NULLs (ownership,
encumbrances from e-Kinnistusraamat) stay with the untouched
`dims_group04` dims and their notary-audit reasons.

## Near-miss proxies considered and refused

- **Probate-count area gradient** (initiation density as a "badness"
  heatmap): counts name estates, not parcels — painting streets red
  on unproven per-parcel history is the refused stigma pattern
  (nomap.md §3 G4, p139/p242 precedent).
- **Publisher-name matching as title proof** (a notary published
  *something* → this parcel is affected): the join key is the
  deceased identity, not the publisher — scoring off publisher
  presence inverts the param's question.
- **Clean window as clear title** (75 → 100, or "proof"): absence
  from known types/windows is not absence of proceedings — capped
  weak-good with the EI OLE clause, never proof.
- **Scoring non-probate notices in mixed windows** (arest,
  enampakkumine): other AT slices live in `dims_p4_ata` — this dim
  answers p362 from the probate-classified subset only.

## What flipped vs stayed NULL

- FLIPPED: p362 AT slice — new scored-or-None
  `dim_probate_delay_overturn` over joined notary+type+window pulls.
- STAYED NULL: paid e-Kinnistusraamat extract facts (ownership,
  encumbrances, title cleanliness) — `dims_group04` dims untouched,
  still pointing at the notary title audit.
- STAYS INVALID: any area gradient for p362 — per-estate signal by
  construction.

## What stays open (not wired here)

Feeding this dim with the listing's joined probate window inside
livability scoring + rebalancing WEIGHTS is one joint change across
all batches (existing tests pin `set(WEIGHTS)` exactly). Updating
the GROUP04 verdict entry and `docs/nomap.md` stays with the final
docs-index PR. Shared/group files (`dims_group04.py`,
`livability.py`, WEIGHTS, `docs/nomap.md`) are deliberately
untouched here.
