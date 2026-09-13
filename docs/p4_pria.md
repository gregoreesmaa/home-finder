# P4 PRIA verdict note — field blocks without an anonymous bulk (P4-024)

> Dated-negative verdict for issue #299 (single-param demo, no
> coverage issue — the issue states 0 remaining params use this
> source, so no follow-up coverage issue exists).
> Checked 2026-09-13. The single param is a documented no-map NULL
> dim (OTA PR #131 precedent); the scorer lives in
> `services/scoring/dims_p4_pria.py`, pinned by
> `services/scoring/tests/test_dims_p4_pria.py`.

## Verdict

**No verified anonymous per-parcel bulk — the dim stays NULL with an
Estonian reason.** PRIA documents field-block spatial data (SHP/TAB/
Excel/CSV, updated daily) via the national Teabevärav catalogue, but
the holder catalogue is a JS app shell with no server-rendered
dataset or download URL, and the live PRIA Veebikaart is an
interactive lookup (last-two-years claimed blocks only), not a bulk
feed. There is no polite anonymous bulk to cache, no TTL to state
beyond this one-off check (re-probe yearly, or sooner if the holder
catalogue server-renders a põllumassiiv bulk URL), and no honest
spray-drift buffer to paint without the field-block polygons — one
interactive lookup says nothing about Tallinn-fringe drift.

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

8 served requests total (single GETs, labelled one-off user-agent
`home-finder openness probe #299 (one-off, single GETs; contact via
GitHub home-finder)`, headers + visible-text keyword scope read
only; no form driving, no AJAX walking, redirects not spidered
beyond the single canonical documented link). Raw bodies:
`/tmp/hf-pria-probe/` (one-off PR record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://www.pria.ee/` → HTTP 200, 146074 bytes, title "PRIA" | Portal front; links `/avaandmed`, `/registrid/pria-kaardiandmed`, `https://kls.pria.ee/kaart/`; sweep: avaandmed x1, põllumassiiv x3, kaart x4; zero WMS/WFS/API/CSV/JSON pointers | Working host confirmed; data paths documented one click deeper, no machine feed on the landing |
| `https://kaart.pria.ee/` → DNS failure (host does not resolve) | Stale guess, tried once | Live map is at kls.pria.ee, not kaart.pria.ee |
| `https://andmed.eesti.ee/dataset?q=pria` → HTTP 200, 75497 bytes, title "Teabevärav" | JS app shell, 12 visible characters, no server-rendered results | No trivially pollable national-portal PRIA dataset (same shell as the #264/#277/#284 checks) |
| `https://www.pria.ee/avaandmed` → HTTP 200, 72856 bytes, title "Avaandmed \| PRIA" (added 27.12.2019, changed 30.03.2021) | "Avaandmed on avalikud kõigile vabalt kasutamiseks antud ja veebist kättesaadavad andmed"; info consolidated in the national portal | Open-data policy exists; no direct bulk link on the page |
| `https://www.pria.ee/registrid/pria-kaardiandmed` → HTTP 200, 78599 bytes, title "PRIA kaardiandmed \| PRIA" (changed 12.03.2026) | Public web map shows ONLY blocks with area-support claims in the last two years; spatial data "kättesaadavad Andmete teabeväravast" in ESRI SHP / MapInfo TAB / MS Excel (2007) / CSV, "uuendamise sagedus: igapäevaselt" | Documented bulk claim with a daily cadence — but it points at the catalogue, not at a file URL |
| `https://kls.pria.ee/kaart/` → HTTP 200, 54913 bytes, title "PRIA Veebikaart" (app v26.9.0, base map © Maa- ja Ruumiamet) | Layer list (Põllumassiivid, loomaregistri tegevuskohad, pärandniidud, katastriüksused); 11-digit-number + address search; verbatim: "Veebikaardil on nähtavad kahel viimasel aastal pindalatoetuste taotlustel märgitud põllumassiivid" | Interactive lookup UI, not a bulk feed |
| Documented holder link (`avaandmed.eesti.ee/information-holders/...`) → HTTP 301 to the canonical `andmed.eesti.ee` host | Single documented-link follow | Redirect target confirmed, not spidered further |
| Canonical holder page → HTTP 200, 75497 bytes, JS "Teabevärav" shell, 12 visible characters | Zero hits for põllumassiiv / ruumiandmed / SHP / CSV / WMS / WFS | No server-rendered bulk URL to poll — dated negative proven, not assumed |

Judgment call: the check stopped at storefront/page level on
purpose — no kls.pria.ee search driving, no AJAX walking, no
Teabevärav JS-app driving (tervise #289 precedent). Driving a
query UI parcel-by-parcel would be scraping human publications,
not polling a feed — exactly what AGENTS.md §5 refuses.

## Honest shape (NULL until a pollable bulk appears)

| Param | Dim key | Honest shape when a feed lands | Buyer-side check meanwhile |
|---|---|---|---|
| P4-024 Country-health, PRIA slice (demo) | `pollupuhver_pria` | coarse Tallinn-fringe hinnang cells off joined field-block polygons (spray-drift buffer bands, e.g. block-adjacent vs 100 m+ clear; never 0/100 on this leg alone — drift hints at caution for kids/dogs, never a guarantee; per-parcel doorway precision stays unscored) | kohapealne vaatlus (pritsimisriba / roheline serv / farmilõhn) + küsi KÜ-lt/naabritelt pritsimisgraafikut; scored cousins: õietolm dims_p4_kaur + elupaik dims_p4_eelis; NULL cousins: puuk/suplusvesi dims_p4_tervise + farmilõhn dims_p4_komun |

Every scored-future reason must trace to a joined field-block
record; a single interactive lookup must never score a parcel.

## Judgment calls (for the reviewer)

1. Single-param demo, no coverage issue: #299 states the remaining
   0 params using this source need only a follow-up created after
   this demo — with a dated-negative demo there is no ingestion to
   extend, so one dim in one module is the whole honest scope.
2. Split-slice contract: the scored KAUR pollen leg
   (dims_p4_kaur dim_tervis_kaur) and EELIS habitat-proxy leg
   (dims_p4_eelis dim_maaloodus_eelis) plus the NULL Terviseamet
   tick/bathing leg (dims_p4_tervise dim_country_health_nuisances)
   and komun farm-odour leg (dims_p4_komun dim_farm_odour_cells)
   stay where they live and are named, never re-scored here.
   Sibling modules were read first; parameters4.md untouched.
3. The documented SHP/CSV daily claim is the reopen anchor, not
   today's verdict: a catalogue page describing a bulk is not a
   verified bulk URL. PRIA's stated "igapäevaselt" cadence is
   recorded as the future-ingestion TTL anchor (daily re-pull
   ticket IF a pollable bulk appears), not as a pull performed.
4. No shared-file edits (livability.py, WEIGHTS, layers, layers.md,
   parameters4.md untouched): 3 new files only. Central hook
   (enrich join + WEIGHTS rebalance) stays one joint change across
   all batches.

## Reopening checklist (when a pollable bulk appears)

1. Re-run the eight probes above yearly (or sooner if the holder
   catalogue server-renders a põllumassiiv bulk URL); paste fresh
   evidence.
2. If a server-rendered SHP/CSV/WFS bulk URL appears: build the
   polite cached ingestion (daily TTL per PRIA's stated cadence)
   and graduate `pollupuhver_pria` to the coarse-cell hinnang
   above — fixtures first, recalibrated buffer bands from a real
   Tallinn-fringe pull.
3. If the bulk stays catalogue-described but never server-rendered:
   keep the NULL — JS-app driving stays out of the repo.
