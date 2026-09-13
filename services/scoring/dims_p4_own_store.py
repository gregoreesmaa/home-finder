"""P4 own-store per-listing dimensions (issues #243 demo + #327 coverage).

Source: Listing-portal exhaust from the own 17-adapter snapshots
(kv.ee / city24.ee / kinnisvara24.ee polite daily snapshots — first_seen,
price-drop history, cross-portal sightings, image-hash index, portal
counters, listing NLP). Zero vendor: every input below is first-party
data accumulated by our own polite pulls.

Params (this module only — 20 P4 ids, demo + coverage paired in one PR
because the #327 coverage body states it extends the #243 demo ingestion):
* P4-001 price history + days-on-market per ad (DEMO: computed)
* P4-002 closed-deal micro-comps (NULL — Maa-amet tehingud bulk missing)
* P4-003 rent reality + Airbnb density (NULL — üüri/Airbnb source missing)
* P4-005 ehitusluba/kasutusluba existence (NULL — EHR join missing)
* P4-007 KÜ loan + remondifond + heating (NULL — Äriregister bulk missing)
* P4-021 developer + broker track record (NULL — aggregate still accumulating)
* P4-022 listing photo forensics (COMPUTED from image-hash + sources_seen)
* P4-028 listing demand exhaust (COMPUTED from views/updates counters)
* P4-029 street-imagery block observer (NULL — Mapillary/KartaView missing)
* P4-034 summer overheating risk (NULL — EHR + LiDAR inputs missing)
* P4-038 bargaining margin (NULL — Maa-amet gap table missing)
* P4-040 last-200 m arrival sequence (NULL — Mapillary sequences missing)
* P4-041 glimpse economics / piilukas (NULL — LiDAR/LoD2 fan missing)
* P4-043 number-13 / name arbitrage (PARTIAL: floor-13 flag from snapshot)
* P4-046 dread removal (COMPUTED from listing-text NLP: kamin/kaev/exit)
* P4-049 taxi/guest test (NULL — findability probe + photo join missing)
* P4-051 zero-consumption stairwells (NULL — hex aggregates + privacy bar)
* P4-052 turnover wave per building (NULL — per-building aggregate missing)
* P4-057 heat-pump hum corridors (NULL — EHR heating changes missing)
* P4-059 wood-burning restriction zones (NULL — zone rule join missing)

Polarity (uniform, reviewable): 100 = most buyer-favourable on the param's
Buy Q, 0 = least, None = unknown (NULL stays NULL with an Estonian reason).
P4-001/P4-028/P4-038-family dims read as steal-opportunity (high = stale or
softening, buyer has leverage); P4-022 reads as listing-cleanliness
(high = unique photo trail); P4-043/P4-046 read as buyer upside
(high = discount or redundancy stated).

HONESTY (AGENTS.md section 7.2): computed dims use ONLY own-store fields
and their reasons say "hinnang" (estimate, never "mõõdetud"/"garanteeritud").
NULL dims return None for EVERY input and their reasons say "hinnang" +
"EI OLE" and name the missing source plus the buyer-side check — never a
faked area score (OTA PR #131 precedent).

Snapshot-record convention (what ingest_snapshot/merge_sightings produce
and every scorer consumes — plain dicts, no DB needed for the demo):
  identity: id, source, source_url, address (canonical adapter record)
  listing facts (None when the card omits them): price, area_m2, rooms, floor
  own-store accumulation: first_seen / last_seen (ISO dates),
    price_history ([{date, price}] in sight order), sources_seen ([SOURCE]),
    image_hash (perceptual-hash hex or None), photo_count, views, updates,
    broker (name or None), text (description or None), relist (bool)
  scoring cursor: asof (ISO date the dim is evaluated for; falls back to
    last_seen so fixtures stay deterministic — no wall-clock reads here)

Politeness / TTL (AGENTS.md sections 5 + 7.4): portals are polled at most
daily (page_limit=1, desktop UA, ROBOTS_URL check, 24 h file cache — see
adapters.DEFAULT_TTL_S and each adapter's ROBOTS_URL); the own store is
therefore a DAILY snapshot series. Quarterly-bulk sources (Maa-amet
tehingud, Statamet KK11, EHR bulk) are NOT in this store — params needing
them stay NULL until their own demo lands. Never commit scraped dumps —
fixtures only.

Style mirrors dims_group20a.py (#212): every scorer is pure and
offline-tested — (snapshot dict) -> (Optional[int 0..100], Estonian
reason). Network lives only in the portal adapters' fetch paths; this
module adds no network calls and no Overpass fragment. Helpers are local
(no livability/sibling imports) so a future central hook cannot cycle.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share one PR because the #327 body states it "extends
  the demoed ingestion" — splitting would leave the demo unreviewed
  against its own consumers.
* P4-038 stays NULL even though per-listing drop-% is computable: that
  signal already belongs to P4-001; scoring it twice would double-count
  the same price cut in the steal sort.
* P4-021 stays NULL even when the broker name is known: a single name is
  not a track record (relist rate / DOM / price cuts need the accumulating
  cross-portal aggregate). The reason varies with broker known/unknown so
  the wiring is fixture-provable, not decorative.
* P4-034 stays NULL even when the text mentions "konditsioneer": a cooling
  mention does not carry the orientation/floor/geometry physics sim.
* P4-051 is a hard NULL (not even partial): per-listing empty-unit scoring
  from meter aggregates would be both dishonest and privacy-unsafe; the
  spec shapes it as a hex flag.
* P4-046 keyword hits are broker-stated claims ("kuulutuse väide"), scored
  modestly (40 + 15/flag, cap 85) with a "kontrolli vaatlusel" caveat.

Integration (deliberately NOT done here): no livability.OVERPASS_QUERY /
_POI_KIND extension (no snapshot tags consumed) and no WEIGHTS change —
existing tests pin set(WEIGHTS) exactly, so per-batch WEIGHTS edits would
break every sibling. Rebalancing stays one joint change across batches.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# Own-store pull cadence: at most daily, matching adapters.DEFAULT_TTL_S
# (24 h file cache) and the daily-cron politeness contract.
OWN_STORE_TTL_S = 24 * 3600

_MISSING_DOM = ("päevade-arvu (DOM) ei saa arvutada (EI OLE hinnangut): "
                "first_seen/asof puudub oma snapshots — oota homset "
                "päevast snapshotti, ära feigi ala skoori")


def _parse_day(value: object) -> Optional[date]:
    """ISO-date or None (never raises — bad dates are missing data)."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def _dom_days(snapshot: dict) -> Optional[int]:
    """Days-on-market from own first_seen to the asof cursor (None if unknown)."""
    first = _parse_day(snapshot.get("first_seen"))
    if first is None:
        return None
    asof = _parse_day(snapshot.get("asof")) or _parse_day(snapshot.get("last_seen"))
    if asof is None:
        return None
    return max(0, (asof - first).days)


