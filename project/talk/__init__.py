"""
对话模块初始化文件
导出主要类和函数
"""

from .config import ConfigManager
from .memory import ShortTermMemory, LongTermMemory
from .llm import LLMClient, load_identity
from .dialog import TalkDialog, show_talk_dialog

__all__ = [
    'ConfigManager',
    'ShortTermMemory',
    'LongTermMemory',
    'LLMClient',
    'load_identity',
    'TalkDialog',
    'show_talk_dialog'
]
