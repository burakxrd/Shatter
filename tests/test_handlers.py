"""tests/test_handlers.py — Unit tests for progress parsing regex."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from ui.handlers import _RE_PROGRESS, _RE_ETA


class TestProgressRegex:

    def test_basic_progress(self):
        line = "Progress.........: 1234/5678 (21.73%)"
        m = _RE_PROGRESS.search(line)
        assert m is not None
        assert float(m.group(1)) == pytest.approx(21.73)

    def test_100_percent(self):
        line = "Progress.........: 99999/99999 (100.00%)"
        m = _RE_PROGRESS.search(line)
        assert m is not None
        assert float(m.group(1)) == 100.0

    def test_zero_percent(self):
        line = "Progress.........: 0/99999 (0.00%)"
        m = _RE_PROGRESS.search(line)
        assert m is not None
        assert float(m.group(1)) == 0.0

    def test_no_match(self):
        line = "Speed.#1.........:  1234.5 MH/s"
        assert _RE_PROGRESS.search(line) is None


class TestETARegex:

    def test_time_format(self):
        line = "Time.Estimated...: Sat May 10 23:59:59 2025 (0 secs)"
        m = _RE_ETA.search(line)
        assert m is not None
        assert "0 secs" in m.group(1)

    def test_longer_eta(self):
        line = "Time.Estimated...: Sun May 11 02:30:00 2025 (2 hours, 30 mins)"
        m = _RE_ETA.search(line)
        assert m is not None
        assert "2 hours" in m.group(1)

    def test_no_match(self):
        line = "Recovered........: 0/1 (0.00%)"
        assert _RE_ETA.search(line) is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
