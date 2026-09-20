# pole/manifest.sh — single-source pole code inventory (issue #806).
#
# Sourced by pole/bootstrap.sh (fresh-Pi setup) and pole/bin/pole-sync.sh
# (hourly auto-sync) so both deploy exactly the same files. Add a dataset
# here once: both paths pick it up, and tests/test_replica.py fails if a
# listed module does not exist in the repo.
#
# Code ONLY — cache/built/state/logs are pole-side data and are never
# listed here (sync touches code, never data).

# Explicit harvester manifest (was audited 2026-09-19, issue #767).
HARVESTERS="batch_datex_cameras batch_datex_counters batch_datex_restrictions
  batch_datex_srti batch_datex_truckpark batch_datex_weather
  batch_delay_sampler batch_fixit batch_medre batch_medre_ads
  batch_mobile_import batch_outage batch_poi batch_tomtom_evpois
  batch_tomtom_flow batch_tomtom_geocode batch_tomtom_incidents
  batch_tomtom_isochrones batch_tomtom_matrix batch_tomtom_parking
  batch_viirs"
DIMS="dims_p4_fixit dims_p4_gtfsstops dims_p4_medre dims_p4_poi
  dims_p4_typical_delay dims_tomtom_evpois dims_tomtom_flow
  dims_tomtom_geocode dims_tomtom_incidents dims_tomtom_isochrones
  dims_tomtom_matrix dims_tomtom_parking"
