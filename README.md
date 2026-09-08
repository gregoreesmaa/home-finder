# home-finder — Estonian home-finder

Users sort listings best-to-worst across BOTH metrics (livability fit + price fairness/steal)
and see region goodness/badness as a heatmap on a real map.

Planned stack: Next.js + MapLibre (frontend/map) + FastAPI scoring + PostGIS.

## Structure (Turborepo scaffold v0.1)

- `apps/web` — Next.js app: `SortBar` (livability/discount/composite sort),
  `ListingMap` (deck.gl `HeatmapLayer` over H3 hexes, mock data fallback),
  `ListingCard` + `TradeoffHint`, `lib/sort.ts` + `lib/heatmap.ts` (vitest).
- `packages/shared` — canonical ranking contract (`ranking.ts`), mirrored by the API.
- `services/scoring` — FastAPI stub (`GET /health`, `GET /listings?sort=`,
  `GET /area-scores`) + `adapters/kv_ee.py` (pytest, offline fixtures).
- `db/init.sql` — PostGIS schema (`listings`, `area_scores`).

## Quickstart

See [AGENTS.md](AGENTS.md) §6 for commands
(`npm install`, `npx turbo run test`, `pytest`, `docker compose up --build`).

Ranking contract: `combined = 0.6*livability_norm + 0.4*deal_norm`
(`deal_norm` maps `discount_pct` in [-15,+25] onto [0,1]);
`discount_pct` positive = below predicted market (steal).
