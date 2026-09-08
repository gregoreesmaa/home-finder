"use client";

import { useMemo, useState } from "react";
import { SortBar } from "../components/SortBar";
import { TradeoffHint } from "../components/TradeoffHint";
import { ListingCard } from "../components/ListingCard";
import { ListingMap } from "../components/ListingMap";
import { sortListings, type SortMode } from "../lib/sort";
import { MOCK_LISTINGS } from "../lib/mockListings";

export default function Home() {
  const [sort, setSort] = useState<SortMode>("combined");
  const [selected, setSelected] = useState<string | null>(null);

  const ranked = useMemo(() => sortListings(MOCK_LISTINGS, sort), [sort]);
  const top = useMemo(
    () => ({
      combined: sortListings(MOCK_LISTINGS, "combined")[0],
      livability: sortListings(MOCK_LISTINGS, "livability")[0],
      deal: sortListings(MOCK_LISTINGS, "deal")[0],
    }),
    [],
  );

  return (
    <main>
      <h1>Kodud Eestis — parimast halvimani</h1>
      <SortBar value={sort} onChange={setSort} count={ranked.length} />
      <TradeoffHint combinedTop={top.combined} livabilityTop={top.livability} dealTop={top.deal} />
      <ListingMap />
      <ol>
        {ranked.map((l, i) => (
          <li key={l.id}>
            <ListingCard listing={l} rank={i + 1} onSelect={setSelected} />
          </li>
        ))}
      </ol>
      {selected && <p aria-live="polite">Valitud: {selected}</p>}
    </main>
  );
}
