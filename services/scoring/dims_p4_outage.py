"""P4 Elektrilevi live-outage dims (issue #729, scoped build of probe #689).

Param (this module only — the LIVE slice; sibling slices untouched):
* P4-009 Power/internet reliability at address: the rikkekaart
  "running outages now" slice (keyless live JSON). Disjoint from
  dims_p4_elektrilevi.dim_power_reliability, which owns the
  UNPUBLISHED feeder-SAIDI-history slice (stays NULL — a live map
  is not a history), and from dims_p4_ookla, which owns the
  throughput slice. No double-scoring: this module never scores
  history, tariffs, export, backup or zero-consumption.

FIELD SEMANTICS (pinned from the app's own JS 2026-09-19 —
``geoserver-api/content/configuration.js``, polite /tmp pull, see
docs/p4_outage.md §1; deferred from probe #689, pinned now):
* ``OUTAGE_T_PLAN = "p"`` (plaaniline), ``OUTAGE_T_FAULT = "f"``
  (rikkeline), ``OUTAGE_T_UPCOMING = "u"`` (tulevane plaaniline).
* Area counters via ``createAreaReplacer``: ``fc`` -> XPFAULTS
  ("Aktiivseid rikkelisi katkestusi"), ``pc`` -> XPPLANS
  ("Aktiivseid plaanilisi katkestusi"), ``uc`` -> XPUPCOMING
  ("Tulevane plaaniline katkestus"); ``fcc``/``pcc``/``ucc`` ->
  XPCUSTOMERS ("Mõjutatud kliente": active view ``fcc+pcc``,
  upcoming view ``ucc``).

LIVE VERDICT (2026-09-19, polite single GET, UA
``home-finder-research/0.1``, ``--max-time`` 30, 429 = stop, raw
``/tmp/hf729/`` only): ``GetApplicationData`` -> 200, 127 003 B
double-encoded JSON ``scopes.p.{areas,dynareas,outages}``: 99 areas
(Tallinn: fc=0/fcc=0/pc=0/pcc=0/uc=27/ucc=3169; Harju maakond:
uc=96/ucc=5766), 516 outages (514 u, 1 f, 1 p). No login.

HONESTY (AGENTS.md 7.2): a live snapshot is thin evidence — bands
are capped and every scored reason says "hetkeseis" (never
reliability): active fault now -> 30, active planned -> 55,
upcoming-only -> 70 weak-good, clean -> 80 weak-good capped (a quiet
live map is NOT proof of a reliable feeder — SAIDI stays
unpublished per dims_p4_elektrilevi). A missing or stale (> 5 min,
OUTAGE_TTL_S) snapshot stays NULL with an Estonian EI OLE reason
pointing at the rikkekaart live map — never a faked calm. The
Tallinn row scores city grain; the Harju row is the documented
fallback when the Tallinn row is absent (never averaged together).
Transport errors in the harvester raise and never touch the cache;
HTTP 429 stops the run.

Style mirrors dims_p4_ookla.py (#268): pure offline scorers
(origin, snapshot) -> (Optional[int], Estonian reason); network
lives ONLY in scripts/build/batch_outage.py. Tests never touch the
network (fixture rows repeat the live SHAPE with the observed
Tallinn/Harju counters — facts, tiny).
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Live JSON endpoint (keyless, ~130 KB, verified 2026-09-19).
OUTAGE_URL = ("https://rikkekaart.elektrilevi.ee/"
              "geoserver-api/GetApplicationData")

#: Freshness ceiling per the issue (live data, pole/operator pull).
OUTAGE_TTL_S = 300

#: Identifying user agent for the harvester pull.
OUTAGE_UA = ("home-finder outage ingest (polite 5-min pulls, single GET, "
             "file cache; contact via GitHub home-finder)")

#: City-grain rows, preferred first (documented fallback order).
OUTAGE_TALLINN_LABEL = "Tallinn"
OUTAGE_HARJU_LABEL = "Harju maakond"

#: Outage-type vocabulary pinned from configuration.js.
OUTAGE_T_PLAN = "p"
OUTAGE_T_FAULT = "f"
OUTAGE_T_UPCOMING = "u"

#: Area counter keys per class (count, affected customers).
OUTAGE_COUNTERS = (("fc", "fcc"), ("pc", "pcc"), ("uc", "ucc"))

_USER_AGENT = OUTAGE_UA


def _num(v) -> Optional[int]:
    """Finite non-bool number as int, else None (never faked from junk)."""
    if isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")):
        return None
    return int(f)


def coerce_area(row: object) -> Optional[dict]:
    """One areas[] row -> canonical counters, or None to skip.

    Rows without a label are skipped (no join key — never a faked
    region). Counter fields may stay None: a row with missing counts
    parses but never scores.
    """
    if not isinstance(row, dict):
        return None
    label = row.get("label")
    if not isinstance(label, str) or not label.strip():
        return None
    area = {"label": label.strip()}
    for count_key, cust_key in OUTAGE_COUNTERS:
        area[count_key] = _num(row.get(count_key))
        area[cust_key] = _num(row.get(cust_key))
    return area


def parse_outage_snapshot(payload: object,
                          now: Optional[datetime] = None) -> Optional[dict]:
    """Double-encoded GetApplicationData body -> fresh snapshot or None.

    Returns ``{"pulled_at": iso, "areas": {label: counters}}`` when the
    payload parses AND ``pulled_at`` is within OUTAGE_TTL_S of ``now``
    (default: current UTC). Stale, missing or malformed input parses
    to None (unknown, never an empty calm snapshot — scorers must not
    read "no file" as "no outages").
    """
    at = now or datetime.now(tz=timezone.utc)
    if not isinstance(payload, dict):
        return None
    pulled = payload.get("pulled_at")
    try:
        pulled_dt = datetime.fromisoformat(str(pulled))
    except (ValueError, TypeError):
        return None
    if pulled_dt.tzinfo is None:
        pulled_dt = pulled_dt.replace(tzinfo=timezone.utc)
    if (at - pulled_dt).total_seconds() > OUTAGE_TTL_S:
        return None
    rows = payload.get("areas")
    if not isinstance(rows, list):
        return None
    areas = {}
    for row in rows:
        area = coerce_area(row)
        if area is not None:
            areas[area["label"]] = area
    if not areas:
        return None
    return {"pulled_at": pulled_dt.isoformat(), "areas": areas}


def pick_city_row(snapshot: dict) -> Optional[dict]:
    """Tallinn row preferred, Harju county fallback (documented order)."""
    areas = snapshot.get("areas", {}) if isinstance(snapshot, dict) else {}
    if OUTAGE_TALLINN_LABEL in areas:
        return areas[OUTAGE_TALLINN_LABEL]
    return areas.get(OUTAGE_HARJU_LABEL)


def _null_no_origin() -> Score:
    return None, ("Elektrikatkestuste hetkeseis eeldab aadressi "
                  "koordinaate (EI OLE hinnangut ilma asukohata): "
                  "Tallinna rea saab siduda vaid teada aadressiga — "
                  "jooksvaid katkestusi näitab rikkekaart, ära feigi")


def _null_no_snapshot() -> Score:
    return None, ("Elektrilevi hetkeseisu väljavõtet pole alla laetud "
                  "või see on vanem kui 5 minutit (EI OLE hinnangut): "
                  "elav JSON tõmmatakse operaatori/pooluse poolt "
                  "(batch_outage.py) — jooksvaid katkestusi näitab "
                  "rikkekaart, ära feigi vanast vahemälust skoori")


def dim_outage_now(origin: Optional[Tuple[float, float]],
                   snapshot: Optional[dict]) -> Score:
    """P4-009 live slice: running-outage hetkeseis, capped bands.

    Active fault now (fc/fcc > 0) -> 30; active planned (pc/pcc > 0)
    -> 55; upcoming-only (uc/ucc > 0) -> 70 weak-good; clean -> 80
    weak-good capped (quiet map is not reliability proof). Rows with
    missing counts are treated as unknown for their class (never
    zero-filled into calm).
    """
    if origin is None:
        return _null_no_origin()
    if not isinstance(snapshot, dict):
        return _null_no_snapshot()
    row = pick_city_row(snapshot)
    if row is None:
        return _null_no_snapshot()
    label = row.get("label", OUTAGE_TALLINN_LABEL)
    fc, fcc = row.get("fc"), row.get("fcc")
    pc, pcc = row.get("pc"), row.get("pcc")
    uc, ucc = row.get("uc"), row.get("ucc")
    if (isinstance(fc, int) and fc > 0) or (isinstance(fcc, int) and fcc > 0):
        return 30, ("Aktiivne rikkeline katkestus %s (hetkeseis: %s "
                    "rikket, %s mõjutatud klienti): vool võib praegu "
                    "puududa — kontrolli rikkekaardilt, ära feigi "
                    "stabiilsust" % (label, fc if isinstance(fc, int) else "?",
                                     fcc if isinstance(fcc, int) else "?"))
    if (isinstance(pc, int) and pc > 0) or (isinstance(pcc, int) and pcc > 0):
        return 55, ("Aktiivne plaaniline katkestus %s (hetkeseis: %s "
                    "tööd, %s mõjutatud klienti): hooldusaknad on "
                    "ajutised — kontrolli rikkekaardilt"
                    % (label, pc if isinstance(pc, int) else "?",
                       pcc if isinstance(pcc, int) else "?"))
    if (isinstance(uc, int) and uc > 0) or (isinstance(ucc, int) and ucc > 0):
        return 70, ("Ainult tulevased plaanilised katkestused %s "
                    "(hetkeseis: %s ees, %s mõjutatud klienti, nõrk hea): "
                    "aktiivset katkestust praegu pole — ajalootõendit "
                    "(SAIDI) EI OLE" % (label,
                                        uc if isinstance(uc, int) else "?",
                                        ucc if isinstance(ucc, int) else "?"))
    if all(row.get(k) == 0 for pair in OUTAGE_COUNTERS for k in pair):
        return 80, ("Rikkekaardil aktiivseid katkestusi %s praegu pole "
                    "(hetkeseis, nõrk hea, lagi 80): vaikne kaart ei ole "
                    " töökindluse tõend — fiidri ajalugu (SAIDI) on "
                    "avaldamata" % label)
    return _null_no_snapshot()


P4_OUTAGE_DIMS = (
    ("outage_now", "P4-009", dim_outage_now),
)


def score_p4_outage(origin: Optional[Tuple[float, float]],
                    snapshot: Optional[dict]
                    ) -> Dict[str, Optional[int]]:
    """P4 live-outage dim for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_OUTAGE_DIMS). Capped
    hetkeseis bands on a fresh snapshot, else None by design."""
    return {key: fn(origin, snapshot)[0] for key, _, fn in P4_OUTAGE_DIMS}
