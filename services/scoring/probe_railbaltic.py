"""Verdict carrier for #704 Rail Baltica corridor probe (PROBE, not build).

VERIFY step (2026-09-19): what plans/notices already hold for a
Tallinn works-corridor layer (construction nuisance today +
station-access premium tomorrow)? Verdict: NEGATIVE — real RB
planning activity exists in Ametlikud Teadaanded, but nothing
Tallinn-joinable verifies (see docs/p4_railbaltic.md inventory).
"""

#: Machine-checkable verdict. `kind` is one of "negative" | "positive".
#: `checked` is ISO date. Counts are measured from the live
#: planeeringud list window (1001 rows, 2026-09-19, /tmp only).
RAILBALTIC_VERDICT = {
    "kind": "negative",
    "checked": "2026-09-19",
    "source": "polite AT planeeringud list pull (/tmp/hf704_at only, "
               "UA home-finder-research/0.1, paced, 429=stop) + code-read "
               "of dims_p4_rb / dims_p4_cityplans / dims_p4_notices "
               "bulk-URL holdings (no new requests)",
    "notices_window": 1001,
    "rb_notices": 2,
    "rb_notice_ids": ["2541352", "2490346"],
    "tallinn_rb_notices": 0,
    "note": "2 Rail Baltic detailplaneering notices verify live "
            "(Assaku peatus kehtestatud, Muuga depoo algatatud — both "
            "outside Tallinn, free-text tunnus only) + 1 MKM "
            "eriplaneering touching the RB corridor; zero Tallinn "
            "corridor rows, zero machine-joinable corridor geometry. "
            "RB/cityplans/notices bulk holdings all still None. "
            "No corridor layer on this — free-text parcels outside "
            "Tallinn cannot score Tallinn addresses.",
    "follow_up": None,
}
