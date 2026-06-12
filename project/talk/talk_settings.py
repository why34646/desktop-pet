"""
对话模型设置模块
提供 DeepSeek/OpenAI 等模型的 API 配置界面
"""

import os
import sys
import winreg
from pathlib import Path

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QLabel, QLineEdit, QComboBox, QSpinBox,
                               QCheckBox, QPushButton, QMessageBox,
                               QGroupBox, QApplication)
from PySide6.QtCore import Qt

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent))
from config import ConfigManager


class TalkSettingsDialog(QDialog):
    """对话模型设置对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = ConfigManager()
        self.current_provider = self.config_manager.provider
        self.init_ui()
        self.load_config()

    def _get_persistent_env(self, name):
        """从持久化环境变量读取"""
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

    def _set_persistent_env(self, name, value):
        """设置持久化环境变量（通过 Windows Registry）"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
            winreg.CloseKey(key)
            return True
        except Exception:
            return False

    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("对话模型设置")
        self.resize(500, 480)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)

        main_layout = QVBoxLayout()

        # 模型选择区
        provider_layout = QHBoxLayout()
        provider_layout.addWidget(QLabel("模型选择："))
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["DeepSeek", "OpenAI"])
        self.provider_combo.currentTextChanged.connect(self.on_provider_changed)
        provider_layout.addWidget(self.provider_combo)
        provider_layout.addStretch()
        main_layout.addLayout(provider_layout)

        # API配置区
        config_group = QGroupBox("API 配置")
        config_layout = QGridLayout()

        # API 地址
        config_layout.addWidget(QLabel("API 地址："), 0, 0)
        self.api_url_input = QLineEdit()
        self.api_url_input.setPlaceholderText("https://api.example.com/v1/chat/completions")
        config_layout.addWidget(self.api_url_input, 0, 1)

        # API Key
        config_layout.addWidget(QLabel("API Key："), 1, 0)
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("输入后不显示明文")
        config_layout.addWidget(self.api_key_input, 1, 1)

        # 模型名称
        config_layout.addWidget(QLabel("模型名称："), 2, 0)
        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("如：deepseek-v4-pro")
        config_layout.addWidget(self.model_input, 2, 1)

        # 超时时间
        config_layout.addWidget(QLabel("超时时间："), 3, 0)
        timeout_layout = QHBoxLayout()
        self.timeout_input = QSpinBox()
        self.timeout_input.setRange(1, 300)
        self.timeout_input.setSuffix(" 秒")
        timeout_layout.addWidget(self.timeout_input)
        timeout_layout.addStretch()
        config_layout.addLayout(timeout_layout, 3, 1)

        # 最大重试次数
        config_layout.addWidget(QLabel("最大重试："), 4, 0)
        retry_layout = QHBoxLayout()
        self.max_retries_input = QSpinBox()
        self.max_retries_input.setRange(1, 10)
        self.max_retries_input.setSuffix(" 次")
        retry_layout.addWidget(self.max_retries_input)
        retry_layout.addStretch()
        config_layout.addLayout(retry_layout, 4, 1)

        config_group.setLayout(config_layout)
        main_layout.addWidget(config_group)

        # DeepSeek 专属设置
        self.deepseek_group = QGroupBox("DeepSeek 设置")
        deepseek_layout = QGridLayout()

        # 推理强度
        deepseek_layout.addWidget(QLabel("推理强度："), 0, 0)
        self.reasoning_effort_combo = QComboBox()
        self.reasoning_effort_combo.addItems(["low", "medium", "high"])
        deepseek_layout.addWidget(self.reasoning_effort_combo, 0, 1)

        # 开启思考过程
        self.thinking_checkbox = QCheckBox("开启思考过程")
        deepseek_layout.addWidget(self.thinking_checkbox, 1, 0, 1, 2)

        self.deepseek_group.setLayout(deepseek_layout)
        main_layout.addWidget(self.deepseek_group)

        # 按钮区
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        self.ok_btn = QPushButton("确定")
        self.ok_btn.clicked.connect(self.on_ok_clicked)
        button_layout.addWidget(self.ok_btn)

        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)
        self.center_on_screen()

    def center_on_screen(self):
        """窗口居中显示"""
        screen = QApplication.primaryScreen()
        if screen:
            screen_geo = screen.availableGeometry()
            geo = self.geometry()
            x = (screen_geo.width() - geo.width()) // 2
            y = (screen_geo.height() - geo.height()) // 2
            self.move(x, y)

    def load_config(self):
        """加载当前配置"""
        # 设置模型选择
        provider_display = self.current_provider.capitalize()
        index = self.provider_combo.findText(provider_display)
        if index >= 0:
            self.provider_combo.setCurrentIndex(index)

        # 加载对应配置
        self.load_provider_config(self.current_provider)

    def load_provider_config(self, provider):
        """加载指定提供商的配置"""
        config = self.config_manager.get_provider_config(provider)
        if not config:
            return

        self.api_url_input.setText(config.get("api_url", ""))
        # API Key 从持久化环境变量读取
        env_key = f"{provider.upper()}_API_KEY"
        api_key = self._get_persistent_env(env_key)
        self.api_key_input.setText(api_key)
        self.model_input.setText(config.get("model", ""))
        self.timeout_input.setValue(config.get("timeout", 60))
        self.max_retries_input.setValue(config.get("max_retries", 3))

        # DeepSeek 专属配置
        if provider == "deepseek":
            extra_params = config.get("extra_params", {})
            reasoning_effort = extra_params.get("reasoning_effort", "high")
            thinking_type = extra_params.get("thinking", {}).get("type", "enabled")

            index = self.reasoning_effort_combo.findText(reasoning_effort)
            if index >= 0:
                self.reasoning_effort_combo.setCurrentIndex(index)

            self.thinking_checkbox.setChecked(thinking_type == "enabled")

        # 根据提供商显示/隐藏 DeepSeek 专属设置
        self.deepseek_group.setVisible(provider == "deepseek")

    def on_provider_changed(self, provider_display):
        """切换提供商时更新界面"""
        provider = provider_display.lower()
        self.current_provider = provider
        self.load_provider_config(provider)

    def on_ok_clicked(self):
        """确定按钮点击"""
        # 校验必填项
        api_url = self.api_url_input.text().strip()
        api_key = self.api_key_input.text()
        model = self.model_input.text().strip()
        timeout = self.timeout_input.value()
        max_retries = self.max_retries_input.value()

        if not api_url:
            QMessageBox.warning(self, "警告", "请输入 API 地址！")
            return

        if not api_key:
            QMessageBox.warning(self, "警告", "请输入 API Key！")
            return

        if not model:
            QMessageBox.warning(self, "警告", "请输入模型名称！")
            return

        # 保存配置
        if self.save_config(api_url, api_key, model, timeout, max_retries):
            QMessageBox.information(self, "成功", "配置已保存！")
            self.accept()

    def save_config(self, api_url, api_key, model, timeout, max_retries):
        """保存配置"""
        try:
            provider = self.current_provider

            # 更新配置
            self.config_manager._config[provider]["api_url"] = api_url
            self.config_manager._config[provider]["model"] = model
            self.config_manager._config[provider]["timeout"] = timeout
            self.config_manager._config[provider]["max_retries"] = max_retries

            # DeepSeek 专属配置
            if provider == "deepseek":
                reasoning_effort = self.reasoning_effort_combo.currentText()
                thinking_enabled = self.thinking_checkbox.isChecked()

                extra_params = {
                    "reasoning_effort": reasoning_effort,
                    "thinking": {"type": "enabled" if thinking_enabled else "disabled"}
                }
                self.config_manager._config[provider]["extra_params"] = extra_params

            # API Key 保存到持久化环境变量
            env_key = f"{provider.upper()}_API_KEY"
            self._set_persistent_env(env_key, api_key)

            # 保存配置文件（api_key 保持为空）
            self.config_manager.save()

            return True

        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败：{str(e)}")
            return False


def main():
    app = QApplication(sys.argv)
    dialog = TalkSettingsDialog()
    dialog.exec_()


if __name__ == "__main__":
    main()
