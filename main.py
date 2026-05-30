import os
import sys
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QMainWindow, QMenu, 
                               QSystemTrayIcon, QStyle, QMessageBox)
from PySide6.QtGui import QPixmap, QPainter, QIcon, QCursor
from PySide6.QtCore import Qt, QTimer, QPoint


class DesktopPet(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.animation_frames = []
        self.current_frame = 0
        self.dragging = False
        self.drag_position = QPoint()
        
        self.init_window()
        self.load_animation_frames()
        self.init_tray()
        self.init_timer()
        
    def init_window(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(256, 256)
        
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        x = screen_geometry.width() - self.width() - 20
        y = screen_geometry.height() - self.height() - 20
        self.move(x, y)
        
    def load_animation_frames(self):
        assets_path = Path(__file__).parent / "assets" / "idle"
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
        
        self.toggle_action = tray_menu.addAction("显示宠物")
        self.toggle_action.triggered.connect(self.toggle_visibility)
        
        tray_menu.addSeparator()
        
        exit_action = tray_menu.addAction("退出程序")
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
        
        settings_action = menu.addAction("设置")
        settings_action.triggered.connect(self.show_settings)
        
        hide_action = menu.addAction("隐藏宠物")
        hide_action.triggered.connect(self.hide_pet)
        
        menu.addSeparator()
        
        exit_action = menu.addAction("退出程序")
        exit_action.triggered.connect(QApplication.instance().quit)
        
        menu.exec_(pos)
        
    def show_settings(self):
        QMessageBox.information(self, "设置", "设置功能开发中...")
        
    def hide_pet(self):
        self.hide()
        self.toggle_action.setText("显示宠物")
        
    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
            self.toggle_action.setText("显示宠物")
        else:
            self.show()
            self.toggle_action.setText("隐藏宠物")
            

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    pet = DesktopPet()
    pet.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
