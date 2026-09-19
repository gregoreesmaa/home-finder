"""Verdict carrier for #699 VIIRS light-pollution probe (PROBE, not build)."""

#: Machine-checkable verdict. `kind` is one of "negative" | "positive".
#: `checked` is ISO date. `follow_up` names the scoped build issue when positive.
VIIRS_VERDICT = {
    "kind": "positive",
    "checked": "2026-09-19",
    "source": "polite WMTS inspection (/tmp only): NASA GIBS keyless, "
               "EOG downloads login-walled",
    "note": "Keyless VIIRS night-lights tiles confirmed: GIBS WMTS layer "
            "VIIRS_Black_Marble, tile z8 y75 x145 over Tallinn -> HTTP 200, "
            "55KB PNG, no login. EOG (eogdata.mines.edu) downloads 302 to "
            "OAuth login -> keyful, not used.",
    "follow_up": 719,
}
