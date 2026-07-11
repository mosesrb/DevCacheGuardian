@echo off
chcp 65001 >nul
:: ╔══════════════════════════════════════════════════════════════════════════╗
:: ║  DevCache Guardian — Developer Storage Intelligence Platform  v9        ║
:: ║  Double-click this file to launch the application.                      ║
:: ║  Python 3.12+ is required.                                              ║
:: ╚══════════════════════════════════════════════════════════════════════════╝
setlocal EnableDelayedExpansion

title DevCache Guardian

:: ── Resolve script directory ──────────────────────────────────────────────
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

echo.
echo  ╔════════════════════════════════════════════════════╗
echo  ║   DevCache Guardian  v9                            ║
echo  ║   Developer Storage Intelligence Platform          ║
echo  ╚════════════════════════════════════════════════════╝
echo.

:: ── Find Python ───────────────────────────────────────────────────────────
:: Try py launcher first (Windows standard), then python3, then python
set "PYTHON="

where py >nul 2>&1
if !errorlevel! == 0 (
    set "PYTHON=py"
    goto :check_version
)

where python3 >nul 2>&1
if !errorlevel! == 0 (
    set "PYTHON=python3"
    goto :check_version
)

where python >nul 2>&1
if !errorlevel! == 0 (
    :: Make sure this isn't the Windows Store stub (returns exit 9009)
    python --version >nul 2>&1
    if !errorlevel! == 0 (
        set "PYTHON=python"
        goto :check_version
    )
)

echo  [ERROR] Python was not found on this system.
echo.
echo  Please install Python 3.12+ from:
echo    https://www.python.org/downloads/
echo.
echo  During installation, tick "Add Python to PATH".
echo.
pause
exit /b 1

:check_version
:: Ask Python itself to validate the version — far more reliable than
:: parsing the version string in batch (avoids rc/alpha/suffix issues)
!PYTHON! -c "import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)" >nul 2>&1
if !errorlevel! NEQ 0 (
    for /f "tokens=*" %%v in ('!PYTHON! --version 2^>^&1') do set "PY_VER=%%v"
    echo  [ERROR] Python 3.12 or later is required.
    echo  Found:    !PY_VER!
    echo  Download: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('!PYTHON! --version 2^>^&1') do set "PY_VER=%%v"
echo  Runtime  : !PY_VER!
echo  Status   : Version check passed

:: ── Check / install dependencies ──────────────────────────────────────────
::
::  Strategy: import every required package in one Python call.
::  If any single one is missing this returns exit code 1 and we run
::  pip install -r requirements.txt which installs all of them.
::  On subsequent runs (all packages present) the import check takes
::  ~50ms and we skip straight to launch.
::
::  Packages checked (must match requirements.txt):
::    PySide6   — Qt6 UI framework
::    loguru    — logging
::    qtawesome — icon fonts (FA5 Solid/Brands) used throughout the UI
::
echo  Status   : Checking dependencies...

!PYTHON! -c "import PySide6, loguru, qtawesome" >nul 2>&1
if !errorlevel! NEQ 0 (
    echo  Status   : One or more dependencies missing — installing now...
    echo  Status   : ^(This takes ~30 seconds on first run, then never again^)
    echo.

    :: Upgrade pip silently first to avoid legacy resolver warnings
    !PYTHON! -m pip install --upgrade pip --quiet 2>nul

    !PYTHON! -m pip install -r "%ROOT%\requirements.txt" --quiet
    if !errorlevel! NEQ 0 (
        echo.
        echo  ════════════════════════════════════════════════════
        echo  [ERROR] Dependency installation failed.
        echo.
        echo  Most common causes:
        echo    1. No internet connection
        echo    2. pip is very outdated  — run:  python -m pip install --upgrade pip
        echo    3. Corporate proxy blocking PyPI — configure pip proxy settings
        echo    4. Insufficient disk space
        echo.
        echo  To install manually, open a terminal in this folder and run:
        echo.
        echo    pip install -r requirements.txt
        echo.
        echo  Required packages: PySide6  loguru  qtawesome
        echo  ════════════════════════════════════════════════════
        echo.
        pause
        exit /b 1
    )

    :: Verify the install actually worked before we try to launch
    !PYTHON! -c "import PySide6, loguru, qtawesome" >nul 2>&1
    if !errorlevel! NEQ 0 (
        echo.
        echo  [ERROR] Packages were installed but cannot be imported.
        echo  This can happen when multiple Python installs exist on the system.
        echo.
        echo  Try running manually:
        echo    pip install -r requirements.txt
        echo    python main.py
        echo.
        pause
        exit /b 1
    )

    echo  Status   : All dependencies installed successfully.
    echo.
) else (
    echo  Status   : All dependencies OK  ^(PySide6 + loguru + qtawesome^)
)

echo  Data     : %USERPROFILE%\.devcache_guardian\
echo.
echo  Launching DevCache Guardian...
echo  ════════════════════════════════════════════════════
echo.

:: ── Launch from project root ──────────────────────────────────────────────
cd /d "%ROOT%"
!PYTHON! main.py

:: ── Exit handling ─────────────────────────────────────────────────────────
set "EXIT_CODE=!errorlevel!"
if !EXIT_CODE! NEQ 0 (
    echo.
    echo  ════════════════════════════════════════════════════
    echo  DevCache Guardian exited with an error ^(code !EXIT_CODE!^).
    echo.
    echo  Log files:  %USERPROFILE%\.devcache_guardian\logs\
    echo.
    echo  Common causes:
    echo    - Missing dependency: run  pip install -r requirements.txt
    echo    - Python version too old: install Python 3.12+ from python.org
    echo    - Permission error: try running as Administrator
    echo    - Corrupted DB: delete  %USERPROFILE%\.devcache_guardian\cache.db
    echo  ════════════════════════════════════════════════════
    echo.
    pause
)

endlocal
