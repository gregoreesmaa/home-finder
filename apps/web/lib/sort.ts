import type { SortMode } from "@home-finder/shared";
export type { SortMode };
export { combinedScore, dealNorm, sortListings, withCombined } from "@home-finder/shared";
export type { Rankable } from "@home-finder/shared";

export const SORT_PARAM: Record<SortMode, string> = {
  combined: "combined",
  livability: "livability",
  deal: "deal",
};
