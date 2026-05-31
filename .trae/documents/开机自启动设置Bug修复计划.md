# 开机自启动设置Bug修复计划

## 一、问题分析

### Bug 1：打开设置时意外弹出确认提示
- **问题**：如果设置了开机自启动，再次打开设置页面会弹出"是否关闭自启动"的提示
- **原因**：`load_autostart_status()` 方法中调用 `setChecked()` 会触发 `stateChanged` 信号，进而调用 `toggle_autostart()` 弹出确认对话框
- **解决**：在设置复选框状态前阻塞信号，设置完成后恢复

## 二、修复方案

### 修改文件：project/main.py

#### 修改 load_autostart_status() 方法
在设置复选框状态前后阻塞和恢复信号，避免触发确认提示：

```python
def load_autostart_status(self):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                            r"Software\Microsoft\Windows\CurrentVersion\Run", 
                            0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, "DesktopPet")
            self.autostart_checkbox.blockSignals(True)
            self.autostart_checkbox.setChecked(True)
            self.autostart_checkbox.blockSignals(False)
        except WindowsError:
            self.autostart_checkbox.blockSignals(True)
            self.autostart_checkbox.setChecked(False)
            self.autostart_checkbox.blockSignals(False)
        winreg.CloseKey(key)
    except Exception:
        self.autostart_checkbox.blockSignals(True)
        self.autostart_checkbox.setChecked(False)
        self.autostart_checkbox.blockSignals(False)
```

#### 保持 toggle_autostart() 方法不变
当前逻辑已经正确：
- 勾选时提示"确认开启开机自启动吗？"
- 取消勾选时提示"确认关闭开机自启动吗？"
