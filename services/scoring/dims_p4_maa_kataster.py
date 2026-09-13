"""P4 Maa-amet kataster + KKIS kitsendused dims: demo (#245) + coverage (#329).

Demo param (this ingestion's anchor):
* P4-004 Kinnistusregistri süva + notary checkpoint -> dim_kinnistus_syva

Coverage params (extend the demoed ingestion, no new plumbing):
* P4-006 Neighbouring detailplaneering pipeline (500 m) -> dim_naaber_planeering
* P4-013 Parking regime + courtyard ratio -> dim_parkimine_hoov
* P4-020 Enforcement: pankrot/täitemenetlus -> dim_enforcement

OPENNESS VERDICT (probed 2026-09-13, single polite fetches, cached /tmp,
3 s pacing, contact UA in headers — full evidence in docs/p4_maa_kataster.md):
* Maa-amet kataster public map apps (Maainfo / Kitsendused listings +
  descriptions on geoportaal.maaamet.ee): OPEN (HTTP 200).
* KKIS public viewer (kitsendused.kataster.ee, "Kitsenduste infosüsteem"):
  OPEN (HTTP 200) — BUT the public layer is generalised: cat I/II
  kaitseobjekte ei näidata avalikus rakenduses, and full per-parcel
  restrictions need an owner-role login. DATED PARTIAL-NEGATIVE for bulk
  per-parcel restriction detail: parcel geometry + generalised restriction
  presence is an honest join, hidden detail stays NULL.
* RIK e-Kinnistusraamat per-parcel depth (keelumärge/hüpoteek detail):
  tasuline / access-controlled — DATED NEGATIVE for open bulk. Hence the
  P4-004 weak-good cap: even a clean public layer never scores above 70.
* TPR (tpr.tallinn.ee): OPEN (HTTP 200, JS-shell SPA). Ametlikud
  Teadaanded: OPEN (HTTP 200, public search + "Andmete taaskasutamine").
* Tallinna tasulise parkimise deep URL (guessed): 404 — DATED NEGATIVE
  for that URL only (the Parkimine section exists; zone polygons come from
  the live määrus lookup, never from the guessed link).

HONESTY (AGENTS.md section 7.2): every shape here is a PER-PARCEL JOIN
off the kataster parcel (katastritunnus) — never a distance gradient,
never interpolation, never a heat-coloured guess. Missing parcel, missing
snapshot, or owner-login-only detail stays NULL ("EI OLE") with an
Estonian reason naming the concrete check (Maainfo/KKIS päring,
notariaalne kontroll, TPR snapshot, parkimise määrus, AT otsing) — never
a faked number. Transport errors in fetch_cached are NEVER cached as
data, and HTTP 429 is a stop signal, not a retry dare (AGENTS.md 7.2/7.4).

Style: pure offline scorers (parcel, plans, ...) -> (Optional[int 0..100],
Estonian reason), mirroring dims_p4_maa_tehingud.py (#244/#328). Network
lives ONLY in fetch_cached (polite single-GET + file cache + TTL); tests
never touch the network. No livability/WEIGHTS/layers integration here —
rebalancing stays one joint change across batches (existing tests pin
WEIGHTS). No dims_group03*.py or other shared/group file is touched:
P4 params live in this file only (#235 owns the G3 WFS verdicts
separately).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage paired in ONE PR because issue #329's body states it
  extends the #245 demo ingestion ("no new plumbing expected") — the same
  pairing rationale as the P4-002/#328 precedent (PR #384).
* P4-004 weak-good cap = 70: a clean PUBLIC layer cannot prove a clean
  register (RIK extract tasuline, owner-login detail hidden), so 70 is
  the ceiling; blocking flags (arest/keelumärge) score 25, a lone
  hüpoteek 55 (routine notary clearance, not a block).
* P4-006 scores the snapshot, dated: "no menetluses plans in 500 m in
  the TPR snapshot" is honestly good (70), never "no plans exist".
  Algatatud counts as pipeline alongside menetluses; kehtestatud nearby
  is context (65), not risk.
* P4-013 needs the zone leg to score: the tasuline tsoon is the regime,
  courtyard ratio only adjusts it. Zone unknown -> NULL even when the
  courtyard is known (documented, not smoothed).
* P4-020 weak-good cap = 70 like P4-004: public AT/kohtutäitur notices
  checked, commercial scores (Creditinfo) and unpublished detail named
  missing, never faked.
"""

