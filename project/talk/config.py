"""
配置管理模块
负责加载和保存对话功能的配置文件
"""

import json
import winreg
from pathlib import Path


class ConfigManager:
    """配置管理器类"""
    
    def __init__(self, config_path=None):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径，默认使用项目根目录下的 talk/config.json
        """
        if config_path is None:
            # 获取项目根目录
            project_root = Path(__file__).parent.parent
            config_path = project_root / "talk" / "config.json"
        
        self.config_path = Path(config_path)
        self._config = None
        self.load()
    
    def load(self):
        """从配置文件加载配置"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
            except Exception as e:
                print(f"加载配置文件失败: {e}")
                self._config = self._get_default_config()
        else:
            self._config = self._get_default_config()
    
    def save(self):
        """保存配置到文件"""
        try:
            # 确保父目录存在
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            return False
    
    def _get_default_config(self):
        """获取默认配置"""
        return {
            "provider": "deepseek",
            "deepseek": {
                "api_url": "https://api.deepseek.com/v1/chat/completions",
                "api_key": "your-api-key-here",
                "model": "deepseek-v4-pro",
                "max_retries": 3,
                "timeout": 60,
                "extra_params": {
                    "reasoning_effort": "high",
                    "thinking": {"type": "enabled"}
                }
            },
            "openai": {
                "api_url": "https://api.openai.com/v1/chat/completions",
                "api_key": "your-api-key-here",
                "model": "gpt-3.5-turbo",
                "max_retries": 3,
                "timeout": 60,
                "extra_params": {}
            }
        }
    
    def get(self, key, default=None):
        """
        获取配置项（从当前服务商配置）
        
        Args:
            key: 配置键名
            default: 默认值
            
        Returns:
            配置值
        """
        current_config = self.get_current_provider_config()
        return current_config.get(key, default)
    
    def set(self, key, value):
        """
        设置配置项（设置到当前服务商配置）
        
        Args:
            key: 配置键名
            value: 配置值
        """
        provider = self.provider
        if provider in self._config:
            self._config[provider][key] = value
    
    @property
    def provider(self):
        """获取当前服务商名称"""
        return self._config.get("provider", "deepseek")
    
    @provider.setter
    def provider(self, value):
        """设置当前服务商名称"""
        self._config["provider"] = value
    
    def get_provider_config(self, provider):
        """
        获取指定服务商的配置
        
        Args:
            provider: 服务商名称
            
        Returns:
            服务商配置字典
        """
        return self._config.get(provider, {})
    
    def get_current_provider_config(self):
        """
        获取当前服务商的配置
        
        Returns:
            当前服务商配置字典
        """
        return self.get_provider_config(self.provider)
    
    @property
    def api_url(self):
        """获取API地址"""
        return self.get("api_url")
    
    @api_url.setter
    def api_url(self, value):
        """设置API地址"""
        self.set("api_url", value)
    
    @property
    def api_key(self):
        """获取API密钥，从持久化环境变量读取"""
        provider = self.provider.upper()
        env_key = f"{provider}_API_KEY"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_READ)
            try:
                value, _ = winreg.QueryValueEx(key, env_key)
                winreg.CloseKey(key)
                return value
            except WindowsError:
                winreg.CloseKey(key)
                return ""
        except Exception:
            return ""
    
    @api_key.setter
    def api_key(self, value):
        """设置API密钥"""
        self.set("api_key", value)
    
    @property
    def model(self):
        """获取模型名称"""
        return self.get("model")
    
    @model.setter
    def model(self, value):
        """设置模型名称"""
        self.set("model", value)
    
    @property
    def max_retries(self):
        """获取最大重试次数"""
        return self.get("max_retries", 3)
    
    @property
    def timeout(self):
        """获取超时时间"""
        return self.get("timeout", 60)
    
    @property
    def extra_params(self):
        """获取额外参数"""
        return self.get("extra_params", {})
