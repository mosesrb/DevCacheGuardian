# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path
import qtawesome

block_cipher = None

# Locate qtawesome package data
qta_path = Path(qtawesome.__file__).parent

datas = [
    ('resources/fonts/*', 'resources/fonts'),
    ('resources/icon.ico', 'resources'),
    ('resources/icon.png', 'resources'),
]

# Include qtawesome font assets
if (qta_path / 'fonts').exists():
    datas.append((str(qta_path / 'fonts' / '*'), 'qtawesome/fonts'))

hiddenimports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtPrintSupport',
    'loguru',
    'qtawesome',
    'app',
    'app.models',
    'app.models.cache_item',
    'app.models.scan_result',
    'app.scanners',
    'app.scanners.base_scanner',
    'app.scanners.pip_scanner',
    'app.scanners.uv_scanner',
    'app.scanners.npm_scanner',
    'app.scanners.huggingface_scanner',
    'app.scanners.ai_extended_scanner',
    'app.scanners.duplicate_model_scanner',
    'app.scanners.dev_ecosystem_scanner',
    'app.scanners.docker_scanner',
    'app.scanners.temp_scanner',
    'app.scanners.venv_scanner',
    'app.cleaners',
    'app.cleaners.cleaner_service',
    'app.services',
    'app.services.scan_worker',
    'app.services.clean_worker',
    'app.services.content_analyzer',
    'app.services.backup_service',
    'app.services.scoring',
    'app.services.report_generator',
    'app.database',
    'app.database.db',
    'app.database.policies',
    'app.ui',
    'app.ui.main_window',
    'app.ui.dashboard_widget',
    'app.ui.cache_table_widget',
    'app.ui.timeline_widget',
    'app.ui.history_widget',
    'app.ui.settings_widget',
    'app.ui.confirm_dialog',
    'app.ui.dry_run_dialog',
    'app.ui.scan_overlay',
    'app.ui.clean_progress_overlay',
    'app.ui.toast',
    'app.ui.status_bar',
    'app.ui.theme',
    'app.ui.palettes',
    'app.ui.eco_colors',
    'app.ui.stylesheet',
]

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'torch', 'torchaudio', 'transformers', 'cv2', 'PIL'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DevCacheGuardian',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/icon.ico',
)
