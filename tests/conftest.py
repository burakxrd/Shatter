"""tests/conftest.py — Shared test configuration.

Sets up a mock HashcatEngine instance so engine tests can build commands
without needing real hashcat/jtr installations.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Configure mock tool paths BEFORE any engine import
from core import tool_paths
tool_paths.hashcat_exe = Path("C:/hashcat/hashcat.exe")
tool_paths.hashcat_dir = Path("C:/hashcat")
tool_paths.jtr_dir = Path("C:/john/run")

import pytest
from core.engine import HashcatEngine


@pytest.fixture
def engine() -> HashcatEngine:
    """Create a HashcatEngine with mock paths for testing."""
    return HashcatEngine(
        hashcat_exe=Path("C:/hashcat/hashcat.exe"),
        hashcat_dir=Path("C:/hashcat"),
        jtr_dir=Path("C:/john/run"),
    )
