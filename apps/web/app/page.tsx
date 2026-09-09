"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { SortBar } from "../components/SortBar";
import { FilterBar } from "../components/FilterBar";
import { TradeoffHint } from "../components/TradeoffHint";
import { ListingCard } from "../components/ListingCard";
import { ListingMap } from "../components/ListingMap";
import { combinedScore, sortListings } from "../lib/sort";
import { fetchListings, parseSortParam, type SortMode } from "../lib/listings";
import {
  applyFilters,
  countiesIn,
  parseFilterParams,
  type Filters,
} from "../lib/filters";
import { MOCK_LISTINGS, type MockListing } from "../lib/mockListings";
import {
  DEFAULT_BALANCE,
  isDefaultWeights,
  parseBalanceParam,
  parseWeightsParam,
  weightedLivability,
  weightsToParam,
  type Multipliers,
} from "../lib/weights";
import {
  parsePois,
  poiBadge,
  poiMinutes,
  poisToParams,
  type Poi,
} from "../lib/poi";
import { WeightsPanel } from "../components/WeightsPanel";
import { PoiPanel } from "../components/PoiPanel";

interface PageState {
  sort: SortMode;
  filters: Filters;
  selected: string | null;
  balance: number;
  multipliers: Multipliers;
  pois: Poi[];
  poiSort: boolean;
}

function toQuery(s: PageState): string {
  const q = new URLSearchParams({ sort: s.sort });
  if (s.filters.county) q.set("county", s.filters.county);
  if (s.filters.maxPrice !== null) q.set("maxPrice", String(s.filters.maxPrice));
  if (s.filters.minRooms !== null) q.set("minRooms", String(s.filters.minRooms));
  if (s.filters.minLiv !== null) q.set("minLiv", String(s.filters.minLiv));
  if (s.selected) q.set("selected", s.selected);
  if (s.balance !== DEFAULT_BALANCE) q.set("bal", String(s.balance));
  const w = weightsToParam(s.multipliers);
  if (w) q.set("w", w);
  for (const p of poisToParams(s.pois)) q.append("poi", p);
  if (s.poiSort) q.set("poisort", "1");
  return `?${q.toString()}`;
}

