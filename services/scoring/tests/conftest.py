"""Make `pytest services/scoring/tests` work from the repo root.

Tests import `app` top-level (same layout `uvicorn --app-dir` expects);
this inserts the service dir on `sys.path` for the test session only.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
