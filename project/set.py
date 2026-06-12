import os
import sys
import subprocess
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout, 
                               QPushButton, QCheckBox, QInputDialog, QMessageBox, QLabel)
from PySide6.QtCore import Qt, QPoint, QTimer
import winreg  # Windows 注册表操作


class ResizeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.resize_cmd_file = Path(__file__).parent.parent / ".resize_cmd"
        self.setWindowTitle("调整大小")
        self.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.resize(400, 150)
        
        layout = QVBoxLayout()
        
        label = QLabel("现在可以拖动桌宠来调整大小，完成后点击确定或取消。")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self.on_ok)
        button_layout.addWidget(ok_btn)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.on_cancel)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def on_ok(self):
        try:
            with open(self.resize_cmd_file, 'w', encoding='utf-8') as f:
                f.write("confirm")
        except Exception:
            pass
        self.accept()
    
    def on_cancel(self):
        try:
            with open(self.resize_cmd_file, 'w', encoding='utf-8') as f:
                f.write("cancel")
        except Exception:
            pass
        self.accept()


class SettingsDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.temp_pos_file = Path(__file__).parent.parent / ".temp_pos"
        self.resize_cmd_file = Path(__file__).parent.parent / ".resize_cmd"
        self.name_update_file = Path(__file__).parent.parent / ".name_update"
        self.init_ui()
        self.load_pet_position()
        
    def init_ui(self):
        self.setWindowTitle("设置")
        self.resize(300, 300)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        
        layout = QVBoxLayout()
        
        change_name_btn = QPushButton("更改姓名")
        change_name_btn.clicked.connect(self.change_name)
        layout.addWidget(change_name_btn)

        talk_settings_btn = QPushButton("对话模型")
        talk_settings_btn.clicked.connect(self.open_talk_settings)
        layout.addWidget(talk_settings_btn)

        resize_btn = QPushButton("调整大小")
        resize_btn.clicked.connect(self.start_resize)
        layout.addWidget(resize_btn)
        
        self.autostart_checkbox = QCheckBox("开机自启动")
        self.autostart_checkbox.stateChanged.connect(self.toggle_autostart)
        self.load_autostart_status()
        layout.addWidget(self.autostart_checkbox)

        self.console_checkbox = QCheckBox("显示运行框")
        self.console_checkbox.stateChanged.connect(self.toggle_console)
        self.load_console_status()
        layout.addWidget(self.console_checkbox)
        
        layout.addStretch()
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.reject)
        button_layout.addWidget(close_btn)
        
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save_settings)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def load_pet_position(self):
        screen_geo = QApplication.primaryScreen().availableGeometry()
        
        if self.temp_pos_file.exists():
            try:
                with open(self.temp_pos_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    if len(lines) >= 2:
                        x = int(lines[0].strip())
                        y = int(lines[1].strip())
                        w = int(lines[2].strip()) if len(lines) > 2 else 256
                        
                        # 计算设置窗口初始位置：桌宠左侧
                        target_x = x - self.width() - 20
                        target_y = y
                        
                        # 检查x坐标是否超出屏幕左侧，如果是则移到桌宠右侧
                        if target_x < screen_geo.left():
                            target_x = x + w + 20
                        
                        # 检查窗口底部是否超出屏幕底部，如果是则向上移动
                        # 增加额外的安全空间50像素
                        if target_y + self.height() > screen_geo.bottom() - 50:
                            target_y = screen_geo.bottom() - self.height() - 50
                        
                        # 检查窗口顶部是否超出屏幕顶部
                        if target_y < screen_geo.top():
                            target_y = screen_geo.top()
                        
                        self.move(target_x, target_y)
                        return
            except Exception:
                pass
        
        # 如果没有位置文件，默认在屏幕中央
        default_x = (screen_geo.width() - self.width()) // 2
        default_y = (screen_geo.height() - self.height()) // 2
        self.move(default_x, default_y)
    
    def change_name(self):
        while True:
            new_name, ok = QInputDialog.getText(self, "更改姓名", "请输入新名字：")
            if not ok:
                return
            new_name = new_name.strip()
            if not new_name:
                QMessageBox.warning(self, "警告", "名字不能为空！")
                continue
            if len(new_name) > 20:
                QMessageBox.warning(self, "警告", "名字不能超过20个字符！")
                continue
            invalid_chars = {'\n', '\r', '\t', '\\', '/'}
            if any(c in new_name for c in invalid_chars):
                QMessageBox.warning(self, "警告", "名字包含非法字符！")
                continue
            break
        
        reply = QMessageBox.question(
            self, "确认", 
            f"确认名字为【{new_name}】吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        
        basic_path = Path(__file__).parent.parent / "basic.txt"
        try:
            with open(basic_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            with open(basic_path, 'w', encoding='utf-8') as f:
                f.write(new_name + '\n')
                if len(lines) > 1:
                    f.write(lines[1])
            
            # 发送名字更新通知
            try:
                with open(self.name_update_file, 'w', encoding='utf-8') as f:
                    f.write('1')
            except Exception:
                pass
            
            QMessageBox.information(self, "成功", "姓名已更新！")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败：{str(e)}")
    
    def open_talk_settings(self):
        """打开对话模型设置窗口"""
        try:
            from talk.talk_settings import TalkSettingsDialog
            dialog = TalkSettingsDialog(self)
            dialog.exec_()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法打开对话模型设置：{str(e)}")
    
    def start_resize(self):
        try:
            with open(self.resize_cmd_file, 'w', encoding='utf-8') as f:
                f.write("start")
            self.close()
            dialog = ResizeDialog(self)
            dialog.exec_()
            # 关闭后重新启动设置窗口
            set_script = Path(__file__).parent / "set.py"
            subprocess.Popen([sys.executable, str(set_script)])
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法开始调整：{str(e)}")
    
    def load_autostart_status(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                r"Software\Microsoft\Windows\CurrentVersion\Run", 
                                0, winreg.KEY_READ)
            try:
                winreg.QueryValueEx(key, "DesktopPet")
                self.autostart_checkbox.blockSignals(True)
                self.autostart_checkbox.setChecked(True)
                self.autostart_checkbox.blockSignals(False)
            except WindowsError:
                self.autostart_checkbox.blockSignals(True)
                self.autostart_checkbox.setChecked(False)
                self.autostart_checkbox.blockSignals(False)
            winreg.CloseKey(key)
        except Exception:
            self.autostart_checkbox.blockSignals(True)
            self.autostart_checkbox.setChecked(False)
            self.autostart_checkbox.blockSignals(False)
    
    def toggle_autostart(self, state):
        pass

    def load_console_status(self):
        """加载显示运行框设置"""
        console_file = Path(__file__).parent.parent / ".console_show"
        if console_file.exists():
            try:
                with open(console_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    self.console_checkbox.blockSignals(True)
                    self.console_checkbox.setChecked(content == "1")
                    self.console_checkbox.blockSignals(False)
            except Exception:
                pass

    def toggle_console(self, state):
        """运行框复选框切换"""
        pass

    def get_python_exe_for_console(self, show_console):
        """根据设置获取正确的 Python 可执行文件路径"""
        python_exe = sys.executable
        if show_console:
            if "pythonw.exe" in python_exe.lower():
                python_exe = python_exe.lower().replace("pythonw.exe", "python.exe")
        else:
            if "pythonw.exe" not in python_exe.lower():
                python_exe = python_exe.replace("python.exe", "pythonw.exe")
        return python_exe
    
    def save_settings(self):
        try:
            # 保存显示运行框设置
            console_file = Path(__file__).parent.parent / ".console_show"
            show_console = "1" if self.console_checkbox.isChecked() else "0"
            with open(console_file, 'w', encoding='utf-8') as f:
                f.write(show_console)

            # 保存开机自启动（用正确的 python 可执行文件）
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Run",
                                0, winreg.KEY_SET_VALUE)
            if self.autostart_checkbox.isChecked():
                script_path = Path(__file__).parent.parent / "start.py"
                python_exe = self.get_python_exe_for_console(self.console_checkbox.isChecked())
                command = f'"{python_exe}" "{script_path}"'
                winreg.SetValueEx(key, "DesktopPet", 0, winreg.REG_SZ, command)
            else:
                try:
                    winreg.DeleteValue(key, "DesktopPet")
                except WindowsError:
                    pass
            winreg.CloseKey(key)

            QMessageBox.information(self, "成功", "设置已保存！")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败：{str(e)}")


def main():
    app = QApplication(sys.argv)
    dialog = SettingsDialog()
    dialog.exec_()


if __name__ == "__main__":
    main()
