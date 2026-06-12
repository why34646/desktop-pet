import sys
import subprocess
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QLineEdit, 
                               QPushButton, QMessageBox)
from PySide6.QtCore import Qt


class NameInputWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.pet_name = ""
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("宠物姓名设置")
        self.setFixedSize(400, 200)
        self.center_window()
        
        main_layout = QVBoxLayout()
        main_layout.setSpacing(20)
        
        title_label = QLabel("Hello~")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        main_layout.addWidget(title_label)
        
        name_layout = QVBoxLayout()
        name_label = QLabel("请输入宠物姓名：")
        name_label.setStyleSheet("font-size: 14px;")
        name_layout.addWidget(name_label)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("在此输入姓名...")
        self.name_input.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                font-size: 14px;
                border: 2px solid #ccc;
                border-radius: 5px;
            }
            QLineEdit:focus {
                border-color: #4CAF50;
            }
        """)
        name_layout.addWidget(self.name_input)
        
        main_layout.addLayout(name_layout)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedSize(100, 35)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        cancel_btn.clicked.connect(self.cancel_input)
        button_layout.addWidget(cancel_btn)
        
        confirm_btn = QPushButton("确认")
        confirm_btn.setFixedSize(100, 35)
        confirm_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        confirm_btn.clicked.connect(self.confirm_input)
        button_layout.addWidget(confirm_btn)
        
        button_layout.addStretch()
        
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)
        
    def center_window(self):
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2
        self.move(x, y)
        
    def cancel_input(self):
        sys.exit()
        
    def confirm_input(self):
        name = self.name_input.text().strip()
        
        if not name:
            QMessageBox.warning(self, "警告", "姓名不能为空！")
            return

        if len(name) > 20:
            QMessageBox.warning(self, "警告", "姓名不能超过20个字符！")
            return

        invalid_chars = {'\n', '\r', '\t', '\\', '/'}
        if any(c in name for c in invalid_chars):
            QMessageBox.warning(self, "警告", "姓名包含非法字符！")
            return
            
        reply = QMessageBox.question(
            self, 
            "确认", 
            f"确认名字为【{name}】吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply == QMessageBox.Yes:
            self.save_name(name)
            self.close()
            
            main_script = Path(__file__).parent / "main.py"
            subprocess.Popen([sys.executable, str(main_script)])
            
            sys.exit()
            
    def save_name(self, name):
        basic_path = Path(__file__).parent.parent / "basic.txt"
        
        try:
            with open(basic_path, 'w', encoding='utf-8') as f:
                f.write(name)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存姓名失败：{str(e)}")


def main():
    app = QApplication(sys.argv)
    window = NameInputWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
