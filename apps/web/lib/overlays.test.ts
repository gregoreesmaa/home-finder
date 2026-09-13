import { describe, expect, it, vi } from "vitest";
import {
  OVERLAY_CAP,
  fetchGraphOverlay,
  needsGraphOverlay,
  overlayColorFor,
  overlayLegendFor,
  overlayWeight,
  selectOverlayPoints,
} from "./overlays";
import { LAYERS, type LayerId } from "./layers";

const BBOX = { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 };

describe("overlay layer routing", () => {
  it("sends only density layers to the graph sidecar", () => {
    expect(needsGraphOverlay("walkability")).toBe(true);
    expect(needsGraphOverlay("pedinfra")).toBe(true);
    expect(needsGraphOverlay("cycling")).toBe(true);
    for (const l of ["parks", "transit", "schools", "grocery", "healthcare"] as const) {
      expect(needsGraphOverlay(l)).toBe(false);
    }
  });
});

describe("overlay weights", () => {
  it("sizes transit by GTFS weekday trips, zero when unknown", () => {
    expect(overlayWeight({ lat: 0, lon: 0, t: 974 }, "transit")).toBe(974);
    expect(overlayWeight({ lat: 0, lon: 0 }, "transit")).toBe(0);
  });

  it("passes area through where the spec scores it", () => {
    expect(overlayWeight({ lat: 0, lon: 0, a: 6.4 }, "parks")).toBe(6.4);
    expect(overlayWeight({ lat: 0, lon: 0, a: 1 }, "grocery")).toBe(1);
  });

  it("weighs unweighted layers at one", () => {
    expect(overlayWeight({ lat: 0, lon: 0, tags: { amenity: "school" } }, "schools")).toBe(1);
  });
});

describe("selectOverlayPoints", () => {
  it("keeps transit hubs first under the cap", () => {
    const pts = [
      { lat: 59.43, lon: 24.75, t: 5 },
      { lat: 59.44, lon: 24.76, t: 3000 },
      { lat: 59.45, lon: 24.77, t: 100 },
    ];
    const out = selectOverlayPoints(pts, "transit", 2);
    expect(out.map((p) => p.w)).toEqual([3000, 100]);
    expect(out).toHaveLength(2);
  });

  it("stride-samples other layers deterministically within the cap", () => {
    const pts = Array.from({ length: 10 }, (_, i) => ({ lat: 59 + i / 100, lon: 24.7 }));
    const out = selectOverlayPoints(pts, "schools", 4);
    expect(out).toHaveLength(4);
    expect(out[0]).toEqual({ lon: 24.7, lat: 59, w: 1 });
    // Same input, same sample (stable across renders/views).
    expect(selectOverlayPoints(pts, "schools", 4)).toEqual(out);
    // Spread, not just the head: last sample comes from the tail half.
    expect(out[3].lat).toBeGreaterThan(59.05);
  });

  it("passes small sets through and drops coordless junk", () => {
    const pts = [
      { lat: 59.43, lon: 24.75 },
      { lat: NaN, lon: 24.76 },
      { lat: 59.45, lon: Infinity },
    ];
    expect(selectOverlayPoints(pts, "grocery")).toHaveLength(1);
  });

  it("caps a Harju-wide tile (performance)", () => {
    const pts = Array.from({ length: 8049 }, (_, i) => ({
      lat: 59 + (i % 1000) / 2000,
      lon: 24 + (i % 1000) / 2000,
      t: i,
    }));
    expect(selectOverlayPoints(pts, "transit")).toHaveLength(OVERLAY_CAP);
  });
});

