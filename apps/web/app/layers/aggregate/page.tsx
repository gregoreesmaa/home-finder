"use client";

// Combined aggregate agreement view (#810): sibling of /layers rendering
// ALL goodness layers on one shared standard-raster grid (#809),
// combined live with user-adjustable per-layer weights and switchable
// combine modes. Green = layers agree good, red = agree bad,
// orange = contested (~50/50 or split). Cells no layer covers render
// no-data (transparent), never mid-orange; layers without live data
// are excluded and named, never faked in. #819: the gradient
// recalibrates to the visible extent (best visible = green) and layer
// weights multiply with per-category multipliers.

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import "maplibre-gl/dist/maplibre-gl.css";
import { ValueHeatLayer } from "../../../components/ValueHeatLayer";
import { ESTONIA_BBOX } from "../../../lib/heatmap";
import {
  LAYERS,
  bonusSpecFor,
  fetchLayerPoints,
  radiusKmFor,
  type BBoxLike,
  type LayerId,
  type LayerPoint,
  type LayerProvenance,
} from "../../../lib/layers";
import { buildScoredField } from "../../../lib/distanceField";
import { standardFromScoredField } from "../../../lib/standardRaster";
import {
  COMBINE_MODES,
  COMBINE_MODE_LABEL,
  aggregateGridFor,
  aggregateToRgba,
  combineStandardRasters,
  sampleAggregate,
  viewportScaleFor,
  type AggregateField,
  type CombineMode,
} from "../../../lib/aggregateRaster";
import {
  CATEGORIES,
  CATEGORY_LABEL,
  DEFAULT_CATEGORY_MULTIPLIERS,
  DEFAULT_WEIGHTS,
  LAYER_CATEGORY,
  STORE_KEY,
  WEIGHT_MAX,
  WEIGHT_STEP,
  effectiveWeight,
  parseStoredAggregate,
  type AggregateCategory,
} from "../../../lib/aggregateWeights";
import { waterMaskFor } from "../../../lib/waterMask";

const ESTONIA_CENTER: [number, number] = [25.0, 58.75];

/** Layers whose fetch returned usable scored coverage. */
interface LayerFeed {
  id: LayerId;
  title: string;
  points: LayerPoint[];
}

/** Provenance values that carry real reads (demo = fallback, excluded). */
function isUsableProvenance(p: LayerProvenance): boolean {
  return p === "live" || p === "cache" || p === "stale" || p === "snapshot" || p === "empty";
}

function loadStored(): {
  weights: Record<string, number>;
  multipliers: Record<string, number>;
  mode: CombineMode;
} | null {
  try {
    const raw = window.localStorage.getItem(STORE_KEY);
    if (!raw) return null;
    // Unreadable v2 blob (or anything unexpected) -> null, and the
    // caller falls back to shipped defaults. The legacy hf-aggregate-v1
    // key is deliberately never read: it has no category multipliers.
    const parsed = parseStoredAggregate(JSON.parse(raw));
    if (!parsed) return null;
    const mode: CombineMode = COMBINE_MODES.includes(parsed.mode as CombineMode)
      ? (parsed.mode as CombineMode)
      : "average";
    return { weights: parsed.weights, multipliers: parsed.multipliers, mode };
  } catch {
    return null;
  }
}

