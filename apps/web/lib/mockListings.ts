import { withCombined } from "@home-finder/shared";

export interface MockListing {
  id: string;
  address: string;
  county: string;
  price: number;
  price_per_m2: number;
  rooms: number;
  area_m2: number;
  score_livability: number;
  discount_pct: number;
  score_combined: number;
  reasons: readonly string[];
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
