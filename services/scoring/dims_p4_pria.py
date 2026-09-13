"""P4 PRIA field-block dims (issue #299, single-param demo, no coverage issue).

Demo (#299): PRIA põllumassiivid (field blocks) for P4-024 end-to-end
in Tallinn — openness verification plus the honest-shape spray-drift
leg. Single param: P4-024 Country-health nuisances, PRIA slice
(source (3), batch 2: Harku/Lasnamäe fringe spray-drift buffers).
Honest shape when a feed lands: coarse hinnang cells, never
per-parcel precision.

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict
per #299): no anonymous per-parcel bulk URL for the field blocks was
verified, so there is no polite pull to cache and no honest join to
score. Polite evidence, 8 served requests total (single GETs with a
labelled one-off user-agent, headers + visible-text keyword scope
read only, no scraping, no auth, no form driving, redirects not
spidered beyond the single canonical documented link), raw bodies
cached at /tmp/hf-pria-probe/ (one-off PR record, never committed):
* https://www.pria.ee/ -> HTTP 200, 146 074 B, title "PRIA". Portal
  front; links the /avaandmed page, the /registrid/pria-kaardiandmed
  page and the https://kls.pria.ee/kaart/ map (visible-text sweep:
  avaandmed x1, põllumassiiv x3, kaart x4; no WMS/WFS/API/CSV/JSON
  machine pointers on the landing itself).
* https://kaart.pria.ee/ -> DNS failure (host does not resolve).
  Stale guess, documented as tried — the live map lives at
  kls.pria.ee (see below).
* https://andmed.eesti.ee/dataset?q=pria -> HTTP 200, 75 497 B,
  title "Teabevärav". JS app shell, 12 visible characters, no
  server-rendered results (same shell as the #264/#277/#284
  checks) — no trivially pollable national-portal PRIA dataset.
* https://www.pria.ee/avaandmed -> HTTP 200, 72 856 B, title
  "Avaandmed | PRIA" (page vintage: added 27.12.2019, changed
  30.03.2021). Open data is "public data free for use, available
  from the web", consolidated in the national portal — no direct
  bulk link on the page itself.
* https://www.pria.ee/registrid/pria-kaardiandmed -> HTTP 200,
  78 599 B, title "PRIA kaardiandmed | PRIA" (changed 12.03.2026).
  The key page: the public web map shows ONLY field blocks with
  area-support claims in the last two years, and the pindalatoetuste
  + livestock-building spatial data is "kättesaadavad Andmete
  teabeväravast" in ESRI SHP / MapInfo TAB / MS Excel (2007) / CSV,
  "uuendamise sagedus: igapäevaselt". A documented bulk claim —
  but the claim points at the Teabevärav catalogue, not at a
  server-rendered file URL (see below).
* https://kls.pria.ee/kaart/ -> HTTP 200, 54 913 B, title "PRIA
  Veebikaart" (app v26.9.0, base map (c) Maa- ja Ruumiamet).
  Interactive map app: layer list (Põllumassiivid, loomaregistri
  tegevuskohad, pärandniidud, katastriüksused), 11-digit-number and
  address search. Verbatim: "Veebikaardil on nähtavad kahel
  viimasel aastal pindalatoetuste taotlustel märgitud
  põllumassiivid." An interactive lookup UI, not a bulk feed —
  driving its search/AJAX would be scraping a human publication,
  not polling a feed (AGENTS.md section 5).
* https://avaandmed.eesti.ee/information-holders/... (the holder
  link the kaardiandmed page documents) -> HTTP 301 to the
  canonical andmed.eesti.ee host (single documented-link follow,
  polite stop otherwise).
* Canonical holder page -> HTTP 200, 75 497 B, JS "Teabevärav"
  shell, 12 visible characters, zero hits for põllumassiiv /
  ruumiandmed / SHP / CSV / WMS / WFS. No server-rendered
  dataset or bulk-download URL to poll politely.
So the single dim returns None for EVERY input including missing
origin: a spray-drift buffer painted without the field-block bulk
(or from one interactive lookup) would be fake precision (OTA PR
#131 precedent). Reasons say "hinnang" (estimate) and "EI OLE"
and point at the concrete buyer-side checks (kohapealne vaatlus:
pritsimisriba / roheline serv / farmilõhn; küsi KÜ-lt/naabritelt
pritsimisgraafikut) — never a faked per-parcel score.

SIBLING OVERLAP (read first, not edited): the other P4-024 legs
stay where they live and are named here, never re-scored — the
Keskkonnaagentuur õietolmu slice (dims_p4_kaur dim_tervis_kaur,
SCORED pollen bands), the EELIS rohevõrgustik habitat-proxy slice
(dims_p4_eelis dim_maaloodus_eelis, SCORED coarse cells), the
Terviseamet tick-stat + suplusvee slice (dims_p4_tervise
dim_country_health_nuisances, NULL: county-grain PDFs + seasonal
PDFs, no machine feed) and the Kommunaalamet farm-odour-kaebuste
slice (dims_p4_komun dim_farm_odour_cells, NULL: no complaint
register). This module owns ONLY the PRIA põllumassiiv leg
(Tallinn-fringe spray-drift buffers), which has no verified
anonymous bulk — hence NULL.

Style mirrors services/scoring/dims_p4_opencellid.py (#269, the
dated-negative single-param precedent): the scorer is pure and
offline-tested — (origin, pois) -> (Optional[int 0..100],
Estonian reason). Network lives only in livability.fetch_pois;
this module adds no network calls, no Overpass fragment, and no
tag mapping: there is no honest snapshot tag to query for
field-block buffers, so there is nothing for the live path to
fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Single-param demo, no coverage issue: #299 states the remaining
  0 params using this source need only a follow-up created after
  this demo — with a dated-negative demo there is no ingestion to
  extend, so there is nothing to split out. One dim, one module,
  three new files, no shared-file edits.
* No ingestion to cache and no TTL to state beyond this one-off
  check (opencellid #269 / rik #252 precedent): re-probe yearly,
  or sooner if the Teabevärav holder catalogue server-renders a
  põllumassiiv bulk URL. PRIA's own stated cadence
  ("uuendamise sagedus: igapäevaselt") is recorded here as the
  future-ingestion TTL anchor — a daily re-pull ticket IF a
  pollable bulk appears — not as a pull performed today.
* The check stopped at storefront/page level on purpose: no
  kls.pria.ee search driving, no AJAX walking, no Teabevärav
  JS-app driving. Driving a query UI parcel-by-parcel would be
  scraping human publications, not polling a feed — exactly what
  this repo refuses (AGENTS.md section 5; tervise #289 precedent).
* Honest future shape (stated, not scored): coarse Tallinn-fringe
  hinnang cells off joined field-block polygons (spray-drift
  buffer bands, e.g. block-adjacent vs 100 m+ clear; never 0/100
  on this leg alone — drift hints at caution for kids/dogs, never
  a guarantee; per-parcel doorway precision stays unscored even
  then). Today every reason says EI OLE and names the veebikaart
  + Teabevärav gap plus the kohapealne-vaatlus checks.

Integration (deliberately NOT done here): this dim needs no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-024: documented no-map PRIA field-block NULL (OTA PR #131
# precedent). Tallinn-fringe spray-drift buffers need the anonymous
# põllumassiiv bulk — the kaardiandmed page documents SHP/CSV via
# Teabevärav, but the holder catalogue is a JS shell with no
# server-rendered bulk URL and the veebikaart is an interactive
# last-two-years lookup — so the scorer reports the gap with the
# concrete buyer-side checks instead of a faked number.
# ---------------------------------------------------------------------------

def dim_pollupuhver_pria(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """P4-024: NULL — PRIA põllumassiivide puhver on sulgemata voog."""
    return None, ("Põllupõhine pritsimispuhver PRIA-st (Tallinna-äärne jäme "
                  "hinnangurakk, tulevikukujus päevase TTL-iga SHP/CSV-tõmmise "
                  "pealt) on masinloetava hulgiliideseta hinnang (EI OLE "
                  "põllumassiivide hulgitõmmet): kls.pria.ee veebikaart on "
                  "interaktiivne otsing, mis näitab ainult kahel viimasel "
                  "aastal pindalatoetust saanud blokke, ja Teabevärava "
                  "holder-kataloog on JS-kest ilma serveris renditud "
                  "allalaadimis-URL-ita — puhverdatavat avatud voogu pole, "
                  "vaata kohapealsel vaatlusel pritsimisriba / rohelist "
                  "serva / farmilõhna ning küsi KÜ-lt ja naabritelt "
                  "pritsimisgraafikut, võrdle õietolmu-legi dims_p4_kaur-ist "
                  "(dim_tervis_kaur) ja elupaiga-legi dims_p4_eelis-ist "
                  "(dim_maaloodus_eelis) ning puugi/suplusvee-legi "
                  "dims_p4_tervise-st (dim_country_health_nuisances) ja "
                  "farmilõhna-legi dims_p4_komun-ist "
                  "(dim_farm_odour_cells), ära feigi")


P4_PRIA_DIMS = (
    ("pollupuhver_pria", "P4-024", dim_pollupuhver_pria),
)


def score_p4_pria(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """The P4 PRIA dim for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_PRIA_DIMS). The value
    is None by design — unverified field-block bulk, never a faked
    spray-drift score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_PRIA_DIMS}
