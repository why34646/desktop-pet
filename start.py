import os
import sys
import ctypes
from pathlib import Path

# ——— 路径设置 ———
# PyInstaller 打包: exe 所在目录
# 开发模式:       start.py 所在目录
if getattr(sys, "frozen", False):
    _app_root = Path(sys.executable).resolve().parent
else:
    _app_root = Path(__file__).resolve().parent

# 把 project/ 加入 sys.path, 让 `import main`, `import name` 等生效
sys.path.insert(0, str(_app_root / "project"))

# ——— 显示运行框 (控制台显示切换) ———
# 开发模式: 由 python.exe / pythonw.exe 自动决定
# 打包模式: 用 Win32 API 动态分配/释放控制台
def _apply_console_setting():
    """根据 .console_show 文件决定是否显示控制台窗口"""
    console_file = _app_root / ".console_show"
    show = False
    if console_file.exists():
        try:
            with open(console_file, 'r', encoding='utf-8') as f:
                show = f.read().strip() == "1"
        except Exception:
            pass

    if not getattr(sys, "frozen", False):
        return  # 开发模式由 python.exe/pythonw.exe 决定，不做额外处理

    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32
    GetConsoleWindow = kernel32.GetConsoleWindow
    ShowWindow = user32.ShowWindow
    SW_HIDE = 0
    SW_SHOW = 5

    hwnd = GetConsoleWindow()
    if show:
        # 尝试分配控制台并显示
        if not hwnd:
            kernel32.AllocConsole()
            hwnd = GetConsoleWindow()
        if hwnd:
            ShowWindow(hwnd, SW_SHOW)
    else:
        # 隐藏或释放控制台
        if hwnd:
            ShowWindow(hwnd, SW_HIDE)

_apply_console_setting()


def _auto_create_basic_txt():
    """如果 basic.txt 不存在, 就动态创建一个空文件"""
    basic_path = _app_root / "basic.txt"
    if not basic_path.exists():
        try:
            basic_path.touch()
        except Exception:
            pass


def check_pet_name():
    """检查 basic.txt 中是否已有有效的名字"""
    basic_path = _app_root / "basic.txt"
    if not basic_path.exists():
        return False
    try:
        with open(basic_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            # 只看第一行(名字行), 若有非空内容就视为已有名字
            first_line = content.splitlines()[0].strip() if content else ""
            return bool(first_line)
    except Exception:
        return False


def _show_name_dialog():
    """弹出名字输入窗口, 保存到 basic.txt"""
    from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel
    from PySide6.QtWidgets import QLineEdit, QPushButton, QMessageBox, QHBoxLayout

    # 确保有 QApplication 实例
    app = QApplication.instance()
    own_app = False
    if app is None:
        app = QApplication(sys.argv)
        own_app = True

    class NameInputDialog(QDialog):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("给小猫起个名字")
            self.resize(320, 130)

            layout = QVBoxLayout(self)
            layout.addWidget(QLabel("请输入小猫的名字:"))

            self.name_input = QLineEdit()
            layout.addWidget(self.name_input)

            btn_layout = QHBoxLayout()
            btn_layout.addStretch()
            ok_btn = QPushButton("确定")
            cancel_btn = QPushButton("取消")
            btn_layout.addWidget(ok_btn)
            btn_layout.addWidget(cancel_btn)
            layout.addLayout(btn_layout)

            ok_btn.clicked.connect(self._on_ok)
            cancel_btn.clicked.connect(self.reject)

        def _on_ok(self):
            name = self.name_input.text().strip()
            if not name:
                QMessageBox.warning(self, "提示", "名字不能为空")
                return
            # 保存到 basic.txt (保留第二行大小值, 若存在)
            basic_path = _app_root / "basic.txt"
            existing_size = ""
            if basic_path.exists():
                try:
                    with open(basic_path, "r", encoding="utf-8") as f:
                        lines = f.read().splitlines()
                        if len(lines) > 1 and lines[1].strip():
                            existing_size = "\n" + lines[1].strip()
                except Exception:
                    pass
            try:
                with open(basic_path, "w", encoding="utf-8") as f:
                    f.write(name + existing_size)
                self.accept()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存失败: {e}")

    dialog = NameInputDialog()
    result = dialog.exec_()

    if own_app:
        app.quit()

    return result == QDialog.Accepted


def main():
    # 确保 basic.txt 存在
    _auto_create_basic_txt()

    # 若还没有名字, 先弹出名字输入窗口
    if not check_pet_name():
        ok = _show_name_dialog()
        if not ok or not check_pet_name():
            return  # 用户取消了, 直接退出

    # 启动主程序 (桌面小猫)
    import main as _main
    _main.run_pet()


if __name__ == "__main__":
    main()
