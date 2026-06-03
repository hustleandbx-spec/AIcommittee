# 委员会配置模板

本目录包含架构委员会配置文件的完整模板，用于快速创建新项目的委员会配置。

---

## 目录结构

```
template/
├── README.md                      # 本文件
├── .committee.yaml                # 测试用元数据
├── .committee.yaml.example        # 完整的元数据示例（光电吊舱项目）
├── config.yaml                    # 主配置模板
├── topics.yaml                    # 议题库模板
├── shared_context/
│   ├── architecture.md            # 架构概览模板
│   └── constraints.md             # 运行时约束模板
├── prompts/
│   ├── architect_review.md        # 架构师评审提示词模板
│   ├── expert_review.md           # 领域专家评审提示词模板
│   ├── critic_attack.md           # 反驳专家攻击提示词模板
│   ├── auditor_audit.md           # 性能审计师提示词模板
│   └── converge.md                # 汇总提示词模板
└── adr/
    └── adr_template.md            # ADR 文档模板
```

---

## 使用方法

### 方式 1: 从零开始（推荐新项目）

使用 AI 工具（Claude Code）从需求书生成：

```
用户: 我有个新项目，需求书在 docs/requirements.md，帮我初始化委员会

Claude:
1. 读取需求书
2. 提取关键信息
3. 生成 .committee.yaml（带标记）
4. 逐项询问待确认项
5. 运行 generate.py 生成配置
```

或命令行：

```bash
# 1. 准备元数据文件（参考 .committee.yaml.example）
# 2. 运行生成脚本
python committee/tools/generate.py .committee.yaml
```

### 方式 2: 手动创建

```bash
# 1. 复制模板目录
cp -r committee/template/<project>/.committee

# 2. 替换占位符（见下方表格）

# 3. 定制领域知识和议题
```

---

## 元数据文件 (.committee.yaml)

元数据文件是"信息收集"和"配置生成"的**边界**。

### 完整示例

参见 `.committee.yaml.example`，这是一个光电吊舱目标检测系统的完整元数据示例。

### 最小示例

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

### 格式规范

完整的元数据格式规范参见 `../tools/METADATA_SPEC.md`。

---

## 标记系统

元数据和生成的配置文件中使用统一的标记：

| 标记 | 含义 | 处理方式 |
|------|------|---------|
| `[待确认]` | AI 推断，需要用户确认 | 用户确认后删除标记 |
| `[待补充]` | 信息缺失，需要用户提供 | 用户补充后删除标记 |
| `[待讨论]` | 有多种可能，需要委员会讨论 | 委员会讨论后更新 |
| `???` | 完全未知 | 需要用户提供 |

---

## 占位符说明

手动创建时，需要替换以下占位符：

| 占位符 | 说明 | 示例 |
|--------|------|------|
| `<项目名>` | 项目名称 | `UAV-FC` |
| `<项目显示名>` | 项目显示名 | `UAV-FC (MBD)` |
| `<系统名称>` | 系统名称 | `无人机飞控系统` |
| `<系统类型>` | 系统类型 | `实时嵌入式控制系统` |
| `<领域>` | 领域名称 | `Matlab/Simulink 建模仿真` |
| `<场景>` | 应用场景 | `飞控场景` |
| `<源文件>` | 源文件路径 | `scheduler.cpp` |
| `<前缀>` | 输出编号前缀 | `M` / `C` / `A` / `P` |

---

## 设计原则

### 1. 事实与方法论分离

- `shared_context/` 存放**事实**：硬件规格、软件架构、约束条件
- `prompts/` 存放**方法论**：如何审查这个领域的设计

### 2. 唯一事实层

所有 `shared_context` 文件必须声明"唯一事实层"，Agent 不得自行编造。

### 3. 标注协议

所有约束必须使用标注协议：
- `[C]` Constraint — 架构硬性约束
- `[F]` Formula — 公式推导值
- `[R]` Relative — 相对比较值
- `[M]` Measured — 实测值

### 4. 结构化输出

每个审查问题必须包含：
- 编号前缀 + 轮次 + 序号
- 评级（Blocker/Critical/Warning）
- 量化数据

### 5. 边界分离

`.committee.yaml` 是"信息收集"和"配置生成"的边界：
- AI 负责语义理解和信息提取
- `generate.py` 负责机械转换
- 用户在边界处确认和补充

---

## 迭代完善

配置文件会随着项目信息的清晰而逐步完善：

| 阶段 | 信息状态 | 配置状态 |
|------|----------|----------|
| 第 1 轮 | 大部分未知 | 骨架配置，大量 `[待补充]` |
| 第 2 轮 | 关键信息确认 | 部分 `[待确认]`，少量 `[待补充]` |
| 第 3 轮 | 委员会运行后 | 大部分确认，少量 `[待讨论]` |
| 第 N 轮 | 信息完整 | 标记全部清除 |

---

## 参考项目

- `odt/` — 光电吊舱目标检测系统（标准参考）
- `uav-fc/` — 无人机飞控系统

---

## 相关文档

| 文档 | 说明 |
|------|------|
| `../COMMITTEE_TEMPLATE.md` | 完整的风格规范 + 工作流说明 |
| `../tools/README.md` | 工具使用说明 |
| `../tools/METADATA_SPEC.md` | 元数据格式规范 |
