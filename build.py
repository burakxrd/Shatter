"""build.py — Build Shatter portable executable.

Usage:
    python build.py          Build portable folder (dist/Shatter/)
    python build.py --zip    Build + create .zip archive

Requires:
    pip install pyinstaller
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DIST_DIR = ROOT / "dist"
OUTPUT_NAME = "Shatter"


def build():
    """Run PyInstaller with the spec file."""
    print("[*] Building Shatter portable...")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        str(ROOT / "shatter.spec"),
        "--noconfirm",
        "--clean",
    ]

    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        print("[!] Build failed!")
        sys.exit(1)

    output_dir = DIST_DIR / OUTPUT_NAME
    if not output_dir.is_dir():
        print(f"[!] Expected output not found: {output_dir}")
        sys.exit(1)

    # Create temp directory in the output (portable needs it)
    (output_dir / "temp").mkdir(exist_ok=True)

    print(f"[+] Build complete: {output_dir}")
    return output_dir


def create_zip(output_dir: Path):
    """Create a .zip archive of the portable build."""
    zip_path = DIST_DIR / OUTPUT_NAME
    print(f"[*] Creating {zip_path}.zip...")
    shutil.make_archive(str(zip_path), "zip", str(DIST_DIR), OUTPUT_NAME)
    print(f"[+] Archive: {zip_path}.zip")


def main():
    output_dir = build()

    if "--zip" in sys.argv:
        create_zip(output_dir)

    print()
    print("[+] Portable folder: dist/Shatter/")
    print("    -> Zip it and distribute. Users run Shatter.exe directly.")
    print("    -> Hashcat/JtR can be downloaded from within the app.")


if __name__ == "__main__":
    main()
