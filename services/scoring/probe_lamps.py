"""Verdict carrier for #707 lamp probe (PROBE, not build)."""

#: Machine-checkable verdict. `kind` is one of "negative" | "positive".
#: `checked` is ISO date. `follow_up` names the scoped build issue when positive.
LAMPS_VERDICT = {
    "kind": "negative",  # or "positive" with evidence below
    "checked": "2026-09-19",
    "source": "polite catalogue/docs inspection (/tmp only)",
    "note": "No keyless machine-readable lamp-location layer found; "
            "city map is a JS app shell with no static WMS/WFS layer refs.",
    "follow_up": None,
}
