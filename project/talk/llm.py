"""
LLM请求模块
负责与大模型API通信
"""

import json
import time
import sys
import re
import requests
from pathlib import Path


def _get_app_root():
    """返回应用根目录（用户可写文件路径）。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def _get_data_root():
    """返回资源根目录（只读资源路径，identity/ 等）。"""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        exe_dir = Path(sys.executable).resolve().parent
        if (exe_dir / "_internal" / "identity").exists():
            return exe_dir / "_internal"
        return exe_dir
    return _get_app_root()


class LLMClient:
    """大模型API客户端"""

    # 历史判断的系统提示词
    HISTORY_CHECK_SYSTEM = """你是一个对话助手。用户正在询问是否需要查看历史对话来回答当前问题。
请判断当前问题是否需要查看历史对话才能回答。
判断规则：
- 如果问题涉及"之前"、"刚才"、"上次"、"之前说过"、"记得吗"等指代历史的内容，必须回答"需要"
- 如果问题涉及具体的之前讨论过的内容、名字、事件等，必须回答"需要"
- 如果问题是一个全新的独立问题，可以立即回答不需要历史，回答"不需要"
- 如果判断"需要"，请在后面列出最相关的会话编号（多个用逗号分隔），格式示例: "需要:0,2"
- 如果判断"不需要"，只回答"不需要"
只回答以上格式，不要回答其他内容。"""
    
    # 摘要生成的系统提示词
    SUMMARY_SYSTEM = """你是一个对话总结助手。请将下面的对话内容总结为结构化的记忆条目。
要求：
1. 从对话中提取关键信息、主人提到的重要事项、宠物做出的承诺或约定
2. 输出严格的 JSON 数组格式，每个元素包含 "content"（记忆内容，不超过100字）和 "tags"（1~3个标签关键词的数组）
3. 若对话中无实质内容，返回空数组 []
4. 示例格式：[{"content": "用户答应买小鱼干","tags": ["承诺","食物"]}]

