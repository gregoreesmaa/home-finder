"""Verdict carrier for #690 lasteaia-queue probe (PROBE, not build)."""

#: Machine-checkable verdict. `kind` is one of "negative" | "positive".
#: `checked` is ISO date. `follow_up` names the scoped build issue when positive.
QUEUE_VERDICT = {
    "kind": "negative",
    "checked": "2026-09-19",
    "source": "polite Tallinn + Harno page inspection (/tmp only): "
               "queues behind self-service auth",
    "note": "No keyless machine-readable queue lengths. Tallinn lasteaed "
            "info page (200, 85KB) has zero 'jarjekord' mentions; "
            "applications run through authenticated self-service "
            "(teatmik.haridus.ee/self-service/). Harno directory "
            "teatmik.haridus.ee/lasteaiad/ (200, 39KB) is a JS-driven "
            "listing (KindergartensController) with a vacantSpots filter "
            "but no static per-kindergarten queue data; its "
            "/lasteaiad/vacant-spots route 301s back to the same JS "
            "listing. Queue positions are per-child personal data by "
            "design (stays out). Guessed taotlus.tallinn.ee did not "
            "resolve (single-network DNS evidence, needs review-time "
            "second-network confirmation).",
    "follow_up": None,
}
