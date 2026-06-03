# Committee — 多模型架构委员会引擎

项目无关的 AI 架构评审引擎。多个 LLM 角色交叉辩论，自动发现设计缺陷并输出结构化行动项。

---

## 目录

- [快速开始](#快速开始)
- [从零开始初始化委员会](#从零开始初始化委员会)
- [命令行用法](#命令行用法)
- [输出产物](#输出产物)
- [目录结构](#目录结构)
- [配置格式](#配置格式)
- [相关文档](#相关文档)

---

## 快速开始

### 1. 安装

在 `committee` 目录下执行：

```bash
pip install -e .
```

这会安装所有依赖并注册 `committee` 命令到系统 PATH，之后可在任意目录调用。

如果只想安装依赖而不注册命令：

```bash
pip install langchain langchain-openai langchain-anthropic langgraph python-dotenv pyyaml
```

### 2. 配置 API 凭证

在本目录下创建 `.env` 文件（参考 `.env.example`）：

```env
QWEN_API_KEY=your-api-key
QWEN_BASE_URL=your-base-url

DEEPSEEK_API_KEY=your-api-key
DEEPSEEK_BASE_URL=your-base-url

MIMO_API_KEY=your-api-key
MIMO_BASE_URL=your-base-url

COMMITTEE_MAX_ROUNDS=3
```

各提供商的 key 和 url 格式参见对应平台文档。`.env` 已被 `.gitignore` 忽略，不会提交。

### 3. 为项目创建配置

有两种方式创建项目配置：

#### 方式 A: 从零开始（推荐新项目）

使用 AI 工具（Claude Code）从需求书生成：

```bash
# 1. AI 读取需求书，生成 .committee.yaml
# 2. 用户确认/补充元数据
# 3. 运行生成脚本
python committee/tools/generate.py .committee.yaml
```

详见 [从零开始初始化委员会](#从零开始初始化委员会)。

#### 方式 B: 手动创建

在项目目录下创建 `.committee/` 目录：

```
<your-project>/
└── .committee/
    ├── config.yaml         # 必需: 角色模型 + 流水线拓扑
    ├── topics.yaml         # 必需: 预设议题库
    ├── prompts/            # 必需: 自定义提示词模板
    └── shared_context/     # 必需: 项目事实文档
```

### 4. 运行

在项目目录下直接运行，会自动检测当前目录的 `.committee/` 子目录：

```bash
cd /your/project

# 指定议题
committee --topic my_topic

# 交互式选择议题
committee

# 列出可用议题
committee --list

# 自定义议题 / 静默 / 指定轮数
committee --topic "评估方案 X 的可行性"
committee --topic my_topic --json-only
committee --topic my_topic --max-rounds 5
```

也可以通过 `--project-dir` 明确指定配置目录（用于测试不同配置或配置不在当前目录时）：

```bash
committee --project-dir /path/to/other/.committee --topic my_topic
```

其他命令：

```bash
committee --list-projects   # 列出所有本地项目
```

---

## 从零开始初始化委员会

### 概述

当开始一个新项目时，通常只有需求书或参考文件，没有完整的项目信息。此时可以通过 AI 工具（Claude Code）逐步提取信息，生成标准化的委员会配置。

### 工作流程

```
┌─────────────────────────────────────────────────────────────┐
│  阶段 1: AI 提取（Claude Code 对话）                         │
│  输入: 需求书/参考文件                                       │
│  输出: .committee.yaml（带 [待确认] [待补充] 标记）          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  阶段 2: 用户确认（Claude Code 对话）                        │
│  AI 逐项询问待确认项，用户补充待补充项                       │
│  输出: .committee.yaml（标记清除）                           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  阶段 3: 脚本生成（确定性转换）                              │
│  python tools/generate.py .committee.yaml                   │
│  输出: .committee/ 目录下的完整配置文件                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  阶段 4: 委员会运行（迭代完善）                              │
│  committee run --topic <topic_id>                           │
│  如发现信息缺失 → 回到阶段 2 补充 .committee.yaml           │
└─────────────────────────────────────────────────────────────┘
```

### 使用示例

#### 交互式初始化（Claude Code）

```
用户: 我有个新项目，需求书在 docs/requirements.md，帮我初始化委员会

Claude:
1. 读取需求书...
2. 提取关键信息...
3. 生成 .committee.yaml...
4. 请确认以下信息：
   - 硬件平台: Jetson Orin NX [待确认]
   - 领域专家: CV 算法专家 [待确认]
   - ...

用户: 确认，硬件是 Jetson Orin AGX

Claude:
1. 更新 .committee.yaml
2. 运行: python tools/generate.py .committee.yaml
3. 输出: 配置已生成到 .committee/
4. 委员会可以运行了
```

#### 命令行生成

```bash
# 从元数据生成配置
python committee/tools/generate.py .committee.yaml

# 指定输出目录
python committee/tools/generate.py .committee.yaml --output my-committee/

# 强制覆盖（忽略手动修改）
python committee/tools/generate.py .committee.yaml --force
```

### 标记系统

`.committee.yaml` 和生成的配置文件中使用统一的标记：

| 标记 | 含义 | 处理方式 |
|------|------|---------|
| `[待确认]` | AI 推断，需要用户确认 | 用户确认后删除标记 |
| `[待补充]` | 信息缺失，需要用户提供 | 用户补充后删除标记 |
| `[待讨论]` | 有多种可能，需要委员会讨论 | 委员会讨论后更新 |
| `???` | 完全未知 | 需要用户提供 |

### 迭代完善

配置文件会随着项目信息的清晰而逐步完善：

| 阶段 | 信息状态 | 配置状态 |
|------|----------|----------|
| 第 1 轮 | 大部分未知 | 骨架配置，大量 `[待补充]` |
| 第 2 轮 | 关键信息确认 | 部分 `[待确认]`，少量 `[待补充]` |
| 第 3 轮 | 委员会运行后 | 大部分确认，少量 `[待讨论]` |
| 第 N 轮 | 信息完整 | 标记全部清除 |

---

## 命令行用法

```bash
# 基本用法
committee --topic <topic_id>

# 交互式选择议题
committee

# 列出可用议题
committee --list

# 自定义议题
committee --topic "评估方案 X 的可行性"

# 静默模式（只输出 JSON）
committee --topic my_topic --json-only

# 指定最大轮数
committee --topic my_topic --max-rounds 5

# 指定配置目录
committee --project-dir /path/to/.committee --topic my_topic

# 列出所有本地项目
committee --list-projects
```

---

## 输出产物

| 文件 | 说明 |
|------|------|
| `<project>/adr/ADR-<topic>.md` | 架构决策记录（ADR） |
| `<project>/adr/ADR-<topic>.actions.json` | 结构化行动项，Claude Code 可直接读取并实现 |
| `<project>/decisions.md` | 决策日志，每次运行追加一行 |

### 行动项 JSON 格式

```json
{
  "action_items": [
    {
      "id": "AI-001",
      "priority": "blocker",
      "file": "path/to/file",
      "action": "具体做什么",
      "detail": "为什么这样做",
      "verification": "如何验证完成"
    }
  ]
}
```

优先级：`blocker` > `critical` > `warning`

---

## 目录结构

### 委员会引擎（本仓库）

```
committee/
├── README.md                      ← 本文档
├── COMMITTEE_TEMPLATE.md          ← 配置文件风格规范
├── pyproject.toml                 ← 包配置 + CLI 入口注册
├── .env.example                   ← API 凭证模板
├── .gitignore
├── engine/                        ← 核心引擎 (项目无关)
│   ├── __init__.py
│   ├── cli.py                     ← 配置加载 + 辩论执行
│   └── graph.py                   ← LangGraph 状态机 + 节点工厂
├── tools/                         ← 工具集
│   ├── README.md                  ← 工具使用说明
│   ├── generate.py                ← 配置生成脚本
│   └── METADATA_SPEC.md           ← 元数据格式规范
└── template/                      ← 配置模板
    ├── README.md                  ← 模板使用说明
    ├── .committee.yaml.example    ← 元数据示例
    ├── config.yaml                ← 配置模板
    ├── topics.yaml                ← 议题模板
    ├── shared_context/            ← 共享事实模板
    │   ├── architecture.md
    │   └── constraints.md
    ├── prompts/                   ← 提示词模板
    │   ├── architect_review.md
    │   ├── expert_review.md
    │   ├── critic_attack.md
    │   ├── auditor_audit.md
    │   └── converge.md
    └── adr/
        └── adr_template.md        ← ADR 模板
```

### 项目配置（生成后）

```
<your-project>/
├── .committee.yaml                ← 项目元数据（AI 填充 + 用户确认）
└── .committee/                    ← 生成的委员会配置
    ├── config.yaml
    ├── topics.yaml
    ├── shared_context/
    │   ├── architecture.md
    │   └── constraints.md
    ├── prompts/
    │   ├── architect_review.md
    │   ├── <expert>_review.md
    │   ├── critic_attack.md
    │   ├── auditor_audit.md
    │   └── converge.md
    ├── adr/                       ← 运行时生成
    │   └── ADR-*.md
    ├── decisions.md               ← 运行时生成
    └── .generated_hashes.yaml     ← 哈希记录（用于检测手动修改）
```

---

## 配置格式

### config.yaml

```yaml
project_name: "My Project"

# API 提供商 (引用 .env 中的环境变量名)
providers:
  qwen:
    api_key_env: QWEN_API_KEY
    base_url_env: QWEN_BASE_URL

# 角色定义
roles:
  architect:
    description: "首席架构师"
    provider: qwen
    model: qwen3.7-max-2026-05-17
    temperature: 0.3
  critic:
    description: "反驳专家"
    provider: deepseek
    model: deepseek-v4-pro
    temperature: 0.7

# 辩论流水线
pipeline:
  max_rounds_default: 3
  converge_role: architect
  debate_stages:
    - node: architect_review
      role: architect
      type: review
    - node: critic_attack
      role: critic
      type: attack

# 共享事实文件 (注入到所有角色的提示词中)
shared_context:
  files:
    - shared_context/architecture.md

# 自定义提示词 (可选, 覆盖引擎内置默认)
prompts:
  architect_review: prompts/architect_review.md
```

### 节点类型

| type | 用途 | 产出 | 提示词模板 |
|------|------|------|-----------|
| `review` | 设计评审 | 方案分析 + 缺口识别 | `architect_review.md` |
| `attack` | 红队攻击 | Blocker / Critical / Warning 漏洞 | `critic_attack.md` |
| `audit` | 量化审计 | 性能数字估算 | `auditor_audit.md` |

引擎自动处理路由：攻击方发现 Blocker/Critical 时循环回到评审方修正，直到清零或达到最大轮数。

### topics.yaml

```yaml
topics:
  my_topic:
    topic: |
      审阅方案 X 的设计。
      现有方案: 一句话概述。

      攻击角度:
      1. 具体技术质疑 1
      2. 具体技术质疑 2
    desc: "简短描述"
```

### .committee.yaml（项目元数据）

用于从零开始初始化委员会，由 AI 工具辅助生成。

```yaml
project:
  name: "项目名称"
  type: "系统类型"
  domain: "应用领域"

roles:
  architect:
    description: "首席架构师"
    provider: qwen
    model: qwen3.7-max-2026-05-17
    temperature: 0.3
  # ...

pipeline:
  - node: architect_review
    role: architect
    type: review
  # ...

hardware:
  platform: "硬件平台"
  resources:
    flash: "2MB"
    ram: "1MB"
  peripherals: []

architecture:
  os: "操作系统"
  modules: []
  tasks: []

constraints:
  realtime: []
  safety: []

experts: []
attack_scenarios: []
topics: []
```

完整格式参见 `tools/METADATA_SPEC.md`。

---

## 相关文档

| 文档 | 说明 |
|------|------|
| `COMMITTEE_TEMPLATE.md` | 配置文件风格规范 + 工作流说明 |
| `tools/README.md` | 工具使用说明 |
| `tools/METADATA_SPEC.md` | 元数据格式规范 |
| `template/README.md` | 模板使用说明 |
| `template/.committee.yaml.example` | 完整的元数据示例 |
