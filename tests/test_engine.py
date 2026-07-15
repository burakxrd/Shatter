"""tests/test_engine.py — Unit tests for engine command building."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from core.engine import HashcatEngine


class TestBuildHashcatCmd:
    """Tests for HashcatEngine._build_hashcat_cmd()."""

    def _base_settings(self, **overrides) -> dict:
        defaults = {
            "device": "1",
            "attack_mode": "0",
            "workload_profile": "2",
            "optimized_kernel": False,
            "session_name": "",
            "hwmon_temp_abort": "90",
            "disable_potfile": False,
            "skip": "",
            "limit": "",
            "wordlist": "C:/wordlists/rockyou.txt",
            "mask": "",
            "rules": [],
        }
        defaults.update(overrides)
        return defaults

    def test_basic_wordlist(self, engine):
        cmd = engine._build_hashcat_cmd("0", self._base_settings())
        assert "-a" in cmd
        assert "0" in cmd[cmd.index("-a") + 1]
        assert "-m" in cmd
        assert "C:/wordlists/rockyou.txt" in cmd

    def test_mask_mode(self, engine):
        cmd = engine._build_hashcat_cmd("0", self._base_settings(
            attack_mode="3", mask="?a?a?a?a", wordlist=""
        ))
        assert "-a" in cmd and cmd[cmd.index("-a") + 1] == "3"
        assert "?a?a?a?a" in cmd

    def test_hybrid_mode6(self, engine):
        cmd = engine._build_hashcat_cmd("1000", self._base_settings(
            attack_mode="6", mask="?d?d?d"
        ))
        assert "-a" in cmd and cmd[cmd.index("-a") + 1] == "6"
        # Mode 6: wordlist first, then mask
        wl_idx = cmd.index("C:/wordlists/rockyou.txt")
        mask_idx = cmd.index("?d?d?d")
        assert wl_idx < mask_idx

    def test_hybrid_mode7(self, engine):
        cmd = engine._build_hashcat_cmd("1000", self._base_settings(
            attack_mode="7", mask="?d?d?d"
        ))
        # Mode 7: mask first, then wordlist
        wl_idx = cmd.index("C:/wordlists/rockyou.txt")
        mask_idx = cmd.index("?d?d?d")
        assert mask_idx < wl_idx

    def test_multi_rule(self, engine):
        cmd = engine._build_hashcat_cmd("0", self._base_settings(
            rules=["best64.rule", "toggles.rule"]
        ))
        r_indices = [i for i, x in enumerate(cmd) if x == "-r"]
        assert len(r_indices) == 2
        assert cmd[r_indices[0] + 1] == "best64.rule"
        assert cmd[r_indices[1] + 1] == "toggles.rule"

    def test_single_rule_backward_compat(self, engine):
        cmd = engine._build_hashcat_cmd("0", self._base_settings(rule="old.rule"))
        assert "-r" in cmd
        assert "old.rule" in cmd

    def test_optimized_kernel(self, engine):
        cmd = engine._build_hashcat_cmd("0", self._base_settings(optimized_kernel=True))
        assert "-O" in cmd

    def test_session(self, engine):
        cmd = engine._build_hashcat_cmd("0", self._base_settings(session_name="test_session"))
        assert "--session" in cmd
        assert "test_session" in cmd

    def test_disable_potfile(self, engine):
        cmd = engine._build_hashcat_cmd("0", self._base_settings(disable_potfile=True))
        assert "--potfile-disable" in cmd

    def test_status_timer(self, engine):
        cmd = engine._build_hashcat_cmd("0", self._base_settings())
        assert "--status" in cmd
        assert "--status-timer=2" in cmd

    def test_hash_file_path(self, engine):
        cmd = engine._build_hashcat_cmd("0", self._base_settings(
            hash_file_path="C:/hashes/dump.txt"
        ))
        assert "C:/hashes/dump.txt" in cmd

    def test_custom_charset(self, engine):
        cmd = engine._build_hashcat_cmd("0", self._base_settings(
            custom_charset_1="?l?d"
        ))
        assert "-1" in cmd
        assert "?l?d" in cmd

    def test_skip_and_limit(self, engine):
        cmd = engine._build_hashcat_cmd("0", self._base_settings(skip="100", limit="500"))
        assert "-s" in cmd and "100" in cmd
        assert "--limit" in cmd and "500" in cmd


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
