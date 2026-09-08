import type { MockListing } from "../lib/mockListings";

export interface Filters {
  county: string;
  maxPrice: number | null;
  minRooms: number | null;
  minLiv: number | null;
}

export const EMPTY_FILTERS: Filters = {
  county: "",
  maxPrice: null,
  minRooms: null,
  minLiv: null,
};

/** Read shareable filter state from URL params (D4). */
export function parseFilterParams(params: URLSearchParams): Filters {
  const num = (key: string): number | null => {
    const raw = params.get(key);
    if (raw === null || raw.trim() === "") return null;
    const v = Number(raw);
    return Number.isFinite(v) && v >= 0 ? v : null;
  };
  return {
    county: params.get("county") ?? "",
    maxPrice: num("maxPrice"),
    minRooms: num("minRooms"),
    minLiv: num("minLiv"),
  };
}

/** Distinct counties present in the data, for the county dropdown. */
export function countiesIn(listings: MockListing[]): string[] {
  const seen = new Set<string>();
  for (const l of listings) if (l.county) seen.add(l.county);
  return [...seen].sort((a, b) => a.localeCompare(b, "et"));
}

export function applyFilters(listings: MockListing[], f: Filters): MockListing[] {
  return listings.filter(
    (l) =>
      (f.county === "" || l.county === f.county) &&
      (f.maxPrice === null || l.price <= f.maxPrice) &&
      (f.minRooms === null || (l.rooms ?? 0) >= f.minRooms) &&
      (f.minLiv === null || l.score_livability >= f.minLiv),
  );
}

export function isFiltered(f: Filters): boolean {
  return f.county !== "" || f.maxPrice !== null || f.minRooms !== null || f.minLiv !== null;
}
