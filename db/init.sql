-- PostGIS + home-finder schema (scaffold v0.1)
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS listings (
  id            TEXT PRIMARY KEY,
  source        TEXT NOT NULL,          -- e.g. 'kv.ee'
  source_url    TEXT NOT NULL,
  address       TEXT NOT NULL,
  county        TEXT NOT NULL,          -- Harju / Tartu / Pärnu / ...
  price         INTEGER NOT NULL,       -- EUR
  image_url     TEXT,                   -- portal thumbnail (#76), NULL when unknown
  dims          JSONB DEFAULT '{}',     -- per-dim livability scores (#74 weights)
  price_per_m2  INTEGER,
  rooms         NUMERIC,
  area_m2       NUMERIC,
  lat           DOUBLE PRECISION,
  lon           DOUBLE PRECISION,
  geom          GEOMETRY(Point, 4326),
  score_livability INTEGER,             -- 0..100
  discount_pct     NUMERIC,             -- % below predicted market (positive = steal)
  score_combined   INTEGER,             -- 0..100, 0.6*liv + 0.4*deal_norm
  reasons       JSONB DEFAULT '[]',
  scraped_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS area_scores (
  h3            TEXT PRIMARY KEY,       -- H3 cell id (res ~8)
  score_goodness INTEGER NOT NULL,      -- 0..100 region goodness
  level         TEXT NOT NULL,          -- 'good' | 'mid' | 'bad'
  geom          GEOMETRY(Polygon, 4326)
);
CREATE INDEX IF NOT EXISTS idx_listings_geom ON listings USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_area_scores_geom ON area_scores USING GIST (geom);
