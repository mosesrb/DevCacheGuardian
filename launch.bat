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
echo  Status   : Checking dependencies...

!PYTHON! -c "import PySide6" >nul 2>&1
if !errorlevel! NEQ 0 (
    echo  Status   : Installing PySide6 ^(first run ^— takes ~30 seconds^)...
    !PYTHON! -m pip install -r "%ROOT%\requirements.txt" --quiet
    if !errorlevel! NEQ 0 (
        echo.
        echo  [ERROR] Dependency installation failed.
        echo  Try running this manually in the project folder:
        echo.
        echo    pip install -r requirements.txt
        echo.
        pause
        exit /b 1
    )
    echo  Status   : PySide6 installed.
) else (
    echo  Status   : PySide6 OK
)

!PYTHON! -c "import loguru" >nul 2>&1
if !errorlevel! NEQ 0 (
    echo  Status   : Installing loguru...
    !PYTHON! -m pip install loguru --quiet
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
    echo  ════════════════════════════════════════════════════
    echo.
    pause
)

endlocal
