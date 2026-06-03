# .committee.yaml 元数据规范

> 本文档定义 `.committee.yaml` 元数据文件的格式规范。
> 该文件由 AI 工具（Claude Code）辅助生成，用户确认后，由 `generate.py` 读取并生成委员会配置。

---

## 1. 概述

`.committee.yaml` 是项目元数据文件，包含：

- 项目基本信息
- 硬件平台配置
- 软件架构描述
- 约束条件
- 领域专家定义
- 攻击场景
- 议题列表

**文件位置**：项目根目录 `.committee.yaml`

**生成流程**：
```
需求书/参考文件 → AI 提取 → .committee.yaml → 用户确认 → generate.py → 委员会配置
```

---

## 2. 完整格式

```yaml
# .committee.yaml — 项目元数据
# 由 AI 工具辅助生成，用户确认后使用
# 生成时间: YYYY-MM-DD HH:MM

# ===========================================================================
# 项目基本信息
# ===========================================================================
project:
  name: "项目显示名"                    # 必填
  type: "系统类型"                      # 必填，如 "实时嵌入式控制系统"
  domain: "应用领域"                    # 必填，如 "无人机飞控"
  description: "项目描述"               # 可选

# ===========================================================================
# API 提供商（可选，使用默认值）
# ===========================================================================
providers:
  qwen:
    api_key_env: QWEN_API_KEY
    base_url_env: QWEN_BASE_URL
  deepseek:
    api_key_env: DEEPSEEK_API_KEY
    base_url_env: DEEPSEEK_BASE_URL
  mimo:
    api_key_env: MIMO_API_KEY
    base_url_env: MIMO_BASE_URL

# ===========================================================================
# 角色定义
# ===========================================================================
roles:
  architect:
    description: "首席系统架构师"
    provider: qwen
    model: qwen3.7-max-2026-05-17
    temperature: 0.3

  # 领域专家（至少 1 个，最多 3 个）
  <expert_key>:
    description: "专家描述"
    provider: deepseek
    model: deepseek-v4-pro
    temperature: 0.3

  # 反驳专家（必须）
  critic:
    description: "极端反驳专家"
    provider: mimo
    model: mimo-v2.5
    temperature: 0.7

  # 性能审计师（必须）
  auditor:
    description: "底层性能审计师"
    provider: mimo
    model: mimo-v2.5
    temperature: 0.1

# ===========================================================================
# 流水线拓扑
# ===========================================================================
pipeline:
  # 第 1 步：架构师评审
  - node: architect_review
    role: architect
    type: review

  # 第 2-N 步：领域专家评审（对应 roles 中的专家）
  - node: <expert_key>_review
    role: <expert_key>
    type: review

  # 倒数第 2 步：反驳专家攻击
  - node: critic_attack
    role: critic
    type: attack

  # 最后一步：性能审计
  - node: auditor_audit
    role: auditor
    type: audit

# ===========================================================================
# 硬件平台（用于生成 shared_context/）
# ===========================================================================
hardware:
  platform: "平台名称"                 # 必填
  resources:
    flash: "2MB"                       # 必填
    ram: "1MB"                         # 必填
    gpu_memory: "16GB"                 # 如适用
  peripherals:                         # 必填
    - name: "IMU"
      model: "ICM-42688-P"
      interface: "SPI"
      frequency: "32kHz"
    - name: "GPS"
      model: "u-blox F9P"
      interface: "UART"
      frequency: "10Hz"

# ===========================================================================
# 软件架构（用于生成 shared_context/）
# ===========================================================================
architecture:
  os: "操作系统"                       # 必填
  modules:                             # 必填
    - name: "模块名"
      description: "模块描述"
      location: "源文件路径"
  tasks:                               # 必填
    - name: "任务名"
      period: "周期"
      priority: "优先级"
      wcet: "WCET"
      stack: "栈大小"
  buses:                               # 可选
    - name: "总线名"
      devices: "设备"
      speed: "速率"
      arbitration: "仲裁方式"

# ===========================================================================
# 约束条件（用于生成 shared_context/）
# ===========================================================================
constraints:
  realtime:                            # 必填
    - description: "约束描述"
      type: "hard"                     # hard / soft
  safety:                              # 必填
    - description: "约束描述"
  mbd:                                 # 如适用
    enabled: true
    solver: "求解器类型"
    target: "目标芯片"
    code_generation:
      tool: "代码生成工具"
      language: "目标语言"
      interface: "接口类型"
    verification:
      - level: "验证层级"
        coverage: "覆盖要求"
    constraints:
      - "约束描述"

# ===========================================================================
# 领域专家配置（用于生成 prompts/）
# ===========================================================================
experts:
  - key: "expert_key"                  # 必须与 roles 中的 key 一致
    domain: "领域名称"
    description: "专家描述"
    focus: "审查重点"
    ignore: "不关心的方面"
    knowledge:                         # 领域知识基线
      - title: "知识板块标题"
        points:
          - "知识点 1"
          - "知识点 2"
    dimensions:                        # 审查维度
      - "维度 1"
      - "维度 2"

# ===========================================================================
# 攻击场景（用于生成 prompts/critic_attack.md）
# ===========================================================================
attack_scenarios:
  - name: "场景名称"
    description: "场景描述"
    extensions:                        # 延伸攻击点
      - "延伸攻击 1"
      - "延伸攻击 2"

# ===========================================================================
# 议题（用于生成 topics.yaml）
# ===========================================================================
topics:
  - id: "topic_id"                     # 必填，snake_case
    module: "源文件"                   # 必填
    summary: "现有方案概述"            # 必填
    attack_angles:                     # 必填，至少 2 个
      - "攻击角度 1"
      - "攻击角度 2"
    desc: "简短描述"                   # 必填
```

