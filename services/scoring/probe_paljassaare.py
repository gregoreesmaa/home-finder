"""Verdict carrier for #710 Paljassaare odor probe (PROBE, not build)."""

#: Machine-checkable verdict. `kind` is one of "negative" | "positive".
#: `checked` is ISO date. `follow_up` names the scoped build issue when positive.
PALJASSAARE_VERDICT = {
    "kind": "negative",  # or "positive" with evidence below
    "checked": "2026-09-19",
    "source": "EIA docs search + polite catalogue check (/tmp only)",
    "note": "No keyless machine-readable odor-footprint zone map found; "
            "footprint lives inside EIA PDFs only.",
    "follow_up": None,
}
