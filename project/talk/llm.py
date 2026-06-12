"""
LLM请求模块
负责与大模型API通信
"""

import json
import time
import requests
from pathlib import Path


class LLMClient:
    """大模型API客户端"""
    
    # 历史判断的系统提示词
    HISTORY_CHECK_SYSTEM = """你是一个对话助手。用户正在询问是否需要查看历史对话来回答当前问题。
请判断当前问题是否需要查看历史对话才能回答。
判断规则：
- 如果问题涉及"之前"、"刚才"、"上次"、"之前说过"、"记得吗"等指代历史的内容，必须回答"需要"
- 如果问题涉及具体的之前讨论过的内容、名字、事件等，必须回答"需要"
- 如果问题是一个全新的独立问题，可以立即回答不需要历史，回答"不需要"
只回答"需要"或"不需要"，不要回答其他内容。"""
    
    # 摘要生成的系统提示词
    SUMMARY_SYSTEM = """你是一个对话总结助手。请将下面的对话内容总结为简洁的记忆摘要。
要求：
1. 提取对话中的关键信息、主人提到的重要事项、宠物做出的承诺或约定
2. 保持摘要简洁，一般不超过200字
3. 使用自然语言描述，不要使用列表格式
4. 摘要应该能够帮助记忆之前的对话内容"""

    def __init__(self, config_manager):
        """
        初始化LLM客户端
        
        Args:
            config_manager: 配置管理器实例
        """
        self.config = config_manager
        self.reload_config()
    
    def reload_config(self):
        """重新加载配置"""
        self.api_url = self.config.api_url
        self.api_key = self.config.api_key
        self.model = self.config.model
        self.max_retries = self.config.max_retries
        self.timeout = self.config.timeout
        self.extra_params = self.config.extra_params
    
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
            response = requests.post(
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
    
    def chat(self, system_prompt, user_input, history_context=""):
        """
        发送对话请求
        
        Args:
            system_prompt: 系统提示词（身份设定）
            user_input: 用户输入
            history_context: 历史上下文（可选）
            
        Returns:
            AI回复内容
        """
        messages = []
        
        # 添加系统提示词
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # 添加历史上下文
        if history_context:
            messages.append({"role": "system", "content": f"以下是历史对话记录：\n{history_context}"})
        
        # 添加用户输入
        messages.append({"role": "user", "content": user_input})
        
        return self._make_request(messages)
    
    def check_need_history(self, user_input, short_context="", long_summary=""):
        """
        询问是否需要查看历史对话
        
        Args:
            user_input: 用户当前输入
            short_context: 短时记忆上下文
            long_summary: 永久记忆摘要
            
        Returns:
            True表示需要历史，False表示不需要
        """
        context_parts = []
        
        if long_summary:
            context_parts.append(f"长期记忆摘要：\n{long_summary}")
        
        if short_context:
            context_parts.append(f"本次对话上下文：\n{short_context}")
        
        context = "\n\n".join(context_parts) if context_parts else "无"
        
        messages = [
            {"role": "system", "content": self.HISTORY_CHECK_SYSTEM},
            {"role": "user", "content": f"当前问题：{user_input}\n\n可用上下文：\n{context}\n\n请判断是否需要查看历史对话？"}
        ]
        
        response = self._make_request(messages).strip()
        
        # 解析回答
        if "不需要" in response:
            return False
        return True
    
    def generate_summary(self, conversations, system_prompt):
        """
        生成对话摘要
        
        Args:
            conversations: 对话记录列表
            system_prompt: 系统提示词
            
        Returns:
            摘要内容
        """
        if not conversations:
            return ""
        
        # 格式化对话内容
        formatted = []
        for conv in conversations:
            formatted.append(f"用户: {conv.get('user', '')}")
            formatted.append(f"助手: {conv.get('assistant', '')}")
        
        conversation_text = "\n".join(formatted)
        
        messages = [
            {"role": "system", "content": self.SUMMARY_SYSTEM},
            {"role": "user", "content": f"请总结以下对话：\n\n{conversation_text}"}
        ]
        
        return self._make_request(messages)


def load_identity(identity_path=None):
    """
    加载身份设定
    
    Args:
        identity_path: 身份文件路径，默认使用项目根目录下的 identity/personality.txt
        
    Returns:
        身份设定文本
    """
    if identity_path is None:
        project_root = Path(__file__).parent.parent.parent
        identity_path = project_root / "identity" / "personality.txt"
    
    identity_path = Path(identity_path)
    
    if identity_path.exists():
        try:
            with open(identity_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception:
            pass
    
    # 默认身份设定
    return """你是一只傲娇小猫，说话语气别扭、嘴硬，表面冷淡不在意，实则愿意陪伴对方。用词软萌带点小脾气，不会过分热情，常口是心非，回应简短可爱，符合猫咪的神态与性格。"""
