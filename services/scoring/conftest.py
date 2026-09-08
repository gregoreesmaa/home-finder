"""Pytest bootstrap: let tests import `app`/`adapters` however pytest is invoked.

AGENTS.md §6 documents `python3 -m pytest services/scoring/tests -q` from the
repo root; without this, that invocation fails with ModuleNotFoundError and
only in-service-dir runs collect. Inserting this directory keeps both working.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
