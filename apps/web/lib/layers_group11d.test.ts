// Tests for layers_group11d.ts (issue #135). Hermetic: pure table +
// math assertions, no network, no snapshot reads.
import { describe, expect, it } from "vitest";
import {
  G11D_BONUS,
  G11D_DECAY,
  G11D_LAYER_IDS,
  G11D_LAYERS,
  G11D_METRO_PREFIXES,
  G11D_PARAM_IDS,
  G11D_RASTER_FILES,
  G11D_TAGS,
  G11D_TRAIL_FAR_SCORE,
  g11dBonusSpecFor,
  g11dQuietFromHalf,
  g11dQuietScore,
  isG11DLayerId,
} from "./layers_group11d";

describe("G11D registry", () => {
  it("ships one layer per mappable batch param (p317 is no-map)", () => {
    expect(G11D_LAYER_IDS).toEqual(["mailbox", "postal", "alley", "trailprivacy"]);
    expect(G11D_PARAM_IDS).toEqual({
      mailbox: [346],
      postal: [470],
      alley: [419],
      trailprivacy: [466],
    });
    for (const id of G11D_LAYER_IDS) {
      const def = G11D_LAYERS.find((l) => l.id === id);
      expect(def?.paramIds).toEqual(G11D_PARAM_IDS[id]);
    }
  });

  it("explains green=good / red=bad in Estonian with snapshot sources", () => {
    for (const def of G11D_LAYERS) {
      expect(def.title.length).toBeGreaterThan(0);
      expect(def.goodLabel.length).toBeGreaterThan(0);
      expect(def.badLabel.length).toBeGreaterThan(0);
      expect(def.source).toContain("2026-09-12");
      expect(def.fallbackPoints.length).toBeGreaterThan(0);
    }
    // Hinnang layers never claim measured quality.
    const mailbox = G11D_LAYERS.find((l) => l.id === "mailbox");
    expect(mailbox?.source).toContain("PROKSI");
    const privacy = G11D_LAYERS.find((l) => l.id === "trailprivacy");
    expect(privacy?.source).toContain("PÖÖRATUD");
  });

  it("documents the verified snapshot tags per layer", () => {
    expect(G11D_TAGS.mailbox).toContain("post_box");
    expect(G11D_TAGS.mailbox).toContain("letter_box");
    expect(G11D_TAGS.postal).toContain("post_office");
    expect(G11D_TAGS.postal).toContain("parcel_locker");
    expect(G11D_TAGS.alley).toContain('service"="alley');
    expect(G11D_TAGS.trailprivacy).toContain('highway"="path');
    // Ways carry the feature: no node-only filters (PR #118).
    for (const q of Object.values(G11D_TAGS)) {
      expect(q).toContain("nwr[");
    }
  });

  it("locks calibration with the Python builder (contract rejects drift)", () => {
    expect(G11D_DECAY).toEqual({ mailbox: 0.5, postal: 0.8, alley: 0.5, trailprivacy: 0.5 });
    expect(G11D_BONUS.mailbox).toEqual({ kind: "area", half: 2.5 });
    expect(G11D_BONUS.postal).toEqual({ kind: "area", half: 12.0 });
    expect(G11D_BONUS.alley).toEqual({ kind: "area", half: 0.3 });
    expect(G11D_BONUS.trailprivacy).toEqual({ kind: "quiet", halfM: 1500 });
    expect(g11dBonusSpecFor("trailprivacy")).toEqual({ kind: "quiet", halfM: 1500 });
  });

  it("names raster masters with no metro (county-only, documented)", () => {
    expect(G11D_RASTER_FILES).toEqual({
      mailbox: "mailbox-walk-raster.json",
      postal: "postal-walk-raster.json",
      alley: "alley-walk-raster.json",
      trailprivacy: "trailprivacy-walk-raster.json",
    });
    expect(Object.keys(G11D_METRO_PREFIXES)).toEqual(G11D_LAYER_IDS);
  });

  it("guards the bonusSpecFor hook", () => {
    expect(isG11DLayerId("mailbox")).toBe(true);
    expect(isG11DLayerId("trailprivacy")).toBe(true);
    expect(isG11DLayerId("parks")).toBe(false);
  });
});

describe("G11D quiet math (mirrors batch_g11d_leftovers.quiet_score)", () => {
  it("scores trail-free walk cells at the honest far value, not 100", () => {
    expect(G11D_TRAIL_FAR_SCORE).toBe(90);
    expect(g11dQuietScore(0, 1.5)).toBe(90);
    expect(g11dQuietScore(-1, 1.5)).toBe(90);
  });

  it("inverts: dense trails read exposed, half reads 50", () => {
    expect(g11dQuietScore(1.5, 1.5)).toBe(50);
    expect(g11dQuietScore(13.5, 1.5)).toBe(10);
    expect(g11dQuietScore(0.01, 1.5)).toBeGreaterThan(90);
  });

  it("calms with distance: 0 on the source, 50 at halfM", () => {
    expect(g11dQuietFromHalf(0, 1500)).toBe(0);
    expect(g11dQuietFromHalf(1500, 1500)).toBe(50);
    expect(g11dQuietFromHalf(Number.POSITIVE_INFINITY, 1500)).toBe(100);
  });
});
