"""Test bootstrap for the repository's src-layout packages."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "iot-streaming-mock"):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)
