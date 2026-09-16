# P4 official-air verdict: Keskkonnaagentuur seirejaamad register (issue #524)

Closes #524.

## 1. Openness verdict (2026-09-16, POSITIVE — no dated negative)

Four small GETs (UA `home-finder-p4-ohuseire-probe/1.0`, `--max-time
20`, paced ≥3 s, no retries), cached to `/tmp/hf-524-probe`:

| # | URL | Result |
|---|-----|--------|
| 1 | `https://keskkonnaandmed.envir.ee/` (root) | **OPEN, keyless PostgREST 12.0.1.** `HTTP/2 200`, `content-type: application/openapi+json` — 302 tables (`/f_seirejaamad`, `/f_keskkonnaseire`, `/f_kliima_*`, …). |
| 2 | `/f_seirejaamad?limit=3` | **OPEN station register, JSON, no key.** `HTTP/2 200`, 6 213 bytes, `content-range: 0-2/*`. Rows carry `nimi`, `seisund`, `sr_programm_nimi`, `ehak_tekst`, `kkr_kood`, `kesk_x/kesk_y` (L-EST97 metres). |
| 3 | `/f_seirejaamad?sr_programm_nimi=ilike.*õhu*&limit=10&select=…` | **Air programme confirmed.** `HTTP/2 200`, 2 775 bytes, 10 rows of `Välisõhu kvaliteedi seire[; linnades]`, incl. **`Tallinn Rahu`** (`Harju maakond, Tallinn, Põhja-Tallinna linnaosa`, `seisund: Kasutusel`, `kesk 540568/6590159`, `SJA9166000`). Suspended historic rows (`Peatatud`, coordless) ride along — filtered, counted, never scored. |

Live conversions (L-EST97 → WGS84, PROJ EPSG:3301, dev check):

| Station | L-EST x/y | WGS84 |
|---|---|---|
| Tallinn Rahu | 540568 / 6590159 | 59.44729, 24.71513 (Pelgulinn — matches `Põhja-Tallinna linnaosa`) |
| Pärnu (Ehitajate tee 1) | 531678 / 6472455 | 58.39139, 24.54167 |
| Tartu (Riia tänav) | 659606 / 6474182 | 58.37889, 26.72889 |
| Kohtla-Järve | 686110 / 6590327 | 59.40991, 27.27837 |

Commands run (evidence):

```bash
mkdir -p /tmp/hf-524-probe && cd /tmp/hf-524-probe
UA="home-finder-p4-ohuseire-probe/1.0 (Estonia open-data openness check, single polite pull)"
curl -sS -A "$UA" --max-time 20 --max-filesize 60000 -o seire.json \
  "https://keskkonnaandmed.envir.ee/f_seirejaamad?limit=3"
# HTTP/2 200, 6213 bytes, content-range 0-2/*
sleep 3
curl -sS -A "$UA" --max-time 20 --max-filesize 60000 -o ohu.json \
  "https://keskkonnaandmed.envir.ee/f_seirejaamad?sr_programm_nimi=ilike.*%C3%B5hu*&limit=10&select=nimi,kesk_x,kesk_y,seisund,sr_programm_nimi,ehak_tekst,keht_staatus,kkr_kood"
# HTTP/2 200, 2775 bytes, 10 rows, Tallinn Rahu Kasutusel
```

## 2. Ingestion contract

`services/scoring/dims_p4_ohuseire.py`: `fetch_ohuseire_dump()`
(polite, cache-first, `OHUSEIRE_TTL_S = 7 d`, default dir
`/tmp/hf-ohuseire`) → `parse_ohuseire_dump()` (pure: coord-carrying
rows, fixture-tested) → `lest_to_wgs84()` (pure-stdlib LCC inverse,
EPSG:3301 params quoted from PROJ, <0.01 m agreement verified in dev)
→ `tallinn_extract()` (pure: Kasutusel + air-programme + Tallinn
admin label + bbox; skipped rows COUNTED) → `dim_official_air()`
(coarse 2 km district coverage: 1 → 60, 2+ → 70, cap 70).
Transport errors raise and never touch the cache; HTTP 429 stops the
run. Operator step mirrors senscom (weekly pull → extract JSON):

```bash
cd /tmp/hf-ohuseire
curl -A "home-finder-p4-ohuseire/1.0 (Estonia open-data weekly adapter; polite single-pull, cache-first)" \
  -o ohuseire-seirejaamad.json "https://keskkonnaandmed.envir.ee/f_seirejaamad?sr_programm_nimi=ilike.*ohu*&limit=1000&select=nimi,kesk_x,kesk_y,seisund,sr_programm_nimi,ehak_tekst,keht_staatus,kkr_kood"
python3 -c "
import json, sys
sys.path.insert(0, 'services/scoring')
from dims_p4_ohuseire import parse_ohuseire_dump, tallinn_extract
raw = open('/tmp/hf-ohuseire/ohuseire-seirejaamad.json').read()
snap = tallinn_extract(parse_ohuseire_dump(raw))
json.dump(snap, open('/tmp/hf-ohuseire/ohuseire-tallinn.json', 'w'))
print(snap['fetched'], snap['n_stations'])
"
```

## 3. Honest shape (never a measurement)

NULL (Estonian, `hinnang` + `EI OLE` + buyer check) when: no origin,
no snapshot, empty extract, or 0 stations in radius. Scored reasons
say `hinnang` + `teisendatud`, never `EI OLE` (machine-checked),
never `mõõdetud`/`garanteeritud`, never above 70. DIY leg untouched:
`dims_p4_senscom.py` stays live-when-present / empty-when-absent.

## 4. Judgment calls for the reviewer

1. Single-slice adapter, no WEIGHTS/livability/layers edits — the
   joint rebalancing stays one joint change (existing tests pin
   `set(WEIGHTS)` exactly).
2. 2 km radius on purpose (reference inlets interpolate; DIY stays
   500 m — balconies do not interpolate).
3. Tallinn membership is the register's own `ehak_tekst` (identity
   join on authority text) AND converted coords in the Tallinn bbox.
4. Accent-folded programme match (`valisohu` ∼ `Välisõhu`) so accent
   drift cannot silently empty the extract.
5. Test fixtures fully synthetic — real values only in §1 above.

## 5. DoD evidence

```text
$ python3 -m pytest services/scoring/tests/test_dims_p4_ohuseire.py -q
13 passed in 0.04s
```

Hermetic: zero network calls in tests. Full-suite output in the PR body.

## 6. Reopening checklist

* Per-pollutant series endpoint appears (hourly PM2.5/NO₂ values per
  station) → NEW param work (exposure bands off vintage-labelled
  series); this register stays the station-inventory leg.
* Station moves/closes → weekly pull absorbs it; reasons carry the
  snapshot date so staleness is reviewable.