def _drop_stats(snapshot: dict) -> Tuple[int, float]:
    """(drop_count, peak_to_current_cut_pct) over price_history + current price.

    Drop counting is deliberately simple (consecutive step-downs in sight
    order, current price as the final point); the cut is measured peak to
    current so a relisted bounce cannot hide the seller's softening.
    """
    series: List[float] = []
    history = snapshot.get("price_history") or []
    for point in history:
        try:
            series.append(float(point.get("price")))
        except (TypeError, ValueError, AttributeError):
            continue
    try:
        current = float(snapshot.get("price"))
    except (TypeError, ValueError):
        current = None
    if current is not None and (not series or series[-1] != current):
        series.append(current)
    series = [p for p in series if p > 0]
    if len(series) < 2:
        return 0, 0.0
    drops = sum(1 for prev, cur in zip(series, series[1:]) if cur < prev)
    peak = max(series)
    cut_pct = (peak - series[-1]) / peak * 100.0 if peak > 0 else 0.0
    return drops, max(0.0, cut_pct)


# ---------------------------------------------------------------------------
# Demo ingestion: daily polite snapshots -> own-store entries (pure, offline).
# ---------------------------------------------------------------------------

def ingest_snapshot(store: Dict[tuple, dict], record: dict, day: str) -> dict:
    """Fold one day's polite portal card into the own store (pure, offline).

    store maps (source, id) -> entry. First sight stamps first_seen; every
    sight refreshes last_seen; price CHANGES append to price_history (repeat
    sightings at the same price leave history untouched). Counters
    (views/photo_count), image_hash, broker, text, floor and the relist flag
    are overwritten with the latest sighting. Returns the entry.
    """
    key = (str(record.get("source") or "?"), str(record.get("id") or "?"))
    entry = store.get(key)
    if entry is None:
        entry = {
            "id": record.get("id"), "source": record.get("source"),
            "source_url": record.get("source_url"),
            "address": record.get("address", ""),
            "first_seen": day, "price_history": [], "sources_seen": [],
        }
        store[key] = entry
    entry["last_seen"] = day
    price = record.get("price")
    hist = entry.setdefault("price_history", [])
    if price is not None and (not hist or hist[-1].get("price") != price):
        hist.append({"date": day, "price": price})
    for field in ("source_url", "address", "price", "area_m2", "rooms",
                  "floor", "image_hash", "photo_count", "views", "updates",
                  "broker", "text", "relist"):
        if record.get(field) is not None:
            entry[field] = record[field]
    return entry


