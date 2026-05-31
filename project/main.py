import os
import sys
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QMainWindow, QMenu, 
                               QSystemTrayIcon, QStyle, QMessageBox,
                               QDialog, QVBoxLayout, QHBoxLayout, 
                               QPushButton, QCheckBox, QInputDialog)
from PySide6.QtGui import QPixmap, QPainter, QIcon, QCursor
from PySide6.QtCore import Qt, QTimer, QPoint
import winreg  # Windows 注册表操作


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.init_ui()
        
    def init_ui(self):
        # 窗口设置
        self.setWindowTitle("设置")
        self.resize(400, 300)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        
        # 布局
        layout = QVBoxLayout()
        
        # 更改姓名按钮
        change_name_btn = QPushButton("更改姓名")
        change_name_btn.clicked.connect(self.change_name)
        layout.addWidget(change_name_btn)
        
        # 开机自启动勾选框
        self.autostart_checkbox = QCheckBox("开机自启动")
        self.autostart_checkbox.stateChanged.connect(self.toggle_autostart)
        self.load_autostart_status()
        layout.addWidget(self.autostart_checkbox)
        
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
    
    def change_name(self):
        # 输入姓名
        while True:
            new_name, ok = QInputDialog.getText(self, "更改姓名", "请输入新名字：")
            if not ok:
                return
            new_name = new_name.strip()
            if new_name:
                break
            QMessageBox.warning(self, "警告", "名字不能为空！")
        
        # 二次确认
        reply = QMessageBox.question(
            self, "确认", 
            f"确认名字为【{new_name}】吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        
        # 保存到 basic.txt
        basic_path = Path(__file__).parent.parent / "basic.txt"
        try:
            with open(basic_path, 'w', encoding='utf-8') as f:
                f.write(new_name)
            # 更新主窗口
            if self.parent_window:
                self.parent_window.pet_name = new_name
            QMessageBox.information(self, "成功", "姓名已更新！")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败：{str(e)}")
    
    def load_autostart_status(self):
        # 读取注册表，检查是否已设置自启动
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                r"Software\Microsoft\Windows\CurrentVersion\Run", 
                                0, winreg.KEY_READ)
            try:
                winreg.QueryValueEx(key, "DesktopPet")
                self.autostart_checkbox.setChecked(True)
            except WindowsError:
                self.autostart_checkbox.setChecked(False)
            winreg.CloseKey(key)
        except Exception:
            self.autostart_checkbox.setChecked(False)
    
    def toggle_autostart(self, state):
        action = "开启" if state == Qt.Checked else "关闭"
        reply = QMessageBox.question(
            self, "确认", 
            f"确认{action}开机自启动吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            self.autostart_checkbox.blockSignals(True)
            self.autostart_checkbox.setChecked(not (state == Qt.Checked))
            self.autostart_checkbox.blockSignals(False)
    
    def save_settings(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                r"Software\Microsoft\Windows\CurrentVersion\Run", 
                                0, winreg.KEY_SET_VALUE)
            if self.autostart_checkbox.isChecked():
                script_path = Path(__file__).parent.parent / "start.py"
                python_exe = sys.executable
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


class DesktopPet(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.animation_frames = []
        self.current_frame = 0
        self.dragging = False
        self.drag_position = QPoint()
        self.pet_name = ""
        
        self.load_pet_name()
        self.init_window()
        self.load_animation_frames()
        self.init_tray()
        self.init_timer()
        
    def load_pet_name(self):
        basic_path = Path(__file__).parent.parent / "basic.txt"
        if basic_path.exists():
            try:
                with open(basic_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    if lines:
                        self.pet_name = lines[0].strip()
            except Exception:
                pass
        
    def init_window(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(256, 256)
        
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        x = screen_geometry.width() - self.width() - 20
        y = screen_geometry.height() - self.height() - 20
        self.move(x, y)
        
    def load_animation_frames(self):
        assets_path = Path(__file__).parent.parent / "assets" / "idle"
        if assets_path.exists():
            png_files = sorted([f for f in assets_path.iterdir() if f.suffix.lower() == '.png'])
            for png_file in png_files:
                pixmap = QPixmap(str(png_file))
                if not pixmap.isNull():
                    self.animation_frames.append(pixmap)
                    
    def init_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        
        if self.animation_frames:
            self.tray_icon.setIcon(QIcon(self.animation_frames[0]))
        else:
            self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
            
        tray_menu = QMenu()
        
        settings_action = tray_menu.addAction("设置")
        settings_action.triggered.connect(self.show_settings)
        
        tray_menu.addSeparator()
        
        self.toggle_action = tray_menu.addAction("隐藏")
        self.toggle_action.triggered.connect(self.toggle_visibility)
        
        tray_menu.addSeparator()
        
        exit_action = tray_menu.addAction("退出")
        exit_action.triggered.connect(QApplication.instance().quit)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        
    def init_timer(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        if self.animation_frames:
            self.timer.start(100)
            
    def update_frame(self):
        if self.animation_frames:
            self.current_frame = (self.current_frame + 1) % len(self.animation_frames)
            self.update()
            
    def paintEvent(self, event):
        painter = QPainter(self)
        if self.animation_frames:
            frame = self.animation_frames[self.current_frame]
            scaled_frame = frame.scaled(256, 256, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = (self.width() - scaled_frame.width()) // 2
            y = (self.height() - scaled_frame.height()) // 2
            painter.drawPixmap(x, y, scaled_frame)
            
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == Qt.RightButton:
            self.show_context_menu(event.globalPos())
            
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.dragging:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
            
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False
            
    def show_context_menu(self, pos):
        menu = QMenu()
        
        name_text = f"{self.pet_name}" if self.pet_name else "名字"
        name_action = menu.addAction(name_text)
        name_action.triggered.connect(self.show_name)
        
        mood_action = menu.addAction("情绪")
        mood_action.triggered.connect(self.show_mood)
        
        status_action = menu.addAction("状态")
        status_action.triggered.connect(self.show_status)
        
        menu.addSeparator()
        
        settings_action = menu.addAction("设置")
        settings_action.triggered.connect(self.show_settings)
        
        hide_action = menu.addAction("隐匿")
        hide_action.triggered.connect(self.hide_pet)
        
        menu.addSeparator()
        
        exit_action = menu.addAction("再见bye")
        exit_action.triggered.connect(QApplication.instance().quit)
        
        menu.exec_(pos)
        
    def show_settings(self):
        dialog = SettingsDialog(self)
        dialog.exec_()
        
    def show_name(self):
        if self.pet_name:
            QMessageBox.information(self, "名字", f"宠物名字：{self.pet_name}")
        else:
            QMessageBox.information(self, "名字", "宠物名字：未设置")
        
    def show_mood(self):
        QMessageBox.information(self, "情绪", "宠物情绪：开心\n（功能开发中）")
        
    def show_status(self):
        QMessageBox.information(self, "状态", "宠物状态：待机中\n（功能开发中）")
        
    def hide_pet(self):
        self.hide()
        self.toggle_action.setText("显示")
        
    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
            self.toggle_action.setText("显示")
        else:
            self.show()
            self.toggle_action.setText("隐藏")
            

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    pet = DesktopPet()
    pet.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
