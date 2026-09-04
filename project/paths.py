"""
统一的路径解析工具

路径策略（根据是否为打包模式自动选择）:

1. 打包模式 (sys.frozen == True):
   - `get_app_root()`: 返回 `sys.executable` 所在目录 (exe 目录)
     -> 用于用户可写文件：basic.txt、.console_show、memory/ 等
   - `get_data_root()`: 返回 PyInstaller 的 `_internal/` 资源目录
     -> 用于只读资源：assets/、identity/、talk/config.json 等
   - 在 onedir 模式下，`sys._MEIPASS` 指向 `_internal/` 目录

2. 开发模式 (sys.frozen == False):
   - `get_app_root()`: 返回项目根目录 (`project/paths.py` 的上级目录)
   - `get_data_root()`: 同 `get_app_root()`，资源就在项目根目录
"""
import sys
from pathlib import Path


def get_app_root() -> Path:
    """返回应用根目录（用户可写文件所在目录）。

    - 打包模式: exe 所在目录 (dist/DesktopPet/)
    - 开发模式: 项目根目录 (project/ 的上级)
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_data_root() -> Path:
    """返回资源根目录（只读资源所在目录）。

    - 打包模式: PyInstaller 的 _internal/ 目录 (即 sys._MEIPASS)
    - 开发模式: 同 get_app_root() (即项目根目录)

    用于读取 assets/、identity/、talk/config.json 等打包进来的只读资源。
    """
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        # 兜底：尝试在 exe 目录和其子目录 _internal/ 中查找
        exe_dir = Path(sys.executable).resolve().parent
        if (exe_dir / "_internal" / "assets").exists():
            return exe_dir / "_internal"
        return exe_dir
    return get_app_root()
