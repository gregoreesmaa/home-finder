# P4 OpenCellID verdict note — key-gated mast-density bulk (P4-009)

> Dated-negative verdict for issue #269 (single-param demo, no
> coverage issue — the issue states 0 remaining params use this
> source, so no follow-up coverage issue exists).
> Checked 2026-09-13. The single param is a documented no-map NULL
> dim (OTA PR #131 precedent); the scorer lives in
> `services/scoring/dims_p4_opencellid.py`, pinned by
> `services/scoring/tests/test_dims_p4_opencellid.py`.

## Verdict

**Key-gated bulk, no anonymous feed — the dim stays NULL with an
Estonian reason.** OpenCellID's Tallinn mast-density bulk pull
needs an API key: the docs say most operations require one, the
CSV downloads hide behind an access token, and the exact area
call this demo would poll (a Tallinn BBOX cell count) answers an
anonymous request with HTTP 401 `API Key not known`. There is no
polite anonymous bulk to cache, no TTL to state beyond this
one-off check (re-probe yearly, or sooner if an anonymous bulk
appears), and no honest mast-density raster to paint without the
keyed bulk — one anonymous cell says nothing about Tallinn
density.

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

4 served requests total (single GETs, labelled one-off user-agent
`home-finder openness probe #269 (one-off, single GETs; contact via
GitHub home-finder)`, headers + visible-text keyword scope read
only; no token read, printed, or sent). Raw bodies:
`/tmp/hf-opencellid-probe/` (one-off PR record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://opencellid.org/` → HTTP 200, 13932 bytes, title "OpenCelliD - Largest Open Database of Cell Towers & Geolocation - by Unwired Labs" | Community-built tower database (55M+ cells, GSM/CDMA/UMTS/LTE/5G NR); landing funnels to "Query the API" + "Download the dataset" | Working host confirmed; both data paths gated (see below) |
| `https://docs.opencellid.org/docs/api/overview` → HTTP 200, 67656 bytes, title "API overview \| OpenCellID" | Verbatim: "Most operations require an API key, supplied as key". Read ops: Get a cell position (`/cell/get`), List cells in an area (`/cell/getInArea`), Count cells in an area (`/cell/getInAreaSize`); data under CC BY-SA 4.0 with attribution | The bulk-shaped reads this demo needs are keyed by design |
| `https://opencellid.org/downloads.php` → HTTP 200, 7319 bytes, title "Data Downloads - OpenCelliD ..." | Verbatim: "Enter your API access token to see download links." Country/worldwide CSV exports cover the last 18 months only | No anonymous CSV to cache; exports need the token-gated account |
| `https://opencellid.org/cell/getInAreaSize?BBOX=59.35,24.55,59.50,24.95&format=json` (anonymous Tallinn count) → HTTP 401, 40 bytes | Verbatim body: `{"error":"API Key not known: ","code":2}` | The honest bulk shape (BBOX count/area over Tallinn) refuses anonymously — dated negative proven, not assumed |

Judgment call: the check stopped at docs + one anonymous count on
purpose — no account registration, no keyed requests (the live
token in the checkout root was never read or sent; baking a
secret into the polite-pull path is exactly what AGENTS.md §5
refuses for a public repo), no CSV pulls, no per-cell
enumeration. Chasing the keyed flow would spend a credential to
prove what the 401 already proves.

## Honest shape (NULL until an anonymous bulk appears)

| Param | Dim key | Honest shape when a feed lands | Buyer-side check meanwhile |
|---|---|---|---|
| P4-009 Power/internet, OpenCellID slice (demo) | `mast_density` | coarse Tallinn raster hinnang off BBOX counts (mast-density bands, weak-good capped — density hints at redundancy, never a guarantee; never 0/100 on this leg alone; per-mast precision stays unscored — markers are estimated cell locations, not confirmed tower sites) | TTJA netikaart (address check) + Telia/Elisa/Tele2 levikaardid + Ookla avaandmed (speed); scored cousins: OSM confirmed-mast proxy dims_group10c + Elektrilevi leg dims_p4_elektrilevi + Elering leg dims_p4_elering |

Every scored-future reason must trace to a joined BBOX-count
record; a single anonymous cell lookup must never score an
address.

## Judgment calls (for the reviewer)

1. Single-param demo, no coverage issue: #269 states the remaining
   0 params using this source need only a follow-up created after
   this demo — with a dated-negative demo there is no ingestion to
   extend, so one dim in one module is the whole honest scope.
2. Split-slice contract: the G10 OSM confirmed-telecom-mast proxy
   (dims_group10c dim_internet, SCORED), the Elektrilevi
   feeder-SAIDI slice (dims_p4_elektrilevi dim_power_reliability,
   NULL) and the Elering national-system slice (dims_p4_elering
   dim_system_adequacy, NULL) stay where they live and are named,
   never re-scored here. The TTJA/Ookla broadband slices are their
   own demos. Sibling modules were read first; parameters4.md
   untouched.
3. Consequence for #230: the B10C mobile cover-kind discs have no
   open OpenCellID raster to consume, so G10 mobile stays on the
   OSM proxy until the key story changes.
4. No shared-file edits (livability.py, WEIGHTS, layers, layers.md,
   parameters4.md untouched): 3 new files only. Central hook
   (enrich join + WEIGHTS rebalance) stays one joint change across
   all batches.

## Reopening checklist (when an anonymous bulk appears)

1. Re-run the four probes above yearly (or sooner if the API
   overview drops the key requirement).
2. If the anonymous BBOX count returns data: build the polite
   cached ingestion (monthly TTL per parameters4.md P4-009) and
   graduate `mast_density` to the coarse-raster hinnang above.
3. If only a keyed bulk exists: keep the NULL — secrets stay out
   of the repo and CI.
