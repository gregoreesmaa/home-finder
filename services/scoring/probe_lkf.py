"""Verdict carrier for #708 LKF probe (PROBE, not build)."""

#: Machine-checkable verdict. `kind` is one of "negative" | "positive".
#: `checked` is ISO date. `follow_up` names the scoped build issue when positive.
LKF_VERDICT = {
    "kind": "negative",  # or "positive" with evidence below
    "checked": "2026-09-19",
    "source": "polite catalogue/docs inspection (/tmp only)",
    "note": "No keyless machine-readable sub-county claim stats found; "
            "LKF statistics page links PDFs only, no CSV/JSON export.",
    "follow_up": None,
}
