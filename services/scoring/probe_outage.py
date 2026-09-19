"""Verdict carrier for #689 Elektrilevi outage probe (PROBE, not build)."""

#: Machine-checkable verdict. `kind` is one of "negative" | "positive".
#: `checked` is ISO date. `follow_up` names the scoped build issue when positive.
OUTAGE_VERDICT = {
    "kind": "positive",
    "checked": "2026-09-19",
    "source": "polite rikkekaart shell + endpoint inspection (/tmp only): "
               "keyless live outage JSON",
    "note": "Keyless live outage feed confirmed: the rikkekaart JS shell "
            "names geoserver-api/GetApplicationData, and a single polite "
            "GET returns HTTP 200, ~130KB JSON (double-encoded: "
            "scopes.p.{areas,dynareas,outages}, 99 areas incl. Harju "
            "maakond with live counters). No login. Companion endpoints "
            "for the build: GetObjectsByTiles, GetNetworkObjects, "
            "content/StaticObjects.",
    "follow_up": 729,
}
