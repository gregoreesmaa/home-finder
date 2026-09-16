# P4 kitsendus verdict note — KPO restriction zones + tehnovõrgud (#543)

> Dated-negative verdict for issue #543. Checked 2026-09-16. Both legs are
> documented no-map NULL dims (OTA PR #131 precedent); scorers + offline
> join core live in `services/scoring/dims_p4_kitsendus.py`, pinned by
> `services/scoring/tests/test_dims_p4_kitsendus.py`.

## Verdict

**No open licence — no ingestion, both dims stay NULL with Estonian
reasons.** The KMA zones WFS is reachable and schema-joinable (18 zone
types, zone-type + rule attributes present), but the catalogue states no
licence and none was found in the capabilities — the issue's hard gate
(`no licence → no ingestion`) forbids pulling a single zone row.

## Openness evidence (one polite round, 2026-09-16, no scraping, no auth)

3 single GETs total, 2 s pacing, `--max-time 30`, labelled one-off
user-agent `home-finder openness-check (one-off, few pages max, no
scrape)`. Raw bodies: `/tmp/hf-probes/` (one-off PR record, not
committed).

| Check | Observed | Meaning |
|---|---|---|
| KMA `kmakitsendused/wfs?…GetCapabilities` → HTTP 200, 127 KB | 18 types `kma_avalik_*`: asjaõigus, elekter, gaas, geodeesia, kaugküte, kemikaal, looduskaitse, maaparandus, muinsuskaitse, planeering, reostusoht, ressurss, riigikaitse, side, sundvaldus, transport, veekogu, veevarustus; CRS EPSG:3301/3857/4326; Fees/Constraints `puudub` (= no charge, NOT a licence) | Zone family fully enumerated; join endpoint proven |
| `…DescribeFeatureType=kma_avalik_looduskaitse` → HTTP 200, 2.4 KB | `voond_liik_id` + `voond_liik_id_vaartus` (zone-type value), `klass`, `nimi`, `reegel` (rule), `ulatus`, `maksusoodustus`, `valise_registri_viide` | The per-parcel join shape is proven at schema level |
| Licence statement | NONE in catalogue, NONE in capabilities | Hard gate: no rows pulled, no Harjumaa counts, no ≥20-parcel live proof |

## Honest shapes per leg (all NULL until the gate clears)

| Leg | Dim key | Honest shape when the gate clears | Buyer-side check meanwhile |
|---|---|---|---|
| Restriction zones | `restriction_zone` | polygon containment → ban 20–35 / conditioned 50–65 (table in code comments); outside → NULL (teadmata, never "clean title") | kinnistusraamat/notar extract — zones ≠ title |
| Utility corridors | `utility_corridor` | tehnovõrgud corridor containment → buyer check | võrguettevõtja (Elektrilevi/vee-ettevõte) + kinnistusraamat |

The offline join core (`point_in_polygon` + `join_zone_flags`,
containment-only, degenerate rings match nothing) is implemented and
proven on fixtures — the reopen PR only flips the gate and runs the live
≥20-parcel proof (kataster tunnus). No gradients, ever.

## Judgment calls (for the reviewer)

1. No licence → no ingestion: pulling even one zone row for "values"
   would breach the gate the issue states — attribute VALUES stay
   unprobed by design, documented here.
2. Zones must never read as title truth: every reason + this legend says
   `tsoonid EI OLE omandiõigus`; the G4 paid-register NULLs are untouched.
3. No shared-file edits: 3 new files only. No map screenshot: nothing is
   painted (polygons-only overlay lands on reopen).

## Reopening checklist (when an open licence is confirmed)

1. Paste the licence statement; pull ONE zone row per family (attribute
   values for `voond_liik_id_vaartus`).
2. Prove the containment join on ≥20 Harjumaa parcels (kataster tunnus)
   with a dated tally; calibrate ban/conditioned bands on it.
3. Graduate the scorers (remove the gate-NULL, keep NULL-outside +
   unknown-type-NULL); add the explicitly-flagged live integration test.