def merge_sightings(entries: List[dict]) -> dict:
    """Merge one listing's cross-portal sightings into a snapshot record.

    Callers group sightings first (adapters.dedup_listings precedent —
    normalised address + price); this merges one group: earliest
    first_seen, latest last_seen, price histories merged by date,
    sources_seen unioned, scalar fields taken first-non-None in
    (source, id) order. Deterministic — same sightings, same snapshot.
    """
    ordered = sorted(entries, key=lambda e: (str(e.get("source") or "?"),
                                             str(e.get("id") or "?")))
    merged: dict = {"sources_seen": [], "price_history": []}
    seen_dates: set = set()
    for entry in ordered:
        if not merged.get("address") and entry.get("address"):
            merged["address"] = entry["address"]
        if entry.get("id") is not None and merged.get("id") is None:
            merged["id"] = entry["id"]
        for day_key in ("first_seen",):
            if entry.get(day_key) and (not merged.get(day_key)
                                       or entry[day_key] < merged[day_key]):
                merged[day_key] = entry[day_key]
        if entry.get("last_seen") and (not merged.get("last_seen")
                                       or entry["last_seen"] > merged["last_seen"]):
            merged["last_seen"] = entry["last_seen"]
        for point in entry.get("price_history") or []:
            stamp = (point.get("date"), point.get("price"))
            if stamp not in seen_dates:
                seen_dates.add(stamp)
                merged["price_history"].append(
                    {"date": point.get("date"), "price": point.get("price")})
        for src in entry.get("sources_seen") or ([entry.get("source")]
                                                 if entry.get("source") else []):
            if src and src not in merged["sources_seen"]:
                merged["sources_seen"].append(src)
        for field in ("source", "source_url", "price", "area_m2", "rooms",
                      "floor", "image_hash", "photo_count", "views",
                      "updates", "broker", "text", "relist"):
            if merged.get(field) is None and entry.get(field) is not None:
                merged[field] = entry[field]
    merged["price_history"].sort(key=lambda p: str(p.get("date")))
    merged["sources_seen"] = sorted(merged["sources_seen"])
    return merged


# ---------------------------------------------------------------------------
# P4-001: price history + days-on-market per ad (DEMO — computed end to end).
# ---------------------------------------------------------------------------

def dim_price_history_dom(snapshot: dict) -> Score:
    """P4-001: steal-opportunity from own DOM + price-drop history (hinnang)."""
    dom = _dom_days(snapshot)
    if dom is None:
        return None, _MISSING_DOM
    drops, cut_pct = _drop_stats(snapshot)
    if cut_pct >= 10.0 or drops >= 2:
        return 80, ("Hinnalanguste hinnang: müüja on tipust %.0f%% alla tulnud "
                    "(%d langust, %d päeva müügis) — kauplemisruumi või "
                    "steal-signaal, kontrolli kuulutuse ajalugu" % (cut_pct, drops, dom))
    if drops == 1 or dom >= 90:
        return 65, ("Jälgimis-hinnang: üks langus või %d päeva müügis — hind "
                    "pehmeneb või kuulutus seisab, küsi maaklerilt põhjust" % dom)
    if dom >= 30:
        return 55, ("Oote-hinnang: %d päeva müügis langusteta — hind kindel, "
                    "aga seisak kasvatab kauplemisruumi" % dom)
    return 40, ("Värske-hinnang: %d päeva müügis, hind kindel — "
                "soodussignaali snapshotis pole" % dom)