describe("overlay legend + colors", () => {
  it("explains every layer's markers and weights in Estonian", () => {
    const ids = LAYERS.map((l) => l.id);
    // G07C-HOOK(#142): vectorhabitat joins the registry.
    // G03D-HOOK (#154): moorage + shoredist join the registry.
    expect(ids).toHaveLength(46);
    for (const id of ids) {
      const legend = overlayLegendFor(id);
      expect(legend.length).toBeGreaterThan(10);
    }
    // Weights match the scoring spec halves/bonuses (see bonusSpecFor).
    expect(overlayLegendFor("transit")).toContain("1500");
    expect(overlayLegendFor("parks")).toContain("15 ha");
    expect(overlayLegendFor("schools")).toContain("+12");
    expect(overlayLegendFor("walkability")).toContain("300");
    expect(overlayLegendFor("pedinfra")).toContain("12 km");
    expect(overlayLegendFor("cycling")).toContain("3 km");
    expect(overlayLegendFor("grocery")).toContain("6");
    expect(overlayLegendFor("healthcare")).toContain("20");
    // Batch B1 halves (see B1_BONUS in layers_batch1.ts).
    expect(overlayLegendFor("pets")).toContain("5,7");
    expect(overlayLegendFor("community")).toContain("3,3");
    expect(overlayLegendFor("culture")).toContain("4,5");
    expect(overlayLegendFor("nightlife")).toContain("7,5");
    expect(overlayLegendFor("libraries")).toContain("(küllastus 3)");
    // Batch B5 halves (see B5_BONUS in layers_batch5.ts).
    expect(overlayLegendFor("safety")).toContain("küllastus 1");
    expect(overlayLegendFor("emergency")).toContain("küllastus 2");
    expect(overlayLegendFor("hydrants")).toContain("küllastus 6");
    expect(overlayLegendFor("evac")).toContain("2 km");
    expect(overlayLegendFor("dispatch")).toContain("küllastus 3");
    // Batch G07B halves (see g07bBonusSpecFor in layers_group07b.ts).
    expect(overlayLegendFor("brownsoil")).toContain("500 m");
    expect(overlayLegendFor("oiltank")).toContain("500 m");
    expect(overlayLegendFor("agriland")).toContain("800 m");
    // G11D halves (see G11D_BONUS in layers_group11d.ts).
    expect(overlayLegendFor("mailbox")).toContain("2,5");
    expect(overlayLegendFor("postal")).toContain("küllastus 12");
    expect(overlayLegendFor("alley")).toContain("0,3 km");
    expect(overlayLegendFor("trailprivacy")).toContain("PÖÖRATUD");
    // Batch G07D halves (see g07dBonusSpecFor in layers_group07d.ts).
    expect(overlayLegendFor("agrifield")).toContain("800 m");
    expect(overlayLegendFor("wildcorr")).toContain("500 m");
    // G07C-HOOK(#142): p257 half (see G07C_BONUS in layers_group07c.ts).
    expect(overlayLegendFor("vectorhabitat")).toContain("300 m");
    // Group G06B halves (see GROUP06B_BONUS in layers_group06b.ts).
    expect(overlayLegendFor("plaster")).toContain("küllastus 6");
    expect(overlayLegendFor("antiques")).toContain("küllastus 1");
    expect(overlayLegendFor("woodfire")).toContain("pöördskaala");
    // Batch G11C halves (see G11C_BONUS in layers_group11c.ts).
    expect(overlayLegendFor("schoolbus")).toContain("küllastus 4");
    expect(overlayLegendFor("schoolbus")).toContain("hinnang");
    expect(overlayLegendFor("recspecial")).toContain("küllastus 8");
    expect(overlayLegendFor("medspecial")).toContain("küllastus 5");
    expect(overlayLegendFor("worship")).toContain("2,5");
    expect(overlayLegendFor("forage")).toContain("küllastus 12");
    // Batch B6 halves/tiers (see B6_CAL in layers_batch6.ts).
    expect(overlayLegendFor("droneclear")).toContain("1300 m");
    expect(overlayLegendFor("droneviab")).toContain("800 m");
    expect(overlayLegendFor("rentbleed")).toContain("800 m");
    expect(overlayLegendFor("droneclear")).toContain("mitte EANS DroneMap");
    expect(overlayLegendFor("rentbleed")).toContain("mitte üüriregister");
    // Batch G07 halves (see g07BonusSpecFor in layers_group07.ts).
    expect(overlayLegendFor("industprox")).toContain("500 m");
    expect(overlayLegendFor("odorsrc")).toContain("500 m");
    // Group G06 half (see GROUP06_BONUS in layers_group06.ts).
    expect(overlayLegendFor("heritage")).toContain("küllastus 2");
    // Batch G02B half (see G02B_BONUS in layers_group02b.ts).
    expect(overlayLegendFor("liftproxy")).toContain("küllastus 2");
    expect(overlayLegendFor("liftproxy")).toContain("hinnang");
    // Batch G03 half (see G03_CAL in layers_group03.ts).
    expect(overlayLegendFor("drainage")).toContain("300 m");
    expect(overlayLegendFor("drainage")).toContain("drenaažiproksi");
    // Batch G03D halves (see G03D_CAL in layers_group03d.ts).
    expect(overlayLegendFor("moorage")).toContain("küllastus 1");
    expect(overlayLegendFor("moorage")).toContain("hinnang");
    expect(overlayLegendFor("shoredist")).toContain("100 m");
    expect(overlayLegendFor("shoredist")).toContain("hinnang");
  });

  it("gives every layer a distinct marker color", () => {
    const seen = new Set((LAYERS.map((l) => l.id) as LayerId[]).map(overlayColorFor));
    expect(seen.size).toBe(46);
    for (const c of seen) expect(c).toMatch(/^#[0-9a-f]{6}$/);
  });
});

describe("fetchGraphOverlay", () => {
  it("calls the overlay endpoint with bbox + cap, cleaning junk", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          points: [
            { lon: 24.75, lat: 59.43, w: 1 },
            { lon: 24.76, lat: 59.44 },
            { lon: "x", lat: 59.44 },
            { lon: 24.77, lat: 59.45, w: -3 },
            null,
          ],
        }),
    });
    const pts = await fetchGraphOverlay("walkability", BBOX, 800, fetchImpl);
    const url = String(fetchImpl.mock.calls[0][0]);
    expect(url.startsWith("/api/layers/walkability/overlay?")).toBe(true);
    expect(url).toContain("cap=800");
    expect(pts).toEqual([
      { lon: 24.75, lat: 59.43, w: 1 },
      { lon: 24.76, lat: 59.44 },
      { lon: 24.77, lat: 59.45 },
    ]);
  });

  it("clamps the cap and reads null on failure", async () => {
    const seen: string[] = [];
    const fetchImpl = vi.fn().mockImplementation((url: string) => {
      seen.push(url);
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ points: [] }) });
    });
    await fetchGraphOverlay("cycling", BBOX, 99999, fetchImpl);
    expect(seen[0]).toContain("cap=2000");
    const bad = vi.fn().mockResolvedValue({ ok: false });
    await expect(fetchGraphOverlay("pedinfra", BBOX, 800, bad)).resolves.toBeNull();
    const shape = vi
      .fn()
      .mockResolvedValue({ ok: true, json: () => Promise.resolve({ points: "nope" }) });
    await expect(fetchGraphOverlay("pedinfra", BBOX, 800, shape)).resolves.toBeNull();
    const boom = vi.fn().mockRejectedValue(new Error("down"));
    await expect(fetchGraphOverlay("pedinfra", BBOX, 800, boom)).resolves.toBeNull();
  });
});