---

## 3. 字段说明

### 3.1 project（必填）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | ✓ | 项目显示名，用于 config.yaml |
| `type` | string | ✓ | 系统类型，用于 prompts 中的系统描述 |
| `domain` | string | ✓ | 应用领域，用于 prompts 中的领域描述 |
| `description` | string | | 项目详细描述 |

### 3.2 roles（必填）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `architect` | object | ✓ | 架构师角色 |
| `<expert>` | object | ✓+ | 领域专家角色，至少 1 个 |
| `critic` | object | ✓ | 反驳专家角色 |
| `auditor` | object | ✓ | 性能审计师角色 |

每个角色包含：
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `description` | string | ✓ | 角色描述 |
| `provider` | string | ✓ | 提供商（qwen/deepseek/mimo） |
| `model` | string | ✓ | 模型名称 |
| `temperature` | float | ✓ | 温度参数 |

### 3.3 pipeline（必填）

流水线阶段列表，每阶段包含：
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `node` | string | ✓ | 节点名称，对应 prompts 文件名 |
| `role` | string | ✓ | 角色名称，对应 roles 中的 key |
| `type` | string | ✓ | 节点类型（review/attack/audit） |

### 3.4 hardware（必填）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `platform` | string | ✓ | 硬件平台名称 |
| `resources` | object | ✓ | 资源配置（flash/ram/gpu_memory） |
| `peripherals` | list | ✓ | 外设列表 |

### 3.5 architecture（必填）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `os` | string | ✓ | 操作系统 |
| `modules` | list | ✓ | 模块列表 |
| `tasks` | list | ✓ | 任务列表 |
| `buses` | list | | 总线列表 |

### 3.6 constraints（必填）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `realtime` | list | ✓ | 实时性约束 |
| `safety` | list | ✓ | 安全性约束 |
| `mbd` | object | | MBD 约束（如适用） |

