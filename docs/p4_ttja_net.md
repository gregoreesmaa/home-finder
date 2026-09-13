# P4 TTJA netikaart verdict note — TTJA broadband address check (P4-009 slice)

> Dated-negative verdict for issue #266 (demo, single-param).
> Checked 2026-09-13. The one param is a documented map-only NULL
> dim (OTA PR #131 precedent); the scorer lives in
> `services/scoring/dims_p4_ttja_net.py`, pinned by
> `services/scoring/tests/test_dims_p4_ttja_net.py`.

## Verdict

**No open feed — the single dim stays NULL with an Estonian
reason.** TTJA's per-address broadband check lives in the
interactive X-GIS `netikaart` map app. There is no public
per-address feed to poll politely, so there is no ingestion to
cache, no TTL to state beyond this one-off check, and no honest
per-address band to paint.

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

~8 tiny requests total (single GETs, labelled one-off user-agent
`home-finder openness-check (one-off, no scrape)`, headers +
visible-text keyword scope read only). Raw bodies:
`/tmp/hf-ttja/` (one-off PR record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://ttja.ee/` → 200, 177990 B, "Eraklient \| TTJA" | Visible text: netikaart 1x (nav link only); avaandmed / open data / arendaja / developer / X-tee / X-Road / andmestik / masinloetav all 0 | Agency portal, not a data portal: no open-data page, no developer portal, no X-tee service advertised |
| `https://ttja.ee/.../sideteenused-numeratsioon/netikaart` ("Sideteenuste kaart") → 200, 157815 B | Info page pointing the live map at Maa-amet X-GIS | The check exists as a human-facing map, linked from TTJA |
| `https://xgis.maaamet.ee/xgis2/page/app/netikaart` → 200, 1243 B, "X-GIS 2.0 [netikaart]" | Pure Dogis JS app shell (mapFrame + Dogis.Map, app "netikaart"); no server-rendered data, no WMS/WFS/API on the shell | Coverage is interactive-map-only, never a pollable per-address join |
| `https://ttja.ee/.../sideteenused/kiire-internet` ("Lairiba") → 200, 175500 B | "Netikaart" only a nav item; "api" hits are a chatbot config URL + the substring in "kapitalimahukad" | No machine data feed on the broadband page |
| `https://netikaart.ttja.ee/` + `https://saadavus.ttja.ee/` | DNS failure (could not resolve) | Legacy guess-hosts retired — nothing to poll |
| `https://andmed.eesti.ee/dataset?q=netikaart` → 200 JS "Teabevärav" shell | No server-rendered netikaart/TTJA results | No trivially pollable national-portal dataset |

Judgment call: the check stopped at storefront/app-shell level on
purpose — no endpoint enumeration, no X-GIS internals probing, no
map-app scraping. Deeper probing is exactly the scraping this
repo refuses (AGENTS.md §5).

## Sibling slices (owned elsewhere, untouched)

- **P4-009 Elektrilevi feeder-SAIDI slice:**
  `dims_p4_elektrilevi.dim_power_reliability` (NULL: unpublished
  DSO feed, #264).
- **P4-009 Elering national-series slice:**
  `dims_p4_elering.dim_system_adequacy` (NULL: national !=
  address, #265).
- **P4-009 Telia/Elisa/Tele2, Ookla, OpenCellID slices:** their
  own demos, not this source.

## What stays open (overturn path, not wired here)

TTJA (or Maa-amet X-GIS / andmed.eesti.ee) publishes a machine
per-address broadband feed → re-open #266, build the polite
cached ingestion (monthly TTL per parameters4.md P4-009), and
graduate `broadband_address` to a per-address join. Until then
the buyer-side check is: manual TTJA sideteenuste-kaart lookup +
operator levikaardid (Telia/Elisa/Tele2).
