# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# 显式指定所有依赖
hidden_imports = [
    'flask_socketio',
    'socketio',
    'socketio.client',
    'socketio.server',
    'engineio',
    'engineio.client',
    'engineio.server',
    'simple_websocket',
    'threading',
    'logging',
    'urllib.parse',
    'datetime',
    'tarfile',
    'shutil',
    'subprocess',
    'socket',
    'json',
    'base64',
    'tempfile',
    'uuid',
    'os',
    'sys',
    'math',
    'numpy',
    'cv2',
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    'requests',
    'AiUtils'
]

# 获取engineio的async_drivers目录路径
import os
import engineio
engineio_path = os.path.dirname(engineio.__file__)
async_drivers_path = os.path.join(engineio_path, 'async_drivers')

# 添加engineio的async_drivers目录、templates目录和static目录到datas
datas = [
    (async_drivers_path, 'engineio/async_drivers'),
    ('templates', 'templates'),
    ('static', 'static')
]

a = Analysis(
    ['app.py'],
    pathex=['d:/project/gitee/xclabel'],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
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
    name='xclabel',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
