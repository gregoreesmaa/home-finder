"""Verdict carrier for #697 RIK KU financials probe (PROBE, not build)."""

#: Machine-checkable verdict. `kind` is one of "negative" | "positive".
#: `checked` is ISO date. `follow_up` names the scoped build issue when positive.
RIK_VERDICT = {
    "kind": "negative",  # or "positive" with evidence below
    "checked": "2026-09-19",
    "source": "polite catalogue/docs inspection (/tmp only)",
    "note": "No keyless bulk KU financials on avaandmed.rik.ee; no CKAN "
            "API, catalogue moved to interactive document register. No "
            "filing scraping per probe scope.",
    "follow_up": None,
}
