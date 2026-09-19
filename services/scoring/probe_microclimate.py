"""Verdict carrier for #661 microclimate-grid probe (PROBE, not build)."""

#: Machine-checkable verdict. `kind` is one of "negative" | "positive".
#: `checked` is ISO date. `follow_up` names the scoped build issue when positive.
MICROCLIMATE_VERDICT = {
    "kind": "negative",
    "checked": "2026-09-19",
    "source": "polite source inspection (/tmp only): UrbClim city list "
               "has no Tallinn; Copernicus distribution is account-walled",
    "note": "No keyless modelled microclimate grid for Tallinn. VITO's "
            "published UrbClim city list (Almada, Antwerp, Barcelona, "
            "Berlin, Bern, Bilbao, Brussels, Delhi, Ghent, Hasselt, "
            "London, Paris, Prague, Rome, Skopje, Tilburg, Vienna) has "
            "no Tallinn; the 100-city Copernicus UrbClim archive is "
            "distributed via the Climate Data Store, which requires an "
            "account (keyful). www.urbclim.eu and uhi.yale.edu did not "
            "resolve on this network (single-network DNS evidence, "
            "needs review-time second-network confirmation). The honest "
            "coarse signal stays the 3-station normals cells "
            "(Harku/Pakri/Kuusiku, never interpolated).",
    "follow_up": None,
}
