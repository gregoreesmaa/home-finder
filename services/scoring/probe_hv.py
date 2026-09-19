"""Verdict carrier for #698 Elering HV geography probe (PROBE, not build)."""

#: Machine-checkable verdict. `kind` is one of "negative" | "positive".
#: `checked` is ISO date. `follow_up` names the scoped build issue when positive.
HV_VERDICT = {
    "kind": "negative",  # or "positive" with evidence below
    "checked": "2026-09-19",
    "source": "polite catalogue/docs inspection (/tmp only)",
    "note": "No keyless Elering network geography found; e-Gridmap is an "
            "interactive connection app behind login, map host fails DNS "
            "from probe network (needs second-network confirmation).",
    "follow_up": None,
}