# ---------------------------------------------------------------------------
# Coverage (#327): remaining params wired to the same snapshot record.
# Computed where the own store honestly carries the signal, else NULL.
# ---------------------------------------------------------------------------

def dim_micro_comps(snapshot: dict) -> Score:
    """P4-002: NULL — same-building/street closed €/m² needs Maa-amet tehingud."""
    return None, ("Mikro-võrdluse hinnang puudub (EI OLE tehinguandmeid): sama "
                  "maja/tänava sulgunud €/m² eeldab Maa-ameti tehingute kvartali-"
                  "pakki, mida oma snapshotis pole — küsi maaklerilt maja "
                  "tehinguid, ära feigi asking-hinnast sulgunut")


def dim_rent_reality(snapshot: dict) -> Score:
    """P4-003: NULL — yield/nuisance needs KV üüri medians + Airbnb density."""
    return None, ("Üürireaalsuse hinnang puudub (EI OLE üüriandmeid): tootlus ja "
                  "lühiajalise üüri tihedus eeldavad KV üüri-mediaane ja Airbnb-"
                  "tihedust, mida snapshotis pole — kontrolli KV üürikuulutusi, "
                  "ära feigi")


def dim_permit_existence(snapshot: dict) -> Score:
    """P4-005: NULL — ehitusluba/kasutusluba existence needs the EHR join."""
    return None, ("Loa-olemasolu hinnang puudub (EI OLE EHR-päringut): "
                  "ehitusloa/kasutusloa olemasolu (sh juurdeehitus) selgub EHR "
                  "ehitise-päringust, mitte portaalikaardilt — küsi luba "
                  "maaklerilt enne broneerimist, ära feigi")


def dim_ku_loan(snapshot: dict) -> Score:
    """P4-007: NULL — KÜ loan/remondifond/heating needs Äriregister bulk."""
    base = ("KÜ-laenu hinnang puudub (EI OLE aruandeandmeid): laenujääk, "
            "remondifond ja kütte €/m² tulevad KÜ majandusaasta aruandest "
            "(e-Äriregister), mitte kuulutuse kaardilt")
    text = str(snapshot.get("text") or "")
    if re.search(r"remondifond", text, re.IGNORECASE):
        return None, (base + " — kuulutuse tekst mainib remondifondi, aga "
                             "summa ja laenujääkita see number pole: küsi KÜ "
                             "eelarvet, ära feigi tekstist finantsi")
    return None, (base + " — küsi KÜ eelarvet ja viimast aruannet, ära feigi")


def dim_broker_track(snapshot: dict) -> Score:
    """P4-021: NULL — one broker name is not a track record (aggregate pending)."""
    broker = (snapshot.get("broker") or "").strip() if isinstance(
        snapshot.get("broker"), str) else snapshot.get("broker")
    if broker:
        return None, ("Maakleri-hinnang ootel (EI OLE agregaati): \"%s\" on "
                      "teada, aga usaldus (relist-määr, DOM, hinnaalandused) "
                      "vajab ristportaali statistikat, mis alles koguneb — "
                      "võrdle sama maakleri kuulutusi ja küsi müügi-ajalugu" % broker)
    return None, ("Maakleri-hinnang puudub (EI OLE maakleritki): kuulutusel pole "
                  "maaklerinime ega ristportaali statistikat (relist/DOM) — "
                  "kogu agregaat koguneb päevaste snapshotidega, küsi "
                  "maaklerilt müügi-ajalugu")


