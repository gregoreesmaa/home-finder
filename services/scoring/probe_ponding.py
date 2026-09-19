"""Verdict carrier for #706 ponding probe (PROBE, not build)."""

#: Machine-checkable verdict. `kind` is one of "negative" | "positive".
#: `checked` is ISO date. `follow_up` names the scoped build issue when positive.
PONDING_VERDICT = {
    "kind": "negative",  # or "positive" with evidence below
    "checked": "2026-09-19",
    "source": "polite catalogue/docs inspection (/tmp only)",
    "note": "No keyless machine-readable cloudburst ponding map found; "
            "guessed city catalogue URLs absent, no WMS/WFS layer refs.",
    "follow_up": None,
}
