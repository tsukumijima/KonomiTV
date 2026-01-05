import sys

from PyInstaller.building.api import EXE, PYZ
from PyInstaller.building.build_main import Analysis
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs


## Windows / Linux でビルド時の指定が異なるため、spec 内で分岐する
if sys.platform == 'win32':
    exe_name = 'KonomiTV-Installer'
    exe_icon = 'KonomiTV-Installer.ico'  # --icon 相当
    is_uac_admin = True  # --uac-admin 相当
else:
    exe_name = 'KonomiTV-Installer.elf'  # --name=KonomiTV-Installer.elf 相当
    exe_icon = None
    is_uac_admin = False

# emoji パッケージ内のデータを同梱する (pyinstaller --collect-datas=emoji 相当)
datas: list[tuple[str, str]] = []
datas += collect_data_files('emoji')

# py7zr -> pyzstd が `from backports import zstd` を行うが、PyInstaller の onefile ビルドでは
# backports-zstd (backports.zstd) が取りこぼされ、実行時に ImportError が発生する
# そのため、backports.zstd 配下の Python モジュールもデータとしてまとめて同梱する
# (include_py_files=True を指定しないと .py が収集されず import できない)
datas += collect_data_files('backports.zstd', include_py_files=True)

# backports.zstd が持つネイティブ拡張 (.so/.pyd) を同梱する
binaries: list[tuple[str, str]] = []
binaries += collect_dynamic_libs('backports.zstd')

block_cipher = None

a = Analysis(
    ['KonomiTV-Installer.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    icon=exe_icon,
    uac_admin=is_uac_admin,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
