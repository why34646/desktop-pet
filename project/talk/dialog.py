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
from memory import ShortTermMemory, LongTermMemory, TempMemory
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
        self.temp_memory = TempMemory()
        self.identity = load_identity()
        self.api_ever_worked = False  # 标记 API 是否曾经成功过
        
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

            # 标记 API 曾成功过
            self.api_ever_worked = True

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
            cursor.insertHtml(f'<p style="margin-left: 10px; color: #ffcc66;">{message}</p>')
        
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
            conversations = self.short_memory.get_conversations()

            if conversations:
                if self.api_ever_worked:
                    # API 曾经成功过，尝试总结
                    try:
                        summary = self.llm_client.generate_summary(conversations, self.identity)
                        self.long_memory.save_session(conversations, summary)
                        self.short_memory.delete_current()  # 删除 short 中的会话
                    except Exception:
                        # API 失败，保存到 temp
                        self.temp_memory.save_unsummarized(conversations)
                        self.short_memory.delete_current()
                        QMessageBox.warning(self, "警告", "API 不可用，对话已暂存，待下次总结")
                else:
                    # API 从未成功过，不保存任何记忆
                    self.short_memory.delete_current()
            else:
                # 没有对话记录，直接关闭
                pass

        except Exception as e:
            QMessageBox.warning(self, "警告", f"保存记忆时出错: {str(e)}")

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
    import json

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    # 检查 API 配置
    config = ConfigManager()
    if not config.api_key:
        QMessageBox.critical(None, "错误", "大模型API未配置！")
        return

    # 检查 temp 目录是否有待总结的会话
    temp_memory = TempMemory()
    pending = temp_memory.get_pending_sessions()
    if pending:
        # 有待总结的会话，尝试总结
        llm_client = LLMClient(config)
        identity = load_identity()
        long_mem = LongTermMemory()
        for session_file in pending:
            try:
                with open(session_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    conversations = data.get("conversations", [])
                if conversations:
                    summary = llm_client.generate_summary(conversations, identity)
                    long_mem.save_session(conversations, summary)
                temp_memory.delete_session(session_file)
            except Exception:
                break  # API 仍不可用，保留剩余的
        remaining = temp_memory.get_pending_sessions()
        if len(remaining) < len(pending):
            QMessageBox.information(None, "提示", "已总结之前的暂存对话")

    dialog = TalkDialog()
    dialog.exec_()


if __name__ == "__main__":
    show_talk_dialog()
