// Group 2 EHR building-registry verdicts, batch A (parameters3.md §5.2,
// issue #136): p21 square footage, p30 accessibility/stories, p33
// property age, p35 energy efficiency, p48 permit history.
//
// ALL FIVE ARE DOCUMENTED NO-MAP VERDICTS. EHR attributes describe the
// DEAL (one building), not the PLACE (the area): a green wash over
// panel districts labelled "accessible" would paint 5th-floor walk-ups
// green because their NEIGHBOURS are tall. Neighbour attributes do not
// transfer to your flat, so no gradient map can be honestly built from
// any source in the snapshot (OTA PR #131 precedent: coarse proxy or
// nothing, never a faked gradient).
//
// Self-contained on purpose (mirrors layers_group15.ts): it imports
// NOTHING, so lib/layers.ts can hook it (G02-HOOK #136) with no
// runtime cycle. It owns no LayerDef/TAGS/DECAY entries -- there is no
// raster, no overlay, and no window to contract-check. The scorer
// fallback lives in services/scoring/dims_group02.py (listing-fact
// dims for p30/p35/p48; p21/p33 are filter/taste, never scored).
//
// Tag verification (2026-09-12, local snapshot PBF -- no network):
//   osmium tags-filter harjumaa-260911.osm.pbf nwr/building \
//     -o /tmp/hf-g02-buildings.pbf   # 252146 buildings county-wide
//   osmium tags-count /tmp/hf-g02-buildings.pbf \
//     building:levels start_date height building:flats
//   13507  building:levels (5% -- and neighbour stories do not make
//          YOUR flat accessible, so p30 stays no-map regardless)
//   328    start_date on buildings (0.13% -- p33 has no honest proxy)
//   (height/EPC/permit/net-area tags: no honest source at any scale;
//   derived-buildings.json carries bare {lon,lat} centroids only.)
// Tallinn bbox (24.55,59.35,24.95,59.55): 83805 buildings, 11816 with
// levels (14%), 283 with start_date (0.3%) -- a p33 dots "layer" would
// be 99.7% honest-red noise, so it stays a verdict, not a button.

/** parameters3.md Group 2 batch-A ids owned by this module. */
export type Group02ParamId = 21 | 30 | 33 | 35 | 48;

export const GROUP02_PARAMS: Group02ParamId[] = [21, 30, 33, 35, 48];

/** Map status for a Group 2 batch-A param (all no-map, see above). */
export type Group02MapStatus = "no-map";

export interface Group02Verdict {
  /** parameters3.md parameter number. */
  param: Group02ParamId;
  /** Short Estonian parameter name. */
  name: string;
  /** Always "no-map" for batch A (locked by test). */
  status: Group02MapStatus;
  /** dims_group02.py dim key, or null when the param is filter/taste. */
  scorerDim: string | null;
  /** Why no honest map exists (Estonian, reviewer-facing). */
  reason: string;
  /** Snapshot evidence backing the verdict. */
  evidence: string;
}

const SNAP = "kohalik hetktõmmis 2026-09-12";

export const GROUP02_VERDICTS: Group02Verdict[] = [
  {
    param: 21,
    name: "Pindala (m²)",
    status: "no-map",
    scorerDim: null,
    reason:
      "Pindala on kuulutuse, mitte asukoha omadus: naaberhoonete suurus " +
      "ei mõõda Sinu korterit. Suurus on ostufilter (mitu tuba soovid), " +
      "mitte monotoonne headus -- 200 m² ei ole parem kui 40 m².",
    evidence: `${SNAP}: EHR netopind registrites puudub (registries/ tühi); ` +
      "OSM-is korteripindade allikas puudub; kv.ee adapter eraldab area_m2 juba filtrina",
  },
  {
    param: 30,
    name: "Ligipääsetavus (korrused)",
    status: "no-map",
    scorerDim: "accessibility",
    reason:
      "Naabermajade korruselisus ei anna Sinu korterile lifti: roheline " +
      "paneelrajoon mõõdaks 5. korruse liftita korteri 'ligipääsetavaks'. " +
      "Ligipääs skooritakse kuulutuse enda korruse + lifti järgi (dims_group02).",
    evidence: `${SNAP}: building:levels 13507/252146 hoonel (5%); liftiandmed ` +
      "OSM-is puuduvad; derived-buildings.json ainult {lon,lat} tsentroidid",
  },
  {
    param: 33,
    name: "Hoone vanus",
    status: "no-map",
    scorerDim: null,
    reason:
      "Vanuse headus on maitse (vanalinna võlu vs uusarendus), mitte " +
      "monotoonne skoor; kaardidiskreet 283 dateeritud hoonet Tallinnas " +
      "oleks 99,7% aus-punast müra, mitte kiht.",
    evidence: `${SNAP}: start_date hoonetel 328 Harjumaal (0,13%), Tallinnas 283; ` +
      "EHR ehitusaasta registrites puudub (registries/ tühi)",
  },
  {
    param: 35,
    name: "Energiatõhusus",
    status: "no-map",
    scorerDim: "energy",
    reason:
      "EPC klass on hoone, mitte asukoha omadus; vanusest tuletatud " +
      "energiaklass oleks proksi proksil (kahekordne võlts). Klass " +
      "skooritakse kuulutuse/EHR fakti järgi (dims_group02), puuduv klass " +
      "jääb NULLiks, mitte hinnanguks.",
    evidence: `${SNAP}: EPC/energia andmed hetktõmmises puuduvad (EHR, KredEx/EIS ` +
      "ega Maa-amet LoD2 pole registrites); OSM-is klassiallikaid pole",
  },
  {
    param: 48,
    name: "Loajalugu",
    status: "no-map",
    scorerDim: "permits",
    reason:
      "Load on hoone, mitte asukoha omadus; naabermajade load ei puhasta " +
      "Sinu korterit. Olek skooritakse kuulutuse/EHR fakti järgi " +
      "(dims_group02), tundmatu olek jääb NULLiks.",
    evidence: `${SNAP}: loa-/menetluse andmed hetktõmmises puuduvad (EHR ` +
      "loamenetlus ega KOV teadaanded pole registrites); OSM-is allikaid pole",
  },
];

/**
 * parameters3.md ids with documented no-map verdicts (Group 2 EHR batch
 * A, #136). lib/layers.ts re-exports this as UNMAPPED_PARAMS
 * (G02-HOOK) and the test below locks every id out of LAYERS.
 */
export const GROUP02_UNMAPPED_PARAMS: readonly number[] = GROUP02_PARAMS;

/** True when every batch-A param carries a no-map verdict. */
export function group02AllNoMap(): boolean {
  return (
    GROUP02_VERDICTS.length === GROUP02_PARAMS.length &&
    GROUP02_VERDICTS.every(
      (v) => v.status === "no-map" && GROUP02_PARAMS.includes(v.param),
    )
  );
}
