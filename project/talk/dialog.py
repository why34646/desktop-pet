"""
对话界面模块
负责对话窗口界面和主逻辑
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, 
                              QTextBrowser, QTextEdit, QPushButton,
                              QMessageBox, QApplication)
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor

# 添加父目录到路径，以便导入模块
sys.path.insert(0, str(Path(__file__).parent))

from config import ConfigManager
from memory import ShortTermMemory, LongTermMemory
from llm import LLMClient, load_identity


class TalkDialog(QDialog):
    """对话窗口类"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 初始化组件
        self.config_manager = ConfigManager()
        self.llm_client = LLMClient(self.config_manager)
        self.short_memory = ShortTermMemory()
        self.long_memory = LongTermMemory()
        self.identity = load_identity()
        
        # 创建新会话
        self.short_memory.new_session()
        
        self.init_ui()
    
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("对话")
        self.resize(500, 600)
        
        # 主布局
        main_layout = QVBoxLayout()
        
        # 对话展示区域
        self.chat_display = QTextBrowser()
        self.chat_display.setPlaceholderText("对话内容将显示在这里...")
        main_layout.addWidget(self.chat_display)
        
        # 输入区域
        input_layout = QVBoxLayout()
        
        self.input_area = QTextEdit()
        self.input_area.setPlaceholderText("请输入您想说的话...")
        self.input_area.setMaximumHeight(100)
        self.input_area.textChanged.connect(self.on_text_changed)
        input_layout.addWidget(self.input_area)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.send_btn = QPushButton("发送")
        self.send_btn.clicked.connect(self.on_send_clicked)
        self.send_btn.setEnabled(False)
        button_layout.addWidget(self.send_btn)
        
        self.end_btn = QPushButton("结束对话")
        self.end_btn.clicked.connect(self.on_end_clicked)
        button_layout.addWidget(self.end_btn)
        
        button_layout.addStretch()
        
        input_layout.addLayout(button_layout)
        
        main_layout.addLayout(input_layout)
        
        self.setLayout(main_layout)
        
        # 设置焦点到输入框
        self.input_area.setFocus()
    
    def on_text_changed(self):
        """输入框文本变化时触发"""
        text = self.input_area.toPlainText().strip()
        self.send_btn.setEnabled(len(text) > 0)
    
    def on_send_clicked(self):
        """发送按钮点击"""
        user_input = self.input_area.toPlainText().strip()
        if not user_input:
            return
        
        # 清空输入框
        self.input_area.clear()
        self.send_btn.setEnabled(False)
        
        # 显示用户输入
        self.append_message("你", user_input)
        
        # 禁用发送按钮，防止重复点击
        self.send_btn.setEnabled(False)
        self.input_area.setEnabled(False)
        
        # 在后台执行请求
        self.process_user_input(user_input)
    
    def process_user_input(self, user_input):
        """
        处理用户输入
        
        Args:
            user_input: 用户输入内容
        """
        try:
            # 获取上下文
            short_context = self.short_memory.format_for_context()
            long_summary = self.long_memory.get_latest_summary()
            
            # 第一轮：询问是否需要历史
            need_history = self.llm_client.check_need_history(
                user_input, 
                short_context, 
                long_summary
            )
            
            # 获取完整上下文
            history_context = ""
            if need_history:
                # 需要历史对话
                long_history = self.long_memory.format_history_for_context()
                if long_history:
                    history_context = long_history
            
            # 第二轮：发送完整请求获取回复
            response = self.llm_client.chat(
                self.identity,
                user_input,
                history_context
            )
            
            # 显示AI回复
            self.append_message("小猫", response)
            
            # 保存到短时记忆
            self.short_memory.add_conversation(user_input, response)
            self.short_memory.save()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"发送消息失败: {str(e)}")
        
        finally:
            # 恢复输入框
            self.input_area.setEnabled(True)
            self.send_btn.setEnabled(True)
            self.input_area.setFocus()
    
    def append_message(self, sender, message):
        """
        在对话区域追加消息
        
        Args:
            sender: 发送者名称
            message: 消息内容
        """
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        # 添加时间戳
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if sender == "你":
            cursor.insertHtml(f'<p><span style="color: #0066cc;">[{timestamp}] {sender}:</span></p>')
            cursor.insertHtml(f'<p style="margin-left: 10px;">{message}</p>')
        else:
            cursor.insertHtml(f'<p><span style="color: #cc6600;">[{timestamp}] {sender}:</span></p>')
            cursor.insertHtml(f'<p style="margin-left: 10px; color: #333;">{message}</p>')
        
        cursor.insertHtml("<hr>")
        
        # 滚动到底部
        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()
    
    def on_end_clicked(self):
        """结束对话按钮点击"""
        self.save_and_close()
    
    def save_and_close(self):
        """保存记忆并关闭"""
        try:
            # 获取对话记录
            conversations = self.short_memory.get_conversations()
            
            if conversations:
                # 生成摘要
                summary = self.llm_client.generate_summary(conversations, self.identity)
                
                # 保存到永久记忆
                self.long_memory.save_session(conversations, summary)
            
            # 保存短时记忆
            self.short_memory.save()
            
        except Exception as e:
            QMessageBox.warning(self, "警告", f"保存记忆时出错: {str(e)}")
        
        # 关闭窗口
        self.close()
    
    def closeEvent(self, event):
        """
        窗口关闭事件
        
        Args:
            event: 关闭事件
        """
        # 先保存记忆
        self.save_and_close()
        event.accept()
    
    def keyPressEvent(self, event):
        """
        键盘事件
        
        Args:
            event: 键盘事件
        """
        if event.key() == Qt.Key_Return and not event.modifiers():
            # Enter键发送消息
            if self.send_btn.isEnabled():
                self.on_send_clicked()
        elif event.key() == Qt.Key_Return and event.modifiers() == Qt.ShiftModifier:
            # Shift+Enter换行
            cursor = self.input_area.textCursor()
            cursor.insertText("\n")
        else:
            super().keyPressEvent(event)


def show_talk_dialog():
    """显示对话窗口"""
    from PySide6.QtWidgets import QMessageBox
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # 检查API配置
    config = ConfigManager()
    if not config.api_key or config.api_key == "your-api-key-here":
        QMessageBox.critical(
            None,
            "错误",
            "大模型API未配置，请先在 talk/config.json 中配置 API密钥！"
        )
        return
    
    # 检查身份设定
    identity = load_identity()
    # 判断是否为空
    if not identity.strip():
        QMessageBox.warning(
            None,
            "警告",
            "身份设定为空，将使用默认身份！"
        )
    
    dialog = TalkDialog()
    dialog.exec_()


if __name__ == "__main__":
    show_talk_dialog()
