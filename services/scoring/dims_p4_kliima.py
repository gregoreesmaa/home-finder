"""P4 kliima dims (issues #319 demo + #378 coverage).

Demo (#319): Tallinna kliimakava ingestion (P4-010) — polite,
cached, TTL-stated pulls of the kliimakava source plus an
honest-shape per-building dim end-to-end in Tallinn. Coverage
(#378): the remaining 1 param off the same source (P4-059),
wired to the demoed ingestion (no new plumbing needed, see
judgment calls).

Params (this module only — sibling batches own disjoint sets):
* P4-010 renovation-grant status + queue, kliimakava leg:
  renoveerimiseesmärgid per linnaosa (batch 1, demo in #319)
* P4-059 wood-burning restriction zones, kliimakava leg:
  heating-transition zones (batch 5, coverage in #378)

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict
per #319: the city publishes no pollable machine-readable feed for
either leg). Polite evidence, 7 requests total with a labelled
one-off user-agent, `--max-time 20/25`, single attempts, 2 s
pacing, raw bodies cached at /tmp/hf-kliima-probe/ (one-off PR
record, never committed):
* https://www.tallinn.ee/en/strateegia/climate-neutral-tallinn-tallinn-sustainable-energy-and-climate-action-plan-2030
  -> HTTP 200, 49 135 B, ~4 224 visible chars. Strategy
  storefront (SECAP 2030); keyword sweep 0 for csv / geojson /
  wfs / andmestik / masinloetav / download. Links out to the
  Estonian kliimakava page and two /et/media/ publications —
  no dataset link.
* https://www.tallinn.ee/et/strateegia/tallinna-kliimakava
  -> HTTP 200, 43 090 B, ~3 357 visible chars. "Tallinna
  pikaajalise kliimakava eesmärk on saavutada kliimaneutraalsus
  aastaks 2050" — human strategy page; sweep 0 for csv /
  geojson / wfs / andmestik / masinloetav. Only data-ish link
  is one more /et/media/ PDF.
* https://www.tallinn.ee/et/media/309750 -> HTTP 200 (HEAD),
  application/pdf — the SECAP 2030 publication itself (human
  document, not a feed).
* https://www.tallinn.ee/et/media/310541 -> HTTP 200 (HEAD),
  application/pdf — second kliimakava publication (human
  document, not a feed).
* https://andmed.eesti.ee/dataset?q=kliimakava -> HTTP 200,
  75 497 B, 12 visible characters ("Teabevärav" JS shell) — no
  server-rendered kliimakava dataset (same shell as the
  #264/#277/#284 national-portal checks).
* https://www.tallinn.ee/avaandmed/ -> HTTP 301 (162 B nginx)
  -> https://andmed.eesti.ee/datasets?ih=tallinna-linnavalitsus
  -> HTTP 200, 75 497 B, 12 visible characters — the city open-data
  route lands on the same Teabevärav JS shell (byte-identical
  size to the national-portal checks above).
So both dims return None for EVERY input including missing
origin: a linnaosa renovation-ambition band painted from a
one-off hand-read of the strategy PDFs would be fake precision
(OTA PR #131 precedent), and parsing the PDFs would be scraping
publications, not polling a feed — exactly the scraping this
repo refuses (AGENTS.md section 5). Reasons say "hinnang"
(estimate) and "EI OLE" and point at the concrete buyer-side
check (EIS register + KÜ enquiry for P4-010; EHR heating type +
Päästeamet chimney notices + Tallinna Keskkonnaamet notices for
P4-059) — never a faked area score.

Style mirrors services/scoring/dims_p4_kesk.py (#291/#364): every
scorer is pure and offline-tested — (origin, pois) ->
(Optional[int 0..100], Estonian reason). Network lives only in
livability.fetch_pois; this module adds no network calls, no
Overpass fragment, and no tag mapping: there is no honest snapshot
tag to query for a strategy document's district targets or
transition zones, so there is nothing for the live path to fetch.

This module needs no local helper copies: the dims take no join
record (no ingestion exists to join), so there is nothing to
normalise or index. When the verdict overturns, the overturn PR
adds the join-record helpers alongside the ingestion (EIS
#260/#341 precedent), not before.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share ONE PR and ONE module because the coverage
  body (#378) states it extends the demoed ingestion (#319): with
  the demo verdict dated-negative, there is no ingestion to extend,
  so the one coverage slice lands in the same verdict module
  rather than a second file importing a pipeline that does not
  exist (same precedent as kesk #291+#364, komun #290+#363,
  Elron #284+#358, TLT #277+#351, RB #281+#355).
* NO fetch/parse helpers are staged even though the strategy pages
  are open: unused ingestion would be fake progress (AGENTS.md
  7.2). The exact page/PDF URLs and sweep counts above plus
  docs/p4_kliima.md give the overturn PR everything needed to
  build the polite cached pull when a machine-readable
  linnaosa-target table or transition-zone layer appears.
* Pairing rationale (each param names the kliimakava in its
  parameters4.md source list, and each kliimakava leg complements
  — never duplicates — the sibling leg that scores): P4-010 the
  "Tallinna kliimakava renoveerimiseesmärgid per linnaosa" leg
  (source 6 of 6) — the grant/queue register itself stays scored
  in dims_p4_eis (EIS slice, #260/#341), the energy-class mirror
  in dims_p4_ehr, the KÜ-toetused leg NULL in dims_p4_komun; this
  dim scores ONLY the district-target pressure and stays NULL
  until a target table exists. P4-059 the "Tallinna kliimakava
  heating-transition zones" leg (source 5 of 6) — the enforceable
  rule join stays scored in dims_p4_paaste (burn_restriction),
  the monitoring cross-check in dims_p4_kaur, the Keskkonnaamet
  notices leg NULL in dims_p4_kesk, the restriction-notice leg
  NULL in dims_p4_komun; this dim scores ONLY the transition-zone
  table and stays NULL until a zone layer exists. Re-scoring a
  cousin leg here would claim the full param on a partial signal
  (same split-slice precedent as P4-020: ATA notices in
  dims_p4_ata, bureau scores NULL in dims_p4_creditinfo).
* The openness check stopped at page + header level on purpose —
  no PDF body download (HEAD only), no Teabevärav JS-app driving,
  no gis.tallinn.ee viewer enumeration (map-app scraping, which
  this repo refuses — same stop-at-shell precedent as komun
  #290 and TLT #277).
* TTL: one-off check 2026-09-13 (no ingestion cached, nothing
  consumed). Re-check annually or when a machine-readable
  kliimakava table appears (linnaosa-target CSV, transition-zone
  WFS/GeoJSON, or a Teabevärav dataset); the strategy pages carry
  no refresh date (SECAP horizon 2030, neutrality 2050).

Integration (deliberately NOT done here): these dims need no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-010/P4-059: documented no-map kliimakava-leg NULLs (OTA PR #131
# precedent). The kliimakava publishes as human strategy pages plus
# PDF publications — no per-linnaosa renovation-target table, no
# heating-transition zone layer as data. Each scorer reports the gap
# with a concrete buyer-side check instead of a faked number; the
# sibling legs that DO score stay named so the NULL is actionable.
# ---------------------------------------------------------------------------

def dim_renovation_targets(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]]) -> Score:
    """P4-010: NULL — kliimakava linnaosa-target leg needs the table (no map)."""
    return None, ("Kliimakava renoveerimiseesmärkide linnaosa-hinnang "
                  "(EI OLE masinloetavat eesmärgitabelit): Tallinna "
                  "kliimakava elab inimloetavate strateegialehte de ja "
                  "PDF-väljaannetena, hoone toetuse staatust ega "
                  "järjekorda neist ei loe — hoone kirje on EIS "
                  "renoveerimistoetuste registris (EIS/KÜ päring, "
                  "mitte hinnang); linnaosa skoori ära feigi")


def dim_heating_zones(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """P4-059: NULL — kliimakava heating-transition leg needs the layer (no map)."""
    return None, ("Kliimakava kütte-ülemineku tsoonide reegli-hinnang "
                  "(EI OLE masinloetavat tsoonikihti): "
                  "strateegiadokumendid ei paku krundipõhist "
                  "üleminekutsoonide voogu — kontrolli EHR kütte liiki "
                  "(ahju/kamina vara), Päästeameti korstnateateid ja "
                  "Tallinna Keskkonnaameti tahkekütte teateid; "
                  "kehtivat reeglit hindab Päästeameti reegli-liides, "
                  "ära feigi")


P4_KLIIMA_DIMS = (
    ("kliima_renovation_targets", "P4-010", dim_renovation_targets),
    ("kliima_heating_zones", "P4-059", dim_heating_zones),
)


def score_p4_kliima(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """Both P4 kliima dims for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_KLIIMA_DIMS). Every value
    is None by design — strategy-document legs, never a faked area
    score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_KLIIMA_DIMS}
