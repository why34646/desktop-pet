"""
记忆管理模块
负责短时记忆和永久记忆的读写功能
"""

import json
import time
from pathlib import Path
from datetime import datetime


class ShortTermMemory:
    """短时记忆管理器"""
    
    def __init__(self, memory_path=None):
        """
        初始化短时记忆管理器
        
        Args:
            memory_path: 短时记忆文件夹路径，默认使用项目根目录下的 memory/short/
        """
        if memory_path is None:
            project_root = Path(__file__).parent.parent.parent
            memory_path = project_root / "memory" / "short"
        
        self.memory_path = Path(memory_path)
        self.memory_path.mkdir(parents=True, exist_ok=True)
        
        self.current_session_file = None
        self.conversations = []
    
    def new_session(self):
        """创建新的会话"""
        timestamp = int(time.time())
        self.current_session_file = self.memory_path / f"session_{timestamp}.json"
        self.conversations = []
        return self.current_session_file
    
    def load_latest_session(self):
        """加载最新的会话"""
        json_files = list(self.memory_path.glob("session_*.json"))
        if not json_files:
            return self.new_session()
        
        # 按修改时间排序，获取最新的
        latest_file = max(json_files, key=lambda p: p.stat().st_mtime)
        
        try:
            with open(latest_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                conversations = data.get("conversations", [])
                if not isinstance(conversations, list):
                    return self.new_session()
                self.conversations = conversations
                self.current_session_file = latest_file
                return latest_file
        except Exception:
            return self.new_session()
    
    def add_conversation(self, user_input, ai_response):
        """
        添加一轮对话
        
        Args:
            user_input: 用户输入
            ai_response: AI回复
        """
        self.conversations.append({
            "user": user_input,
            "assistant": ai_response,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    
    def save(self):
        """保存当前会话"""
        if self.current_session_file is None:
            self.new_session()
        
        data = {
            "session_file": str(self.current_session_file),
            "conversations": self.conversations
        }
        
        try:
            with open(self.current_session_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存短时记忆失败: {e}")
            return False
    
    def get_conversations(self):
        """获取所有对话记录"""
        return self.conversations
    
    def format_for_context(self):
        """
        格式化对话用于上下文拼接
        
        Returns:
            格式化的对话字符串
        """
        if not self.conversations:
            return ""
        
        formatted = []
        for conv in self.conversations:
            formatted.append(f"用户: {conv['user']}")
            formatted.append(f"助手: {conv['assistant']}")
        
        return "\n".join(formatted)
    
    def clear(self):
        """清空当前会话"""
        self.conversations = []
        self.current_session_file = None
    
    def delete_current(self):
        """删除当前会话文件"""
        if self.current_session_file and self.current_session_file.exists():
            try:
                self.current_session_file.unlink()
            except Exception:
                pass
        self.conversations = []
        self.current_session_file = None


class TempMemory:
    """临时记忆管理器 - 保存未总结的会话"""

    def __init__(self, temp_path=None):
        if temp_path is None:
            project_root = Path(__file__).parent.parent.parent
            temp_path = project_root / "memory" / "temp"
        self.temp_path = Path(temp_path)
        self.temp_path.mkdir(parents=True, exist_ok=True)

    def save_unsummarized(self, conversations):
        """保存未总结的会话到 temp"""
        timestamp = int(time.time())
        temp_file = self.temp_path / f"pending_{timestamp}.json"
        data = {"conversations": conversations}
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return temp_file
        except Exception as e:
            print(f"保存临时记忆失败: {e}")
            return None

    def get_pending_sessions(self):
        """获取所有待总结的会话"""
        return list(self.temp_path.glob("pending_*.json"))

    def delete_session(self, session_file):
        """删除指定的临时会话文件"""
        if session_file.exists():
            session_file.unlink()


class LongTermMemory:
    """永久记忆管理器"""

    def __init__(self, memory_path=None):
        """
        初始化永久记忆管理器

        Args:
            memory_path: 永久记忆文件夹路径，默认使用项目根目录下的 memory/long/
        """
        if memory_path is None:
            project_root = Path(__file__).parent.parent.parent
            memory_path = project_root / "memory" / "long"

        self.memory_path = Path(memory_path)
        self.memory_path.mkdir(parents=True, exist_ok=True)
    
    def save_session(self, conversations, summary=None):
        """
        保存完整会话到永久记忆
        
        Args:
            conversations: 对话记录列表
            summary: 摘要内容（可选）
            
        Returns:
            保存的文件夹路径
        """
        # 创建以时间命名的子文件夹
        folder_name = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_folder = self.memory_path / folder_name
        session_folder.mkdir(parents=True, exist_ok=True)
        
        # 保存历史对话
        history_file = session_folder / "history.json"
        history_data = {
            "timestamp": folder_name,
            "conversations": conversations
        }
        
        try:
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存历史对话失败: {e}")
        
        # 保存摘要
        if summary:
            summary_file = session_folder / "summary.txt"
            try:
                with open(summary_file, 'w', encoding='utf-8') as f:
                    f.write(summary)
            except Exception as e:
                print(f"保存摘要失败: {e}")
        
        return session_folder
    
    def get_latest_summary(self):
        """
        获取最新的记忆摘要
        
        Returns:
            最新的摘要内容，如果没有则返回空字符串
        """
        folders = sorted([p for p in self.memory_path.iterdir() if p.is_dir()], 
                        key=lambda p: p.name, reverse=True)
        
        for folder in folders:
            summary_file = folder / "summary.txt"
            if summary_file.exists():
                try:
                    with open(summary_file, 'r', encoding='utf-8') as f:
                        return f.read()
                except Exception:
                    continue
        
        return ""
    
    def get_latest_history(self):
        """
        获取最新的一次完整对话历史
        
        Returns:
            最新的对话历史列表，如果没有则返回空列表
        """
        folders = sorted([p for p in self.memory_path.iterdir() if p.is_dir()],
                        key=lambda p: p.name, reverse=True)
        
        for folder in folders:
            history_file = folder / "history.json"
            if history_file.exists():
                try:
                    with open(history_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        conversations = data.get("conversations", [])
                        if not isinstance(conversations, list):
                            continue
                        return conversations
                except Exception:
                    continue
        
        return []
    
    def get_all_summaries(self):
        """
        获取所有已总结会话的摘要及其文件夹名

        Returns:
            [(folder_name, summary_text), ...] 列表
        """
        results = []
        folders = sorted([p for p in self.memory_path.iterdir() if p.is_dir()],
                        key=lambda p: p.name, reverse=True)

        for folder in folders:
            summary_file = folder / "summary.txt"
            if summary_file.exists():
                try:
                    with open(summary_file, 'r', encoding='utf-8') as f:
                        results.append((folder.name, f.read().strip()))
                except Exception:
                    continue

        return results

    def get_history_by_folders(self, folder_names):
        """
        按指定的文件夹名列表加载历史对话

        Args:
            folder_names: 文件夹名列表

        Returns:
            格式化的历史对话字符串
        """
        formatted = []
        for name in folder_names:
            history_file = self.memory_path / name / "history.json"
            if not history_file.exists():
                continue
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    conversations = data.get("conversations", [])
                    if not isinstance(conversations, list):
                        continue
                    for conv in conversations:
                        formatted.append(f"用户: {conv['user']}")
                        formatted.append(f"助手: {conv['assistant']}")
            except Exception:
                continue

        return "\n".join(formatted)

    def format_history_for_context(self):
        """
        格式化历史对话用于上下文拼接
        
        Returns:
            格式化的历史对话字符串
        """
        conversations = self.get_latest_history()
        if not conversations:
            return ""
        
        formatted = []
        for conv in conversations:
            formatted.append(f"用户: {conv['user']}")
            formatted.append(f"助手: {conv['assistant']}")
        
        return "\n".join(formatted)
