"""
build_windows_dist.py

Automates compiling DevCache Guardian to a standalone Windows executable
and packaging it into a distribution-ready zip file for GitHub Releases.

Usage:
    python build_windows_dist.py
"""
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

VERSION = "1.0.0"
APP_NAME = "DevCacheGuardian"

def main():
    root = Path(__file__).parent.resolve()
    os.chdir(root)

    print("==================================================")
    print(f"  Building {APP_NAME} v{VERSION} for Windows x64")
    print("==================================================")

    # 1. Clean previous build artifacts
    for d in ["build", "dist"]:
        p = root / d
        if p.exists():
            print(f"Cleaning {d}/ directory...")
            shutil.rmtree(p, ignore_errors=True)

    # 2. Run PyInstaller with build.spec
    print("\n[1/3] Running PyInstaller...")
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "build.spec"]
    ret = subprocess.run(cmd)
    if ret.returncode != 0:
        print("\n[ERROR] PyInstaller compilation failed.")
        sys.exit(1)

    exe_path = root / "dist" / f"{APP_NAME}.exe"
    if not exe_path.exists():
        print(f"\n[ERROR] Output executable not found at: {exe_path}")
        sys.exit(1)

    exe_size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f"[OK] Successfully built: {exe_path} ({exe_size_mb:.1f} MB)")

    # 3. Create distribution zip
    zip_name = f"{APP_NAME}-v{VERSION}-windows-x64.zip"
    zip_path = root / "dist" / zip_name
    print(f"\n[2/3] Packaging into {zip_name}...")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(exe_path, arcname=f"{APP_NAME}.exe")
        if (root / "README.md").exists():
            zf.write(root / "README.md", arcname="README.md")
        if (root / "LICENSE").exists():
            zf.write(root / "LICENSE", arcname="LICENSE")

    zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"[OK] Archive created: {zip_path} ({zip_size_mb:.1f} MB)")

    # 4. Summary
    print("\n[3/3] Build Complete!")
    print("--------------------------------------------------")
    print(f" Standalone Exe : dist/{APP_NAME}.exe")
    print(f" Release Archive: dist/{zip_name}")
    print("--------------------------------------------------")
    print("You can upload both files to your GitHub Release.")

if __name__ == "__main__":
    main()