export default function AggregatePage() {
  const [view, setView] = useState<BBoxLike>(ESTONIA_BBOX);
  const [feeds, setFeeds] = useState<LayerFeed[]>([]);
  const [excluded, setExcluded] = useState<string[]>([]);
  const [loadedCount, setLoadedCount] = useState(0);
  const [totalCount, setTotalCount] = useState(0);
  const [building, setBuilding] = useState(false);
  const [weights, setWeights] = useState<Record<string, number>>({ ...DEFAULT_WEIGHTS });
  const [multipliers, setMultipliers] = useState<Record<string, number>>({
    ...DEFAULT_CATEGORY_MULTIPLIERS,
  });
  const [mode, setMode] = useState<CombineMode>("average");

  const mapDiv = useRef<HTMLDivElement>(null);
  const tipRef = useRef<HTMLDivElement>(null);
  const layerRef = useRef<ValueHeatLayer | null>(null);
  const fieldRef = useRef<AggregateField | null>(null);
  const maskRef = useRef<Uint8Array | null>(null);
  const requestRef = useRef(0);

  // Restore persisted weights + multipliers + mode once (client only).
  // Anything unreadable falls back to the shipped defaults above.
  useEffect(() => {
    const stored = loadStored();
    if (stored) {
      setWeights({ ...DEFAULT_WEIGHTS, ...stored.weights });
      setMultipliers({ ...DEFAULT_CATEGORY_MULTIPLIERS, ...stored.multipliers });
      setMode(stored.mode);
    }
  }, []);

  // Persist on every change (cheap: one small JSON blob).
  useEffect(() => {
    try {
      window.localStorage.setItem(
        STORE_KEY,
        JSON.stringify({ weights, multipliers, mode }),
      );
    } catch {
      // Private mode etc: persistence is a nicety, never a blocker.
    }
  }, [weights, multipliers, mode]);

  // Fetch every layer's points for the settled view. Pins layers are
  // markers-only by decision (no scored field) and are skipped before
  // any fetch; demo/empty fetches are excluded after (nodata honesty).
  useEffect(() => {
    let cancelled = false;
    const id = ++requestRef.current;
    const fresh = () => !cancelled && id === requestRef.current;
    const eligible = LAYERS.filter((l) => {
      try {
        return bonusSpecFor(l.id).kind !== "pins";
      } catch {
        return false;
      }
    });
    setTotalCount(eligible.length);
    setLoadedCount(0);
    setBuilding(true);
    let done = 0;
    type FetchOutcome = { feed: LayerFeed } | { excluded: string } | null;
    void Promise.all<FetchOutcome>(
      eligible.map(async (l): Promise<FetchOutcome> => {
        try {
          const res = await fetchLayerPoints(l.id, view);
          if (!fresh()) return null;
          done += 1;
          setLoadedCount(done);
          if (!isUsableProvenance(res.provenance) || res.points.length === 0) {
            return { excluded: l.title };
          }
          return { feed: { id: l.id, title: l.title, points: res.points } };
        } catch {
          if (!fresh()) return null;
          done += 1;
          setLoadedCount(done);
          return { excluded: l.title };
        }
      }),
    ).then((results) => {
      if (!fresh()) return;
      const ok: LayerFeed[] = [];
      const out: string[] = [];
      for (const r of results) {
        if (!r) continue;
        if ("feed" in r) ok.push(r.feed);
        else out.push(r.excluded);
      }
      setFeeds(ok);
      setExcluded(out);
      setBuilding(false);
    });
    return () => {
      cancelled = true;
    };
  }, [view]);

  // Shared grid + per-layer standard rasters + combine. Weight/mode
  // edits only re-run the cheap combine below (fields are memoised on
  // the fetched feeds, so sliders stay live).
  const grid = useMemo(() => aggregateGridFor(view), [view]);
  const aggregate = useMemo<AggregateField | null>(() => {
    if (feeds.length === 0) return null;
    const inputs = [];
    for (const f of feeds) {
      const valid = f.points.filter(
        (p) => Number.isFinite(p.lon) && Number.isFinite(p.lat),
      );
      if (valid.length === 0) continue;
      const scored = buildScoredField(
        valid,
        grid.bbox,
        grid.cols,
        grid.rows,
        radiusKmFor(f.id),
        bonusSpecFor(f.id),
      );
      inputs.push({
        raster: standardFromScoredField(scored),
        weight: effectiveWeight(f.id, weights, multipliers),
      });
    }
    if (inputs.length === 0) return null;
    return combineStandardRasters(inputs, grid, mode);
  }, [feeds, grid, weights, multipliers, mode]);

  // Open-water mask (#821): sea/lakes excluded from the scale and
  // painted blue. Built from the grid (same memo scope as the field),
  // so pan/zoom rebuild it with the settled view.
  const mask = useMemo(() => waterMaskFor(grid), [grid]);

  // Viewport-recalibrated gradient (#819): normalize to the visible
  // extent so green = best visible cell, red = worst visible cell.
  // Derived from the field, which rebuilds per debounced view, so pan
  // and zoom re-recalibrate with the 600 ms settled-view schedule.
  // Water cells never enter the scale (#821).
  const scale = useMemo(
    () => (aggregate ? viewportScaleFor(aggregate, mask) : null),
    [aggregate, mask],
  );

  useEffect(() => {
    fieldRef.current = aggregate;
    maskRef.current = mask;
    const layer = layerRef.current;
    if (!layer) return;
    if (!aggregate) {
      layer.setField(null, 0, 0, [0, 0, 0, 0]);
      return;
    }
    const b = aggregate.bbox;
    layer.setField(
      aggregateToRgba(aggregate, scale, mask),
      aggregate.cols,
      aggregate.rows,
      [b.minlon, b.minlat, b.maxlon, b.maxlat],
    );
  }, [aggregate, scale, mask]);

  // Map shell: base map + one agreement overlay + hover readout +
  // settled-view reports (debounced, like ValueHeatMap's schedule).
  useEffect(() => {
    let cancelled = false;
    let map: { remove: () => void } | null = null;
    let timer: ReturnType<typeof setTimeout> | null = null;
    (async () => {
      const maplibregl = (await import("maplibre-gl")) as typeof import("maplibre-gl");
      if (cancelled || !mapDiv.current) return;
      const mapObj = new maplibregl.Map({
        container: mapDiv.current,
        style: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        center: ESTONIA_CENTER,
        zoom: 7,
        // Compact attribution: the v4 <details> attribution would
        // otherwise spill over the weight list below the map.
        attributionControl: { compact: true },
      });
      map = { remove: () => mapObj.remove() };
      const layer = new ValueHeatLayer("aggregate-heat");
      layerRef.current = layer;
      mapObj.on("load", () => {
        if (cancelled) return;
        const styleLayers = mapObj.getStyle()?.layers;
        const beforeId = styleLayers?.find(
          (l) => l.type === "line" || l.type === "symbol",
        )?.id;
        try {
          if (beforeId) {
            mapObj.addLayer(
              layer as unknown as maplibregl.CustomLayerInterface,
              beforeId,
            );
          } else {
            mapObj.addLayer(layer as unknown as maplibregl.CustomLayerInterface);
          }
        } catch {
          mapObj.addLayer(layer as unknown as maplibregl.CustomLayerInterface);
        }
        // Paint the field computed before the map finished loading
        // (recalibrated like the live path: best visible = green,
        // water masked like the live path).
        const f = fieldRef.current;
        if (f) {
          const b = f.bbox;
          const m = maskRef.current;
          layer.setField(
            aggregateToRgba(f, viewportScaleFor(f, m), m),
            f.cols,
            f.rows,
            [b.minlon, b.minlat, b.maxlon, b.maxlat],
          );
        }
      });
      const schedule = () => {
        if (timer) clearTimeout(timer);
        timer = setTimeout(() => {
          if (cancelled) return;
          const vb = mapObj.getBounds();
          setView({
            minlon: vb.getWest(),
            minlat: vb.getSouth(),
            maxlon: vb.getEast(),
            maxlat: vb.getNorth(),
          });
        }, 600);
      };
      mapObj.on("moveend", schedule);
      mapObj.on("zoomend", schedule);
      mapObj.getCanvas().addEventListener("mousemove", (e: MouseEvent) => {
        const tip = tipRef.current;
        if (!tip) return;
        const rect = mapObj.getCanvas().getBoundingClientRect();
        const ll = mapObj.unproject([e.clientX - rect.left, e.clientY - rect.top]);
        const hit =
          fieldRef.current &&
          sampleAggregate(fieldRef.current, ll.lng, ll.lat, maskRef.current);
        if (!hit) {
          tip.style.display = "none";
          return;
        }
        tip.style.display = "block";
        tip.style.left = `${e.clientX - rect.left + 12}px`;
        tip.style.top = `${e.clientY - rect.top + 12}px`;
        tip.textContent = hit.water
          ? "vesi"
          : `koondskoor ${Math.round(hit.score)} · ${hit.known} kihti` +
            (hit.spread >= 25 ? " · vastukäiv" : "");
      });
    })();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      layerRef.current = null;
      try {
        map?.remove();
      } catch {
        // Tear-down races a still-loading map: nothing to clean.
      }
    };
  }, []);

  const weightFor = (id: LayerId): number => effectiveWeight(id, weights, multipliers);
  const multiplierFor = (c: AggregateCategory): number =>
    multipliers[c] ?? DEFAULT_CATEGORY_MULTIPLIERS[c] ?? 1;
  const activeCount = feeds.filter((f) => weightFor(f.id) > 0).length;
  const resetAll = () => {
    setWeights({ ...DEFAULT_WEIGHTS });
    setMultipliers({ ...DEFAULT_CATEGORY_MULTIPLIERS });
    setMode("average");
  };
  const feedsByCategory = useMemo(() => {
    const groups = new Map<AggregateCategory, LayerFeed[]>();
    for (const c of CATEGORIES) groups.set(c, []);
    for (const f of feeds) groups.get(LAYER_CATEGORY[f.id])?.push(f);
    return CATEGORIES.map((c) => ({
      category: c,
      feeds: (groups.get(c) ?? []).sort((a, b) => a.title.localeCompare(b.title, "et")),
    })).filter((g) => g.feeds.length > 0);
  }, [feeds]);

  return (
    <main style={{ padding: 16, maxWidth: 1100, margin: "0 auto" }}>
      <p>
        <Link href="/layers">← Tagasi ühe kihi vaatele</Link>
      </p>
      <h1>Kombineeritud vaade</h1>
      <p>
        Kõik andmetega kihid ühel kaardil: <strong style={{ color: "#16a34a" }}>roheline</strong>{" "}
        = kihid nõustuvad, et hea,{" "}
        <strong style={{ color: "#dc2626" }}>punane</strong> = nõustuvad, et halb,{" "}
        <strong style={{ color: "#d97706" }}>oranž</strong> = vastukäiv (~50/50). Tühi ala =
        andmed puuduvad (ei hinnata, ei peideta keskmise taha). Skaala
        kalibreerub nähtava ala järgi: roheline = parim nähtav koht,
        punane = halvim nähtav koht.{" "}
        <strong style={{ color: "#3b82f6" }}>Sinine</strong> = avavesi
        (meri/järv — skaalast väljas, hinnangut ei anta).
      </p>
      <p aria-live="polite">
        {building || feeds.length === 0
          ? `Laen kihte… ${loadedCount}/${totalCount}`
          : `${activeCount} kihti arvesse · ${excluded.length} andmeteta (välja jäetud) · ` +
            `ruudustik ${grid.cols}×${grid.rows}`}
      </p>
      <fieldset>
        <legend>Kombineerimisviis</legend>
        {COMBINE_MODES.map((m) => (
          <label key={m} style={{ display: "block", margin: "4px 0" }}>
            <input
              type="radio"
              name="combine-mode"
              checked={mode === m}
              onChange={() => setMode(m)}
            />{" "}
            {COMBINE_MODE_LABEL[m]}
          </label>
        ))}
      </fieldset>
      <div style={{ position: "relative" }}>
        <div ref={mapDiv} style={{ width: "100%", height: 520 }} />
        <div
          ref={tipRef}
          style={{
            display: "none",
            position: "absolute",
            pointerEvents: "none",
            background: "rgba(0,0,0,0.8)",
            color: "#fff",
            padding: "2px 6px",
            borderRadius: 4,
            fontSize: 12,
          }}
        />
      </div>
      <h2 style={{ marginTop: 24 }}>Kategooriate kordajad</h2>
      <p>
        Iga kategooria võimendab oma kihte: tegelik kaal = kihi kaal ×
        kategooria kordaja (0 = kategooria välja arvatud).
      </p>
      <ul style={{ columns: 2, listStyle: "none", padding: 0 }}>
        {CATEGORIES.map((c) => (
          <li key={c} style={{ breakInside: "avoid", margin: "4px 0" }}>
            <label>
              {CATEGORY_LABEL[c]}{" "}
              <input
                type="range"
                min={0}
                max={WEIGHT_MAX}
                step={WEIGHT_STEP}
                value={multiplierFor(c)}
                aria-label={`${CATEGORY_LABEL[c]} kordaja`}
                onChange={(e) =>
                  setMultipliers((prev) => ({
                    ...prev,
                    [c]: Number(e.target.value),
                  }))
                }
              />{" "}
              ×{multiplierFor(c)}
            </label>
          </li>
        ))}
      </ul>
      <h2 style={{ marginTop: 24 }}>Kihi kaalud</h2>
      <p>
        Lohista kaalu (0 = kiht välja arvatud). Tegelik kaal arvestab ka
        kategooria kordajat. Muudatused rakenduvad kohe ja salvestuvad
        sellesse brauserisse.{" "}
        <button type="button" onClick={resetAll}>
          Lähtesta
        </button>
      </p>
      {feedsByCategory.map((g) => (
        <div key={g.category}>
          <h3>
            {CATEGORY_LABEL[g.category]} (×{multiplierFor(g.category)})
          </h3>
          <ul style={{ columns: 2, listStyle: "none", padding: 0 }}>
            {g.feeds.map((f) => {
              const layerW = weights[f.id] ?? DEFAULT_WEIGHTS[f.id] ?? 1;
              return (
                <li key={f.id} style={{ breakInside: "avoid", margin: "4px 0" }}>
                  <label>
                    {f.title}{" "}
                    <input
                      type="range"
                      min={0}
                      max={WEIGHT_MAX}
                      step={WEIGHT_STEP}
                      value={layerW}
                      aria-label={`${f.title} kaal`}
                      onChange={(e) =>
                        setWeights((prev) => ({
                          ...prev,
                          [f.id]: Number(e.target.value),
                        }))
                      }
                    />{" "}
                    ×{weightFor(f.id)}
                  </label>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
      {excluded.length > 0 && (
        <details>
          <summary>Andmeteta kihid ({excluded.length}) — kaardil ei osale</summary>
          <p>{excluded.join(" · ")}</p>
        </details>
      )}
      <p>
        <Link href="/">← Tagasi nimekirja</Link>
      </p>
    </main>
  );
}
