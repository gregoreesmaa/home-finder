"""P4 own-snapshot per-asum asking medians (issue #495, dated negative).

Derives per-asum (Tallinn linnaosa-subdistrict) median EUR/m2 ASKING
prices ONLY from the repo's own 17-adapter listing snapshots — no
external price source, no invented medians. The map twin lives in
apps/web/lib/layers_asumedia.ts (layer "asumedia", same MIN_N, same
thin->NULL rule, parity pinned by tests on both sides).

Verify-first verdict (Group B, tallied 2026-09-14 — see the TS module
header for the tally command + counts): DATED NEGATIVE. Adapter
records carry NO `asum` key (30 parsed fixture records, 0 with the
key; addresses sit at street+locality grain) and no Tallinn asum
polygons are vendored, so production groups are always empty and every
asum stays NULL with an Estonian reason. This kernel is the honest
derivation rule the reopen PR feeds with real joined rows — it proves
the shape on fixtures without faking a single median.

Join discipline (statkov #485 identity-join-or-NULL precedent): rows
join on the exact `asum` key only. Free-text address mentions never
join (a "Kalamaja" substring is not an exact key). Rows without the
key are skipped and COUNTED (never silently dropped — the skipped
count rides in the reason).

Threshold: MIN_N = 5 (Land Board publications >= 5 deals per
settlement precedent — asking prices are noisier than closed deals,
so the strict bar, not the tehingud micro >= 3). Asums below MIN_N
stay NULL with their n labeled (never fake precision — no band table
is calibrated here; bands belong to the reopen PR, off the real
accumulated store).

Row convention (what the reopen ingestion will produce; fixtures
already carry it): plain dicts with `asum` (exact key string),
`price` (EUR asking), `area_m2`, optionally `price_per_m2` (wins when
finite and > 0). Non-positive / non-finite / missing prices never
enter a median pool.

Style mirrors dims_p4_own_store.py (#243/#327): pure, offline, no
network, no livability/sibling imports. Reasons are Estonian, say
"hinnang" for estimates and "EI OLE" + missing input + buyer check
for NULLs.
"""

from __future__ import annotations

import math
import statistics
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[float], str]  # (median EUR/m2 | None, Estonian reason)

# Minimum snapshots per asum for an honest median (see docstring).
# Byte parity with ASUMEDIA_MIN_N in apps/web/lib/layers_asumedia.ts.
MIN_N = 5


def _eur_m2(row: dict) -> Optional[float]:
    """EUR/m2 asking for one snapshot row (None when unusable)."""
    ppm = row.get("price_per_m2")
    if isinstance(ppm, bool):
        return None
    if isinstance(ppm, (int, float)) and ppm is not None:
        try:
            value = float(ppm)
        except (TypeError, ValueError):
            value = None
        if value is not None and math.isfinite(value) and value > 0:
            return value
    try:
        price = float(row.get("price"))
        area = float(row.get("area_m2"))
    except (TypeError, ValueError):
        return None
    if (math.isfinite(price) and math.isfinite(area)
            and price > 0 and area > 0):
        return price / area
    return None


def _asum_key(row: dict) -> Optional[str]:
    """Exact asum join key (None when absent — never guessed from text)."""
    asum = row.get("asum")
    if not isinstance(asum, str) or not asum.strip():
        return None
    return asum.strip()


def group_by_asum(rows: List[dict]) -> Tuple[Dict[str, List[float]], int]:
    """Group usable EUR/m2 values by exact asum key.

    Returns (groups, skipped): skipped counts rows with no join key or
    no usable price (reported, never silently dropped).
    """
    groups: Dict[str, List[float]] = {}
    skipped = 0
    for row in rows:
        if not isinstance(row, dict):
            skipped += 1
            continue
        key = _asum_key(row)
        value = _eur_m2(row)
        if key is None or value is None:
            skipped += 1
            continue
        groups.setdefault(key, []).append(value)
    return groups, skipped


def describe_asum(asum: str, values: List[float],
                 min_n: int = MIN_N) -> Score:
    """(median EUR/m2 | None, Estonian reason) for one asum's group.

    Thin groups (< min_n) stay NULL with their n labeled — never a
    faked median. A single snapshot never sets a "median" (tehingud
    MIN_COMPS precedent).
    """
    n = len(values)
    if n < min_n:
        return None, (
            "Asumi \"%s\" küsi-mediaani hinnang puudub (EI OLE piisavalt "
            "oma snapshotte): %d snapshotti, vaja vähemalt %d — oota "
            "päevase korje kogunemist, ära feigi ühe kuulutuse hinnast "
            "asumi taset" % (asum, n, min_n))
    median = statistics.median(sorted(values))
    return median, (
        "Asumi \"%s\" küsi-mediaani hinnang: %.0f €/m² (%d oma snapshotti, "
        "küsi-, mitte sulgunud tehinguhind — võrdle maakleri tehingutega, "
        "ära loe garantiiks" % (asum, median, n))


def describe_store(rows: List[dict], min_n: int = MIN_N) -> Dict[str, Score]:
    """Whole-store medians: asum -> (median | None, reason).

    Every grouped asum appears (thin ones as labeled NULLs); keyless or
    priceless rows are skipped (count available via group_by_asum).
    """
    groups, _skipped = group_by_asum(rows)
    return {asum: describe_asum(asum, values, min_n)
            for asum, values in sorted(groups.items())}
