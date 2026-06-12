# 桌面宠物项目 Code Wiki

> 本 Wiki 对项目的整体架构、模块职责、核心类与函数、依赖关系与运行方式进行结构化说明，是面向开发者的技术文档。

---

## 1. 项目概述

**桌面宠物（Desktop Pet）** 是一个基于 PySide6 的 Windows 桌面应用。它在桌面上以无边框、置顶、透明背景的窗口显示一只动画宠物，支持拖动、多种动作播放、右键菜单交互、系统托盘控制，以及通过独立设置窗口进行姓名更改、尺寸调整和开机自启动配置。

### 1.1 核心特性

- 256×256 无边框透明置顶窗口，默认出现在桌面右下角
- 帧动画播放（`idle` 待机循环 / `lickfur` 舔毛 / `dance` 跳舞 / `sleep` 睡觉三阶段）
- 左键拖动（可超出屏幕边界约 35 像素）
- 右键菜单（名字 / 情绪 / 状态 / 设置 / 隐匿 / Bye-bye）
- 系统托盘图标菜单（设置 / 显示隐藏 / 退出）
- 独立设置窗口（更改姓名 / 调整大小 / 开机自启动）
- 动作/状态集中管理在 `state.py`，设置逻辑集中在 `set.py`，保持 `main.py` 简洁

### 1.2 技术栈

| 类别 | 技术 |
|------|------|
| 语言 | Python 3.7+ |
| GUI 框架 | PySide6（Qt for Python）|
| 目标平台 | Windows（使用 `winreg` 操作开机自启动注册表项）|
| 动画格式 | PNG 序列帧 |

---

## 2. 目录结构

```
the pet/
├── start.py              # 程序入口：检查 basic.txt，决定先弹姓名设置还是直接启宠物
├── basic.txt             # 宠物信息存储（第 1 行姓名，第 2 行尺寸）
├── requirements.txt      # 依赖声明（PySide6）
├── CODE_WIKI.md          # 本文档
├── .temp_pos             # 运行时产生：宠物位置与尺寸临时记录
├── .resize_cmd           # 运行时产生：设置窗口与主窗口的跨进程指令通道
├── .name_update          # 运行时产生：设置窗口通知主窗口姓名已更新
├── project/
│   ├── main.py           # 桌面宠物主程序（窗口、动画、交互、托盘）
│   ├── name.py           # 姓名设置窗口（首次启动使用）
│   ├── set.py            # 设置窗口（更改姓名 / 调整大小 / 开机自启动）
│   └── state.py          # 状态/动作集中管理（StateManager）
└── assets/
    ├── idle/             # 待机动画帧 PNG
    ├── lickfur/          # 舔毛动画帧 PNG
    ├── dance/            # 跳舞动画帧 PNG
    ├── sleep1/           # 睡觉-入睡阶段 PNG
    ├── sleep2/           # 睡觉-沉睡循环阶段 PNG
    └── sleep3/           # 睡觉-苏醒阶段 PNG
```

---

## 3. 模块职责说明

### 3.1 start.py — 启动脚本

**职责**：作为项目的唯一入口脚本。

