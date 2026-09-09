"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { SortBar } from "../components/SortBar";
import { FilterBar } from "../components/FilterBar";
import { TradeoffHint } from "../components/TradeoffHint";
import { ListingCard } from "../components/ListingCard";
import { ListingMap } from "../components/ListingMap";
import { sortListings } from "../lib/sort";
import { fetchListings, parseSortParam, type SortMode } from "../lib/listings";
import {
  applyFilters,
  countiesIn,
  parseFilterParams,
  type Filters,
} from "../lib/filters";
import { MOCK_LISTINGS, type MockListing } from "../lib/mockListings";

function toQuery(sort: SortMode, f: Filters, selected: string | null): string {
  const q = new URLSearchParams({ sort });
  if (f.county) q.set("county", f.county);
  if (f.maxPrice !== null) q.set("maxPrice", String(f.maxPrice));
  if (f.minRooms !== null) q.set("minRooms", String(f.minRooms));
  if (f.minLiv !== null) q.set("minLiv", String(f.minLiv));
  if (selected) q.set("selected", selected);
  return `?${q.toString()}`;
}

function HomeInner() {
  const params = useSearchParams();
  const router = useRouter();
  const sort = parseSortParam(params.get("sort"));
  const filters = parseFilterParams(params);
  const selected = params.get("selected");

  const [listings, setListings] = useState<MockListing[] | null>(null);

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

  const setSort = (s: SortMode) => {
    router.replace(toQuery(s, filters, selected), { scroll: false });
  };
  const setFilters = (f: Filters) => {
    router.replace(toQuery(sort, f, selected), { scroll: false });
  };
  const setSelected = (id: string) => {
    router.replace(toQuery(sort, filters, id), { scroll: false });
  };

  const visible = useMemo(
    () => (listings === null ? null : applyFilters(listings, filters)),
    [listings, filters],
  );
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
      <ListingMap listings={visible ?? undefined} selectedId={selected} />
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
