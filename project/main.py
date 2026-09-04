import os
import sys
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QMainWindow, QMenu,
                               QSystemTrayIcon, QStyle, QMessageBox, QDialog,
                               QVBoxLayout, QPushButton)
from PySide6.QtGui import QPixmap, QPainter, QIcon, QCursor, QPen, QColor
from PySide6.QtCore import Qt, QTimer, QPoint

from state import StateManager
from paths import get_app_root, get_data_root


class DesktopPet(QMainWindow):
    def __init__(self):
        super().__init__()

        self.animation_frames = []
        self.current_frame = 0
        self.dragging = False
        self.resizing = False
        self.drag_position = QPoint()
        self.resize_start_size = 256
        self.pet_size = 256
        self.min_size = 64
        self.max_size = 512
        self.pet_name = ""
        self.scaled_frames = []
        self.screen_geo = None

        _root = get_app_root()
        self.temp_pos_file = _root / ".temp_pos"
        self.resize_cmd_file = _root / ".resize_cmd"
        self.name_update_file = _root / ".name_update"

        # 睡觉状态: None, 'entering', 'looping', 'exiting'
        self.sleep_stage = None
        self.sleep_target = None  # 睡觉前/后的目标动作
        self.sleep2_counter = 0  # 用于减慢 sleep2 的播放速度

        # 初始化状态管理器 (assets/ 是只读资源，用 data_root)
        self.state_manager = StateManager(str(get_data_root() / "assets"))

        self.load_basic_info()
        self.init_window()
        self.load_current_action_frames()
        self.init_tray()
        self.init_timer()
        self.check_resize_cmd()

    def load_basic_info(self):
        basic_path = get_app_root() / "basic.txt"
        if basic_path.exists():
            try:
                with open(basic_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    if lines:
                        self.pet_name = lines[0].strip()
                    if len(lines) > 1:
                        try:
                            self.pet_size = int(lines[1].strip())
                            self.pet_size = max(self.min_size, min(self.max_size, self.pet_size))
                        except Exception:
                            self.pet_size = 256
            except Exception:
                pass

    def save_basic_info(self):
        basic_path = get_app_root() / "basic.txt"
        try:
            with open(basic_path, 'w', encoding='utf-8') as f:
                f.write(self.pet_name + '\n')
                f.write(str(self.pet_size) + '\n')
        except Exception:
            pass

    def init_window(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(self.pet_size, self.pet_size)

        screen_geometry = QApplication.primaryScreen().availableGeometry()
        x = screen_geometry.width() - self.width() - 20
        y = screen_geometry.height() - self.height() - 20
        self.move(x, y)

    def load_current_action_frames(self):
        self.animation_frames = self.state_manager.get_current_frames()
        self.current_frame = 0
        self._update_scaled_frames()

    def load_sleep_frames(self, stage):
        self.animation_frames = self.state_manager.load_sleep_frames(stage)
        self.current_frame = 0
        self._update_scaled_frames()

    def _update_scaled_frames(self):
        self.scaled_frames = []
        for frame in self.animation_frames:
            if not frame.isNull():
                self.scaled_frames.append(
                    frame.scaled(self.pet_size, self.pet_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )

    def switch_action(self, action_name):
        if self.state_manager.is_sleep_action(action_name):
            self.sleep_target = self.state_manager.current_action
            self.sleep_stage = 'entering'
            self.sleep2_counter = 0
            self.state_manager.set_action('sleep')
            self.load_sleep_frames('sleep1')
        elif self.sleep_stage:
            self.sleep_stage = 'exiting'
            self.sleep_target = action_name
            self.state_manager.set_action('sleep')
            self.load_sleep_frames('sleep3')
        else:
            self.state_manager.set_action(action_name)
            self.load_current_action_frames()
        if not self.timer.isActive() and self.animation_frames:
            self.timer.start(100)
        return True

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
            if self.sleep_stage:
                if self.sleep_stage == 'entering':
                    self.current_frame += 1
                    if self.current_frame >= len(self.animation_frames):
                        self.sleep_stage = 'looping'
                        self.sleep2_counter = 0
                        self.load_sleep_frames('sleep2')
                        self.current_frame = 0
                elif self.sleep_stage == 'looping':
                    self.sleep2_counter += 1
                    if self.sleep2_counter >= 2:
                        self.sleep2_counter = 0
                        self.current_frame = (self.current_frame + 1) % len(self.animation_frames)
                elif self.sleep_stage == 'exiting':
                    self.current_frame += 1
                    if self.current_frame >= len(self.animation_frames):
                        self.sleep_stage = None
                        self.state_manager.set_action(self.sleep_target)
                        self.load_current_action_frames()
                        return
            else:
                self.current_frame += 1
                if self.state_manager.current_action == 'idle':
                    self.current_frame = self.current_frame % len(self.animation_frames)
                elif self.current_frame >= len(self.animation_frames):
                    self.switch_action('idle')
                    self.current_frame = 0
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        if self.scaled_frames and 0 <= self.current_frame < len(self.scaled_frames):
            frame = self.scaled_frames[self.current_frame]
            x = (self.width() - frame.width()) // 2
            y = (self.height() - frame.height()) // 2
            painter.drawPixmap(x, y, frame)

        if self.resizing:
            pen = QPen(QColor(0, 0, 255), 3)
            painter.setPen(pen)
            painter.drawRect(0, 0, self.width() - 1, self.height() - 1)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.screen_geo = QApplication.primaryScreen().availableGeometry()
            if self.resizing:
                self.dragging = True
                self.drag_position = event.globalPosition().toPoint()
                self.resize_start_size = self.pet_size
            else:
                self.dragging = True
                self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == Qt.RightButton:
            self.show_context_menu(event.globalPos())

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.dragging:
            if self.resizing:
                delta = event.globalPosition().toPoint() - self.drag_position
                size_change = delta.x() + delta.y()
                new_size = self.resize_start_size + size_change
                new_size = max(self.min_size, min(self.max_size, new_size))
                if new_size != self.pet_size:
                    self.pet_size = new_size
                    self.resize(self.pet_size, self.pet_size)
                    self._update_scaled_frames()
            else:
                new_pos = event.globalPosition().toPoint() - self.drag_position

                margin = 35
                sg = self.screen_geo
                if sg is None:
                    sg = QApplication.primaryScreen().availableGeometry()

                x = max(-margin, min(new_pos.x(), sg.width() - self.width() + margin))
                y = max(-margin, min(new_pos.y(), sg.height() - self.height() + margin))

                self.move(x, y)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False
            self.save_position()

    def show_context_menu(self, pos):
        menu = QMenu()

        name_text = f"{self.pet_name}" if self.pet_name else "名字"
        name_action = menu.addAction(name_text)
        name_action.triggered.connect(self.show_name)

        mood_action = menu.addAction("情绪")
        mood_action.triggered.connect(self.show_mood)

        current_state_name = self.state_manager.get_current_state_name()
        status_action = menu.addAction(f"状态: {current_state_name}")
        status_action.triggered.connect(self.show_status_dialog)

        menu.addSeparator()

        talk_action = menu.addAction("对话")
        talk_action.triggered.connect(self.show_talk)

        settings_action = menu.addAction("设置")
        settings_action.triggered.connect(self.show_settings)

        hide_action = menu.addAction("隐匿")
        hide_action.triggered.connect(self.hide_pet)

        menu.addSeparator()

        exit_action = menu.addAction("Bye-bye")
        exit_action.triggered.connect(QApplication.instance().quit)

        menu.exec_(pos)

    def show_settings(self):
        """直接在当前进程内打开设置窗口"""
        self.save_position()
        try:
            from set import SettingsDialog
            dialog = SettingsDialog(self)
            dialog.exec_()
            # 设置窗口关闭后, 可能更新了名字/大小, 重新读取
            self.load_basic_info()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法打开设置窗口: {e}")

    def show_talk(self):
        """直接在当前进程内打开对话窗口"""
        try:
            sys.path.insert(0, str(get_app_root() / "project"))
            from talk.dialog import show_talk_dialog as _show_talk
            _show_talk()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法打开对话窗口: {e}")

    def save_position(self):
        try:
            with open(self.temp_pos_file, 'w', encoding='utf-8') as f:
                f.write(str(self.x()) + '\n')
                f.write(str(self.y()) + '\n')
                f.write(str(self.pet_size) + '\n')
        except Exception:
            pass

    def check_resize_cmd(self):
        # 检查名字更新通知
        try:
            if self.name_update_file.exists():
                self.load_basic_info()
                self.name_update_file.unlink()
        except Exception:
            pass

        # 检查调整大小命令
        try:
            if self.resize_cmd_file.exists():
                with open(self.resize_cmd_file, 'r', encoding='utf-8') as f:
                    cmd = f.read().strip()
                if cmd == "start":
                    self.resizing = True
                    self.update()
                elif cmd == "confirm":
                    self.resizing = False
                    self.save_basic_info()
                    self.update()
                elif cmd == "cancel":
                    self.resizing = False
                    self.load_basic_info()
                    self.init_window()
                    self.update()
                try:
                    self.resize_cmd_file.unlink()
                except FileNotFoundError:
                    pass
        except FileNotFoundError:
            pass
        except Exception:
            pass

        QTimer.singleShot(500, self.check_resize_cmd)

    def show_name(self):
        if self.pet_name:
            QMessageBox.information(self, "名字", f"宠物名字: {self.pet_name}")
        else:
            QMessageBox.information(self, "名字", "宠物名字: 未设置")

    def show_mood(self):
        QMessageBox.information(self, "情绪", "宠物情绪: 开心\n(功能开发中)")

    def show_status_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("选择动作")
        dialog.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint)
        dialog.resize(200, 150)

        layout = QVBoxLayout()

        actions = self.state_manager.get_all_actions()
        for action_name in actions:
            display_name = self.state_manager.get_action_display_name(action_name)
            btn = QPushButton(display_name)
            btn.clicked.connect(lambda checked, name=action_name: self.on_action_selected(dialog, name))
            layout.addWidget(btn)

        dialog.setLayout(layout)
        dialog.exec_()

    def on_action_selected(self, dialog, action_name):
        self.switch_action(action_name)
        dialog.accept()

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


def run_pet():
    """供 start.py 调用的主入口"""
    app = QApplication.instance()
    own_app = False
    if app is None:
        app = QApplication(sys.argv)
        own_app = True
    app.setQuitOnLastWindowClosed(False)

    pet = DesktopPet()
    pet.show()

    if own_app:
        sys.exit(app.exec())
    else:
        app.exec()


def main():
    """原 main() — 保留供直接 `python project/main.py` 调试使用"""
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    pet = DesktopPet()
    pet.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
