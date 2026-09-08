import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchListings, listingsUrl, parseSortParam } from "./listings";
import { MOCK_LISTINGS } from "./mockListings";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("?sort= URL param", () => {
  it("passes the three known modes through", () => {
    expect(parseSortParam("combined")).toBe("combined");
    expect(parseSortParam("livability")).toBe("livability");
    expect(parseSortParam("deal")).toBe("deal");
  });

  it("falls back to combined for missing/unknown values", () => {
    expect(parseSortParam(null)).toBe("combined");
    expect(parseSortParam(undefined)).toBe("combined");
    expect(parseSortParam("price")).toBe("combined");
    expect(parseSortParam("")).toBe("combined");
  });
});

describe("GET /listings?sort= wiring", () => {
  it("builds the scoring-API URL with the sort param", () => {
    expect(listingsUrl("deal", "http://api:8000")).toBe("http://api:8000/listings?sort=deal");
    expect(listingsUrl("livability", "http://api:8000/")).toBe("http://api:8000/listings?sort=livability");
  });

  it("returns API items as-is on success", async () => {
    const apiItems = [{ id: "api-only" }];
    const seen: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        seen.push(url);
        return { ok: true, json: async () => ({ items: apiItems }) };
      }),
    );
    await expect(fetchListings("deal")).resolves.toBe(apiItems);
    expect(seen).toHaveLength(1);
    expect(seen[0]).toContain("/listings?sort=deal");
  });

  it("falls back to the local ranking contract when the API is unreachable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("network down");
      }),
    );
    const items = await fetchListings("livability");
    expect(items.map((l) => l.id)).toEqual(["parnu-rannarajoon", "tallinn-kalamaja", "tartu-karlova"]);
    expect(items).toHaveLength(MOCK_LISTINGS.length);
  });

  it("falls back to the local ranking contract on HTTP errors", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false, status: 500, json: async () => ({}) })));
    const items = await fetchListings("deal");
    expect(items[0].id).toBe("tartu-karlova"); // steal-first, same as scoring API
  });
});
