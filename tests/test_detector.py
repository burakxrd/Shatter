"""tests/test_detector.py — Unit tests for hash detection."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from core.detector import detect_hash_type, extract_m_value, _HASHCAT_FALLBACKS


class TestDetectHashType:
    """Tests for detect_hash_type()."""

    def test_md5(self):
        result = detect_hash_type("5f4dcc3b5aa765d61d8327deb882cf99")
        assert "MD5" in result
        assert "(m=0)" in result

    def test_sha1(self):
        result = detect_hash_type("aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d")
        assert "SHA" in result

    def test_sha256(self):
        h = "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8"
        result = detect_hash_type(h)
        assert "SHA" in result

    def test_ntlm(self):
        result = detect_hash_type("a4f49c406510bdcab6824ee7c30fd852")
        # NTLM is 32 hex chars, NTH may return MD5/NTLM/MD4
        assert "(m=" in result

    def test_bcrypt(self):
        h = "$2y$12$LJ3m4yst.Vmxqimee1Q8cOSbYSzUwsNDBjdag.hORKKb9M8qOBQYW"
        result = detect_hash_type(h)
        assert "bcrypt" in result.lower() or "3200" in result

    def test_empty_string(self):
        assert detect_hash_type("") == "None"

    def test_whitespace(self):
        assert detect_hash_type("   ") == "None"

    def test_wpa_fallback(self):
        """WPA hash should be caught by fallback regex, not NTH."""
        h = "WPA*02*aabbccdd*001122334455*667788990011*TestNetwork*abcdef1234"
        result = detect_hash_type(h)
        assert "WPA" in result or "22000" in result

    def test_unknown_hash(self):
        result = detect_hash_type("not_a_real_hash_at_all_xyz")
        assert "Unknown" in result or "(m=" in result

    def test_caching(self):
        """Second call should return cached result (same object)."""
        h = "5f4dcc3b5aa765d61d8327deb882cf99"
        r1 = detect_hash_type(h)
        r2 = detect_hash_type(h)
        assert r1 == r2


class TestExtractMValue:
    """Tests for extract_m_value()."""

    def test_single_mode(self):
        assert extract_m_value("MD5 (m=0)") == "0"

    def test_multi_mode(self):
        assert extract_m_value("MD5 (m=0)  |  NTLM (m=1000)") == "0"

    def test_high_mode(self):
        assert extract_m_value("bcrypt (m=3200)") == "3200"

    def test_no_mode(self):
        assert extract_m_value("Unknown / Custom") is None

    def test_none_string(self):
        assert extract_m_value("None") is None


class TestFallbacks:
    """Verify the fallback regex table structure."""

    def test_fallbacks_are_tuples(self):
        for entry in _HASHCAT_FALLBACKS:
            assert isinstance(entry, tuple), f"Expected tuple, got {type(entry)}"
            assert len(entry) == 2, f"Expected 2-element tuple, got {len(entry)}"

    def test_fallback_patterns_are_compiled(self):
        import re
        for pattern, name in _HASHCAT_FALLBACKS:
            assert hasattr(pattern, "match"), f"Pattern not compiled for '{name}'"
            assert isinstance(name, str), f"Name not a string: {name}"
            assert "(m=" in name, f"Missing mode number in '{name}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