def dim_photo_forensics(snapshot: dict) -> Score:
    """P4-022: listing cleanliness from own image-hash index (hinnang)."""
    if not snapshot.get("image_hash"):
        return None, ("Fotoforensika hinnang puudub (EI OLE fotojälge): "
                      "image_hashi pole snapshotis — oota homset dedup-"
                      "snapshotti, ära feigi puhtust")
    sources = snapshot.get("sources_seen") or []
    if len(sources) >= 2:
        return 30, ("Topeltkuulutuse-hinnang: sama fotojälg %d portaalil "
                    "(%s) — relist/ristpostituse signaal, kontrolli kuulutuse "
                    "vanust ja varjatud viga" % (len(sources), ", ".join(sorted(sources))))
    if snapshot.get("photo_count") == 0:
        return 45, ("Fotovaesuse-hinnang: fotosid 0 — võimalik varjatud viga, "
                    "küsi pilte ja kohapealset vaatlust")
    return 75, ("Puhas-hinnang: unikaalne fotojälg ühel portaalil — "
                "topeltsignaali snapshotis pole")


def dim_demand_exhaust(snapshot: dict) -> Score:
    """P4-028: stale-vs-steal from own views/updates counters (hinnang)."""
    dom = _dom_days(snapshot)
    views = snapshot.get("views")
    if isinstance(views, (int, float)) and views >= 0 and dom is not None and dom >= 1:
        per_day = views / dom
        if per_day >= 50:
            return 30, ("Nõudlushinnang: %.0f vaatamist/päev (%d päevaga) — kuum "
                        "kuulutus, konkurents, kauplemisruumi vähe" % (per_day, dom))
        if per_day <= 5 and dom >= 30:
            return 75, ("Leige-hinnang: %.1f vaatamist/päev %d päevaga — seisev "
                        "kuulutus, steal-võimalus, küsi põhjust" % (per_day, dom))
        return 55, ("Keskmise-hinnang: %.1f vaatamist/päev — tavaline nõudlus, "
                    "otsustavat signaali pole" % per_day)
    updates = snapshot.get("updates")
    if isinstance(updates, (int, float)) and updates >= 0:
        if updates >= 3:
            return 65, ("Uuendus-hinnang: %d uuendust snapshotis — korduvalt "
                        "värskendatud/ümberpostitatud, jälgi hinnaajalugu" % updates)
        return 55, ("Väheuuendus-hinnang: %d uuendust, vaatamisloendurit pole — "
                    "nõudlussignaali snapshotis napib" % updates)
    return None, ("Nõudlushinnang puudub (EI OLE loendureid): views/update-ajalugu "
                  "pole snapshotis — oota homset counter-snapshotti, ära feigi")


def dim_street_imagery(snapshot: dict) -> Score:
    """P4-029: NULL — facade/litter/sidewalk CV needs Mapillary/KartaView."""
    return None, ("Tänavapildi-hinnang puudub (EI OLE fotoseeriat): fassaad, "
                  "prügi, vrakid ja kõnniteed eeldavad Mapillary/KartaView "
                  "date-stamped seeriaid — jaluta kvartal läbi, ära feigi")


def dim_overheating(snapshot: dict) -> Score:
    """P4-034: NULL — August-sauna physics needs EHR + LiDAR, not keywords."""
    return None, ("Ülekuumenemise hinnang puudub (EI OLE füüsikasisendeid): S/W "
                  "suund, korrus, klaasipind ja läbiv tuulutus eeldavad EHR "
                  "andmeid + LiDAR-varjutust — teksti 'konditsioneer' seda simu "
                  "ei kanna, ära feigi")


def dim_bargaining_margin(snapshot: dict) -> Score:
    """P4-038: NULL — opening-bid gap needs the Maa-amet area-type table."""
    return None, ("Kauplemisvaru hinnang puudub (EI OLE gap-tabelit): pakkumise "
                  "vs tehingu vahe eeldab Maa-ameti area-type tabelit — "
                  "kuulutuse enda hinnalangus on juba P4-001 skoor (topelt "
                  "ei hinda), küsi asumistatistikat maaklerilt")


def dim_arrival_sequence(snapshot: dict) -> Score:
    """P4-040: NULL — 23:00 November walk needs Mapillary arrival sequences."""
    return None, ("Saabumis-hinnang puudub (EI OLE saabumisseeriat): viimase "
                  "200 m tunne eeldab Mapillary date-stamped seeriaid + "
                  "valgustustihedust — kõnni marsruut novembriõhtul läbi, "
                  "ära feigi")


