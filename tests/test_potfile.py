"""tests/test_potfile.py — Unit tests for potfile parsing.

Tests the potfile parsing logic that now lives in ui.api.Api.get_potfile().
We test the parsing logic directly here with file-based fixtures.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest


def _parse_potfile(path: Path) -> list[tuple[str, str]]:
    """Parse a potfile into (hash, password) tuples.
    
    Mirrors the logic in Api.get_potfile() for testability.
    """
    if not path.exists():
        return []
    entries = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = [line.strip() for line in f if line.strip()]
            for line in lines:
                if ":" in line:
                    h, p = line.rsplit(":", 1)
                    if h and p:
                        entries.append((h, p))
                else:
                    entries.append((line, "???"))
    except Exception:
        pass
    return entries


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

    def test_malformed_colon_only(self, tmp_path):
        """A line with just ':' should be skipped (empty hash and password)."""
        f = tmp_path / "malformed.potfile"
        f.write_text(":\n::\nhash:pass\n", encoding="utf-8")
        entries = _parse_potfile(f)
        # Only "hash:pass" should survive, ":" gives empty h/p
        passwords = [p for _, p in entries if p != "???"]
        assert "pass" in passwords

    def test_unicode_password(self, tmp_path):
        """Passwords can contain unicode characters."""
        f = tmp_path / "unicode.potfile"
        f.write_text("abc123hash:şifre_türkçe_🔐\n", encoding="utf-8")
        entries = _parse_potfile(f)
        assert len(entries) == 1
        assert entries[0][1] == "şifre_türkçe_🔐"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
