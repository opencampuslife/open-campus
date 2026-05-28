"""P2-B conftest: inject heart package onto sys.path for all test modules."""

from __future__ import annotations

import sys
from pathlib import Path

_HEART_SRC = Path(__file__).resolve().parents[2] / "src" / "heart"
if str(_HEART_SRC.parent) not in sys.path:
    sys.path.insert(0, str(_HEART_SRC.parent))