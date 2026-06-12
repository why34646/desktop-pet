import os
import sys
import subprocess
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QMainWindow, QMenu, 
                               QSystemTrayIcon, QStyle, QMessageBox, QDialog,
                               QVBoxLayout, QPushButton)
from PySide6.QtGui import QPixmap, QPainter, QIcon, QCursor, QPen, QColor
from PySide6.QtCore import Qt, QTimer, QPoint

from state import StateManager


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
        self.temp_pos_file = Path(__file__).parent.parent / ".temp_pos"
        self.resize_cmd_file = Path(__file__).parent.parent / ".resize_cmd"
        self.name_update_file = Path(__file__).parent.parent / ".name_update"
        
        # 睡觉状态：None, 'entering', 'looping', 'exiting'
        self.sleep_stage = None
        self.sleep_target = None  # 睡觉前/后的目标动作
        self.sleep2_counter = 0  # 用于减慢 sleep2 的播放速度
        
        # 初始化状态管理器
        self.state_manager = StateManager(Path(__file__).parent.parent / "assets")
        
        self.load_basic_info()
        self.init_window()
        self.load_current_action_frames()
        self.init_tray()
        self.init_timer()
        self.check_resize_cmd()
        
    def load_basic_info(self):
        basic_path = Path(__file__).parent.parent / "basic.txt"
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
        basic_path = Path(__file__).parent.parent / "basic.txt"
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
        """加载当前动作的帧数据"""
        self.animation_frames = self.state_manager.get_current_frames()
        self.current_frame = 0
        
    def load_sleep_frames(self, stage):
        """加载睡觉指定阶段的帧"""
        self.animation_frames = self.state_manager.load_sleep_frames(stage)
        self.current_frame = 0
        
    def switch_action(self, action_name):
        """切换到指定动作"""
        if self.state_manager.is_sleep_action(action_name):
            # 进入睡觉流程
            self.sleep_target = self.state_manager.current_action  # 保存当前动作
            self.sleep_stage = 'entering'
            self.sleep2_counter = 0  # 重置计数器
            self.state_manager.set_action('sleep')
            self.load_sleep_frames('sleep1')
        elif self.sleep_stage:
            # 如果正在睡觉，先退出睡觉
            self.sleep_stage = 'exiting'
            self.sleep_target = action_name
            self.state_manager.set_action('sleep')
            self.load_sleep_frames('sleep3')
        else:
            self.state_manager.set_action(action_name)
            self.load_current_action_frames()
        # 确保定时器正常运行
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
            # 处理睡觉状态
            if self.sleep_stage:
                if self.sleep_stage == 'entering':
                    # sleep1 播放一次后进入循环
                    self.current_frame += 1
                    if self.current_frame >= len(self.animation_frames):
                        self.sleep_stage = 'looping'
                        self.sleep2_counter = 0  # 重置计数器
                        self.load_sleep_frames('sleep2')
                        self.current_frame = 0
                elif self.sleep_stage == 'looping':
                    # sleep2 循环播放，每200ms播放一帧
                    self.sleep2_counter += 1
                    if self.sleep2_counter >= 2:
                        self.sleep2_counter = 0
                        self.current_frame = (self.current_frame + 1) % len(self.animation_frames)
                elif self.sleep_stage == 'exiting':
                    # sleep3 播放一次后切换目标动作
                    self.current_frame += 1
                    if self.current_frame >= len(self.animation_frames):
                        self.sleep_stage = None
                        self.state_manager.set_action(self.sleep_target)
                        self.load_current_action_frames()
                        return
            else:
                # 非睡觉状态
                self.current_frame += 1
                # 待机动作循环播放
                if self.state_manager.current_action == 'idle':
                    self.current_frame = self.current_frame % len(self.animation_frames)
                # 其他动作播放一次后切换回待机
                elif self.current_frame >= len(self.animation_frames):
                    self.switch_action('idle')
                    self.current_frame = 0
            self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        if self.animation_frames and 0 <= self.current_frame < len(self.animation_frames):
            frame = self.animation_frames[self.current_frame]
            scaled_frame = frame.scaled(self.pet_size, self.pet_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = (self.width() - scaled_frame.width()) // 2
            y = (self.height() - scaled_frame.height()) // 2
            painter.drawPixmap(x, y, scaled_frame)
        
        if self.resizing:
            pen = QPen(QColor(0, 0, 255), 3)
            painter.setPen(pen)
            painter.drawRect(0, 0, self.width() - 1, self.height() - 1)
            
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
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
            else:
                new_pos = event.globalPosition().toPoint() - self.drag_position
                
                # 获取屏幕边界
                screen_geo = QApplication.primaryScreen().availableGeometry()
                
                # 扩大移动范围，四周留出约35像素
                margin = 35
            
                
                # 限制X坐标：窗口左边界可以超出左边界35像素，右边界可以超出右边界35像素
                x = max(-margin, min(new_pos.x(), screen_geo.width() - self.width() + margin))
                
                # 限制Y坐标：窗口上边界可以超出上边界35像素，下边界可以超出下边界35像素
                y = max(-margin, min(new_pos.y(), screen_geo.height() - self.height() + margin))
                
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
        
        # 动态显示当前状态名称
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
        self.save_position()
        set_script = Path(__file__).parent / "set.py"
        subprocess.Popen([sys.executable, str(set_script)])
        
    def show_talk(self):
        """显示对话窗口"""
        talk_script = Path(__file__).parent / "talk.py"
        subprocess.Popen([sys.executable, str(talk_script)])
        
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
            self.load_basic_info()
            self.name_update_file.unlink()
        except FileNotFoundError:
            pass
        except Exception:
            pass
        
        # 检查调整大小命令
        try:
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
        
        QTimer.singleShot(100, self.check_resize_cmd)
        
    def show_name(self):
        if self.pet_name:
            QMessageBox.information(self, "名字", f"宠物名字：{self.pet_name}")
        else:
            QMessageBox.information(self, "名字", "宠物名字：未设置")
        
    def show_mood(self):
        QMessageBox.information(self, "情绪", "宠物情绪：开心\n（功能开发中）")
        
    def show_status_dialog(self):
        """显示状态选择弹窗"""
        dialog = QDialog(self)
        dialog.setWindowTitle("选择动作")
        dialog.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint)
        dialog.resize(200, 150)
        
        layout = QVBoxLayout()
        
        # 获取所有可用动作
        actions = self.state_manager.get_all_actions()
        for action_name in actions:
            display_name = self.state_manager.get_action_display_name(action_name)
            btn = QPushButton(display_name)
            btn.clicked.connect(lambda checked, name=action_name: self.on_action_selected(dialog, name))
            layout.addWidget(btn)
        
        dialog.setLayout(layout)
        dialog.exec_()
        
    def on_action_selected(self, dialog, action_name):
        """选择动作后的处理"""
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
            

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    pet = DesktopPet()
    pet.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
