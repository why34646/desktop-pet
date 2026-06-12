import os
import sys
import subprocess
import ctypes
from pathlib import Path


def check_pet_name():
    basic_path = Path(__file__).parent / "basic.txt"

    if not basic_path.exists():
        return False

    try:
        with open(basic_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            return bool(content)
    except Exception:
        return False


def get_console_setting():
    """读取显示运行框设置"""
    console_file = Path(__file__).parent / ".console_show"
    if console_file.exists():
        try:
            with open(console_file, 'r', encoding='utf-8') as f:
                return f.read().strip() == "1"
        except Exception:
            pass
    return False


def get_python_exe():
    """根据设置获取正确的 Python 可执行文件"""
    show_console = get_console_setting()
    python_exe = sys.executable
    if show_console:
        if "pythonw.exe" in python_exe.lower():
            python_exe = python_exe.lower().replace("pythonw.exe", "python.exe")
    else:
        if "pythonw.exe" not in python_exe.lower():
            python_exe = python_exe.replace("python.exe", "pythonw.exe")
    return python_exe


def relaunch_with_correct_exe():
    """检查当前可执行文件是否匹配设置，不匹配则重新启动"""
    correct_exe = get_python_exe()
    current_exe = sys.executable
    if correct_exe.lower() != current_exe.lower():
        subprocess.Popen([correct_exe, str(Path(__file__))])
        sys.exit(0)


def setup_console_icon():
    """将 assets/idle 中的 PNG 转换为图标并设置为控制台窗口图标"""
    try:
        from PIL import Image
    except ImportError:
        return

    project_root = Path(__file__).parent
    idle_dir = project_root / "assets" / "idle"
    ico_path = project_root / "assets" / "console.ico"

    png_files = sorted(idle_dir.glob("*.png"))
    if not png_files:
        return

    if not ico_path.exists():
        try:
            img = Image.open(png_files[0])
            img.save(ico_path, format="ICO")
        except Exception:
            return

    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        hwnd = kernel32.GetConsoleWindow()
        if not hwnd:
            return

        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x00000010
        WM_SETICON = 0x0080
        ICON_BIG = 1
        ICON_SMALL = 0
        SMTO_ABORTIFHUNG = 0x0002
        RDW_INVALIDATE = 0x0001
        RDW_UPDATENOW = 0x0100
        RDW_ALLCHILDREN = 0x0080

        hicon_big = user32.LoadImageW(0, str(ico_path), IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
        hicon_small = user32.LoadImageW(0, str(ico_path), IMAGE_ICON, 16, 16, LR_LOADFROMFILE)

        # 1) 用 SendMessageTimeoutW 设置窗口图标（跨进程 conhost.exe 更可靠）
        result_ptr = ctypes.c_ulong(0)
        if hicon_big:
            user32.SendMessageTimeoutW(
                hwnd, WM_SETICON, ICON_BIG, hicon_big,
                SMTO_ABORTIFHUNG, 2000, ctypes.byref(result_ptr)
            )
        if hicon_small:
            user32.SendMessageTimeoutW(
                hwnd, WM_SETICON, ICON_SMALL, hicon_small,
                SMTO_ABORTIFHUNG, 2000, ctypes.byref(result_ptr)
            )

        # 2) SetConsoleIcon（kernel32）
        try:
            if hicon_big:
                kernel32.SetConsoleIcon(hicon_big)
        except Exception:
            pass

        # 3) 强制刷新窗口
        try:
            user32.RedrawWindow(hwnd, None, None, RDW_INVALIDATE | RDW_UPDATENOW | RDW_ALLCHILDREN)
        except Exception:
            pass

    except Exception:
        pass


def run_name_script():
    name_script = Path(__file__).parent / "project" / "name.py"
    python_exe = get_python_exe()
    subprocess.run([python_exe, str(name_script)], check=True)


def run_main_script():
    main_script = Path(__file__).parent / "project" / "main.py"
    python_exe = get_python_exe()
    subprocess.run([python_exe, str(main_script)], check=True)


def main():
    relaunch_with_correct_exe()

    if get_console_setting():
        setup_console_icon()

    if check_pet_name():
        run_main_script()
    else:
        run_name_script()
        if check_pet_name():
            run_main_script()


if __name__ == "__main__":
    main()
