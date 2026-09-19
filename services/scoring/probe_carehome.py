"""Verdict carrier for #709 care-home probe (PROBE, not build)."""

#: Machine-checkable verdict. `kind` is one of "negative" | "positive".
#: `checked` is ISO date. `follow_up` names the scoped build issue when positive.
CAREHOME_VERDICT = {
    "kind": "negative",  # or "positive" with evidence below
    "checked": "2026-09-19",
    "source": "polite catalogue/docs inspection (/tmp only)",
    "note": "No keyless machine-readable care-home provider list found; "
            "MTR register is interactive HTML search only, open-data API path moved.",
    "follow_up": None,
}
