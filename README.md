# Committee — 多模型架构委员会引擎

项目无关的 AI 架构评审引擎。多个 LLM 角色交叉辩论，自动发现设计缺陷并输出结构化行动项。

## 快速开始

### 1. 安装依赖

```bash
pip install langchain langchain-openai langgraph python-dotenv pyyaml
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

在任意位置创建项目配置目录：

```
<your-project>/committee/
├── config.yaml         # 必需: 角色模型 + 流水线拓扑
├── topics.yaml         # 可选: 预设议题库
├── prompts/            # 可选: 自定义提示词模板
└── shared_context/     # 可选: 项目事实文档
```

### 4. 运行

```bash
# 指定议题
python committee.py --project-dir /path/to/project/committee --topic my_topic

# 交互式选择议题
python committee.py --project-dir /path/to/project/committee

# 列出可用议题
python committee.py --project-dir /path/to/project/committee --list

# 自定义议题 / 静默 / 指定轮数
python committee.py --project-dir /path/to/project/committee --topic "评估方案 X 的可行性"
python committee.py --project-dir /path/to/project/committee --topic my_topic --json-only
python committee.py --project-dir /path/to/project/committee --topic my_topic --max-rounds 5
```

## 输出产物

| 文件 | 说明 |
|------|------|
| `<project>/adr/ADR-<topic>.actions.json` | 结构化行动项，Claude Code 可直接读取并实现 |
| `<project>/decisions.md` | 决策日志，每次运行追加一行 |

## 项目配置格式

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

| type | 用途 | 产出 |
|------|------|------|
| `review` | 设计评审 | 方案分析 + 缺口识别 |
| `attack` | 红队攻击 | Blocker / Critical / Warning 漏洞 |
| `audit` | 量化审计 | 性能数字估算 |

引擎自动处理路由：攻击方发现 Blocker/Critical 时循环回到评审方修正，直到清零或达到最大轮数。

### topics.yaml

```yaml
topics:
  my_topic:
    topic: |
      审阅方案 X 的设计。
      攻击角度: 1. ... 2. ...
    desc: "简短描述"
```

## 文件结构

```
committee/
├── README.md
├── .env.example           ← API 凭证模板
├── .gitignore
├── committee.py           ← CLI 入口
└── engine/                ← 核心引擎 (项目无关)
    ├── __init__.py
    ├── cli.py             ← 配置加载 + 辩论执行
    └── graph.py           ← LangGraph 状态机 + 节点工厂
```
