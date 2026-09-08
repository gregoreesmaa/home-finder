"""Pytest bootstrap: make `import app` / `import adapters.*` work.

The suite is invoked from the repo root (`npm run test:python`, CI),
so the scoring service directory is not on sys.path by default.
Inserting it here keeps the root-level invocation green without
depending on the caller's working directory.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
