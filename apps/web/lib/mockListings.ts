import { withCombined } from "@home-finder/shared";

export interface MockListing {
  id: string;
  address: string;
  county: string;
  price: number;
  /** Null when the portal card omits the field (common on live imports). */
  price_per_m2: number | null;
  rooms: number | null;
  area_m2: number | null;
  score_livability: number;
  discount_pct: number;
  score_combined: number;
  reasons: readonly string[];
  /** Present on live API rows (portal domain, e.g. "pindi.ee"). */
  source?: string;
  /** Original portal listing URL (#70); absent when unknown. */
  source_url?: string;
  /** Portal thumbnail photo (#76); null/ absent renders an honest placeholder. */
  image_url?: string | null;
  /** True when the row came from a real portal import, false for mocks. */
  is_live?: boolean;
  /** Geocoded coordinates (live rows after the livability import); absent on mocks. */
  lat?: number | null;
  lon?: number | null;
}

const etNum = (v: number | null, unit: string): string =>
  v === null || v === undefined ? "–" : `${v.toLocaleString("et-EE")} ${unit}`;

/** One-line facts for the card; missing live fields render as "–". */
export function formatFacts(l: MockListing): string {
  const rooms = l.rooms === null || l.rooms === undefined ? "–" : `${l.rooms} tuba`;
  return (
    `${etNum(l.price, "€")} · ${etNum(l.price_per_m2, "€/m²")} · ` +
    `${rooms} · ${etNum(l.area_m2, "m²")}`
  );
}

// Deliberately constructed so each sort mode yields a DIFFERENT top-1
// (exercises the TradeoffHint component).
const RAW = [
  {
    id: "tallinn-kalamaja",
    address: "Kotzebue 12, Tallinn",
    county: "Harju maakond",
    price: 285000,
    price_per_m2: 4200,
    rooms: 3,
    area_m2: 68,
    score_livability: 88,
    discount_pct: 10,
    reasons: ["Harju keskmisest -5%", "12 min kesklinna"],
    source: "pindi.ee",
    source_url: "https://www.pindi.ee/kinnisvarapakkumised/kotzebue-12/",
    image_url: "https://www.pindi.ee/media/kotzebue-12.jpg",
  },
  {
    id: "tartu-karlova",
    address: "Tähe 45, Tartu",
    county: "Tartu maakond",
    price: 149000,
    price_per_m2: 2600,
    rooms: 2,
    area_m2: 57,
    score_livability: 64,
    discount_pct: 18,
    reasons: ["Turuennustusest -18% alla", "8 min ülikooli"],
  },
  {
    id: "parnu-rannarajoon",
    address: "Mere pst 7, Pärnu",
    county: "Pärnu maakond",
    price: 198000,
    price_per_m2: 3100,
    rooms: 3,
    area_m2: 64,
    score_livability: 95,
    discount_pct: -9,
    reasons: ["Parim koolide ligipääs", "5 min randa"],
  },
] as const;

export const MOCK_LISTINGS: MockListing[] = RAW.map((l) => withCombined({ ...l }));
