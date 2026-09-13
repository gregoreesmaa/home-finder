# P4 konkurents: Konkurentsiamet heat price-cap verdict note (issue #262)

Demo (#262) implements the Konkurentsiamet kooskõlastatud soojuse
piirhinnad ingestion + P4-008 end-to-end in Tallinn. Single param,
single dim, no coverage issue: this source feeds only P4-008 source
(3), so no follow-up issue extends this ingestion (unlike heat
#261/#342 or tvesi #263/#343).

## Openness verdict: zone table OPEN, per-address feed CLOSED (2026-09-13)

Four polite requests total (custom UA `home-finder konkurents
ingest`, short timeouts, paced ≥5 s, bodies to
`/tmp/hf-p4-konkurents/`, no scraping, no auth attempts, redirects
not spidered):

```
HEAD https://www.konkurentsiamet.ee/                       -> HTTP 200 (Cloudflare)
GET  https://www.konkurentsiamet.ee/                       -> HTTP 200, 120 078 B ("Avaleht | Konkurentsiamet")
GET  .../soojus/kooskolastatud-hinnad                      -> HTTP 200, 114 278 B ("Kooskõlastatud hinnad")
GET  .../2026-09/Kooskõlastatud lõpptarbijahinnad seisuga 08.09.2026.xlsx -> HTTP 200 (43 371 B)
```

What each response actually carries:

- Konkurentsiamet front page: authority homepage, no tariff table —
  the hub link carries the substance.
- Kooskõlastatud-hinnad hub: a decision hub ("Kooskõlastatud soojuse
  piirhinna peab soojusettevõtja avalikustama oma võrgupiirkonnas
  vähemalt üks kuu enne selle kehtima hakkamist. Soojust võib müüa
  ka kooskõlastatud piirhinnast madalama hinnaga. Konkurentsiameti
  poolt kooskõlastatud soojuse piirhinnad ei sisalda käibemaksu.")
  with downloadable tables: "Kooskõlastatud soojuse tootmise
  piirhinnad" (PDF), "Kooskõlastatud soojuse piirhinnad
  lõpptarbijale" (XLSX, seisuga 08.09.2026), "Esitatud soojuse
  hinnataotlused" (PDF).
- Lõpptarbijahinnad XLSX (sheet "Kehtiv"): header rows Ettevõte |
  otsuse nr | kuupäev | piirhind €/MWh (käibemaksuta) | uue otsuse
  nr | kuupäev | uus piirhind; company-group rows (e.g. "Adven
  Eesti AS:", "Utilitas Tallinn AS") plus zone rows (võrgupiirkond,
  otsus nr like 7-3/2024-090, kuupäev like 27.12.2024 or Excel
  serial, piirhind like 77.82). Tallinn demo row: Utilitas Tallinn
  AS / Tallinna võrgupiirkond / 77.82 €/MWh käibemaksuta / otsus
  7-3/2024-090 (27.12.2024), no pending uue-hinna columns.

The cap leg is OPEN as a per-võrgupiirkond zone table (Tallinn
present, transcribed into the snapshot layout the parser reads).
Per-address reality is CLOSED as a feed: the file carries no
address-level mapping — which võrgupiirkond serves a given address
needs the operator's võrgupiirkonna kaart. Honest shape is the zone
table join; missing stays NULL with the check named.

Pull contract: max 1 download / 30 d per cache dir
(`KONKURENTS_TTL_S = 2592000`; cap-change driven per
parameters4.md P4-008 — re-pull on Konkurentsiamet decisions, i.e.
when the hub lists a newer "seisuga" vintage), single GET, no
retries — HTTP 429/errors are a stop signal. Transport errors are
never cached as data; the scorer stays NULL with an Estonian EI OLE
reason until a join lands. Scored shapes are proven on fixtures only
(hermetic tests).

## Honest shape (bands, NULL stays NULL)

| Param | Dim key | Joined slice | Scored shape | NULL when |
|---|---|---|---|---|
| P4-008 heat cap (demo) | `heat_price_cap` | per-address → KA cap record | kehtiv otsus + cap → 55 (January ceiling known, cap named); uus hind muutmisel → 40 (weak, ceiling moving); otsus/cap half-leg → 40 (weak, trace incomplete) | record missing/non-dict, or joined-but-empty (no company/area, no cap, no decision) |

Never 0 (the cap alone never prices a January bill — the operator
may charge below the cap and building consumption dominates) and
never 100 (partial coverage by construction — absence of a joined
record is not proof of expensive heat). P4-008 here scores cap
GROUNDEDNESS, not cheapness: ranking zones by €/MWh without
consumption data would be fake precision. Every scored reason says
`registriandmed, mitte hinnang` with the joined company/area/cap/
decision; every NULL reason says `EI OLE` and points at the
operator kaart check + KÜ January-bill check. The 55 sits one band
below heat's 60 on purpose: heat joins the operator's applied
tariff, the KA cap is only the ceiling (käibemaksuta).

## Judgment calls (for the reviewer)

1. Single dim, no coverage issue: the KA cap file feeds only P4-008
   source (3) — no second param extends this ingestion, so unlike
   heat (#261/#342) or tvesi (#263/#343) there is nothing to share
   a PR with.
2. Complement, not duplicate, of `dims_p4_heat.dim_heating_tariff`
   (#261, READ first per #262): heat scores the OPERATOR slice
   (operator + tariff_status bands 60/45, plus water_zone/
   return_bonus columns and the P4-036 roof_bonus); this dim scores
   the KA DECISION slice (company + decision_no + käibemaksuta cap
   + new-price columns, bands 55/40). Different dim key
   (`heat_price_cap` vs `heating_tariff`), different cache prefix
   (`konkurents-*.xlsx` vs `heat-*.csv`), different parse fields.
   The central hook joins one source per address later — one joint
   change.
3. Transcription, not direct XLSX parsing: the parser reads a
   semicolon CSV snapshot transcribed from the XLSX (tvesi hinnakiri
   precedent) so the suite stays stdlib-only and hermetic; the
   fetch proves the polite pull of the real XLSX bytes. Column
   mapping (Ettevõte → company, võrgupiirkond → network_area,
   piirhind → cap_eur_mwh, otsus nr → decision_no, kuupäev →
   decided, uue-hinna columns → new_*, seisuga → vintage) is stated
   in code, not hidden.
4. Pending uue-hind reads as 40, not 55: a ceiling in motion cannot
   ground a January budget. Half-legs (decision without number-cap
   or vice versa) read as 40, never NULL: the decision exists, the
   buyer can ask operator/KA for the number.
5. Joined-but-empty reads as NULL (not 40): a cap record carrying
   neither company/area nor cap nor decision proves coverage of
   nothing (heat precedent).
6. Unparseable caps read as None, never zero — zero would fake free
   heat. Negative caps read as None. Comma decimals parse (Estonian
   CSV convention). Company names are open-ended (never restricted
   to a token set).
7. No shared-file edits (livability.py, WEIGHTS, layers, layers.md,
   parameters4.md untouched): 3 new files only. Central hook
   (enrich join + WEIGHTS rebalance) stays one joint change across
   all batches.

## Reopening checklist (when a per-address feed appears)

1. Re-run the probes above; paste fresh evidence in the reopen PR.
2. Transcribe the new "seisuga" vintage into the cache dir; run it
   through `parse_konkurents_caps` + `index_by_cap` on fixtures
   first.
3. Recalibrate the 55/40 bands against the new cap spread (note
   otsus + kehtestatud + vintage in the snapshot).
4. Add the explicitly-flagged live integration test (not a unit run).
