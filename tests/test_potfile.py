"""tests/test_potfile.py — Unit tests for potfile parsing."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from ui.potfile import _parse_potfile


@pytest.fixture
def sample_potfile(tmp_path) -> Path:
    """Create a sample potfile for testing."""
    f = tmp_path / "test.potfile"
    f.write_text(
        "5f4dcc3b5aa765d61d8327deb882cf99:password\n"
        "a4f49c406510bdcab6824ee7c30fd852:admin123\n"
        "aabb*ccdd*eeff*TestNet:hunter42\n"
        "\n"
        "onlyhash_no_colon\n",
        encoding="utf-8",
    )
    return f


class TestParsePotfile:

    def test_basic_parsing(self, sample_potfile):
        entries = _parse_potfile(sample_potfile)
        assert len(entries) == 4  # 4 non-empty lines

    def test_password_extraction(self, sample_potfile):
        entries = _parse_potfile(sample_potfile)
        passwords = [p for _, p in entries]
        assert "password" in passwords
        assert "admin123" in passwords
        assert "hunter42" in passwords

    def test_hash_extraction(self, sample_potfile):
        entries = _parse_potfile(sample_potfile)
        assert entries[0][0] == "5f4dcc3b5aa765d61d8327deb882cf99"

    def test_complex_hash_with_colons(self, sample_potfile):
        """Hash with multiple colons — password is always last field."""
        entries = _parse_potfile(sample_potfile)
        assert entries[2][1] == "hunter42"

    def test_no_colon_line(self, sample_potfile):
        entries = _parse_potfile(sample_potfile)
        no_colon = [e for e in entries if e[1] == "???"]
        assert len(no_colon) == 1

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.potfile"
        f.write_text("", encoding="utf-8")
        assert _parse_potfile(f) == []

    def test_missing_file(self, tmp_path):
        f = tmp_path / "nope.potfile"
        assert _parse_potfile(f) == []

    def test_blank_lines_skipped(self, tmp_path):
        f = tmp_path / "blanks.potfile"
        f.write_text("\n\n\nhash:pw\n\n", encoding="utf-8")
        entries = _parse_potfile(f)
        assert len(entries) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
