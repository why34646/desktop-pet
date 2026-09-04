"""
记忆管理模块
负责短时记忆和永久记忆的读写功能
"""

import json
import time
import sys
import uuid
from pathlib import Path
from datetime import datetime


def _get_app_root():
    """返回应用根目录（用户可写文件路径）。

    memory/short/ 和 memory/long/ 都是用户可写数据，放在 exe 同目录。
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def _get_data_root():
    """返回资源根目录（只读资源路径，memory.py 中基本不使用，保留以备扩展）。"""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        exe_dir = Path(sys.executable).resolve().parent
        if (exe_dir / "_internal").exists():
            return exe_dir / "_internal"
        return exe_dir
    return _get_app_root()


class ShortTermMemory:
    """短时记忆管理器"""

    def __init__(self, memory_path=None):
        """
        初始化短时记忆管理器

        Args:
            memory_path: 短时记忆文件夹路径，默认使用应用根目录下的 memory/short/
        """
        if memory_path is None:
            project_root = _get_app_root()
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
        latest_file = max(json_files, key=lambda p: int(p.stem.split('_')[1]))
        
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
            project_root = _get_app_root()
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


class MidTermMemory:
    """中期记忆管理器 — 保存最近 N 个已结束会话的索引摘要"""

    def __init__(self, mid_path=None, max_entries=5):
        if mid_path is None:
            mid_path = _get_app_root() / "memory" / "mid"
        self.mid_path = Path(mid_path)
        self.mid_path.mkdir(parents=True, exist_ok=True)
        self.max_entries = max_entries
        self.index_file = self.mid_path / "session_index.json"
        self._data = self._load_index()

    def _load_index(self):
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {"max_entries": self.max_entries, "entries": []}

    def _save_index(self):
        try:
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[MidTerm] 保存失败: {e}")

    def add_session(self, session_folder, summary, conversations, message_count):
        """新增一条会话索引，超过 max_entries 时移除最旧条目"""
        entry = {
            "session_folder": session_folder.name,
            "summary": summary,
            "key_entities": [],
            "ended_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "message_count": message_count
        }
        self._data["entries"].insert(0, entry)
        self._data["entries"] = self._data["entries"][:self.max_entries]
        self._save_index()

    def get_recent_entries(self, count=3):
        return self._data["entries"][:count]

    def get_formatted_context(self, count=3):
        entries = self.get_recent_entries(count)
        if not entries:
            return ""
        lines = ["[近期会话摘要]"]
        for i, e in enumerate(entries):
            lines.append(f"[{i}] {e['ended_at']}: {e['summary']}")
        return "\n".join(lines)

    def clear(self):
        self._data = {"max_entries": self.max_entries, "entries": []}
        self._save_index()


class UserProfile:
    """用户画像管理器"""

    def __init__(self, profile_path=None):
        if profile_path is None:
            profile_path = _get_app_root() / "memory" / "long" / "user_profile.json"
        self.profile_path = Path(profile_path)
        self.profile_path.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()

    def _load(self):
        if self.profile_path.exists():
            try:
                with open(self.profile_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return self._default_profile()

    def _default_profile(self):
        return {
            "version": 1,
            "last_updated": "",
            "preferences": {},
            "habits": [],
            "important_events": [],
            "interaction_stats": {
                "total_sessions": 0,
                "total_messages": 0,
                "first_interaction": "",
                "last_interaction": ""
            }
        }

    def save(self):
        self.data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(self.profile_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[UserProfile] 保存失败: {e}")

    def update_profile(self, extracted_data):
        """增量更新画像，extracted_data 来自 LLM 的 JSON 输出"""
        prefs = extracted_data.get("preferences_to_update", {})
        for k, v in prefs.items():
            self.data["preferences"][k] = v
        for h in extracted_data.get("new_habits", []):
            if h.get("habit"):
                h["first_observed"] = datetime.now().strftime("%Y-%m-%d")
                self.data["habits"].insert(0, h)
        for ev in extracted_data.get("new_events", []):
            if ev.get("event"):
                self.data["important_events"].insert(0, ev)
        self.save()

    def format_for_prompt(self):
        """格式化为 system prompt 追加段落"""
        parts = []
        prefs = self.data.get("preferences", {})
        if prefs:
            pref_lines = [f"{k}: {v}" for k, v in prefs.items()]
            parts.append("用户偏好：" + "；".join(pref_lines))
        habits = self.data.get("habits", [])
        if habits:
            habit_lines = [h.get("habit", "") for h in habits[:3] if h.get("habit")]
            if habit_lines:
                parts.append("用户习惯：" + "；".join(habit_lines))
        events = self.data.get("important_events", [])
        if events:
            ev_lines = [f"{e.get('date','')} {e.get('event','')}" for e in events[:3] if e.get("event")]
            if ev_lines:
                parts.append("重要事件：" + "；".join(ev_lines))
        if not parts:
            return ""
        return "[用户画像]\n" + "\n".join(parts)

    def increment_stats(self, session_messages):
        stats = self.data["interaction_stats"]
        stats["total_sessions"] += 1
        stats["total_messages"] += session_messages
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stats["last_interaction"] = now
        if not stats["first_interaction"]:
            stats["first_interaction"] = now


class LongTermMemory:
    """永久记忆管理器"""

    def __init__(self, memory_path=None):
        """
        初始化永久记忆管理器

        Args:
            memory_path: 永久记忆文件夹路径，默认使用项目根目录下的 memory/long/
        """
        if memory_path is None:
            project_root = _get_app_root()
            memory_path = project_root / "memory" / "long"

        self.memory_path = Path(memory_path)
        self.memory_path.mkdir(parents=True, exist_ok=True)
        self._summaries_cache = None
    
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

        self._summaries_cache = None

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
        if self._summaries_cache is not None:
            return self._summaries_cache

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

        self._summaries_cache = results
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

    # ──────────────── 记忆归因溯源：新方法 ────────────────

    def add_entries(self, session_folder, entries_list):
        """批量写入记忆条目到 memory_index.json"""
        idx_file = session_folder / "memory_index.json"
        data = {
            "session_folder": session_folder.name,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "entries": []
        }
        try:
            if idx_file.exists():
                with open(idx_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if "entries" not in data:
                        data["entries"] = []
        except Exception:
            pass
        for item in entries_list:
            entry = {
                "id": uuid.uuid4().hex,
                "content": item.get("content", ""),
                "source_session": session_folder.name,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "tags": item.get("tags", []),
                "access_count": 0
            }
            data["entries"].append(entry)
        try:
            with open(idx_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[LongTerm] 写入 memory_index 失败: {e}")

    def _ensure_index(self, session_folder):
        """确保 session_folder 下有 memory_index.json（兼容旧 summary.txt）"""
        idx_file = session_folder / "memory_index.json"
        if idx_file.exists():
            return
        summary_file = session_folder / "summary.txt"
        content = ""
        if summary_file.exists():
            try:
                with open(summary_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
            except Exception:
                pass
        data = {
            "session_folder": session_folder.name,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "entries": [{
                "id": uuid.uuid4().hex,
                "content": content,
                "source_session": session_folder.name,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "tags": [],
                "access_count": 0
            }]
        }
        try:
            with open(idx_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get_all_entries(self):
        """返回所有会话的所有记忆条目，按 created_at 倒序"""
        all_entries = []
        for folder in sorted(self.memory_path.iterdir(), key=lambda p: p.name, reverse=True):
            if not folder.is_dir():
                continue
            self._ensure_index(folder)
            idx_file = folder / "memory_index.json"
            if not idx_file.exists():
                continue
            try:
                with open(idx_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for entry in data.get("entries", []):
                        entry["_folder"] = folder.name
                        all_entries.append(entry)
            except Exception:
                continue
        return all_entries

    def search_entries(self, tag=None, keyword=None):
        """按标签或关键词搜索记忆条目"""
        all_entries = self.get_all_entries()
        results = []
        for entry in all_entries:
            if tag and tag not in entry.get("tags", []):
                continue
            if keyword and keyword.lower() not in entry.get("content", "").lower():
                continue
            results.append(entry)
        return results

    def update_entry(self, entry_id, new_content=None, new_tags=None):
        for folder in self.memory_path.iterdir():
            if not folder.is_dir():
                continue
            idx_file = folder / "memory_index.json"
            if not idx_file.exists():
                continue
            try:
                with open(idx_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for entry in data.get("entries", []):
                    if entry["id"] == entry_id:
                        if new_content is not None:
                            entry["content"] = new_content
                        if new_tags is not None:
                            entry["tags"] = new_tags
                        with open(idx_file, 'w', encoding='utf-8') as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                        return True
            except Exception:
                continue
        return False

    def delete_entry(self, entry_id):
        for folder in self.memory_path.iterdir():
            if not folder.is_dir():
                continue
            idx_file = folder / "memory_index.json"
            if not idx_file.exists():
                continue
            try:
                with open(idx_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                before = len(data["entries"])
                data["entries"] = [e for e in data.get("entries", []) if e["id"] != entry_id]
                if len(data["entries"]) < before:
                    with open(idx_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    return True
            except Exception:
                continue
        return False

    def increment_access_count(self, entry_id):
        for folder in self.memory_path.iterdir():
            if not folder.is_dir():
                continue
            idx_file = folder / "memory_index.json"
            if not idx_file.exists():
                continue
            try:
                with open(idx_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for entry in data.get("entries", []):
                    if entry["id"] == entry_id:
                        entry["access_count"] = entry.get("access_count", 0) + 1
                        with open(idx_file, 'w', encoding='utf-8') as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                        return True
            except Exception:
                continue
        return False

    def get_history_by_folders(self, folder_names):
        """加载指定文件夹的对话历史，同时追踪记忆引用"""
        formatted = []
        for name in folder_names:
            folder = self.memory_path / name
            if not folder.exists():
                continue
            self._ensure_index(folder)
            idx_file = folder / "memory_index.json"
            if idx_file.exists():
                try:
                    with open(idx_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    for entry in data.get("entries", []):
                        self.increment_access_count(entry["id"])
                except Exception:
                    pass
            history_file = folder / "history.json"
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
