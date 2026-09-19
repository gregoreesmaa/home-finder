# Build: Elektrilevi live-outage sidecar + dims (issue #729)

> Scoped build from probe #689 (positive 2026-09-19 —
> `services/scoring/probe_outage.py`).
> Code: `scripts/build/batch_outage.py` (harvester);
> `services/scoring/dims_p4_outage.py` (scorer, `outage_now` key);
> overlay: `apps/web/lib/layers_p4_outage.ts` + server
> `apps/web/lib/server/outage.ts` + route branch (city-grain
> hetkeseis point). Tests: `test_dims_p4_outage.py` +
> `test_batch_outage.py` (hermetic) + `layers_p4_outage.test.ts` +
> `server/outage.test.ts` (hermetic). Pole: `GET /v1/outage`
> (honest 503 until the first pull).

## Buyer question

"Kas siin praegu vool kõigub?" — running-outage hetkeseis for the
power half of P4-009 (the Ookla slices own throughput; SAIDI history
stays unpublished per `dims_p4_elektrilevi.py` — untouched).

## §1 Field semantics (pinned from the app's own JS — deferred from the probe, now)

`geoserver-api/content/configuration.js` (200, 67 009 B, polite
/tmp pull 2026-09-19) carries the Elektrilevi presentation layer:

```js
var OUTAGE_T_PLAN = "p";
var OUTAGE_T_FAULT = "f";
var OUTAGE_T_UPCOMING = "u";
function createAreaReplacer(data, upcoming) {
    return createReplacer(
    [/XPFAULTS/, data.fc],
    [/XPPLANS/, data.pc],
    [/XPUPCOMING/, data.uc],
    [/XPCUSTOMERS/, upcoming ? data.ucc : data.fcc + data.pcc],
    ...}
```

Per-area tooltip templates (cid 7639 municipalities):

- `Aktiivseid rikkelisi katkestusi: XPFAULTS` → **fc** = active
  fault-outage count; `Aktiivseid plaanilisi katkestusi: XPPLANS` →
  **pc** = active planned count; `Tulevane plaaniline katkestus:
  XPUPCOMING` → **uc** = upcoming count; `Mõjutatud kliente:
  XPCUSTOMERS` → **fcc/pcc/ucc** = affected customers (active view
  `fcc+pcc`, upcoming view `ucc`).
- Outage rows carry `t` ∈ {p, f, u} with the same vocabulary, plus
  `starttime/plannedstart/plannedend/estendtime/estimatecode/
  estimatedescr/reason/cc` rendered by `gssOutageText`.

`main.js` (603 kB) is the generic Tekla map framework (markers,
clusters, `getCustomerCount`) — counter semantics live ONLY in
`configuration.js`, pinned above. No deeper enumeration was done
(AGENTS.md §7.4).

## §2 Live verification (2026-09-19, polite, /tmp only)

UA `home-finder-research/0.1`, paced ≥ 2 s, 429 = stop (none seen).
Raw bodies in `/tmp/hf729/`, never committed.

| Check | Observed | Meaning |
|---|---|---|
| `GET geoserver-api/GetApplicationData` | **200, 127 003 B**, double-encoded JSON `scopes.p.{areas,dynareas,outages}` | Live basis confirmed |
| areas | **99 rows** `{cid, fc, fcc, id, label, pc, pcc, uc, ucc}` — Tallinn (cid 7639): 0/0/0/0/**27**/**3169**; Harju maakond (cid 7638): 0/0/0/0/**96**/**5766** | City grain verified; zero active, upcoming-only noon |
| outages | **516 rows** (t: 514 u, 1 f, 1 p), `estendtime`/`estimatedescr` ("taastame 2 h jooksul") etc. | Running + upcoming mix |
| `GET /` shell + `scripts/main.js` + `content/configuration.js` | 200s, 21 873 B / 603 373 B / 67 009 B | §1 pins |

## §3 Harvester (short-lived cache design — live data)

`batch_outage.py --pull --cache-dir DIR --out sidecar.json`: single
GET (UA, 30 s timeout, 429 = stop, errors raise and never touch the
cache) → decode double envelope → sidecar `{pulled_at, ttl_s: 300,
areas (verbatim), outage_tallies}`. No `--build` without `--pull`
(the harvester refuses to build hetkeseis from cache — exit 2).
Companion endpoints (`GetObjectsByTiles`, `GetNetworkObjects`,
`content/StaticObjects`) stay untouched: area rows have no coords,
so per-outage points would need the tile scheme — out of scope;
city grain is the honest shape (re-open path).

## §4 Scorer + overlay (capped hetkeseis, never reliability)

`dim_outage_now`: fault-active → 30 / planned-active → 55 /
upcoming-only → 70 / clean → 80 (capped — quiet map ≠ reliable
feeder) / missing-or-stale → NULL with EI OLE + rikkekaart check.
Tallinn row first, Harju fallback (never averaged). The map kernel
(`outageBandForRow`) is byte parity with the scorer (drift = red
test). Overlay: ONE Tallinn centroid point, hard 15 km radius,
`fallbackPoints: []` until the operator pull; route serves the fresh
sidecar (`snapshot` + pull age) else 500 → labeled demo.

## §5 Pole wiring (pole files, recorded here per AGENTS.md §9)

Wrapper `bin/run-outage.sh` (every 5 min — live TTL):

```sh
#!/bin/sh
# Pole wrapper: Elektrilevi hetkeseis sidecar (5-min pull, keyless).
set -eu
POLE="$HOME/hf-pole"
OUT="$POLE/built/outage/table.json"
mkdir -p "$POLE/cache/outage" "$(dirname "$OUT")"
python3 "$POLE/harvesters/batch_outage.py" \
  --pull --cache-dir "$POLE/cache/outage" --out "$OUT.tmp"
mv "$OUT.tmp" "$OUT"
```

Cron (pole crontab, every 5 min):
`*/5 * * * * $HOME/hf-pole/bin/run-outage.sh >>$HOME/hf-pole/logs/outage.log 2>&1`

Read API: `GET /v1/outage` (honest 503 until the first pull).
Consumers use `POLE_BASE_URL`; the web route reads `OUTAGE_SNAPSHOT_PATH`
(or its `os.tmpdir()/hf-outage` default — `/tmp/hf-outage` on
Linux/pole, `$TMPDIR/hf-outage` on macOS dev) with the 5-min TTL
enforced in `loadOutageSnapshot` — stale sidecars never render.

## Buyer-side check

Jooksev seis rikkekaardilt (kaart näitab minuteid, mitte fiidri
ajalugu); püsiühenduse TTJA netikaardilt.
