"use client";

import type { MockListing } from "../lib/mockListings";

export function livabilityTone(score: number): "green" | "amber" | "red" {
  if (score >= 75) return "green";
  if (score >= 55) return "amber";
  return "red";
}

/** discount_pct positive = below market (steal). Displayed with a minus sign. */
export function dealBadge(discountPct: number): { label: string; tone: string } {
  if (discountPct >= 8) return { label: `STEAL -${discountPct}%`, tone: "green" };
  if (discountPct >= -3) return { label: `FAIR ±${Math.abs(discountPct)}%`, tone: "neutral" };
  return { label: `OVER +${Math.abs(discountPct)}%`, tone: "red" };
}

export function ListingCard({
  listing,
  rank,
  onSelect,
}: {
  listing: MockListing;
  rank: number;
  onSelect?: (id: string) => void;
}) {
  const deal = dealBadge(listing.discount_pct);
  return (
    <article aria-label={`#${rank} ${listing.address}`}>
      <span aria-label={`Koht ${rank}`}>#{rank}</span>
      <h3>{listing.address}</h3>
      <p>
        {listing.price.toLocaleString("et-EE")} € · {listing.price_per_m2.toLocaleString("et-EE")} €/m² ·{" "}
        {listing.rooms} tuba · {listing.area_m2} m²
      </p>
      <span data-tone={livabilityTone(listing.score_livability)}>
        Sobivus {listing.score_livability}/100
      </span>{" "}
      <span data-tone={deal.tone} title="vs prognoositud turuhind samas piirkonnas">
        {deal.label}
      </span>
      <p>{listing.reasons.join(" · ")}</p>
      <button type="button" onClick={() => onSelect?.(listing.id)}>
        Näita kaardil
      </button>
    </article>
  );
}
