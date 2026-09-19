# P4 micromobility: bike-share GBFS (issue #688)

> Code: `scripts/build/batch_gbfs.py`; tests:
> `services/scoring/tests/test_batch_gbfs.py` (hermetic).
> Scorer: `services/scoring/dims_gbfs.py` + `tests/test_dims_gbfs.py`
> (dated-negative NULL, OTA PR #131 precedent).
> Overlay: `apps/web/lib/layers_p4_gbfs.ts` + `.test.ts`
> (honest-empty pins, paaste #493 precedent).

## Buyer question

"Kas lähimal on rendiratast — ja kas jaamas on rattaid?" — live
station/dock status from a keyless GBFS feed as a micromobility
amenity layer (Tallinn + Tartu).

## §6 Feed verdict (STEP ZERO — dated negative, 2026-09-19)

**NO verified keyless GBFS feed for Tallinn or Tartu — nothing is
polled, nothing is faked.** Polite one-off round, UA
`home-finder-research/0.1`, `--max-time` 20–25, paced ≥ 3 s,
429 as stop. Raw bodies in `/tmp/hf_gbfs_*` + `/tmp/hf_tartu_*`
(one-off PR record, never committed).

| Check | Observed | Meaning |
|---|---|---|
| `raw.githubusercontent.com/MobilityData/gbfs/master/systems.csv` → 200, 219 078 B | Zero rows match tartu/tallinn/estonia | Neither city is in the official GBFS registry |
| `GET ratas.tartu.ee/` → 200, 8 822 B HTML | Angular SPA shell; backend `https://serverapp.ratas.tartu.ee/api`, tenant `europe/tartu` (WeGoShare) | "Smart Bike" is a Tartu-only brand on a vendor platform |
| `GET ratas.tartu.ee/main.*.js` → 200, 2 578 878 B | **Zero** `gbfs` references in 2.6 MB; map calls `GET {api}/map/stations/` with `{}` | No GBFS surface in the official app at all |
| `GET serverapp.ratas.tartu.ee/api` → 404 (`Cannot GET /api`) | API root is not a browser surface | Vendor API, app-shaped |
| `GET serverapp.ratas.tartu.ee/api/map/stations/` (± slash) → HTTP 500 `{"message":"Wrong request!","code":"0"}` | Anonymous GET rejected at app level (session `be-token` header when logged in) | Station JSON is session-keyed, not pollable — stop, no UA spoofing |
| `GET gbfs.api.ridedott.com/public/v2/tallinn/gbfs.json` → 404 `ERR_REGION_NOT_FOUND` | Dott's public keyless pattern has no Tallinn region | Operator fleets are not keyless-GBFS here |
| `GET gbfs.api.ridedott.com/public/v2/tartu/gbfs.json` → 404 `ERR_REGION_NOT_FOUND` | Same for Tartu | Same |
| Brand check | No municipal "Tallinn Smart Bike" system exists (brand is Tartu-only) | The issue's Tallinn half has no feed to verify |

Judgment call: probing stopped at the app gate on purpose — no
account creation, no session-minting fetcher, no browser-UA
spoofing around the bot check (AGENTS.md §§5, 7.4).

## Harvester

`batch_gbfs.py --pull/--build --cache-dir DIR [--discovery URL]
[--city NAME] [--info/--status files]`. `FEEDS` is empty by the
verdict above, so `--pull` honestly refuses (exit 2, Estonian)
until an operator passes a verified `--discovery` URL. The
auto-discovery + info/status-join machinery is proven on hermetic
fixtures (2-station join, `with_bikes` counts), so a future
verified feed plugs straight in. `--build` prints
`{"total", "with_bikes"}`.

## Pole wiring (intentionally ABSENT)

No `bin/run-gbfs.sh`, no cron line, no `pole/api.py` entry:
there is nothing to poll on a cadence. When a keyless feed
verifies (FEEDS non-empty, this doc updated), add the wrapper +
`GET /v1/gbfs` per AGENTS.md §9 and re-open #688.

## Buyer-side check (until a feed verifies)

Tartu: vaata jaamade seisu `ratas.tartu.ee` kaardilt või Tartu
Smart Bike äpist ja käi lähim jaam kohapeal läbi. Tallinn:
operaatori (Bolt/Tuul) äpp + kohapealne jalutuskäik lähima
rendipunktini.
