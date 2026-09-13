"""Overturn re-check for G6 muinas-register designations (issue #237).

Scope: the G6 no-map set p158/p272/p320/p351/p354/p355/p359/p360
(parameters3.md section 5.6, Group 6). p72/p352/p353/p356 already
ship via dims_group06.py (#138) / dims_group06b.py (#139) -- READ
first, untouched here, as is dims_p4_muinsus.py (#324/#380: the
P4-005 heritage-permit and P4-041 corridor slices, a different
question family from these G6 district/craft/friction params).

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict:
the register has no pollable designation dump, so all eight dims
stay NULL). Polite evidence, 2 single GETs + 2 DNS lookups total
(labelled one-off user-agent, >= 20 s pacing, `--max-time 25`,
headers + visible-text scope read only, no scraping, no auth; the
second GET is a spaced down-confirmation, not a retry dare -- HTTP
429/520 is a stop signal), raw bodies cached at /tmp/hf-muinas-237/
(one-off PR record, never committed):
* https://register.muinas.ee/ -> HTTP 520 ("error code: 520",
  16 bytes), twice, ~22 s apart: the moved register's origin is
  down. DNS resolves (proxy answers) -- a 520ing page cannot be
  polled, let alone joined. Transport error, never data.
* register.muinsuskaitseamet.ee -> DNS NXDOMAIN (nslookup): the
  parameters3 Group 6 documented registry hostname is still dead.

So every scorer below returns None for EVERY input including
missing origin: a per-building designation hand-read from a down
register would be fake precision (OTA PR #131 precedent), and a
gradient painted from mapped-heritage density would re-skin p72
under eight new names. Reasons say "hinnang" (estimate) and
"EI OLE" and point at the concrete buyer-side check -- never a
faked per-building fact.

Honest shapes when the register answers (per-building join, never
a gradient -- a designation is a per-building decree, nomap.md
section 3 G6): DESIGNATION_GRADUABLE params (p158/p320/p355/p360)
graduate to per-building procedure/designation dims fed ONLY by
lookup_muinas on a cached dump; DESIGNATION_NEVER params
(p272/p351/p354/p359) stay NULL permanently -- their questions
need a different record (kataster easement, window survey,
geotechnical survey, lab result) that no designation dump holds.
The parse/index/lookup helpers below are the pinned join path:
pure, hermetic, fixture-tested, waiting for a dump.

Style mirrors services/scoring/dims_overturn_p317.py (#240, the
closest sibling: same dated-negative NULL shape): every scorer is
pure and offline-tested -- (origin, pois) ->
(Optional[int 0..100], Estonian reason). Network lives only in
livability.fetch_pois; this module adds no network calls, no
Overpass fragment, and no tag mapping: there is no honest snapshot
tag for registry designations, so there is nothing for the live
path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Dated negative, not a stub farm: the eight dims duplicate the
  group06/06b None-stubs' questions on purpose -- the stubs say
  "no honest signal", these dims say "the named dump was probed
  on this date and answered 520/NXDOMAIN, re-probe by
  RECHECK_AFTER". Same verdict, dated evidence.
* p320/p355 keep their OSM heuristic scorers in dims_group06.py /
  dims_group06b.py (untouched, still scoring); these overturn dims
  are the registry-truth procedure slices, NULL until joined.
  Inverse-density heuristics predict review likelihood; only a
  joined designation states it.
* Fixture shape is synthetic and labelled so: {"building_ref",
  "designation", "register_id"}. Real-dump column mapping happens
  in the reopen PR -- the fixture pins the JOIN contract (exact
  match, first wins, unknown class never joins), not the
  register's schema, which a 520ing origin cannot show us.
* The Maa-amet mka:ehitis/mka:kaitsevoond mirror stays a
  reopening lead, not a silent substitution (same line as
  docs/p4_muinsus.md): no WFS crawl was run -- entry-level
  probing only, deeper harvesting is the scraping this repo
  refuses (AGENTS.md section 5).
* No shared-file edits (dims_group06*.py, dims_p4_muinsus.py,
  livability.py, WEIGHTS, layers, nomap.md untouched): 3 new
  files only. The final docs-index PR updates nomap.md.

Integration (deliberately NOT done here): these dims need no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change - existing tests pin
set(WEIGHTS) exactly, so per-issue WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, Iterable, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Verdict date (2026-09-13) -- the day the polite probes above ran.
VERDICT_DATE = "2026-09-13"

#: Re-probe register.muinas.ee no later than this date (quarterly
#: down-register cadence per docs/p4_muinsus.md reopening checklist).
RECHECK_AFTER = "2026-12-13"

#: Designation classes a joined dump may state (terms grounded in
#: docs/p4_muinsus.md: listed monument, kaitsevoond, milieu-value
#: area). Unknown classes never join (fail closed).
DESIGNATION_CLASSES = ("mälestis", "kaitsevöönd", "miljööala")

#: Params whose question a designation dump CAN answer once joined
#: (per-building procedure/designation dims -- still never a map
#: gradient: a decree is not a field).
DESIGNATION_GRADUABLE = ("p158", "p320", "p355", "p360")

#: Params whose question no designation dump can answer (wrong
#: record type by construction -- stay NULL permanently).
DESIGNATION_NEVER = ("p272", "p351", "p354", "p359")


# ---------------------------------------------------------------------------
# Per-building designation join (pure, hermetic, fixture-tested).
# Today the index is always empty (no dump: 520/NXDOMAIN above); the
# helpers pin the contract the reopen PR feeds with a cached dump.
# ---------------------------------------------------------------------------

def parse_muinas_row(row: object) -> Optional[dict]:
    """Normalize one raw designation-dump row to a joinable record.

    Fixture shape (synthetic, see module docstring): {"building_ref":
    str, "designation": one of DESIGNATION_CLASSES, "register_id":
    str | None}. Returns None for anything unjoinable -- missing or
    blank building ref, unknown designation class -- so a dirty dump
    can never fake a per-building fact.
    """
    if not isinstance(row, dict):
        return None
    ref = row.get("building_ref")
    if not isinstance(ref, str) or not ref.strip():
        return None
    designation = row.get("designation")
    if designation not in DESIGNATION_CLASSES:
        return None
    register_id = row.get("register_id")
    if register_id is not None and not isinstance(register_id, str):
        return None
    return {"building_ref": ref.strip(), "designation": designation,
            "register_id": register_id}


def build_muinas_index(rows: Iterable[dict]) -> Dict[str, dict]:
    """Index parsed designation records by building ref (first wins).

    Unparseable rows are skipped, never coerced: a dump gap stays a
    gap (NULL with register reason downstream), not a guess.
    """
    index: Dict[str, dict] = {}
    for row in rows or []:
        parsed = parse_muinas_row(row)
        if parsed is not None and parsed["building_ref"] not in index:
            index[parsed["building_ref"]] = parsed
    return index


def lookup_muinas(building_ref: object,
                  index: Optional[Dict[str, dict]]) -> Optional[dict]:
    """Exact-match designation lookup for one building ref.

    Returns the joined record, or None where unresolvable (unknown
    building, empty dump, blank ref): NULL-with-register-reason
    downstream, never a neighbouring building's decree.
    """
    if not isinstance(building_ref, str) or not building_ref.strip():
        return None
    if not index:
        return None
    return index.get(building_ref.strip())


# ---------------------------------------------------------------------------
# p158/p272/p320/p351/p354/p355/p359/p360: documented no-dump
# designation NULLs (OTA PR #131 precedent). Each scorer reports the
# gap with the concrete buyer-side check instead of a faked number.
# ---------------------------------------------------------------------------

def dim_tax_credits_muinas(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]]) -> Score:
    """p158: NULL -- EUR tax-credit needs the register (no dump)."""
    _ = (origin, pois)
    return None, ("Ajaloolise hoone maksusoodustuse (EUR) hinnangut EI OLE "
                  "võimalik anda -- kultuurimälestiste registri "
                  "masinloetav väljavõte puudub (register.muinas.ee "
                  "vastab veaga HTTP 520, dokumenteeritud "
                  "register.muinsuskaitseamet.ee on surnud/NXDOMAIN, "
                  "kontrollitud 2026-09-13): kas hoone on soodustuse "
                  "aluseks olev mälestis, küsi Muinsuskaitseameti "
                  "registri uksest ja maksu-nõustajalt/EMTA-st, ära feigi "
                  "olematut eurosummat (puuduv väärtus katkestab tehingu "
                  "skoori)")


def dim_facade_easements_muinas(origin: Optional[Tuple[float, float]],
                                pois: Optional[List[dict]]) -> Score:
    """p272: NULL -- easements are parcel-legal facts (no dump helps)."""
    _ = (origin, pois)
    return None, ("Fassaadi servituudi hinnangut EI OLE võimalik anda -- "
                  "servituut on katastriseaduslik fakt, mida ükski "
                  "mälestiste-nimekiri ei tõesta (register.muinas.ee "
                  "vastab veaga HTTP 520, kontrollitud 2026-09-13): küsi "
                  "kinnistusraamatu väljavõtet ja katastri servituudi "
                  "päringut, ära feigi -- lähedane mälestis ei tõesta "
                  "servituuti")


def dim_commission_muinas(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """p320: NULL -- commission procedure needs the joined dump."""
    _ = (origin, pois)
    return None, ("Muinsuskomisjoni menetlusvajaduse hinnangut EI OLE "
                  "võimalik registrist anda -- hoone-põhine "
                  "mälestis/kaitsevööndi liide puudub "
                  "(register.muinas.ee vastab veaga HTTP 520, "
                  "kontrollitud 2026-09-13): kas renoveerimine vajab "
                  "Muinsuskaitseameti/KOV kooskõlastust, küsi ametist ja "
                  "KOV miljööalade plaanidest, ära feigi -- "
                  "tihedusheuristik elab dims_group06-s, registriotsus "
                  "puudub")


def dim_leadglass_muinas(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p351: NULL -- windows are component-level (no dump surveys them)."""
    _ = (origin, pois)
    return None, ("Pliiklaas-akende säilivuse hinnangut EI OLE võimalik "
                  "anda -- ükski mälestiste-nimekiri ei kirjelda akende "
                  "olukorda (register.muinas.ee vastab veaga HTTP 520, "
                  "kontrollitud 2026-09-13): telli kohapealne akende "
                  "ülevaatus, ära feigi -- mälestise staatus ei tõesta "
                  "akende seisukorda")


