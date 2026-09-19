"""Verdict carrier for #696 STR density probe (PROBE, not build)."""

#: Machine-checkable verdict. `kind` is one of "negative" | "positive".
#: `checked` is ISO date. `follow_up` names the scoped build issue when positive.
STR_VERDICT = {
    "kind": "negative",  # or "positive" with evidence below
    "checked": "2026-09-19",
    "source": "polite city-list inspection (/tmp only)",
    "note": "No Tallinn dump on InsideAirbnb city list; nearest covered "
            "city is Riga. Zero Tallinn/Estonia mentions.",
    "follow_up": None,
}