def dim_glimpse(snapshot: dict) -> Score:
    """P4-041: NULL — piilukas view class needs the LiDAR/LoD2 view fan."""
    return None, ("Piiluka-hinnang puudub (EI OLE vaatelehvikut): mere/vanalinna "
                  "viil eeldab LiDAR/LoD2 vaate-fani + korruse-infost — "
                  "hinda vaade kohapeal aknast, ära feigi korruse pealt")


def dim_number_arbitrage(snapshot: dict) -> Score:
    """P4-043: floor-13 flag from the snapshot (PARTIAL — street leg is NULL)."""
    try:
        floor = int(snapshot.get("floor"))
    except (TypeError, ValueError):
        floor = None
    if floor == 13:
        return 70, ("Numbri-hinnang: 13. korrus — ebausklike allahindluse "
                    "võimalus ükskõiksele ostjale (hinnang, mitte garantii): "
                    "võrdle maja tehinguid, tänava-prestiizhi snapshot ei hinda")
    return None, ("Numbri-hinnang puudub (EI OLE residuaale): 13/tänavanime-"
                  "arbitraaž eeldab Maa-ameti tehingu-residuaale prestiiži-"
                  "lõikes — korruse-fakt üksi allahindlust ei tõesta, ära feigi")


_REDUNDANCY_PATTERNS = (
    # Trailing \w* covers Estonian inflections (kamin/kaminaga, kaev/kaevu);
    # leading \b keeps "ahi" from matching inside "lahing".
    ("kaminasoojus", re.compile(r"\b(kamin\w*|ahi|ahiküte\w*)\b", re.IGNORECASE)),
    ("kaevuvesi", re.compile(r"\b(puurkaev\w*|kaev\w*)\b", re.IGNORECASE)),
    ("varuväljapääs", re.compile(r"(varuväljapääs|varutee|teine\s+väljapääs)",
                                 re.IGNORECASE)),
)


def dim_dread_removal(snapshot: dict) -> Score:
    """P4-046: redundancy hints from listing-text NLP (hinnang, capped)."""
    text = str(snapshot.get("text") or "")
    if not text.strip():
        return None, ("Dread-hinnang puudub (EI OLE kuulutuseteksti): kamin/kaev/"
                      "varuväljapääs selguvad kuulutuse kirjeldusest — oota "
                      "teksti-snapshotti, ära feigi")
    hits = [label for label, pat in _REDUNDANCY_PATTERNS if pat.search(text)]
    if not hits:
        return 40, ("Dread-hinnang: tekstis dubleerimis-märget (kamin/kaev/"
                    "varuväljapääs) pole — varuplaan kuulutuse väitel puudub, "
                    "kontrolli vaatlusel")
    score = min(85, 40 + 15 * len(hits))
    return score, ("Dread-hinnang (%s — kuulutuse väide, hinnang): tekst mainib "
                  "%s — kontrolli kohapeal ja KÜ-lt" % (score, ", ".join(hits)))


def dim_taxi_guest(snapshot: dict) -> Score:
    """P4-049: NULL — findability probe + entrance-tidiness join not built."""
    return None, ("Külalise-hinnang puudub (EI OLE leitavusproovi): takso-otsingu "
                  "tabamus, nime hääldatavus ja sissepääsu korrasolek eeldavad "
                  "ADS-proovi + foto-liidest (P4-022/P4-029 join) — testi "
                  "Bolt-otsingut ja külasta õhtul, ära feigi")


def dim_zero_consumption(snapshot: dict) -> Score:
    """P4-051: HARD NULL — hex-only governance flag, never per-listing."""
    return None, ("Tühja-treppkoja hinnangut EI OLE (privaatsuspiir): null-"
                  "tarbimine on Elektrilevi/Vee agregeeritud hex-lipp (KOV/"
                  "hex, mitte aadressid) — aadressi-tasemel tühi-investori "
                  "skoor oleks nii ebaaus kui lubamatu, küsi KÜ remondifondi "
                  "seisu")