def dim_settling_muinas(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """p354: NULL -- settling is geotechnical (no dump measures it)."""
    _ = (origin, pois)
    return None, ("Pärandhoone vundamendi vajumise hinnangut EI OLE "
                  "võimalik anda -- vajumine on geotehniline fakt "
                  "(pinnas/vesi), mida registrikanne ei mõõda "
                  "(register.muinas.ee vastab veaga HTTP 520, "
                  "kontrollitud 2026-09-13): telli geotehniline "
                  "ekspertiis/uuring, ära feigi")


def dim_society_muinas(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p355: NULL -- society friction needs the joined dump."""
    _ = (origin, pois)
    return None, ("Seltsiliikumise kooskõlastusvajaduse hinnangut EI OLE "
                  "võimalik registrist anda -- hoone-põhine "
                  "mälestis/miljööala liide puudub (register.muinas.ee "
                  "vastab veaga HTTP 520, kontrollitud 2026-09-13): küsi "
                  "Muinsuskaitseametist ja kohalikust seltsist, ära feigi "
                  "-- tihedusheuristik elab dims_group06b-s, seltsiotsus "
                  "puudub")


def dim_asbestos_muinas(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """p359: NULL -- asbestos needs a lab (no dump tests it)."""
    _ = (origin, pois)
    return None, ("Asbestkatte eluea hinnangut EI OLE võimalik anda -- "
                  "asbesti tuvastab ainult laboriproov, mida ükski "
                  "mälestiste-nimekiri ei sisalda (register.muinas.ee "
                  "vastab veaga HTTP 520, kontrollitud 2026-09-13): telli "
                  "laboriuuring, ära feigi -- kaardistamata ei tähenda "
                  "puudub")


def dim_provenance_muinas(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """p360: NULL -- provenance chain needs the joined archive."""
    _ = (origin, pois)
    return None, ("Kinnistu päritoluahela hinnangut EI OLE võimalik anda "
                  "-- ahel elab arhiivikannetes, mille masinloetav liide "
                  "puudub (register.muinas.ee vastab veaga HTTP 520, "
                  "kontrollitud 2026-09-13): küsi kinnistusraamatu "
                  "väljavõtet ja registri arhiivi-päringut, ära feigi -- "
                  "ehitusaasta ei ole päritolutõend")


#: Registry for the central weight-rebalance follow-up: (dims key, param id, fn).
MUINAS_OVERTURN_DIMS = (
    ("tax_credits_muinas", "p158", dim_tax_credits_muinas),
    ("facade_easements_muinas", "p272", dim_facade_easements_muinas),
    ("commission_muinas", "p320", dim_commission_muinas),
    ("leadglass_muinas", "p351", dim_leadglass_muinas),
    ("settling_muinas", "p354", dim_settling_muinas),
    ("society_muinas", "p355", dim_society_muinas),
    ("asbestos_muinas", "p359", dim_asbestos_muinas),
    ("provenance_muinas", "p360", dim_provenance_muinas),
)


def score_overturn_muinas(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """The eight G6 muinas overturn-check dims for one listing (entry
    point for the weight-rebalance follow-up; keys match
    MUINAS_OVERTURN_DIMS)."""
    return {key: fn(origin, pois)[0] for key, _, fn in MUINAS_OVERTURN_DIMS}
