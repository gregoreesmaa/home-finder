"use client";

import type { MockListing } from "../lib/mockListings";

/** Pure derived hint shown when the best-balance pick differs from both single-metric tops. */
export function tradeoff({
  combinedTop,
  livabilityTop,
  dealTop,
}: {
  combinedTop: MockListing;
  livabilityTop: MockListing;
  dealTop: MockListing;
}): string | null {
  if (combinedTop.id === livabilityTop.id || combinedTop.id === dealTop.id) return null;
  const livDelta = livabilityTop.score_livability - combinedTop.score_livability;
  return (
    `Parim tasakaal: ${combinedTop.address}. ` +
    `Puhta kvaliteedi tipp: ${livabilityTop.address} (+${livDelta}p). ` +
    `Suurim steal: ${dealTop.address} (${dealTop.discount_pct}% alla turu).`
  );
}

export function TradeoffHint(props: {
  combinedTop: MockListing;
  livabilityTop: MockListing;
  dealTop: MockListing;
}) {
  const text = tradeoff(props);
  if (!text) return null;
  return <p>{text}</p>;
}
