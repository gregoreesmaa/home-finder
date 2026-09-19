"""Verdict carrier for #693 Ookla speed-tile probe (PROBE, not build)."""

#: Machine-checkable verdict. `kind` is one of "negative" | "positive".
#: `checked` is ISO date. `follow_up` names the scoped build issue when positive.
OOKLA_VERDICT = {
    "kind": "positive",
    "checked": "2026-09-19",
    "source": "polite S3 keyless-listing inspection (/tmp only): "
               "ookla-open-data bucket, CC BY-NC-SA 4.0",
    "note": "Keyless quarterly fixed-performance tiles confirmed: S3 "
            "list-type=2 on s3://ookla-open-data/shapefiles/performance/ "
            "type=fixed/ -> years 2019-2026, latest 2026-Q2 "
            "(2026-04-01_performance_fixed_tiles.zip, ~343MB, HEAD 200, "
            "Last-Modified 2026-08-19). No login anywhere. License is "
            "CC BY-NC-SA 4.0 (non-commercial) per the AWS registry page.",
    "follow_up": 725,
}