只输出 JSON，不要输出其他内容。"""

    def __init__(self, config_manager):
        """
        初始化LLM客户端
        
        Args:
            config_manager: 配置管理器实例
        """
        self.config = config_manager
        self.session = requests.Session()
        self.reload_config()
    
    def reload_config(self):
        """重新加载配置"""
        self.api_url = self.config.api_url
        self.api_key = self.config.api_key
        self.model = self.config.model
        self.max_retries = self.config.max_retries
        self.timeout = self.config.timeout
        self.extra_params = self.config.get_validated_extra_params()
    
    def _make_request(self, messages, retry_count=0):
        """
        发送API请求
        
        Args:
            messages: 消息列表
            retry_count: 当前重试次数
            
        Returns:
            API响应内容
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7
        }
        
        # 合并额外参数
        if self.extra_params:
            data.update(self.extra_params)
        
        try:
            response = self.session.post(
                self.api_url,
                headers=headers,
                json=data,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            elif response.status_code == 401:
                raise Exception("API密钥无效或已过期")
            elif response.status_code == 429:
                # 限流，稍后重试
                if retry_count < self.max_retries:
                    time.sleep(2 ** retry_count)
                    return self._make_request(messages, retry_count + 1)
                raise Exception("请求过于频繁，请稍后再试")
            else:
                raise Exception(f"API请求失败: {response.status_code}")
        
        except requests.exceptions.Timeout:
            if retry_count < self.max_retries:
                time.sleep(1)
                return self._make_request(messages, retry_count + 1)
            raise Exception("请求超时，请检查网络连接")
        except requests.exceptions.ConnectionError:
            raise Exception("无法连接到API服务器，请检查网络")
        except Exception as e:
            raise e
    
    def chat(self, system_prompt, user_input, mid_context="", history_context="",
             short_context_msgs=None, max_context_tokens=4000):
        """
        发送对话请求（带 Token 预算控制和记忆分层上下文）

        Args:
            system_prompt: 系统提示词（身份设定 + 用户画像）
            user_input: 用户输入
            mid_context: 中期记忆上下文字符串
            history_context: 长期记忆详细历史字符串
            short_context_msgs: 短期记忆 OpenAI 格式消息列表
            max_context_tokens: 最大上下文 token 数

        Returns:
            AI回复内容
        """
        messages = []

        # 1. system prompt
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # 2. 中期记忆（始终带入，role=system）
        if mid_context:
            messages.append({"role": "system", "content": f"以下是近期会话摘要：\n{mid_context}"})

        # 3. 长期记忆详细历史（role=system）
        if history_context:
            messages.append({"role": "system", "content": f"以下是历史对话记录：\n{history_context}"})

        # 4. 短期记忆对话历史（user/assistant 交替）
        if short_context_msgs and isinstance(short_context_msgs, list):
            for msg in short_context_msgs:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content})

        # 5. 当前用户输入
        user_msg = {"role": "user", "content": user_input}

        # Token 预算截断（截断中间上下文，保持 system + user 不变）
        budget = TokenBudget(max_context_tokens)
        kept_messages = budget.truncate_context(
            [m for m in messages if m["role"] == "system" and m["content"] != system_prompt],
            system_prompt, user_input
        )

        # 重建最终消息列表
        final_messages = []
        if system_prompt:
            final_messages.append({"role": "system", "content": system_prompt})
        final_messages.extend(kept_messages)
        if short_context_msgs and isinstance(short_context_msgs, list):
            for msg in short_context_msgs:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role in ("user", "assistant") and content:
                    final_messages.append({"role": role, "content": content})
        final_messages.append(user_msg)

        return self._make_request(final_messages)
    
    def check_need_history(self, user_input, short_context="", summaries=None):
        """
        询问是否需要查看历史对话

        Args:
            user_input: 用户当前输入
            short_context: 短时记忆上下文
            summaries: [(folder_name, summary_text), ...] 所有历史会话摘要

        Returns:
            (need_history, folder_names)
            need_history: True表示需要历史，False表示不需要
            folder_names: 需要加载的文件夹名列表
        """
        context_parts = []

        if summaries:
            summary_lines = []
            for i, (folder_name, summary_text) in enumerate(summaries):
                summary_lines.append(f"[{i}] {folder_name}: {summary_text}")
            context_parts.append("历史会话摘要：\n" + "\n".join(summary_lines))

        if short_context:
            context_parts.append(f"本次对话上下文：\n{short_context}")

        context = "\n\n".join(context_parts) if context_parts else "无"

        messages = [
            {"role": "system", "content": self.HISTORY_CHECK_SYSTEM},
            {"role": "user", "content": f"当前问题：{user_input}\n\n可用上下文：\n{context}\n\n请判断是否需要查看历史对话？"}
        ]

        response = self._make_request(messages).strip()

        if "不需要" in response:
            return False, []

        folder_names = []
        if "需要" in response and summaries:
            colon_idx = response.find(":")
            if colon_idx != -1:
                indices_part = response[colon_idx + 1:]
                try:
                    for idx_str in indices_part.split(","):
                        idx = int(idx_str.strip())
                        if 0 <= idx < len(summaries):
                            folder_names.append(summaries[idx][0])
                except (ValueError, IndexError):
                    pass

        return True, folder_names
    
    def generate_summary(self, conversations, system_prompt):
        """
        生成结构化记忆条目

        Args:
            conversations: 对话记录列表
            system_prompt: 系统提示词（未使用，保留以兼容调用方）

        Returns:
            list: [{"content": "...", "tags": ["标签"]}, ...]
        """
        if not conversations:
            return []

        formatted = []
        for conv in conversations:
            formatted.append(f"用户: {conv.get('user', '')}")
            formatted.append(f"助手: {conv.get('assistant', '')}")
        conversation_text = "\n".join(formatted)

        messages = [
            {"role": "system", "content": self.SUMMARY_SYSTEM},
            {"role": "user", "content": f"请总结以下对话：\n\n{conversation_text}"}
        ]

        response = self._make_request(messages).strip()

        # 尝试解析 JSON 数组
        try:
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                entries = json.loads(json_match.group())
                if isinstance(entries, list):
                    return entries
        except Exception:
            pass

        # 回退：生成一条默认 entry
        return [{"content": response[:200], "tags": []}]

    # 用户画像提取的系统提示词
    PROFILE_UPDATE_SYSTEM = """你是一个用户画像分析助手。请从对话中提取用户偏好、习惯和重要事件。
要求：
1. 只输出有明确依据的信息，不要臆测
2. 输出严格的 JSON 格式，包含以下字段（若某项无内容则为空对象或空数组）：
   - preferences_to_update: {"key": "value"} 格式的用户偏好
   - new_habits: [{"habit": "习惯描述", "confidence": "high/medium/low"}]
   - new_events: [{"date": "YYYY-MM-DD", "event": "事件描述", "source_session": ""}]
3. 若对话中无新信息，返回 {"preferences_to_update": {}, "new_habits": [], "new_events": []}

只输出 JSON，不要输出其他内容。"""

    def generate_profile_update(self, conversations, current_profile_json, identity):
        """
        从对话中提取并更新用户画像

        Args:
            conversations: 对话记录列表
            current_profile_json: 当前画像 JSON 字符串
            identity: 身份设定文本

        Returns:
            dict: {"preferences_to_update": {}, "new_habits": [], "new_events": []}
        """
        if not conversations:
            return {"preferences_to_update": {}, "new_habits": [], "new_events": []}

        formatted = []
        for conv in conversations:
            formatted.append(f"用户: {conv.get('user', '')}")
            formatted.append(f"助手: {conv.get('assistant', '')}")
        conversation_text = "\n".join(formatted)

        messages = [
            {"role": "system", "content": self.PROFILE_UPDATE_SYSTEM},
            {"role": "system", "content": f"当前用户画像：\n{current_profile_json}\n\n身份设定：\n{identity}"},
            {"role": "user", "content": f"请分析以下对话，提取用户信息：\n\n{conversation_text}"}
        ]

        response = self._make_request(messages).strip()

        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception:
            pass

        return {"preferences_to_update": {}, "new_habits": [], "new_events": []}