- 检查项目根目录的 [basic.txt](file:///c:/Users/lenovo/Desktop/the%20pet/basic.txt) 是否存在且非空
- 若没有姓名 → 先启动 [project/name.py](file:///c:/Users/lenovo/Desktop/the%20pet/project/name.py) 供用户设置，成功后再启动 [project/main.py](file:///c:/Users/lenovo/Desktop/the%20pet/project/main.py)
- 若已有姓名 → 直接启动 [project/main.py](file:///c:/Users/lenovo/Desktop/the%20pet/project/main.py)

**关键函数**：

| 函数 | 说明 |
|------|------|
| `check_pet_name()` | 读取 `basic.txt` 并判断是否存在有效姓名 |
| `run_name_script()` | 以 `subprocess` 启动 `name.py` |
| `run_main_script()` | 以 `subprocess` 启动 `main.py` |
| `main()` | 决策流程总入口 |

### 3.2 project/name.py — 姓名设置窗口

**职责**：首次启动（或姓名缺失）时弹出的图形化姓名设置窗口。

- UI：标题 + 输入框 + 取消/确认按钮
- 校验：姓名不能为空；点击"确认"后还需二次确认
- 保存成功后，将姓名写入 `basic.txt`，然后以 `subprocess` 启动 `main.py`

**核心类**：`NameInputWindow(QWidget)`

### 3.3 project/state.py — 状态与动作管理

**职责**：集中管理所有动作与帧动画加载，是 `main.py` 中动作切换逻辑的单一来源。

**核心类**：`StateManager`

#### 主要成员

| 成员 | 类型 | 说明 |
|------|------|------|
| `assets_path` | `Path` | `assets/` 目录的绝对路径 |
| `action_map` | `dict` | 目录名 → 中文显示名（`idle`/`lickfur`/`dance`/`sleep`） |
| `current_action` | `str` | 当前正在播放的动作名，默认 `'idle'` |
| `action_frames` | `dict` | 缓存：`{action_name: [QPixmap, ...]}` |
| `sleep_stages` | `list` | `['sleep1', 'sleep2', 'sleep3']`，供 `main.py` 复用 |

#### 主要方法

| 方法 | 说明 |
|------|------|
| `load_action_frames(action_name)` | 加载指定动作的 PNG 序列帧，按文件名**数字序**排序并缓存在 `action_frames` 中 |
| `get_current_state_name()` | 返回当前动作的中文显示名（用于右键菜单"状态: xxx"）|
| `get_all_actions()` | 返回所有动作目录名列表（用于状态弹窗动态生成按钮）|
| `get_action_display_name(action_name)` | 返回指定动作的中文显示名 |
| `set_action(action_name)` | 设置当前动作（需存在于 `action_map`）|
| `get_current_frames()` | 返回当前动作的帧数据 |
| `is_sleep_action(action_name)` | 判断是否为 `'sleep'` 动作 |
| `load_sleep_frames(stage)` | 加载 `sleep1/sleep2/sleep3` 指定阶段的帧 |

**帧排序要点**：必须使用 `int(x.stem)` 作为排序 key，否则会出现 `1, 10, 11, 2, ...` 的字典序错误。

### 3.4 project/main.py — 桌面宠物主程序

**职责**：负责窗口创建、动画绘制、用户交互（拖/菜单/托盘）、跨进程命令（设置窗口通信）。

**核心类**：`DesktopPet(QMainWindow)`

#### 重要初始化参数

| 属性 | 默认值 | 说明 |
|------|--------|------|
| `pet_size` | 256 | 当前宠物尺寸（正方形，单位像素）|
| `min_size` / `max_size` | 64 / 512 | 可调整大小的上下限 |
| `animation_frames` | `[]` | 当前正在播放的帧列表（`QPixmap`）|
| `current_frame` | 0 | 当前帧索引 |
| `state_manager` | `StateManager(assets)` | 负责动作与帧加载 |
| `sleep_stage` | `None` | 睡觉状态机：`'entering'` / `'looping'` / `'exiting'` / `None` |

#### 关键方法

| 方法 | 位置 | 说明 |
|------|------|------|
| `__init__` | [L15-L45](file:///c:/Users/lenovo/Desktop/the%20pet/project/main.py#L15-L45) | 初始化成员、加载 `basic.txt`、初始化窗口/托盘/定时器 |
| `load_basic_info()` | [L47-L62](file:///c:/Users/lenovo/Desktop/the%20pet/project/main.py#L47-L62) | 从 `basic.txt` 读取姓名与尺寸；尺寸会被钳制在 `[min_size, max_size]` |
| `save_basic_info()` | [L64-L71](file:///c:/Users/lenovo/Desktop/the%20pet/project/main.py#L64-L71) | 写回姓名与尺寸 |
| `init_window()` | [L73-L81](file:///c:/Users/lenovo/Desktop/the%20pet/project/main.py#L73-L81) | 设置无边框 / 置顶 / 透明背景，定位至屏幕右下角 |
| `load_current_action_frames()` | [L83-L86](file:///c:/Users/lenovo/Desktop/the%20pet/project/main.py#L83-L86) | 委托 `state_manager` 加载当前动作帧 |
| `switch_action(action_name)` | [L93-L114](file:///c:/Users/lenovo/Desktop/the%20pet/project/main.py#L93-L114) | 切换动作；睡觉动作走 `entering → looping → exiting` 三阶段 |
| `init_tray()` | [L116-L140](file:///c:/Users/lenovo/Desktop/the%20pet/project/main.py#L116-L140) | 创建系统托盘图标与菜单（设置 / 隐藏显示 / 退出）|
| `update_frame()` | [L148-L184](file:///c:/Users/lenovo/Desktop/the%20pet/project/main.py#L148-L184) | 定时（100ms）推进帧；`idle` 循环播放，其他动作播放一次后切回 `idle`；`sleep2` 用计数器降速播放 |
| `paintEvent()` | [L186-L198](file:///c:/Users/lenovo/Desktop/the%20pet/project/main.py#L186-L198) | 绘制帧；若处于 `resizing` 状态，额外绘制蓝色边框 |
| `mousePressEvent` / `mouseMoveEvent` / `mouseReleaseEvent` | [L200-L240](file:///c:/Users/lenovo/Desktop/the%20pet/project/main.py#L200-L240) | 左键：拖动窗口 / 调整大小；移动范围可超出屏幕边界约 35 像素；右键：弹出菜单 |
| `show_context_menu(pos)` | [L247-L275](file:///c:/Users/lenovo/Desktop/the%20pet/project/main.py#L247-L275) | 右键菜单：名字 / 情绪 / 状态 / 设置 / 隐匿 / Bye-bye |
| `show_settings()` | [L277-L280](file:///c:/Users/lenovo/Desktop/the%20pet/project/main.py#L277-L280) | 以 `subprocess.Popen` 启动 `set.py` |
| `save_position()` | [L282-L289](file:///c:/Users/lenovo/Desktop/the%20pet/project/main.py#L282-L289) | 将 `x/y/pet_size` 写入 `.temp_pos` 供设置窗口定位 |
| `check_resize_cmd()` | [L291-L321](file:///c:/Users/lenovo/Desktop/the%20pet/project/main.py#L291-L321) | 轮询 `.resize_cmd` 文件：`start` 进入调整大小；`confirm` 保存；`cancel` 还原；同时轮询 `.name_update` 以刷新姓名 |
| `show_status_dialog()` | [L332-L350](file:///c:/Users/lenovo/Desktop/the%20pet/project/main.py#L332-L350) | 状态弹窗：动态列出所有可用动作按钮，点击切换 |
| `toggle_visibility()` | [L361-L367](file:///c:/Users/lenovo/Desktop/the%20pet/project/main.py#L361-L367) | 托盘"隐藏/显示"切换，动态更新菜单项文字 |

#### 睡觉状态机

```
switch_action('sleep')
    └─> sleep_stage = 'entering'
        └─> 播放 sleep1 一次
            └─> sleep_stage = 'looping'
                └─> 循环播放 sleep2（计数器 2x 降速）
                    └─> 切换到其他动作时：
                        └─> sleep_stage = 'exiting'
                            └─> 播放 sleep3 一次
                                └─> sleep_stage = None，切换到目标动作
```

### 3.5 project/set.py — 设置窗口

**职责**：独立进程运行，为用户提供更改姓名、调整宠物大小、开启/关闭开机自启动三项功能。通过文件（`.resize_cmd` / `.name_update` / `.temp_pos`）与主进程通信。

**核心类**：

- `ResizeDialog(QDialog)` — 调整大小引导窗口（发出 `confirm` / `cancel`）
- `SettingsDialog(QDialog)` — 主设置窗口

#### 关键方法

| 方法 | 说明 |
|------|------|
| `load_pet_position()` | 读取 `.temp_pos`，在宠物左侧显示；左侧不够则放右侧；底部不够向上移动 50 像素，确保窗口完全可见 |
| `change_name()` | 输入新姓名 → 非空校验 → 二次确认 → 写回 `basic.txt` → 创建 `.name_update` 通知主进程 |
| `start_resize()` | 写 `"start"` 到 `.resize_cmd`，关闭设置窗口，弹出 `ResizeDialog`；用户点确定/取消后，再 `Popen` 重启设置窗口 |
| `load_autostart_status()` | 读取注册表 `HKCU\...\Run\DesktopPet`，设置复选框初始状态 |
| `save_settings()` | 保存开机自启动注册表项（勾选时写入 `python.exe start.py`，未勾选时删除）|

---

## 4. 进程间通信（IPC）机制

本项目不使用 Qt 的多进程/线程来维持设置窗口，而是采用**独立子进程 + 文件信号** 的方式。这保证了设置窗口无论何时关闭都不会影响主窗口的动画运行。

| 信号文件 | 生产者 | 消费者 | 用途 |
|---------|--------|--------|------|
| `.temp_pos` | `main.py`（拖动结束时）| `set.py` | 记录宠物位置与尺寸，用于设置窗口定位 |
| `.resize_cmd` | `set.py` | `main.py`（`check_resize_cmd` 轮询） | `start` / `confirm` / `cancel` 控制进入/保存/取消调整大小 |
| `.name_update` | `set.py`（改姓名后） | `main.py` | 通知主进程重新读取 `basic.txt` 中的姓名 |

轮询周期：`QTimer.singleShot(100, ...)` 持续递归触发，约每 100 ms 检查一次。

---

## 5. 动画与帧资源规范

### 5.1 动作目录

`assets/` 下每个子目录对应一个动作。目录名必须与 `state.py` 中 `action_map` 的 key 一致：

| 目录名 | 显示名 | 播放方式 |
|--------|--------|----------|
| `idle/` | 待机中... | 循环播放 |
| `lickfur/` | 舔毛 | 播放一次后自动回到 `idle` |
| `dance/` | 跳舞 | 播放一次后自动回到 `idle` |
| `sleep1/` | 入睡 | 进入睡觉的首段，播放一次 |
| `sleep2/` | 沉睡 | 睡觉的循环段 |
| `sleep3/` | 苏醒 | 退出睡觉的尾段，播放一次 |

### 5.2 文件命名规则

- 文件名必须形如 `1.png`, `2.png`, `3.png`, ...，纯数字 stem + `.png` 后缀
- **排序规则**：按 stem 的整数值升序排列（`int(x.stem)`）。不要使用字符串排序，否则会出现 `1, 10, 2, ...` 的错误顺序

### 5.3 帧率

- 普通动作：每 100 ms 一帧
- `sleep2`（沉睡循环）：每 2 个 tick 才前进一帧（相当于 ~200 ms/帧），以呈现更缓慢的呼吸感

---

## 6. 依赖与运行方式

### 6.1 依赖

[requirements.txt](file:///c:/Users/lenovo/Desktop/the%20pet/requirements.txt)：

```
PySide6>=6.0.0
```

安装命令：

```bash
pip install -r requirements.txt
```

### 6.2 运行方式

1. 安装依赖（首次或环境变更时）
   ```bash
   pip install -r requirements.txt
   ```

2. 启动程序
   ```bash
   python start.py
   ```

3. 启动流程
   - 若 `basic.txt` 为空或不存在 → 弹出姓名设置窗口（`name.py`），成功后自动启动宠物
   - 若已存在姓名 → 直接显示宠物窗口（`main.py`）

4. 交互方式
   - **左键拖动**：移动宠物位置
   - **右键宠物**：弹出交互菜单
   - **右键托盘图标**：弹出托盘菜单（设置 / 显示隐藏 / 退出）

### 6.3 数据文件

- `basic.txt`：第 1 行 = 姓名；第 2 行 = 尺寸（整数，范围 64–512）
- 可以手动编辑 `basic.txt`，但注意不要写入额外空行

---

## 7. 关键类与函数一览（Quick Reference）

### 7.1 入口层（启动脚本）

| 位置 | 名称 | 职责 |
|------|------|------|
| [start.py](file:///c:/Users/lenovo/Desktop/the%20pet/start.py) | `check_pet_name()` | 检查 `basic.txt` 是否存在有效姓名 |
| [start.py](file:///c:/Users/lenovo/Desktop/the%20pet/start.py) | `run_name_script()` / `run_main_script()` | 通过子进程启动 `name.py` / `main.py` |

### 7.2 UI 层

| 位置 | 名称 | 职责 |
|------|------|------|
| [project/name.py](file:///c:/Users/lenovo/Desktop/the%20pet/project/name.py) | `NameInputWindow` | 首次启动的姓名输入窗口 |
| [project/main.py](file:///c:/Users/lenovo/Desktop/the%20pet/project/main.py) | `DesktopPet` | 宠物主窗口、动画、菜单、托盘 |
| [project/set.py](file:///c:/Users/lenovo/Desktop/the%20pet/project/set.py) | `SettingsDialog` / `ResizeDialog` | 独立的设置与调整大小窗口 |

### 7.3 业务逻辑层

| 位置 | 名称 | 职责 |
|------|------|------|
| [project/state.py](file:///c:/Users/lenovo/Desktop/the%20pet/project/state.py) | `StateManager` | 动作/帧加载、动作切换、中文显示名映射 |

### 7.4 关键方法（按功能索引）

- 动作切换：`DesktopPet.switch_action()`、`StateManager.set_action()`、`StateManager.load_action_frames()`
- 动画循环：`DesktopPet.update_frame()`、`DesktopPet.paintEvent()`
- 拖动与范围限制：`DesktopPet.mouseMoveEvent()`
- 菜单与状态弹窗：`DesktopPet.show_context_menu()`、`DesktopPet.show_status_dialog()`
- 跨进程指令处理：`DesktopPet.check_resize_cmd()`、`DesktopPet.save_position()`
- 设置窗口定位：`SettingsDialog.load_pet_position()`
- 开机自启动：`SettingsDialog.load_autostart_status()`、`SettingsDialog.save_settings()`

---

## 8. 模块依赖关系图

```
start.py
   │
   ├─> project/name.py   (当 basic.txt 无姓名时)
   │         │
   │         └─> subprocess 启动 project/main.py
   │
   └─> project/main.py   (当 basic.txt 已有姓名时)
            │
            ├── 依赖 state.py (StateManager)
            │
            ├── 右键菜单 → show_settings → subprocess 启动 project/set.py
            │                                                  │
            │                                                  ├── 读 .temp_pos 定位
            │                                                  ├── 写 .resize_cmd / .name_update
            │                                                  │
            └── check_resize_cmd 轮询 .resize_cmd / .name_update <──┘

assets/ 目录仅被 state.py 读取（由 main.py 通过 StateManager 间接使用）
```

**依赖方向原则**：UI（`main.py` / `set.py` / `name.py`）→ 逻辑（`state.py`）→ 资源（`assets/`、`basic.txt`）。状态与动作逻辑全部下沉到 `StateManager`，设置窗口逻辑独立于 `set.py`，`main.py` 只负责窗口、绘制与交互调度。

---

## 9. 架构约束与约定（保持代码一致性）

1. **窗口样式**：主窗口始终使用 `Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool` 与 `WA_TranslucentBackground`
2. **动作规则**：只有 `idle` 循环播放；其他动作播放一次后自动切回 `idle`。睡觉动作必须按 `sleep1 → sleep2 → sleep3` 三阶段状态机处理
3. **设置窗口定位**：必须完整显示在屏幕内；底部超出时向上移动；左侧不够时放右侧
4. **拖动范围**：允许宠物窗口四周超出屏幕边界约 35 像素（`margin = 35`）
5. **进程通信**：设置窗口与主窗口之间只能使用信号文件（`.resize_cmd`、`.name_update`、`.temp_pos`）通信，不使用内存共享或网络
6. **帧排序**：所有 PNG 帧加载必须使用文件名 stem 的整数值排序，禁止字符串序
7. **状态集中**：动作名称、显示名映射、帧加载统一放在 `StateManager`；设置窗口独立放在 `set.py`，不要把设置 GUI 或状态逻辑写进 `main.py`

---

## 10. 开发扩展指南

### 10.1 新增动作

1. 在 `assets/` 下新建动作目录，例如 `yawn/`，放入按 `1.png, 2.png, ...` 命名的帧
2. 在 [state.py](file:///c:/Users/lenovo/Desktop/the%20pet/project/state.py) 的 `action_map` 中添加：`'yawn': '打哈欠'`
3. 该动作即可自动出现在右键菜单"状态"弹窗中，并按"播放一次后回到 `idle`"规则播放

### 10.2 新增睡觉以外的多阶段动作

参考 `DesktopPet.switch_action()` 与 `update_frame()` 中的 `sleep_stage` 状态机模式：

- 新增阶段枚举变量（如 `yawn_stage`）
- 在 `switch_action` 中触发起始阶段
- 在 `update_frame` 中按阶段推进并切换下一阶段 / 回退到 `idle`

### 10.3 新增设置项

1. 在 [set.py](file:///c:/Users/lenovo/Desktop/the%20pet/project/set.py) `SettingsDialog.init_ui()` 中添加 UI 控件
2. 读取/保存可以复用现有文件（`basic.txt` 新增行）或新增信号文件
3. 若需要主窗口实时响应，参考 `.name_update` 在 `main.py` 的 `check_resize_cmd()` 中增加对新文件的轮询处理

---

*Wiki 维护说明：本文档随代码同步更新。修改 `action_map`、新增动作目录、或调整进程通信机制时，请同时更新对应章节。*

---

## 11. 对话模块（AI对话功能）

### 11.1 功能概述

对话模块为桌面宠物新增AI对话功能，支持与用户进行多轮对话，具备短时记忆和永久记忆的分层存储能力。

**核心特性**：
- 右键菜单新增【对话】入口
- 双轮对话逻辑（大模型先判断是否需要历史记忆）
- 短时会话记录（`memory/short/`）
- 永久记忆摘要（`memory/long/`）
- 退出保护（任何退出方式都会保存记忆）

### 11.2 目录结构

```
the pet/
├── talk/                      # 对话模块代码
│   ├── __init__.py           # 模块初始化
│   ├── config.py             # 配置管理
│   ├── memory.py             # 记忆管理
│   ├── llm.py                # LLM请求封装
│   └── dialog.py             # 对话界面
├── talk.py                    # 对话模块入口（由main.py调用）
├── memory/                    # 记忆存储
│   ├── short/                # 短时记忆（本次会话）
│   │   └── session_*.json   # 会话记录
│   └── long/                 # 永久记忆
│       └── YYYYMMDD_HHMMSS/
│           ├── history.json   # 完整对话
│           └── summary.txt   # 对话摘要
└── identity/
    └── personality.txt       # AI身份设定
```

### 11.3 配置文件说明

**talk/config.json** - API配置：
```json
{
    "api_url": "https://api.openai.com/v1/chat/completions",
    "api_key": "your-api-key-here",
    "model": "gpt-3.5-turbo",
    "max_retries": 3,
    "timeout": 60
}
```

**identity/personality.txt** - AI身份设定：
```
你是一只可爱的小猫宠物，性格温顺友善，喜欢和主人互动。你会用软萌的语气说话，称呼用户为"主人"。你有良好的记忆力，能够记住和主人的对话内容。
```

### 11.4 模块职责

| 模块 | 文件 | 职责 |
|------|------|------|
| 配置管理 | talk/config.py | 加载/保存API配置 |
| 记忆管理 | talk/memory.py | 短时/永久记忆读写 |
| LLM请求 | talk/llm.py | 大模型API封装 |
| 对话界面 | talk/dialog.py | GUI和主逻辑 |
| 入口文件 | talk.py | 启动对话窗口 |

### 11.5 对话流程

#### 双轮对话逻辑：

1. **第一轮请求** - 询问是否需要历史：
   - 拼接内容：【短时上下文 + 永久记忆摘要 + 用户当前输入】
   - 大模型判断是否需要查看历史对话

2. **第二轮请求** - 获取回复：
   - 如果需要历史：拼接【短时上下文 + 历史对话 + 用户当前输入】
   - 如果不需要历史：拼接【短时上下文 + 用户当前输入】
   - 大模型返回最终回复
   - 问答存入短时记忆

### 11.6 记忆存储规则

**短时记忆（memory/short/）**：
- 文件格式：`session_{timestamp}.json`
- 存储本次会话全部对话
- 会话结束前持续读取复用

**永久记忆（memory/long/）**：
- 按时间分子文件夹：`YYYYMMDD_HHMMSS/`
- `history.json`：完整对话记录
- `summary.txt`：大模型生成的精简摘要
- 会话结束后自动生成，不重复冗余存储

### 11.7 运行方式

1. 右键点击桌面宠物
2. 选择【对话】选项
3. 在对话框中输入内容并发送
4. 点击【结束对话】或关闭窗口，系统自动保存记忆

### 11.8 代码入口

| 位置 | 函数 | 说明 |
|------|------|------|
| project/main.py | `show_talk()` | 右键菜单触发，启动talk.py子进程 |
| project/talk.py | `main()` | 对话模块入口 |
| talk/dialog.py | `TalkDialog` | 对话窗口类 |
| talk/dialog.py | `show_talk_dialog()` | 显示对话窗口函数 |

### 11.9 退出保护机制

无论何种退出方式，都会触发 `closeEvent` 保存记忆：
- 点击"结束对话"按钮
- 点击窗口X按钮
- 退出整个程序