### 3.7 experts（必填）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `key` | string | ✓ | 专家标识符，与 roles 中的 key 一致 |
| `domain` | string | ✓ | 领域名称 |
| `description` | string | ✓ | 专家描述 |
| `focus` | string | ✓ | 审查重点 |
| `ignore` | string | ✓ | 不关心的方面 |
| `knowledge` | list | ✓ | 领域知识基线 |
| `dimensions` | list | ✓ | 审查维度 |

### 3.8 attack_scenarios（必填）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | ✓ | 场景名称 |
| `description` | string | ✓ | 场景描述 |
| `extensions` | list | ✓ | 延伸攻击点 |

### 3.9 topics（必填）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | ✓ | 议题标识符（snake_case） |
| `module` | string | ✓ | 相关源文件 |
| `summary` | string | ✓ | 现有方案概述 |
| `attack_angles` | list | ✓ | 攻击角度列表 |
| `desc` | string | ✓ | 简短描述 |

---

## 4. 标记系统

元数据中可使用以下标记表示信息状态：

| 标记 | 含义 | 处理方式 |
|------|------|---------|
| `[待确认]` | AI 推断，需要用户确认 | 用户确认后删除标记 |
| `[待补充]` | 信息缺失，需要用户提供 | 用户补充后删除标记 |
| `[待讨论]` | 有多种可能，需要委员会讨论 | 委员会讨论后更新 |
| `???` | 完全未知 | 需要用户提供 |

**示例**：
```yaml
hardware:
  platform: "Jetson Orin NX"           # 已确认
  resources:
    gpu_memory: "[待确认]"              # AI 推断，需用户确认
    npu_memory: "[待补充]"              # 信息缺失
```

---

## 5. AI 工作流

### 5.1 初始提取

AI 读取需求书/参考文件，提取关键信息：

```
输入: requirements.md
输出: .committee.yaml（带标记）
```

提取策略：
1. 明确的信息 → 直接填入
2. 可推断的信息 → 填入 + 标记 `[待确认]`
3. 缺失的信息 → 标记 `[待补充]`

### 5.2 交互确认

AI 逐项询问待确认项：

```
AI: 硬件平台推断为 "Jetson Orin NX"，是否正确？
用户: 正确
AI: 已更新，删除 [待确认] 标记
```

### 5.3 生成配置

用户确认后，运行生成脚本：

```bash
python committee/tools/generate.py .committee.yaml
```

---

## 6. 示例

### 6.1 最小示例

```yaml
project:
  name: "My Project"
  type: "嵌入式系统"
  domain: "物联网"

roles:
  architect:
    description: "首席系统架构师"
    provider: qwen
    model: qwen3.7-max-2026-05-17
    temperature: 0.3
  critic:
    description: "极端反驳专家"
    provider: mimo
    model: mimo-v2.5
    temperature: 0.7
  auditor:
    description: "底层性能审计师"
    provider: mimo
    model: mimo-v2.5
    temperature: 0.1

pipeline:
  - node: architect_review
    role: architect
    type: review
  - node: critic_attack
    role: critic
    type: attack
  - node: auditor_audit
    role: auditor
    type: audit

hardware:
  platform: "[待补充]"
  resources:
    flash: "[待补充]"
    ram: "[待补充]"
  peripherals: []

architecture:
  os: "[待补充]"
  modules: []
  tasks: []

constraints:
  realtime: []
  safety: []

experts: []
attack_scenarios: []
topics: []
```

### 6.2 完整示例

参见 `template/.committee.yaml.example`

---

## 7. 注意事项

1. **必须字段**：标记为 ✓ 的字段必须填写，否则生成脚本报错
2. **标记清理**：生成前应尽量清理标记，保留标记的文件会生成带占位符的配置
3. **编码格式**：文件必须使用 UTF-8 编码
4. **YAML 语法**：确保 YAML 语法正确，可使用在线工具验证
5. **相对路径**：源文件路径使用相对于项目根目录的相对路径
