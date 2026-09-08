"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { SortBar } from "../components/SortBar";
import { TradeoffHint } from "../components/TradeoffHint";
import { ListingCard } from "../components/ListingCard";
import { ListingMap } from "../components/ListingMap";
import { sortListings } from "../lib/sort";
import { fetchListings, parseSortParam, type SortMode } from "../lib/listings";
import { MOCK_LISTINGS, type MockListing } from "../lib/mockListings";

function HomeInner() {
  const params = useSearchParams();
  const router = useRouter();
  const sort = parseSortParam(params.get("sort"));

  const [listings, setListings] = useState<MockListing[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

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
    router.replace(`?sort=${s}`, { scroll: false });
  };

  const top = {
    combined: sortListings(MOCK_LISTINGS, "combined")[0],
    livability: sortListings(MOCK_LISTINGS, "livability")[0],
    deal: sortListings(MOCK_LISTINGS, "deal")[0],
  };

  return (
    <main>
      <h1>Kodud Eestis — parimast halvimani</h1>
      <SortBar value={sort} onChange={setSort} count={listings?.length ?? MOCK_LISTINGS.length} />
      <TradeoffHint combinedTop={top.combined} livabilityTop={top.livability} dealTop={top.deal} />
      <ListingMap listings={listings ?? undefined} />
      {listings === null ? (
        <ol aria-busy="true" aria-label="Loend laeb">
          {[0, 1, 2].map((i) => (
            <li key={i} aria-hidden="true">
              Laadimine…
            </li>
          ))}
        </ol>
      ) : (
        <ol>
          {listings.map((l, i) => (
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
