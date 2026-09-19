"""Verdict carrier for #694 Tallinna Vesi zones probe (PROBE, not build)."""

#: Machine-checkable verdict. `kind` is one of "negative" | "positive".
#: `checked` is ISO date. `follow_up` names the scoped build issue when positive.
WATER_VERDICT = {
    "kind": "negative",  # or "positive" with evidence below
    "checked": "2026-09-19",
    "source": "polite catalogue/docs inspection (/tmp only)",
    "note": "No keyless hardness/quality zones per district; quality page "
            "is a city-wide HTML explainer with sampling-point list only, "
            "no CSV/JSON/WMS export.",
    "follow_up": None,
}
