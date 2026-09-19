"""Joint livability x price score (issue #701).

The stack holds the two halves separately: livability 0..100 from
`livability.combine` (weight-renormalized mean over available dims) and
price fairness as `discount_pct` (% below predicted market, POSITIVE =
steal) in `app.py` / `packages/shared/src/ranking.ts`. The canonical
ranker is `app.combined_score(livability 0..100, discount_pct)` ==
TS `combinedScore`, both 0.6 livability / 0.4 deal (deal mapped through
`deal_norm`, discount [-15, +25] -> [0, 1]).

`joint_score` is the analytic twin for area/flat comparison: it takes
both halves PRE-NORMALIZED to 0..100 — {"liv": 0..100, "price": 0..100}
where price = deal_norm(discount_pct) * 100 — and combines them with
the same 0.6/0.4 weights, so it agrees with the canonical ranker
exactly (pinned by test). Raw discount_pct must NOT be passed as
"price": deal_norm clamps everything above +25 to 1.0, which would hide
the best-half signal the test guards against (documented, not silently
remapped — passing a second scale through one parameter name would be
fake precision).

No harvest, no network: pure function, hermetic tests. Estonian
reasons are the caller's job (this returns the number only); the API
and UI already label combined as "hinnang".
"""

from typing import Dict

#: Canonical weights, parity with app.combined_score / TS combinedScore.
LIV_WEIGHT = 0.6
PRICE_WEIGHT = 0.4


def _clamp100(v: float) -> float:
    """Clamp one 0..100 half (mirrors deal_norm clamping honesty)."""
    return min(100.0, max(0.0, float(v)))


def joint_score(d: Dict[str, float]) -> int:
    """Joint 0..100 score: balanced flats beat best-single-half flats.

    d = {"liv": livability 0..100, "price": price-fairness 0..100}.
    Linear 0.6/0.4 so a flat at 75/75 outranks 90/40 and 40/90 —
    the issue's "best flat, not best halves".
    """
    liv = _clamp100(d["liv"])
    price = _clamp100(d["price"])
    return int(round(100 * (LIV_WEIGHT * liv / 100.0 + PRICE_WEIGHT * price / 100.0)))