import datetime as _dt
import os
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion: polite fetch + cache + TTL (demo #245 acceptance criterion 2).
# ---------------------------------------------------------------------------

SOURCE_URLS = {
    # Open public map-app listings + descriptions (probed 2026-09-13).
    "kataster_apps": (
        "https://geoportaal.maaamet.ee/est/kaardirakendused-p2.html"
    ),
    "kkis_viewer": "https://kitsendused.kataster.ee/",
    # Open notice / planning registers feeding coverage params.
    "tpr": "https://tpr.tallinn.ee/",
    "ametlikud_teadaanded": "https://www.ametlikudteadaanded.ee/",
}

# TTLs in days. Kataster geometry changes slowly (quarterly); KKIS
# restrictions publish monthly-ish; TPR stages move weekly; parking zones
# change only by regulation (annual re-check); AT notices publish daily
# (polite weekly pull).
TTL_DAYS = {
    "kataster_geometry": 91,
    "kkis_restrictions": 30,
    "tpr_pipeline": 7,
    "parking_zones": 365,
    "at_notices": 7,
}

CACHE_SUBDIR = "hf-p4-maa-kataster"
USER_AGENT = (
    "home-finder-research/0.1 (polite kataster/KKIS harvest; "
    "GitHub gregoreesmaa/home-finder issue 245)"
)

# Restriction kinds that can freeze a closing (normalised lowercase).
BLOCKING_LIIKID = frozenset({
    "arest", "arestimine", "keelumärge", "keelumarge",
})
# Routine encumbrance cleared at the notary table, not a block.
HYPOTHEEK_LIIKID = frozenset({"hüpoteek", "hypoteek"})

PIPELINE_STAGES = frozenset({"menetluses", "algatatud"})
BUFFER_M = 500.0  # P4-006 neighbouring-plan buffer per parameters4.md

WEAK_GOOD_CAP = 70  # ceiling while register depth needs paid/owner access


def cache_path(cache_dir: str, name: str) -> str:
    """Cache file location for a named fetch (flat files, no dumps committed)."""
    return os.path.join(cache_dir, CACHE_SUBDIR, name)


def is_fresh(path: str, ttl_days: int,
             now: Optional[_dt.datetime] = None) -> bool:
    """True when a cached file exists and is younger than ttl_days."""
    try:
        mtime = _dt.datetime.fromtimestamp(
            os.path.getmtime(path), tz=_dt.timezone.utc)
    except OSError:
        return False
    at = now or _dt.datetime.now(tz=_dt.timezone.utc)
    return (at - mtime) <= _dt.timedelta(days=ttl_days)


def fetch_cached(url: str, cache_dir: str, name: str, ttl_days: int,
                 timeout_s: int = 25) -> str:
    """Polite single-GET with file cache. Returns the cache path.

    Fresh cache wins (no request). Transport errors are raised and NEVER
    written as data; HTTP 429 raises immediately (stop signal, no retry).
    Pulls urllib only (no new dependency).
    """
    import urllib.request

    dest = cache_path(cache_dir, name)
    if is_fresh(dest, ttl_days):
        return dest
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            if resp.status == 429:
                raise RuntimeError("HTTP 429 — stop, do not retry: " + url)
            body = resp.read()
    except Exception:
        raise
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    with open(tmp, "wb") as fh:
        fh.write(body)
    os.replace(tmp, dest)
    return dest


# ---------------------------------------------------------------------------
# Pure helpers (per-parcel join core — hermetically tested).
# ---------------------------------------------------------------------------

def normalise_liik(raw: Optional[str]) -> Optional[str]:
    """Lowercase + collapse whitespace for restriction-kind matching."""
    if raw is None:
        return None
    key = " ".join(str(raw).strip().lower().split())
    return key or None


def _clamp(score: float) -> int:
    return max(0, min(100, int(round(score))))


def parcel_id(parcel: Optional[dict]) -> Optional[str]:
    """Katastritunnus when the parcel join is honest, else None."""
    if not isinstance(parcel, dict):
        return None
    kid = parcel.get("katastritunnus")
    if kid is None:
        return None
    key = " ".join(str(kid).strip().split())
    return key or None


def split_restrictions(parcel: dict) -> Tuple[List[str], List[str], List[str]]:
    """(blocking, hypotheek, other) restriction-kind labels from a parcel.

    Reads parcel["kitsendused"] — a list of {"liik": ...} rows from the
    KKIS/kataster join. Unknown shapes are ignored (never crash the join).
    """
    blocking, hypo, other = [], [], []
    rows = parcel.get("kitsendused")
    if not isinstance(rows, list):
        return blocking, hypo, other
    for row in rows:
        if not isinstance(row, dict):
            continue
        liik = normalise_liik(row.get("liik"))
        if not liik:
            continue
        label = str(row.get("liik")).strip()
        if liik in BLOCKING_LIIKID:
            blocking.append(label)
        elif liik in HYPOTHEEK_LIIKID:
            hypo.append(label)
        else:
            other.append(label)
    return blocking, hypo, other


# ---------------------------------------------------------------------------
# Demo dim: P4-004 kinnistus süva + notary checkpoint (issue #245).
# ---------------------------------------------------------------------------

def dim_kinnistus_syva(parcel: Optional[dict]) -> Score:
    """P4-004: closing-readiness checkpoint from the parcel restriction join.

    Blocking KKIS flags (arest/keelumärge) -> 25 with a notary checkpoint;
    a lone hüpoteek -> 55 (routine clearance); a clean public layer ->
    WEAK_GOOD_CAP (the RIK paid extract + owner-login detail is unchecked,
    so the score is capped, never "clean"). NULL when there is no parcel
    join or no restriction snapshot at all.
    """
    kid = parcel_id(parcel)
    if kid is None:
        return None, ("Katastritunnust EI OLE (hinnang puudub): kinnistus-süva "
                      "vajab katastriüksuse join'i — tee Maainfo/KKIS päring "
                      "aadressi järgi, ära feigi")
    assert isinstance(parcel, dict)
    if parcel.get("kitsendused") is None:
        return None, ("Katastriüksuse %s kitsendusandmeid avalikus kihis EI "
                      "OLE (hinnang puudub): täisdetail vajab omaniku-rolli "
                      "sisselogimist kitsendused.kataster.ee-s või notari "
                      "päringut — küsi notarilt, ära feigi" % kid)
    blocking, hypo, other = split_restrictions(parcel)
    if blocking:
        return 25, ("Katastriüksusel %s sulgemist takistav kitsendus avalikus "
                    "kihis: %s — tehingu valmiduse hinnang 25/100: notari "
                    "kontrollkohustus (keelumärge/arest tuleb kustutada enne "
                    "sulgemist; RIK tasulise väljavõtte detaili EI OLE)"
                    % (kid, ", ".join(blocking)))
    if hypo:
        return 55, ("Katastriüksusel %s hüpoteek avalikus kihis (%s): "
                    "sulgemise hinnang 55/100 — rutiinne notariaalne "
                    "kustutamine tehingupäeval; keelumärget/aresti EI OLE "
                    "avalikus kihis (tasulise RIK-väljavõtte jalga EI OLE)"
                    % (kid, ", ".join(hypo)))
    extra = ("; muid kitsendusi avalikus kihis: %s" % ", ".join(other)
             if other else "")
    return WEAK_GOOD_CAP, ("Katastriüksuse %s avalikus kitsenduskihis "
                           "takistusi EI OLE%s: sulgemisvalmiduse hinnang "
                           "%d/100 (nõrk-hea lagi — täisdetail vajab RIK "
                           "tasulist väljavõtet + notari kontrolli)"
                           % (kid, extra, WEAK_GOOD_CAP))


# ---------------------------------------------------------------------------
# Coverage dims: the 3 remaining params off this source (issue #329).
# ---------------------------------------------------------------------------

def dim_naaber_planeering(parcel: Optional[dict],
                          plans: Optional[List[dict]],
                          snapshot: Optional[str] = None) -> Score:
    """P4-006: neighbouring detailplaneering pipeline within BUFFER_M.

    plans rows: {"nimetus": ..., "staadium": "menetluses"/"algatatud"/
    "kehtestatud", "kaugus_m": float} from the TPR join. A pipeline-stage
    plan inside the buffer -> 45 (päikese/vaate risk); only kehtestatud
    nearby -> 65 (context); none in the buffer -> 70, always dated to the
    TPR snapshot (absence in the snapshot, never "no plans exist").
    NULL when the parcel join or the TPR snapshot is missing.
    """
    kid = parcel_id(parcel)
    if kid is None:
        return None, ("Katastritunnust EI OLE (hinnang puudub): naaber- "
                      "planeeringute join vajab katastriüksust — tee "
                      "Maainfo/KKIS päring, ära feigi")
    if plans is None:
        return None, ("TPR hetktõmmist katastriüksuse %s ümbruse kohta EI OLE "
                      "(hinnang puudub): torujuhtme-seis vajab TPR päringut "
                      "(500 m puhver) — hinda snapshot'ist, ära feigi" % kid)
    dated = "TPR hetktõmmis %s" % snapshot if snapshot else "TPR hetktõmmis"
    pipe = [(p.get("nimetus"), p.get("kaugus_m")) for p in plans
            if isinstance(p, dict)
            and normalise_liik(p.get("staadium")) in PIPELINE_STAGES
            and isinstance(p.get("kaugus_m"), (int, float))
            and 0 <= p.get("kaugus_m") <= BUFFER_M]
    if pipe:
        pipe.sort(key=lambda t: t[1])
        nimi, kaugus = pipe[0]
        return 45, ("Naaber-planeering torujuhtmes %s lähedal (%s, %.0f m, "
                    "%s): päikese/vaate-riski hinnang 45/100 — kontrolli "
                    "menetlusestaadiumi TPR-st enne pakkumist"
                    % (kid, nimi or "nimetu planeering", kaugus, dated))
    nearby_set = [(p.get("nimetus"), p.get("kaugus_m")) for p in plans
                  if isinstance(p, dict)
                  and isinstance(p.get("kaugus_m"), (int, float))
                  and 0 <= p.get("kaugus_m") <= BUFFER_M]
    if nearby_set:
        return 65, ("Katastriüksuse %s 500 m puhvris ainult kehtestatud "
                    "planeeringuid (%d tk, %s): konteksti-hinnang 65/100 — "
                    "torujuhtme-riski EI OLE snapshot'is"
                    % (kid, len(nearby_set), dated))
    return 70, ("Katastriüksuse %s 500 m puhvris menetluses planeeringuid EI "
                "OLE (%s): vaate/päikese-rahu hinnang 70/100 (ainult "
                "snapshot'i ulatuses, mitte garantii)"
                % (kid, dated))


def dim_parkimine_hoov(parcel: Optional[dict],
                       parking: Optional[dict]) -> Score:
    """P4-013: parking regime (tasuline tsoon) + courtyard ratio.

    parking: {"tsoon": "A"/"B"/"C"/None (tasuta), "hooviala_osakaal":
    0..1|None}. The zone is the regime leg and must be known to score;
    the courtyard ratio only adjusts. Base 70, paid zone A -20 / B -10 /
    C -5, roomy courtyard (>= 0.3) +10 capped at 85, paved-over
    courtyard (< 0.1) with a paid zone -5. NULL when the parcel join or
    the zone leg is missing.
    """
    kid = parcel_id(parcel)
    if kid is None:
        return None, ("Katastritunnust EI OLE (hinnang puudub): parkimise "
                      "režiim on katastriüksuse join — tee Maainfo päring, "
                      "ära feigi")
    if not isinstance(parking, dict) or "tsoon" not in parking \
            or parking.get("tsoon") == "teadmata":
        return None, ("Parkimistsooni katastriüksuse %s kohta EI OLE "
                      "(hinnang puudub): režiim vajab Tallinna parkimise "
                      "määruse tsooniotsingut — kontrolli Transpordiameti "
                      "kaardilt, ära feigi" % kid)
    tsoon = parking.get("tsoon") if isinstance(parking, dict) else None
    if tsoon not in (None, "A", "B", "C"):
        return None, ("Parkimistsoon '%s' on tundmatu väärtus — režiimi- "
                      "hinnangut EI OLE: paranda tsooniotsing" % tsoon)
    if tsoon is None and (not isinstance(parking, dict)
                          or parking.get("hooviala_osakaal") is None):
        return None, ("Parkimisandmeid katastriüksuse %s kohta EI OLE "
                      "(hinnang puudub): vaja tsooni + hooviala suhet "
                      "katastri join'ist" % kid)
    score = 70
    if tsoon == "A":
        score -= 20
        zone_txt = "tasuline tsoon A (Kesklinn/Vanalinn)"
    elif tsoon == "B":
        score -= 10
        zone_txt = "tasuline tsoon B"
    elif tsoon == "C":
        score -= 5
        zone_txt = "tasuline tsoon C"
    else:
        zone_txt = "tasuta parkimisala"
    ratio = parking.get("hooviala_osakaal") if isinstance(parking,
                                                          dict) else None
    if isinstance(ratio, (int, float)):
        if ratio >= 0.3:
            score = min(85, score + 10)
            yard_txt = "avar hooviala (%.0f%%)" % (ratio * 100.0)
        elif ratio < 0.1 and tsoon is not None:
            score -= 5
            yard_txt = "hooviala peaaegu puudub (%.0f%%)" % (ratio * 100.0)
        else:
            yard_txt = "hooviala %.0f%%" % (ratio * 100.0)
    else:
        yard_txt = "hooviala suhet EI OLE (ainult tsooni-jalg)"
    score = _clamp(score)
    return score, ("Katastriüksus %s: %s, %s — parkimise hinnang %d/100 "
                   "(tsoon katastri-joinist, määruse-järgne)"
                   % (kid, zone_txt, yard_txt, score))


def dim_enforcement(parcel: Optional[dict],
                    enforcement: Optional[dict]) -> Score:
    """P4-020: pankrot/täitemenetlus freeze risk per entity (weak-good cap).

    enforcement: {"nimi": ..., "pankrot": bool, "taitementlus_aktiivne":
    bool, "at_teated": [...], "kontrollitud": "YYYY-MM-DD"}. Active
    pankrot/täitemenetlus -> 20 (frozen-deal risk); only historical AT
    notices -> 55; nothing found in the checked notices -> WEAK_GOOD_CAP
    (commercial scores + unpublished detail named missing). NULL when no
    entity is named or no notice check exists at all.
    """
    kid = parcel_id(parcel)
    if kid is None:
        return None, ("Katastritunnust EI OLE (hinnang puudub): sundtäitmise "
                      "kiht on katastriüksuse join — tee Maainfo päring, "
                      "ära feigi")
    if not isinstance(enforcement, dict) or not enforcement.get("nimi"):
        return None, ("Isikut/arendajat katastriüksuse %s kohta EI OLE "
                      "nimetatud (hinnang puudub): sundtäitmise kontroll "
                      "vajab nime + AT/kohtutäituri otsingut" % kid)
    nimi = enforcement.get("nimi")
    if enforcement.get("kontrollitud") is None \
            and enforcement.get("at_teated") is None \
            and not enforcement.get("pankrot") \
            and not enforcement.get("taitementlus_aktiivne"):
        return None, ("Sundtäitmise kontrolli '%s' kohta EI OLE (hinnang "
                      "puudub): tee Ametlike Teadaannete + kohtutäiturite "
                      "registri otsing, ära feigi" % nimi)
    if enforcement.get("pankrot") or enforcement.get("taitementlus_aktiivne"):
        kinds = [k for k, v in (("pankrot", enforcement.get("pankrot")),
                                ("aktiivne täitemenetlus",
                                 enforcement.get("taitementlus_aktiivne")))
                 if v]
        return 20, ("'%s' kohta %s (katastriüksus %s): külmunud tehingu riski "
                    "hinnang 20/100 — notari sulgemiskontroll kohustuslik, "
                    "tehing võib seiskuda" % (nimi, " + ".join(kinds), kid))
    teated = enforcement.get("at_teated")
    if isinstance(teated, list) and teated:
        return 55, ("'%s' kohta %d ajaloolist AT teadet, aktiivset menetlust "
                    "EI OLE (katastriüksus %s): järelriski hinnang 55/100 — "
                    "kontrolli kustutamismärked notariga"
                    % (nimi, len(teated), kid))
    return WEAK_GOOD_CAP, ("'%s' kohta aktiivset pankroti/täitemenetlust EI "
                           "OLE avalikes teadetes (katastriüksus %s): "
                           "hinnang %d/100 (nõrk-hea lagi — Creditinfo skoori "
                           "+ avaldamata detaili jalga EI OLE)"
                           % (nimi, kid, WEAK_GOOD_CAP))


# ---------------------------------------------------------------------------
# Registry + aggregator (entry point for the weight-rebalance follow-up).
# ---------------------------------------------------------------------------

P4_MAA_KATASTER_DIMS = (
    ("kinnistus_syva", "P4-004", dim_kinnistus_syva),
    ("naaber_planeering", "P4-006", dim_naaber_planeering),
    ("parkimine_hoov", "P4-013", dim_parkimine_hoov),
    ("enforcement", "P4-020", dim_enforcement),
)


def score_p4_maa_kataster(
        parcel: Optional[dict],
        plans: Optional[List[dict]] = None,
        parking: Optional[dict] = None,
        enforcement: Optional[dict] = None,
        snapshot: Optional[str] = None) -> Dict[str, Optional[int]]:
    """All 4 P4 maa-kataster dims for one parcel (keys match registry).

    Every dim returns (score, reason); the aggregator unwraps to
    score-only. plans=None means "no TPR snapshot" (P4-006 NULL), not
    "no plans" — pass [] for an honestly empty buffer.
    """
    out: Dict[str, Optional[int]] = {}
    out["kinnistus_syva"] = dim_kinnistus_syva(parcel)[0]
    out["naaber_planeering"] = dim_naaber_planeering(parcel, plans,
                                                     snapshot)[0]
    out["parkimine_hoov"] = dim_parkimine_hoov(parcel, parking)[0]
    out["enforcement"] = dim_enforcement(parcel, enforcement)[0]
    return out
