// Regression test for issue #785: honest-empty layers (harno, skis,
// gbfs, paaste, planktpr) name their dated verdict instead of the
// generic "DEMO-varu (live ebaõnnestus)" load-failure label. Silly
// #774 precedent (sillyDemoStatus): each status names EI OLE / ootel
// + source + buyer-side check, never a failure; 0 markers stay 0.
// Hermetic: pure status functions + registry fallbackPoints only.

import { describe, expect, it } from "vitest";
import { LAYERS } from "./layers";
import { harnoDemoStatus } from "./layers_p4_harno";
import { skisDemoStatus } from "./layers_p4_skis";
import { gbfsDemoStatus } from "./layers_p4_gbfs";
import { paasteDemoStatus } from "./layers_paaste";
import { planktprDemoStatus } from "./layers_planktpr";

const HONEST_EMPTY_IDS = ["harno", "skis", "gbfs", "paaste", "planktpr"] as const;

const STATUS_FOR: Record<(typeof HONEST_EMPTY_IDS)[number], (n: number) => string> = {
  harno: harnoDemoStatus,
  skis: skisDemoStatus,
  gbfs: gbfsDemoStatus,
  paaste: paasteDemoStatus,
  planktpr: planktprDemoStatus,
};

describe("honest-empty demo status (#785)", () => {
  it("names the dated verdict per layer, never live ebaõnnestus", () => {
    expect(harnoDemoStatus(0)).toBe(
      "EI OLE verifitseeritud aastasnapshotti (Haridussilm/EIS, 2026-09-19: " +
        "per-kooli masin-eksporti pole) · 0 punkti — kvaliteeti " +
        "näitab Haridussilma kooli-leht",
    );
    expect(skisDemoStatus(0)).toBe(
      "Hooaeg läbi, ootel (tallinn.ee Pirita Spordikeskus, 2026-09-19: " +
        "2025/26 hooaeg läbi) · 0 punkti — olekut näitab " +
        "tallinn.ee leht, tel 600 8333",
    );
    expect(gbfsDemoStatus(0)).toBe(
      "EI OLE keyless jaama-voogu (GBFS-register, 2026-09-19: Eestit " +
        "pole) · 0 punkti — seisu näitab ratas.tartu.ee kaart " +
        "ja operaatori äpp",
    );
    expect(paasteDemoStatus(0)).toBe(
      "EI OLE masinloetavat komando-voogu (Päästeamet, 2026-09-13: nimed " +
        "+ aadressid, koordinaate pole) · 0 punkti — lähim " +
        "komando selgub rescue.ee kontaktidest",
    );
    expect(planktprDemoStatus(0)).toBe(
      "EI OLE elusaid polügoone (PLANK-WFS/TPR, 2026-09-13: WFS-liides " +
        "puudub, korje ootel) · 0 punkti — kehtestatud " +
        "sihtotstarve selgub TPR veebivaatest",
    );
  });

  it("every honest-empty status carries verdict + date + check, never failure", () => {
    for (const id of HONEST_EMPTY_IDS) {
      const status = STATUS_FOR[id](0);
      // Dated verdict: EI OLE or ootel plus a 2026-09 probe date.
      expect(status).toMatch(/EI OLE|ootel/);
      expect(status).toMatch(/2026-09-\d{2}/);
      expect(status).toContain("0 punkti");
      // Never the generic load-failure label.
      expect(status).not.toContain("ebaõnnestus");
      expect(status).not.toContain("DEMO-varu");
    }
  });

  it("0 markers stay 0 markers — no invented points", () => {
    for (const id of HONEST_EMPTY_IDS) {
      const def = LAYERS.find((l) => l.id === id);
      expect(def).toBeTruthy();
      expect(def!.fallbackPoints).toEqual([]);
    }
  });
});
