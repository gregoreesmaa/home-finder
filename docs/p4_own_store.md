# P4 own-store verdict note (issues #243 demo + #327 coverage)

Source: Listing-portal exhaust from the own 17-adapter snapshots (kv.ee /
city24.ee / kinnisvara24.ee polite daily snapshots: `first_seen`, price-drop
history, cross-portal sightings, image-hash index, portal counters, listing
NLP). Implementation: `services/scoring/dims_p4_own_store.py` (pure,
offline; network lives only in the adapters' fetch paths).

## Openness / politeness evidence (from real code, no live calls needed)

- The store is FIRST-PARTY derived data (our own snapshot facts: first-seen
  dates, price points, hashes, counters) — zero vendor, no openness question
  and nothing to re-license. No portal HTML is stored or committed.
- Pulls stay polite per `services/scoring/adapters/__init__.py`:
  `DEFAULT_TTL_S = 24 * 3600` (daily cron at most), `page_limit=1` default,
  desktop UA `home-finder/0.1 (+research scaffold; daily poll)`, per-adapter
  `ROBOTS_URL` (e.g. `kv_ee.py: ROBOTS_URL`), 24 h file cache so repeat runs
  hit disk. Never commit scraped dumps — fixtures only (AGENTS.md §5).
- ToS note (dated 2026-09-13, keeps the verdict either way): only listing
  FACTS (prices, dates, counters, hashes) enter the store, never ad text
  dumps or personal data; broker names are business identifiers already
  published on the ad. Operator re-checks portal ToS before enabling cron.

## TTL statement

Own store: DAILY snapshot series (ingestion stamps `first_seen`/`last_seen`
per pull day; `asof` cursor keeps scoring deterministic). Quarterly-bulk
sources (Maa-amet tehingud, Statamet KK11, EHR bulk) are NOT in this store —
params needing them stay NULL until their own demo lands (named below).

## Verdicts per param (honest shape: per-listing dim; NULL stays NULL)

| Param | Verdict | Basis / missing source |
|---|---|---|
| P4-001 price history + DOM | COMPUTED (demo) | own `first_seen` + `price_history` → steal-opportunity 40–80 |
| P4-022 photo forensics | COMPUTED | own image-hash + `sources_seen` → 30/45/75 |
| P4-028 demand exhaust | COMPUTED | own views/updates counters → 30–75 |
| P4-043 number-13/name | PARTIAL | floor-13 flag → 70; street leg NULL (Maa-amet residuals) |
| P4-046 dread removal | COMPUTED (capped 85) | listing-text NLP (kamin/kaev/varuväljapääs), broker-claim caveat |
| P4-002 micro-comps | NULL | Maa-amet tehingud quarterly bulk |
| P4-003 rent/Airbnb | NULL | KV üüri medians + Airbnb density |
| P4-005 permits | NULL | EHR ehitusluba/kasutusluba join |
| P4-007 KÜ loan | NULL | Äriregister KÜ aruanded (text mention noted, not scored) |
| P4-021 broker track | NULL | cross-portal aggregate still accumulating |
| P4-029 street imagery | NULL | Mapillary/KartaView sequences |
| P4-034 overheating | NULL | EHR orientation/floor + LiDAR (AC mention insufficient) |
| P4-038 bargaining margin | NULL | Maa-amet gap table (drop-% already P4-001's — no double-score) |
| P4-040 arrival | NULL | Mapillary arrival sequences |
| P4-041 glimpse | NULL | LiDAR/LoD2 view fan |
| P4-049 taxi/guest | NULL | ADS findability probe + photo join |
| P4-051 zero-consumption | HARD NULL | hex-only + privacy bar (never per-listing) |
| P4-052 turnover wave | NULL | per-building tehingud/relist aggregate |
| P4-057 heat-pump hum | NULL | EHR heating changes + complaints (own unit ≠ neighbour hum) |
| P4-059 wood-burning zone | NULL | restriction-zone + EHR heating-type join |

Polarity: 100 = most buyer-favourable on the param's Buy Q, 0 = least,
None = unknown. Reasons are Estonian, say "hinnang" for estimates and
"EI OLE" + missing source + buyer check for NULLs.

## Judgment calls (for the reviewer)

See module docstring (demo+coverage paired because #327 extends the demo
ingestion; P4-038 not double-scored; P4-021/P4-052/P4-007 text-wiring noted
but NULL; P4-051 privacy hard NULL; 40+15/flag cap for NLP claims).
No edits to shared files (livability.py, WEIGHTS, layers, docs/layers.md,
docs/nomap.md); WEIGHTS rebalancing stays one joint change across batches.

## Per-asum asking medians (issue #495, dated negative 2026-09-14)

Group B verify-first: per-asum (Tallinn, 84 asumit) median €/m² asking
prices derived ONLY from this store — no external price source. Tally
from real repo content (each adapter fixture through that adapter's own
`parse_search` entry point): 30 records → 26 with price+area, 13
Tallinn-usable — **0 carrying an `asum` key** (the adapter record schema
has none; portal addresses sit at street+locality grain, e.g.
"Sireli tee 4, Haiba, Saue vald"). No Tallinn asum polygons are vendored
and `listings` has no asum column, so the exact join (statkov #485
identity-join-or-NULL precedent) cannot run today.

Honest shape: kernel `services/scoring/dims_p4_own_asum.py`
(`group_by_asum` + `describe_asum`, MIN_N = 5 — Land Board ≥5/settlement
precedent, asking noisier than closed so the strict bar) with thin asums
staying NULL (Estonian hinnang + EI OLE + n labeled); map twin
`apps/web/lib/layers_asumedia.ts` (layer `asumedia`, empty-on-purpose,
no bands calibrated off fixtures). Reopen bar: accumulated geocoded
snapshots (≥MIN_N in ≥1 asum) + vendored 84-asum polygons + bands
calibrated off the real store.
