# P4 Stat — openness verdict + demo/coverage note (issues #292, #365)

> Verdict date: 2026-09-13 (all probes single polite GETs, ~14 requests,
> 3 s pacing, contact UA in headers, cached `/tmp/hf-p4-stat/`).
> Code: `services/scoring/dims_p4_stat.py` (demo P4-002 + 9 coverage
> params); tests: `services/scoring/tests/test_dims_p4_stat.py`
> (hermetic, synthetic fixtures, no network).

## Verdict

| Source | Result | Evidence (2026-09-13) |
|---|---|---|
| PX-Web API root (`/api/v1/et`) | **OPEN** | HTTP 200, 67 B: lists `stat`/`statsql` DBs |
| stat tree (`/et/stat`) | **OPEN** | HTTP 200: 7 topic folders |
| `majandus/hinnad` (IA027/IA028 dwelling-price index, quarterly) | **OPEN** | HTTP 200, 30 tables incl. IA028 ELUASEME HINNAINDEKS (KVARTALID) |
| `ehitus/ehitus-ja-kasutusload` (EH04/EH05/EH06/EH44U/EH46U) | **OPEN** | HTTP 200: permits + completions, incl. haldusüksus grain (EH44U/EH46U) |
| `rahvastik/.../ranne` (RVR02..RVR10) | **OPEN** | HTTP 200; RVR02 metadata (7 983 B): annual, 201 haldusüksus values, Sisseränne/Väljaränne/Rändesaldo variables |
| `leibkonnad/.../eluruumid` (LER series, 17 tables) | **OPEN** | HTTP 200 |
| KOV eelarve (RR300/RR302) | **OPEN** | HTTP 200 |
| HH01/KK11 as literal codes | **PARTIAL NEGATIVE (dated)** | Neither code appears in the traversed `stat` + `statsql` listings (statsql holds only väliskaubandus under majandus). Legacy codes; honest substitutes wired: IA028 quarterly index, EH series, RVR migration, RR budgets, LER dwellings |
| Maa-amet per-address deals | **RESTRICTED (dated negative, sibling module)** | See `docs/p4_maa_tehingud.md`; building/street fineness stays that module's job |

Consequence (honest shape): every dim below is an exact area-table join
(linnaosa/asum/KOV/settlement) on the latest period present — never a
gradient, never interpolation. Missing area rows stay NULL with an
Estonian reason. Re-probe quarterly (annual tables: 365 d TTL).

## Pull policy (polite, cached, TTL-stated)

- One request per source per run; `User-Agent: home-finder-research/0.1`
  (polite quarterly bulk; issues 292/365); 25 s timeout; 3 s pacing.
- `fetch_cached(url, cache_dir, name, ttl_days)`: fresh cache wins (no
  request); transport errors are raised and **never cached as data**; HTTP 429
  raises immediately (stop signal, no retry).
- TTLs: quarterly Stat tables **91 d** (IA28 index, EH permits, KK11-shaped
  medians), annual Stat tables **365 d** (RVR migration, RR budgets, RV
  population, LER dwellings).

## Per-param wiring (all honest shapes = exact area-table join)

| Param | Wired leg (this ingestion) | Legs honestly missing (EI OLE, named not faked) |
|---|---|---|
| P4-002 micro-comps (demo) | latest-quarter area median; score = 100·median/asking | building/street fineness (sibling tehingud, restricted) |
| P4-001 DOM history | stale (≥ 90 d / ≥ 2 cuts) × Stat median anchor | adapter `first_seen` history; tehingud micro-comp anchor |
| P4-003 rent reality | gross yield = 12·area rent median / price | Airbnb density, KV-medians, REL2021 rental-share grid |
| P4-019 KOV fiscal | debt burden + operating result (RR-shaped, annual) | arengukava investments (cityplans), EMTA/audits |
| P4-025 micro-liquidity | net migration /1000 (RVR02-shaped, annual) | REL2021 age/vacancy grid, school plans, tehingud turnover |
| P4-038 bargaining margin | quarterly index QoQ change (IA028-shaped heat) | area-type gap table itself (sibling tehingud) |
| P4-043 number-13 | 13-mark × linnaosa baseline (area vs Tallinn median) | street residual (tehingud), education control (rel2021) |
| P4-050 permit glut | permits/completions ratio (EH-shaped, quarterly) | EHR per-building counts, tehingud price check |
| P4-051 zero-consumption | empty-dwelling share at area grain (never addresses) | Elektrilevi/Vesi aggregates, KÜ remondifond, REL2021 grid, arireg arrears |
| P4-061 last-shop spiral | pop change + 12 mo deals per fringe settlement | shop/pharmacy/ATM + bus-cut checklist (siblings) |

Never a gradient: exact-match joins only; latest period only (P4-038
excepted — its param IS the quarterly change); zero completions never
divides (NULL); P4-043 is taste-match only ("maitse-sobivus, mitte
väärtushinnang").
