# 桌宠对话功能模块 - 产品需求文档

## Overview
- **Summary**: 为桌面宠物应用新增对话功能模块，支持与AI大模型进行多轮对话，具备短时记忆和永久记忆分层存储能力
- **Purpose**: 实现宠物与用户的智能对话交互，支持上下文理解和长期记忆
- **Target Users**: 使用桌面宠物的终端用户

## Goals
1. 在右键菜单新增【对话】入口选项
2. 实现完整的对话界面（输入框、发送按钮、对话展示区、结束按钮）
3. 支持AI身份设定，自定义AI角色描述
4. 实现双轮对话逻辑（大模型先判断是否需要历史记忆）
5. 实现记忆分层存储（短时记忆+永久记忆）
6. 确保所有退出场景（关闭弹窗、结束对话、退出程序）都能正确保存记忆

## Non-Goals (Out of Scope)
- 不实现多宠物对话
- 不实现语音对话
- 不实现图片识别功能
- 不实现具体的大模型API实现（仅提供接口定义）

## Background & Context
- 现有项目结构：`project/main.py` 为主程序，`project/talk.py` 为对话模块（空文件待实现）
- 文件夹约定：
  - `memory/short/` - 短时记忆文件夹
  - `memory/long/` - 永久记忆文件夹（按时间分子文件夹）
  - `identity/` - 身份设定文件夹（包含 `personality.txt`）
  - `talk/` - 对话代码文件夹
- 依赖外部大模型API（需用户配置API地址和密钥）

## Functional Requirements

### FR-1: 交互入口
- 在 `main.py` 的右键菜单 `show_context_menu()` 中新增【对话】选项
- 点击后调用 `talk.py` 中的对话窗口启动函数

### FR-2: 对话界面
- 创建独立对话窗口 `TalkDialog` 类
- 窗口大小：500x600 像素
- 包含以下组件：
  - 对话展示区域（QTextBrowser，只读，滚动显示历史对话）
  - 输入框（QTextEdit，用于用户输入）
  - 发送按钮（QPushButton，点击发送消息）
  - 结束对话按钮（QPushButton，点击结束当前会话并保存记忆）
- 窗口关闭事件需拦截，触发保存记忆后再关闭

### FR-3: 对话逻辑（双轮请求）

#### 第一轮请求
- 拼接内容：【短时上下文 + 身份设定 + 永久记忆中的历史总结 + 用户当前输入】
- 请求大模型，询问"是否需要查看历史对话"
- 如果大模型回答需要查看历史：从long文件夹加载最新历史对话，拼接完整上下文

#### 第二轮请求（可选）
- 如果需要历史：拼接【短时上下文 + 身份设定 + 历史对话 + 用户当前输入】
- 如果不需要历史：拼接【短时上下文 + 身份设定 + 用户当前输入】
- 请求大模型获取最终回复
- 将问答存入短时记忆

### FR-4: 记忆存储规则

#### 短时记忆 (memory/short/)
- 存储格式：JSON文件
- 文件内容：本次会话的全部对话记录
- 文件名：`session_{timestamp}.json`
- 会话结束前持续读取复用

#### 永久记忆 (memory/long/)
- 存储结构：按时间分子文件夹 `YYYYMMDD_HHMMSS/`
- 每个子文件夹包含：
  - `history.json` - 本次会话的完整对话记录
  - `summary.txt` - 大模型生成的对话摘要（精简记忆）
- 会话结束后自动生成摘要，不重复冗余存储

### FR-5: 身份设定
- 从 `identity/personality.txt` 读取AI身份描述
- 每次请求时作为系统提示词拼接

### FR-6: 配置管理
- 配置文件：`talk/config.json`
- 包含：大模型API地址、API密钥、模型名称
- 支持运行时修改配置

## Non-Functional Requirements

### NFR-1: 代码解耦
- `talk.py` - 对话界面和主逻辑
- `talk/memory.py` - 记忆读写模块
- `talk/llm.py` - 大模型请求模块
- `talk/config.py` - 配置管理模块

### NFR-2: 退出保护
- 无论何种退出方式（点击X、点击结束、退出程序），都需保存记忆后再退出
- 使用 `closeEvent` 拦截窗口关闭事件

### NFR-3: 错误处理
- API请求失败时显示错误提示
- 网络异常时提供重试机制
- 空输入时禁用发送按钮

## Constraints

### Technical
- Python 3.8+
- PySide6 GUI框架
- requests 库用于API请求

### Business
- 需要用户自行配置大模型API

### Dependencies
- 大模型API（如OpenAI兼容接口）
- 网络连接

## Assumptions
- 用户具备基本的Python环境
- 用户有可用的API密钥
- 文件夹结构由程序自动创建

## Acceptance Criteria

### AC-1: 右键菜单
- **Given**: 用户右键点击桌面宠物
- **When**: 菜单弹出
- **Then**: 【对话】选项可见且可点击
- **Verification**: `human-judgment`

### AC-2: 对话界面
- **Given**: 用户点击【对话】选项
- **When**: 对话窗口打开
- **Then**: 输入框、发送按钮、对话展示区、结束按钮均可见
- **Verification**: `human-judgment`

### AC-3: 发送消息
- **Given**: 用户在输入框输入内容并点击发送
- **When**: 消息发送
- **Then**: 大模型回复显示在对话区，并存入短时记忆
- **Verification**: `programmatic`（检查JSON文件内容）

### AC-4: 历史记忆判断
- **Given**: 用户发送消息
- **When**: 大模型第一轮回复
- **Then**: 系统根据回复决定是否加载历史对话
- **Verification**: `programmatic`（检查日志/调试输出）

### AC-5: 记忆保存
- **Given**: 用户结束对话或关闭窗口
- **When**: 退出操作
- **Then**: short文件夹和long文件夹中都有对应文件生成
- **Verification**: `programmatic`（检查文件系统）

### AC-6: 退出保护
- **Given**: 用户直接关闭对话窗口或退出程序
- **When**: 退出操作
- **Then**: 记忆保存完成后再退出
- **Verification**: `human-judgment`

## Open Questions
- [x] 大模型API的具体实现方式（OpenAI兼容 vs 定制）
- [x] 是否需要支持流式输出
- [x] 历史对话加载的优先级策略
