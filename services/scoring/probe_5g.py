"""Verdict carrier for #691 per-operator 5G probe (PROBE, not build)."""

#: Machine-checkable verdict. `kind` is one of "negative" | "positive".
#: `checked` is ISO date. `follow_up` names the scoped build issue when positive.
COVERAGE5G_VERDICT = {
    "kind": "negative",
    "checked": "2026-09-19",
    "source": "polite operator + TTJA page inspection (/tmp only): "
               "no keyless polygons/WMS",
    "note": "No keyless per-operator 5G coverage polygons found. Telia "
            "guessed paths (/era/abi-ja-tugi/leviala, /leviala) -> 404; "
            "Elisa /leviala/ -> 404; Tele2 tele2.ee/leviala -> 200 but a "
            "marketing CMS page whose map is one JS-driven "
            "'network_outage' widget (no iframe, no WMS/GeoJSON/API "
            "endpoint in static HTML or __NEXT_DATA__); TTJA ttja.ee has "
            "only a regulatory 5G page and a netikaart page whose "
            "'Interaktiivne kaart' is an unrelated Rail Baltica viewer. "
            "No operator WMS/GeoJSON anywhere in the static surface.",
    "follow_up": None,
}
