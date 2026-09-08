import { sortListings, type SortMode } from "./sort";
import { MOCK_LISTINGS, type MockListing } from "./mockListings";

export type { SortMode };

export const SORT_MODES: SortMode[] = ["combined", "livability", "deal"];

/** Parse a `?sort=` URL value. Unknown/missing values fall back to "combined". */
export function parseSortParam(value: unknown): SortMode {
  return value === "livability" || value === "deal" || value === "combined"
    ? value
    : "combined";
}

export function listingsUrl(sort: SortMode, base?: string): string {
  const root = (base ?? process.env.NEXT_PUBLIC_SCORING_URL ?? "http://localhost:8000").replace(
    /\/$/,
    "",
  );
  return `${root}/listings?sort=${sort}`;
}

/**
 * Fetch best-to-worst ranked listings from the scoring API
 * (GET /listings?sort=combined|livability|deal).
 * Falls back to the local ranking contract on network/API errors so the
 * ranked list still renders offline with identical sort semantics.
 */
export async function fetchListings(sort: SortMode, signal?: AbortSignal): Promise<MockListing[]> {
  try {
    const res = await fetch(listingsUrl(sort), { signal });
    if (!res.ok) throw new Error(`GET /listings?sort=${sort} -> ${res.status}`);
    const data: unknown = await res.json();
    if (typeof data !== "object" || data === null || !Array.isArray((data as { items?: unknown }).items)) {
      throw new Error("GET /listings: unexpected shape (want { items: [...] })");
    }
    return (data as { items: MockListing[] }).items;
  } catch {
    return sortListings(MOCK_LISTINGS, sort);
  }
}
