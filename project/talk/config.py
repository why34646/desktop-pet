"""
配置管理模块
负责加载和保存对话功能的配置文件
"""

import json
import winreg
import sys
from pathlib import Path


def _get_app_root():
    """返回应用根目录（用户可写文件路径）。

    - 打包模式: exe 所在目录 (dist/DesktopPet/)
    - 开发模式: 项目根目录
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def _get_data_root():
    """返回资源根目录（只读资源路径）。

    - 打包模式: PyInstaller 的 _internal/ 目录 (sys._MEIPASS)
    - 开发模式: 同 _get_app_root()
    """
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        exe_dir = Path(sys.executable).resolve().parent
        if (exe_dir / "_internal" / "talk").exists():
            return exe_dir / "_internal"
        return exe_dir
    return _get_app_root()


class ConfigManager:
    """配置管理器类"""

    ALLOWED_EXTRA_PARAMS = {"reasoning_effort", "thinking"}

    def __init__(self, config_path=None):
        """
        初始化配置管理器

        路径策略:
        - 开发模式: 读写同一个 talk/config.json (位于项目根目录)
        - 打包模式: 默认从 _internal/talk/config.json 读取初始值，
          但读写都在 exe 同目录的 talk/config.json（确保配置持久化）

        Args:
            config_path: 配置文件路径，默认使用应用根目录下的 talk/config.json
        """
        if config_path is None:
            # 用户可写目录下的 config.json（用于读写）
            user_root = _get_app_root()
            self.config_path = user_root / "talk" / "config.json"

            # 若用户配置文件尚不存在，但资源目录下有默认配置，则复制一份
            if not self.config_path.exists():
                data_root = _get_data_root()
                default_cfg = data_root / "talk" / "config.json"
                if default_cfg.exists() and default_cfg != self.config_path:
                    try:
                        self.config_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(default_cfg, 'r', encoding='utf-8') as src:
                            content = src.read()
                        with open(self.config_path, 'w', encoding='utf-8') as dst:
                            dst.write(content)
                    except Exception:
                        # 复制失败也不致命，后续用默认配置
                        pass
        else:
            self.config_path = Path(config_path)
        self._config = None
        self._cached_api_key = None
        self._migration_done = False
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

        self._migrate_api_keys()
    
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

    def _migrate_api_keys(self):
        """将配置文件中的旧 api_key 迁移到注册表并从内存中移除（仅执行一次）"""
        if self._migration_done:
            return
        self._migration_done = True
        modified = False
        for provider in ("deepseek", "openai"):
            provider_config = self._config.get(provider, {})
            if "api_key" in provider_config:
                api_key = provider_config.pop("api_key")
                modified = True
                if api_key and api_key != "your-api-key-here":
                    self._set_registry_key(provider.upper() + "_API_KEY", api_key)
        if modified:
            self.save()

    def _set_registry_key(self, name, value):
        """写入注册表持久化环境变量"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
            winreg.CloseKey(key)
            return True
        except Exception:
            return False

    def _get_registry_key(self, name):
        """从注册表读取持久化环境变量"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_READ)
            try:
                value, _ = winreg.QueryValueEx(key, name)
                winreg.CloseKey(key)
                return value
            except WindowsError:
                winreg.CloseKey(key)
                return ""
        except Exception:
            return ""
    
    def _get_default_config(self):
        """获取默认配置"""
        return {
            "provider": "deepseek",
            "deepseek": {
                "api_url": "https://api.deepseek.com/v1/chat/completions",
                "model": "deepseek-v4-pro",
                "max_retries": 3,
                "timeout": 60,
                "max_context_tokens": 4000,
                "extra_params": {
                    "reasoning_effort": "high",
                    "thinking": {"type": "enabled"}
                }
            },
            "openai": {
                "api_url": "https://api.openai.com/v1/chat/completions",
                "model": "gpt-3.5-turbo",
                "max_retries": 3,
                "timeout": 60,
                "max_context_tokens": 4000,
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
        """获取API密钥，从持久化环境变量读取（首次读取后缓存）"""
        if self._cached_api_key is None:
            provider = self.provider.upper()
            env_key = f"{provider}_API_KEY"
            self._cached_api_key = self._get_registry_key(env_key)
        return self._cached_api_key
    
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

    def get_validated_extra_params(self):
        """获取经过白名单过滤的额外参数"""
        raw = self.extra_params
        if not isinstance(raw, dict):
            return {}
        return {k: v for k, v in raw.items() if k in self.ALLOWED_EXTRA_PARAMS}

    def get_max_context_tokens(self):
        """获取最大上下文 token 数（默认 4000）"""
        cfg = self.get_current_provider_config()
        return cfg.get("max_context_tokens", 4000)
