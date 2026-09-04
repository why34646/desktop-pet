"""
对话界面模块
负责对话窗口界面和主逻辑
"""

import json
import sys
from pathlib import Path
from datetime import datetime

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                              QTextBrowser, QTextEdit, QPushButton,
                              QMessageBox, QApplication)
from PySide6.QtCore import Qt, QThread, QObject, Signal
from PySide6.QtGui import QTextCursor


def _get_app_root():
    """返回应用根目录（用户可写文件路径，basic.txt / memory/ 等）。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def _get_data_root():
    """返回资源根目录（只读资源路径，assets/ identity/ talk/config.json 等）。"""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        exe_dir = Path(sys.executable).resolve().parent
        if (exe_dir / "_internal" / "assets").exists():
            return exe_dir / "_internal"
        return exe_dir
    return _get_app_root()


# 打包模式下，talk 模块可能直接在 exe 目录或在 _MEIPASS 中
# 开发模式下，talk 模块在 project/talk/ 下
_root = _get_app_root()
sys.path.insert(0, str(_root / "talk"))
sys.path.insert(0, str(_root / "project"))
sys.path.insert(0, str(_root / "project" / "talk"))
# 确保 _MEIPASS（PyInstaller 临时解压目录）也被搜索
_meipass = getattr(sys, "_MEIPASS", None)
if _meipass:
    sys.path.insert(0, str(Path(_meipass)))
    sys.path.insert(0, str(Path(_meipass) / "talk"))

from config import ConfigManager
from memory import ShortTermMemory, LongTermMemory, TempMemory, MidTermMemory, UserProfile
from llm import LLMClient, load_identity


_HTML_ESCAPE_TABLE = str.maketrans({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#x27;',
})


def _escape_html(text):
    return text.translate(_HTML_ESCAPE_TABLE)


class TalkWorker(QObject):
    """后台线程：执行 API 调用"""

    response_ready = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, config_manager, identity, short_memory, long_memory,
                 mid_memory, user_profile, max_context_tokens=4000):
        super().__init__()
        self.config_manager = config_manager
        self.identity = identity
        self.short_memory = short_memory
        self.long_memory = long_memory
        self.mid_memory = mid_memory
        self.user_profile = user_profile
        self.max_context_tokens = max_context_tokens
        self.llm_client = LLMClient(config_manager)

    def do_chat(self, user_input):
        try:
            # 构建 system_prompt（静态 identity + 动态画像）
            system_prompt = self.identity
            profile_ctx = self.user_profile.format_for_prompt()
            if profile_ctx:
                system_prompt = system_prompt + "\n\n" + profile_ctx

            # 中期记忆（始终带入）
            mid_context = self.mid_memory.get_formatted_context(count=3)

            # 长期记忆召回
            all_summaries = self.long_memory.get_all_summaries()
            need_history, folder_names = self.llm_client.check_need_history(
                user_input, self.short_memory.format_for_context(), all_summaries
            )
            history_context = ""
            if need_history:
                if folder_names:
                    history_context = self.long_memory.get_history_by_folders(folder_names)
                if not history_context:
                    history_context = self.long_memory.format_history_for_context()

            # 短期记忆（OpenAI 格式）
            short_msgs = self._format_short_as_messages()

            response = self.llm_client.chat(
                system_prompt=system_prompt,
                user_input=user_input,
                mid_context=mid_context,
                history_context=history_context,
                short_context_msgs=short_msgs,
                max_context_tokens=self.max_context_tokens
            )

            self.response_ready.emit(response)
        except Exception as e:
            self.error_occurred.emit(str(e))

    def _format_short_as_messages(self):
        """将短期记忆格式化为 OpenAI 消息列表"""
        convs = self.short_memory.get_conversations()
        messages = []
        for conv in convs:
            if conv.get("user"):
                messages.append({"role": "user", "content": conv["user"]})
            if conv.get("assistant"):
                messages.append({"role": "assistant", "content": conv["assistant"]})
        return messages


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
        self.mid_memory = MidTermMemory()
        self.user_profile = UserProfile()
        self.identity = load_identity()
        self.api_ever_worked = False  # 标记 API 是否曾经成功过
        self.is_processing = False
        self.save_pending = False
        self.max_context_tokens = self.config_manager.get_max_context_tokens()

        self.short_memory.new_session()

        # 后台线程：发送消息
        self.chat_thread = QThread()
        self.chat_worker = TalkWorker(
            self.config_manager, self.identity,
            self.short_memory, self.long_memory,
            self.mid_memory, self.user_profile,
            self.max_context_tokens
        )
        self.chat_worker.moveToThread(self.chat_thread)
        self.chat_worker.response_ready.connect(self.on_response_ready)
        self.chat_worker.error_occurred.connect(self.on_chat_error)
        self.chat_thread.started.connect(lambda: self.chat_worker.do_chat(self._pending_input))

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
        self.send_btn.setEnabled(len(text) > 0 and not self.is_processing)
    
    def on_send_clicked(self):
        """发送按钮点击"""
        user_input = self.input_area.toPlainText().strip()
        if not user_input or self.is_processing:
            return
        
        self.is_processing = True
        
        self.input_area.clear()
        self.send_btn.setEnabled(False)
        
        self.append_message("你", user_input)
        self.append_thinking()
        
        self.input_area.setEnabled(False)
        
        self._pending_input = user_input
        self.chat_thread.start()

    def on_response_ready(self, response):
        """后台线程返回 AI 回复"""
        self.remove_thinking()
        self.append_message("小猫", response)
        self.api_ever_worked = True
        self.short_memory.add_conversation(self._pending_input, response)
        self.short_memory.save()
        self._finish_processing()

    def on_chat_error(self, error_msg):
        """后台线程返回错误"""
        self.remove_thinking()
        QMessageBox.critical(self, "错误", f"发送消息失败: {error_msg}")
        self._finish_processing()

    def _finish_processing(self):
        self.chat_thread.quit()
        self.chat_thread.wait()
        self.is_processing = False
        self.input_area.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.input_area.setFocus()

    def append_thinking(self):
        """追加思考中提示"""
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml('<p style="color: #888888; font-style: italic;">小猫思考中...</p>')
        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()

    def remove_thinking(self):
        """移除思考中提示（通过重新追加内容实现，QTextBrowser不支持删除行）"""
        pass
    
    def append_message(self, sender, message):
        """
        在对话区域追加消息
        
        Args:
            sender: 发送者名称
            message: 消息内容
        """
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if sender == "你":
            cursor.insertHtml(f'<p><span style="color: #0066cc;">[{timestamp}] {_escape_html(sender)}:</span></p>')
            cursor.insertHtml(f'<p style="margin-left: 10px;">{_escape_html(message)}</p>')
        else:
            cursor.insertHtml(f'<p><span style="color: #cc6600;">[{timestamp}] {_escape_html(sender)}:</span></p>')
            cursor.insertHtml(f'<p style="margin-left: 10px; color: #ffcc66;">{_escape_html(message)}</p>')
        
        cursor.insertHtml("<hr>")
        
        # 滚动到底部
        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()
    
    def on_end_clicked(self):
        """结束对话按钮点击"""
        self._start_save_and_close()

    def save_and_close(self):
        self._start_save_and_close()

    def _start_save_and_close(self):
        if self.save_pending:
            return
        self.save_pending = True

        conversations = self.short_memory.get_conversations()
        print(f"[Dialog] 开始关闭流程，对话数量: {len(conversations)}, api_ever_worked: {self.api_ever_worked}")

        if conversations and self.api_ever_worked:
            self.hide()
            QMessageBox.information(None, "提示", "正在整理对话记忆")
            try:
                # 1. 生成结构化记忆条目
                entries = self.llm_client.generate_summary(conversations, self.identity)
                # 2. 保存到长期记忆（session_folder + history.json + summary.txt + memory_index.json）
                session_folder = self.long_memory.save_session(conversations, summary=None)
                if entries:
                    self.long_memory.add_entries(session_folder, entries)
                # 3. 保存摘要文本（兼容旧格式）
                summary_text = " | ".join([e.get("content", "") for e in entries]) if entries else ""
                summary_file = session_folder / "summary.txt"
                with open(summary_file, 'w', encoding='utf-8') as f:
                    f.write(summary_text)
                # 4. 加入中期记忆
                self.mid_memory.add_session(session_folder, summary_text, conversations, len(conversations))
                # 5. 更新用户画像
                profile_json_str = json.dumps(self.user_profile.data, ensure_ascii=False)
                profile_update = self.llm_client.generate_profile_update(
                    conversations, profile_json_str, self.identity
                )
                if profile_update:
                    self.user_profile.update_profile(profile_update)
                # 6. 更新交互统计
                self.user_profile.increment_stats(len(conversations))
                print("[Dialog] 记忆整理完成")
            except Exception as e:
                print(f"[Dialog] 记忆整理失败 ({e})，暂存到 temp/")
                try:
                    self.temp_memory.save_unsummarized(conversations)
                    print("[Dialog] 已暂存到 temp/")
                except Exception as e2:
                    print(f"[Dialog] 警告：temp 保存也失败: {e2}")
        else:
            if conversations:
                self.short_memory.delete_current()
                print("[Dialog] 无API记录，已删除 short/")

        try:
            self.short_memory.delete_current()
            print("[Dialog] short/ 已清理")
        except Exception:
            pass

        self.accept()

    def closeEvent(self, event):
        print(f"[Dialog] closeEvent triggered, is_processing={self.is_processing}, save_pending={self.save_pending}")
        if self.is_processing:
            self.chat_worker.response_ready.disconnect(self.on_response_ready)
            self.chat_worker.error_occurred.disconnect(self.on_chat_error)
            self.chat_thread.quit()
        if not self.save_pending:
            self._start_save_and_close()
        event.ignore()
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return and not event.modifiers():
            if self.send_btn.isEnabled():
                self.on_send_clicked()
        elif event.key() == Qt.Key_Return and event.modifiers() == Qt.ShiftModifier:
            cursor = self.input_area.textCursor()
            cursor.insertText("\n")
        else:
            super().keyPressEvent(event)


def show_talk_dialog():
    """显示对话窗口"""
    import json

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    # 检查 API 配置
    config = ConfigManager()
    if not config.api_key:
        QMessageBox.critical(None, "错误", "大模型API未配置！请先在设置中配置。")
        return

    # 收集 short/ 和 temp/ 中的孤儿文件
    project_root = _get_app_root()
    short_dir = project_root / "memory" / "short"
    short_files = list(short_dir.glob("session_*.json")) if short_dir.exists() else []
    temp_memory = TempMemory()
    temp_files = temp_memory.get_pending_sessions()

    pending_files = []  # [(path, conversations), ...]
    for f in short_files:
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
                convs = data.get("conversations", [])
                if isinstance(convs, list) and convs:
                    pending_files.append((f, convs, "short/"))
                else:
                    f.unlink()
        except Exception:
            try:
                f.unlink()
            except Exception:
                pass
    for f in temp_files:
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
                convs = data.get("conversations", [])
                if isinstance(convs, list) and convs:
                    pending_files.append((f, convs, "temp/"))
                else:
                    f.unlink()
        except Exception:
            try:
                f.unlink()
            except Exception:
                pass

    if pending_files:
        print(f"[Dialog] 发现 {len(pending_files)} 个孤儿对话文件，将在后台整理...")

        class CleanupWorker(QObject):
            finished = Signal(int)
            def do_cleanup(self):
                cnt = 0
                llm = LLMClient(config)
                ident = load_identity()
                long_mem = LongTermMemory()
                mid_mem = MidTermMemory()
                user_profile = UserProfile()
                for filepath, convs, source in pending_files:
                    try:
                        # 生成结构化记忆条目
                        entries = llm.generate_summary(convs, ident)
                        session_folder = long_mem.save_session(convs, summary=None)
                        if entries:
                            long_mem.add_entries(session_folder, entries)
                        # 保存摘要文本（兼容）
                        summary_text = " | ".join([e.get("content", "") for e in entries]) if entries else ""
                        summary_file = session_folder / "summary.txt"
                        with open(summary_file, 'w', encoding='utf-8') as f:
                            f.write(summary_text)
                        # 加入中期记忆
                        mid_mem.add_session(session_folder, summary_text, convs, len(convs))
                        # 更新画像
                        profile_json_str = json.dumps(user_profile.data, ensure_ascii=False)
                        profile_update = llm.generate_profile_update(convs, profile_json_str, ident)
                        if profile_update:
                            user_profile.update_profile(profile_update)
                        user_profile.increment_stats(len(convs))
                        filepath.unlink()
                        cnt += 1
                        print(f"[Dialog] 已整理 {source}{filepath.name}")
                    except Exception as e:
                        print(f"[Dialog] 整理 {source}{filepath.name} 失败: {e}")
                        break
                self.finished.emit(cnt)

        cleanup_thread = QThread()
        cleanup_worker = CleanupWorker()
        cleanup_worker.moveToThread(cleanup_thread)
        cleanup_worker.finished.connect(
            lambda n: (QMessageBox.information(None, "提示", f"已整理 {n} 个之前的对话到长期记忆") if n else None, cleanup_thread.quit())
        )
        cleanup_thread.started.connect(cleanup_worker.do_cleanup)
        cleanup_thread.finished.connect(cleanup_thread.deleteLater)
        cleanup_thread.start()

    dialog = TalkDialog()
    dialog.exec_()


if __name__ == "__main__":
    show_talk_dialog()
