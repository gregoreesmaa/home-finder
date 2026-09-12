import { describe, expect, it, vi } from "vitest";
import { OverpassError, fetchOverpassPoints } from "./overpass";

const QUERY = '[out:json][timeout:25];(nwr["leisure"="park"](1,2,3,4););out center 5;';
const BODY = { elements: [{ type: "node", id: 1, lat: 59.43, lon: 24.75 }] };

describe("overpass loader", () => {
  it("identifies the app with a User-Agent (Overpass usage policy)", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(BODY),
    });
    await fetchOverpassPoints(QUERY, fetchImpl);
    const init = fetchImpl.mock.calls[0][1] as { headers?: Record<string, string> };
    expect(init?.headers?.["User-Agent"]).toContain("home-finder");
  });

  it("posts as a form with a content type Overpass accepts", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(BODY),
    });
    await fetchOverpassPoints(QUERY, fetchImpl);
    const init = fetchImpl.mock.calls[0][1] as { headers?: Record<string, string> };
    expect(init?.headers?.["Content-Type"]).toContain("x-www-form-urlencoded");
  });

  it("keeps allowlisted feature tags, drops the rest", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () =>
        Promise.resolve({
          elements: [
            {
              type: "node",
              id: 1,
              lat: 59.43,
              lon: 24.75,
              tags: {
                amenity: "kindergarten",
                name: "Päike",
                "addr:city": "Tallinn",
                leisure: "park",
              },
            },
            { type: "node", id: 2, lat: 59.44, lon: 24.76 },
          ],
        }),
    });
    await expect(fetchOverpassPoints(QUERY, fetchImpl)).resolves.toEqual([
      { lat: 59.43, lon: 24.75, tags: { amenity: "kindergarten", leisure: "park" } },
      { lat: 59.44, lon: 24.76 },
    ]);
  });

  it("parses nodes and centered ways", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(BODY),
    });
    await expect(fetchOverpassPoints(QUERY, fetchImpl)).resolves.toEqual([
      { lat: 59.43, lon: 24.75 },
    ]);
  });

  it("throws OverpassError on HTTP 429 (stop signal, never cached as data)", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      json: () => Promise.resolve({}),
    });
    await expect(fetchOverpassPoints(QUERY, fetchImpl)).rejects.toBeInstanceOf(
      OverpassError,
    );
  });

  it("throws on transport errors and timeouts", async () => {
    const failing = vi.fn().mockRejectedValue(new Error("boom"));
    const slow = vi.fn().mockImplementation(() => new Promise(() => {}));
    await expect(fetchOverpassPoints(QUERY, failing)).rejects.toThrow();
    await expect(fetchOverpassPoints(QUERY, slow, 20)).rejects.toThrow(/timeout/);
  });
});
