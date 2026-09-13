# P4 elektrilevi verdict note — Elektrilevi DSO feed (P4-009 + 4 slices)

> Dated-negative verdict for issues #264 (demo) and #344 (coverage).
> Checked 2026-09-13. All five params are documented no-map NULL dims
> (OTA PR #131 precedent); scorers live in
> `services/scoring/dims_p4_elektrilevi.py`, pinned by
> `services/scoring/tests/test_dims_p4_elektrilevi.py`.

## Verdict

**No open feed — all five dims stay NULL with Estonian reasons.**
Elektrilevi's outage history (SAIDI/feeder), tariff zones, connection
map, backup-feed info and zero-consumption aggregates live in an
interactive fault-map app, the account-gated "minu.elektrilevi"
self-service, or nowhere at all. There is no public bulk feed to
poll politely, so there is no ingestion to cache, no TTL to state
beyond this one-off check, and no honest per-address/hex band to
paint.

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

~10 tiny requests total (HEADs + single GETs, labelled one-off
user-agent `home-finder openness-check (one-off, no scrape)`,
headers + visible-text keyword scope read only). Raw bodies:
`/tmp/elektrilevi-open/` (one-off PR record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://www.elektrilevi.ee/` → 302 to `/et/avaleht` | Cloudflare + Liferay CMS storefront | Canonical site is a CMS, not a data portal |
| Canonical landing (168 KB) visible-text sweep: avaandmed / open data / arendaja / developer / X-tee / X-Road / andmestik / masinloetav | All 0 (katkestused 3x, hinnakiri 2x as service pages) | No open-data page, no developer portal, no X-tee service advertised |
| `https://rikkekaart.elektrilevi.ee/` → 200, text/html app shell (linked from `/et/katkestused/katkestuste-kaart`) | Live fault map, not a history feed | Outage history (SAIDI/feeder) has no bulk endpoint; the map shows running faults only |
| `https://minu.elektrilevi.ee/` liitumised + `minu-andmed?reAuthenticate=true` | Connection/capacity behind login; free-capacity (`vabadvoimsused`) map app | Liitumiskaart export feasibility is gated/interactive, never a pollable join |
| `https://andmed.eesti.ee/dataset?q=elektrilevi` (301 from avaandmed.eesti.ee) → 200 JS "Teabevärav" shell; `/api/3/action/package_search` → 404 | No server-rendered results, no CKAN API | No trivially pollable national-portal Elektrilevi dataset |
| Zero-consumption aggregates / backup-feed info | Published nowhere | Nothing to poll; the former is privacy-sensitive by construction anyway |

Judgment call: the check stopped at storefront/app-shell level on
purpose — no endpoint enumeration, no account creation, no session
flows, no map-app internals scraping. Deeper probing is exactly the
scraping this repo refuses (AGENTS.md §5).

## What stays open (overturn paths, not wired here)

- **P4-009 broadband half:** TTJA netikaart address check and Ookla
  open tiles are openly checkable cousins, but they are per-address
  live lookups / a different source's tiles — not the Elektrilevi
  feeder history this verdict covers. Wiring them belongs to their
  own demos, not to this NULL module.
- **P4-008 tariff half:** the hinnakiri price lists are
  human-readable, but the per-address join needs the tariff ZONE
  map (which feeder/price area serves this address), and that map
  is interactive-only. Konkurentsiamet piirhinnad + Utilitas/Adven
  tariffs + Tallinna Vesi + KÜ actual €/m² stay the buyer-side
  checks.
- **P4-036 roof half:** Elering mikrotootja tingimused + EHR katuse
  andmed + Maa-amet LiDAR stay the buyer-side checks; the
  liitumiskaart export join graduates only if Elektrilevi opens a
  machine feed.
- **P4-046 backup half:** EHR kütte liik/kamin + listing NLP
  (kamin, kaev) + kohapealne vaatlus stay the checks.
- **P4-051 hex flag:** KÜ kogumata remondifond + REL2021 vakants +
  KV long-DOM clusters stay the checks. Even a future open
  aggregate must stay a hex/KOV flag — never addresses.
- **Full overturn:** Elektrilevi (or andmed.eesti.ee) publishes a
  machine feed for any slice → re-open #264, build the polite
  cached ingestion (monthly TTL per parameters4.md), and graduate
  that dim to a per-address/hex join.

## Why demo + coverage share one PR

The coverage body (#344) states it extends the demo ingestion
(#264). With the demo verdict dated-negative there is no ingestion
to extend, so the four coverage slices (P4-008, P4-036, P4-046,
P4-051) land in the same verdict module instead of a second file
importing a pipeline that does not exist. One module, one test
file, one verdict note — no edits to shared files.