def load_identity(identity_path=None):
    """
    加载身份设定
    
    Args:
        identity_path: 身份文件路径，默认使用项目根目录下的 identity/personality.txt
        
    Returns:
        身份设定文本
    """
    if identity_path is None:
        identity_path = _get_data_root() / "identity" / "personality.txt"
    
    identity_path = Path(identity_path)
    
    if identity_path.exists():
        try:
            with open(identity_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception:
            pass
    
    # 默认身份设定
    return """你是一只傲娇小猫，说话语气别扭、嘴硬，表面冷淡不在意，实则愿意陪伴对方。用词软萌带点小脾气，不会过分热情，常口是心非，回应简短可爱，符合猫咪的神态与性格。"""


class TokenBudget:
    """Token 预算管理器（无 tiktoken 依赖，基于字符数估算）"""

    @staticmethod
    def _estimate_tokens(text):
        """估算文本 token 数（粗略）：中文 1.5 token/字，英文 0.75 token/字符"""
        if not text:
            return 0
        chinese = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other = len(text) - chinese
        return int(chinese * 1.5 + other * 0.75)

    @staticmethod
    def estimate_messages_tokens(messages):
        """估算 OpenAI 格式 messages 列表总 token 数"""
        total = 0
        for msg in messages:
            total += 4  # 每个消息 overhead
            total += TokenBudget._estimate_tokens(msg.get("role", ""))
            total += TokenBudget._estimate_tokens(msg.get("content", ""))
        return total

    def __init__(self, max_tokens=4000):
        self.max_tokens = max_tokens

    def truncate_context(self, messages, system_msg, user_msg, reserve_tokens=500):
        """
        截断中间上下文以满足 token 预算，返回截断后的 messages 列表
        
        Args:
            messages: 待截断的中间上下文（role=system 的中期+长期记忆消息）
            system_msg: system prompt 字符串（不可截断）
            user_msg: 当前用户输入字符串（不可截断）
            reserve_tokens: 为模型回复预留的 token 数
        
        Returns:
            截断后的 messages 列表（不含 system_msg 和 user_msg）
        """
        system_tokens = self._estimate_tokens(system_msg)
        user_tokens = self._estimate_tokens(user_msg)
        available = self.max_tokens - system_tokens - user_tokens - reserve_tokens
        if available < 0:
            available = 500

        before_tokens = self.estimate_messages_tokens(messages)
        kept = []
        for msg in messages:
            msg_tokens = self.estimate_messages_tokens([msg])
            if available >= msg_tokens:
                kept.append(msg)
                available -= msg_tokens
            else:
                break

        after_tokens = self.estimate_messages_tokens(kept)
        print(f"[TokenBudget] 截断前: 总tokens={before_tokens}, 中间上下文={before_tokens - system_tokens - user_tokens}")
        print(f"[TokenBudget] 截断后: 总tokens={after_tokens + system_tokens + user_tokens}, 中间上下文={after_tokens}")

        if after_tokens == 0 and before_tokens > 0:
            print("[TokenBudget] 警告：所有中间上下文均被截断，模型无历史参考")

        return kept
