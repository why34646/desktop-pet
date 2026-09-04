# -*- mode: python ; coding: utf-8 -*-
# 桌面小猫打包配置 —— 目录模式 (onedir)
# 使用方法:
#     pyinstaller DesktopPet.spec --clean
#
# 打包后目录结构:
#   dist/DesktopPet/
#   ├── DesktopPet.exe
#   ├── assets/           <-- 动画图片
#   ├── identity/         <-- 身份描述文件
#   ├── talk/             <-- 对话模块配置 (config.json)
#   ├── (PySide6 runtime DLL)
#   └── ...
# 首次运行: 若 basic.txt 不存在，会自动创建空文件并弹出名字输入框

block_cipher = None

# ——— 数据文件打包规则 ———
# 格式: (源相对路径, 目标目录名)
datas = [
    ('assets', 'assets'),
    ('identity', 'identity'),
    ('project/talk/config.json', 'talk'),
]

# ——— 隐藏导入 ———
# PyInstaller 可能无法自动发现以下模块，在此明确列出
hiddenimports = [
    'PySide6',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'requests',
    'winreg',
    'ctypes',
    # 项目模块：start.py 把 `project/` 加入 sys.path 后
    # 以 `import main`, `import set`, `from talk.dialog import ...`
    # 等形式导入，故不需要写 project.xxx 前缀
    'main',
    'set',
    'name',
    'paths',
    'state',
    'talk',
    'talk.config',
    'talk.dialog',
    'talk.llm',
    'talk.memory',
    'talk.talk_settings',
    'talk.memory_manager',
]

a = Analysis(
    ['start.py'],
    pathex=['project', 'project/talk'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
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
    [],
    exclude_binaries=True,
    name='DesktopPet',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # 默认不显示控制台；运行时由 start.py 根据 .console_show 切换
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DesktopPet',
)