function HomeInner() {
  const params = useSearchParams();
  const router = useRouter();
  const state: PageState = {
    sort: parseSortParam(params.get("sort")),
    filters: parseFilterParams(params),
    selected: params.get("selected"),
    balance: parseBalanceParam(params.get("bal")),
    multipliers: parseWeightsParam(params.get("w")),
    pois: parsePois(params),
    poiSort: params.get("poisort") === "1",
  };
  const { sort, filters, selected, balance, multipliers, pois, poiSort } = state;

  const [listings, setListings] = useState<MockListing[] | null>(null);
  const [armed, setArmed] = useState(false);
  const [pendingLabel, setPendingLabel] = useState("Punkt");

  useEffect(() => {
    let live = true;
    setListings(null); // skeleton while (re)loading
    fetchListings(sort).then((items) => {
      if (live) setListings(items);
    });
    return () => {
      live = false;
    };
  }, [sort]);

  const go = (patch: Partial<PageState>) => {
    router.replace(toQuery({ ...state, ...patch }), { scroll: false });
  };
  const setSort = (v: SortMode) => go({ sort: v });
  const setFilters = (f: Filters) => go({ filters: f });
  const setSelected = (id: string) => go({ selected: id });

  // #74: client-side re-score. Untouched sliders reproduce base scores
  // exactly (score_combined from the API is kept); any deviation recomputes
  // weighted livability + combined and labels the card "Kaalutud".
  const customized = !isDefaultWeights(multipliers, balance);
  const scored = useMemo(() => {
    if (listings === null) return null;
    if (!customized && pois.length === 0) return listings;
    return listings.map((l) => {
      const out: MockListing = { ...l };
      if (customized) {
        const w = weightedLivability(l.dims, multipliers);
        if (w !== null) {
          out.score_weighted = w;
          out.score_combined = combinedScore(w, l.discount_pct, balance / 100);
        } else {
          out.score_combined = combinedScore(
            l.score_livability,
            l.discount_pct,
            balance / 100,
          );
        }
      }
      if (pois.length > 0) {
        out.poiLines = pois
          .map((p) => poiBadge(l.lat, l.lon, p))
          .filter((s): s is string => s !== null);
      }
      return out;
    });
  }, [listings, customized, multipliers, balance, pois]);

  const visible = useMemo(() => {
    if (scored === null) return null;
    const filtered = applyFilters(scored, filters);
    // Custom weights change score_combined after the fetch: re-sort so the
    // visible order matches the buyer's weights, not the server default.
    const ordered = customized ? sortListings(filtered, sort) : filtered;
    if (poiSort && pois.length > 0) {
      const mins = (l: MockListing): number => {
        let best = Infinity;
        for (const p of pois) {
          const m = poiMinutes(l.lat, l.lon, p);
          if (m && m.car < best) best = m.car;
        }
        return best;
      };
      return [...ordered].sort((a, b) => mins(a) - mins(b));
    }
    return ordered;
  }, [scored, filters, poiSort, pois, customized, sort]);
  const counties = useMemo(
    () => countiesIn(listings ?? MOCK_LISTINGS),
    [listings],
  );

  // Tops describe the visible (live, filtered) list, not the mock set.
  const topSource = visible && visible.length > 0 ? visible : MOCK_LISTINGS;
  const top = {
    combined: sortListings(topSource, "combined")[0],
    livability: sortListings(topSource, "livability")[0],
    deal: sortListings(topSource, "deal")[0],
  };

  return (
    <main>
      <h1>Kodud Eestis — parimast halvimani</h1>
      <SortBar
        value={sort}
        onChange={setSort}
        count={visible?.length ?? MOCK_LISTINGS.length}
      />
      <FilterBar
        value={filters}
        counties={counties}
        onChange={setFilters}
        onReset={() => setFilters({ county: "", maxPrice: null, minRooms: null, minLiv: null })}
      />
      {listings !== null && (
        <p aria-live="polite">
          Näitan {visible?.length ?? 0} / {listings.length} kuulutusest
        </p>
      )}
      <TradeoffHint combinedTop={top.combined} livabilityTop={top.livability} dealTop={top.deal} />
      <WeightsPanel
        balance={balance}
        multipliers={multipliers}
        onBalance={(v) => go({ balance: v })}
        onMultipliers={(v) => go({ multipliers: v })}
        onReset={() => go({ balance: DEFAULT_BALANCE, multipliers: {} })}
      />
      <PoiPanel
        pois={pois}
        armed={armed}
        sortByPoi={poiSort}
        onRemove={(i) => go({ pois: pois.filter((_, j) => j !== i) })}
        onArm={(a, label) => {
          setArmed(a);
          setPendingLabel(label);
        }}
        onSortByPoi={(v) => go({ poiSort: v })}
      />
      <ListingMap
        listings={visible ?? undefined}
        selectedId={selected}
        onPickLocation={
          armed
            ? (lon, lat) => {
                setArmed(false);
                go({ pois: [...pois, { lat, lon, label: pendingLabel }] });
              }
            : undefined
        }
      />
      {visible === null ? (
        <ol aria-busy="true" aria-label="Loend laeb">
          {[0, 1, 2].map((i) => (
            <li key={i} aria-hidden="true">
              Laadimine…
            </li>
          ))}
        </ol>
      ) : visible.length === 0 ? (
        <div role="status">
          <p>Ükski kuulutus ei vasta filtritele.</p>
          <button
            type="button"
            onClick={() => setFilters({ county: "", maxPrice: null, minRooms: null, minLiv: null })}
          >
            Tühjenda filtrid
          </button>
        </div>
      ) : (
        <ol>
          {visible.map((l, i) => (
            <li key={l.id}>
              <ListingCard listing={l} rank={i + 1} onSelect={setSelected} />
            </li>
          ))}
        </ol>
      )}
      {selected && <p aria-live="polite">Valitud: {selected}</p>}
    </main>
  );
}

export default function Home() {
  return (
    <Suspense>
      <HomeInner />
    </Suspense>
  );
}