def dim_turnover_wave(snapshot: dict) -> Score:
    """P4-052: NULL — problem-vs-gentrifying needs the per-building aggregate."""
    if snapshot.get("relist"):
        return None, ("Käibe-hinnang ootel (EI OLE hoone-agregaati): relist-"
                      "signaal on näha, aga probleem-vs-gentrifitseerumine "
                      "vajab maja tehingu-/relist-sagedust mõlemapoolse "
                      "lugemisega — küsi maja tehinguajalugu")
    return None, ("Käibe-hinnang puudub (EI OLE hoone-agregaati): miks kõik "
                  "lahkuvad/tormavad sisse — selgub maja tehingu- ja relist-"
                  "sagedusest (probleem vs gentrifitseerumine), mida ühe "
                  "snapshotiga pole — küsi maaklerilt")


def dim_heatpump_hum(snapshot: dict) -> Score:
    """P4-057: NULL — neighbour-hum needs EHR heating changes + complaints."""
    text = str(snapshot.get("text") or "")
    own_unit = bool(re.search(r"soojuspump", text, re.IGNORECASE))
    tail = ("kuulutus mainib soojuspumpa (oma seade, mitte naabri müra)"
            if own_unit else "ka kuulutuse soojuspumba-mainimine üksi müra ei tõesta")
    return None, ("Humi-hinnang puudub (EI OLE naabri-allikat): õhksoojuspumba "
                  "dümin eeldab EHR kütte-liigi muutusi + mürakaebusi — %s: "
                  "küsi KÜ-lt väliseadmete paigutust, ära feigi" % tail)


def dim_woodburn_zone(snapshot: dict) -> Score:
    """P4-059: NULL — stranded-stove exposure needs the restriction-zone join."""
    text = str(snapshot.get("text") or "")
    stove = bool(re.search(r"\b(ahi|kamin|puuküte|puuküttel)\b", text, re.IGNORECASE))
    tail = ("kuulutus mainib ahju/kaminat (vara-inventuur, tsoon teadmata)"
            if stove else "ka ahju-mainimine üksi tsooni ei määra")
    return None, ("Piirangu-hinnang puudub (EI OLE tsooniliidest): tahkekütte "
                  "piiranguala + EHR kütte-liik määravad, kas ahi on "
                  "tulevikuvara või keeld — %s: kontrolli Keskkonnaameti "
                  "piirangualasid, ära feigi" % tail)


OWN_STORE_DIMS = (
    ("price_dom", "P4-001", dim_price_history_dom),
    ("micro_comps", "P4-002", dim_micro_comps),
    ("rent_reality", "P4-003", dim_rent_reality),
    ("permit_existence", "P4-005", dim_permit_existence),
    ("ku_loan", "P4-007", dim_ku_loan),
    ("broker_track", "P4-021", dim_broker_track),
    ("photo_forensics", "P4-022", dim_photo_forensics),
    ("demand_exhaust", "P4-028", dim_demand_exhaust),
    ("street_imagery", "P4-029", dim_street_imagery),
    ("overheating", "P4-034", dim_overheating),
    ("bargaining_margin", "P4-038", dim_bargaining_margin),
    ("arrival_sequence", "P4-040", dim_arrival_sequence),
    ("glimpse", "P4-041", dim_glimpse),
    ("number_arbitrage", "P4-043", dim_number_arbitrage),
    ("dread_removal", "P4-046", dim_dread_removal),
    ("taxi_guest", "P4-049", dim_taxi_guest),
    ("zero_consumption", "P4-051", dim_zero_consumption),
    ("turnover_wave", "P4-052", dim_turnover_wave),
    ("heatpump_hum", "P4-057", dim_heatpump_hum),
    ("woodburn_zone", "P4-059", dim_woodburn_zone),
)


def score_own_store(snapshot: dict) -> Dict[str, Optional[int]]:
    """All twenty P4 own-store dims for one snapshot record (entry point for
    the weight-rebalance follow-up; keys match OWN_STORE_DIMS). Computed
    dims carry own-store evidence; the rest are None by design — their
    source is not in the snapshot, and faking them would mislead."""
    return {key: fn(snapshot)[0] for key, _, fn in OWN_STORE_DIMS}
