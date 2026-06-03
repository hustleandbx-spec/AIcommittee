# 委员会工具集

## 工具列表

| 工具 | 用途 | 用法 |
|------|------|------|
| `generate.py` | 从元数据生成委员会配置 | `python tools/generate.py <metadata>` |

---

## generate.py

从 `.committee.yaml` 元数据文件生成完整的委员会配置。

### 用法

```bash
python tools/generate.py <metadata_file> [--output <output_dir>] [--force]
```

### 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `metadata` | 元数据文件路径 | 必填 |
| `--output`, `-o` | 输出目录 | `.committee/` |
| `--force`, `-f` | 强制覆盖所有文件 | 否 |

### 示例

```bash
# 从项目元数据生成，输出到 .committee/
python tools/generate.py ../uav-fc/.committee.yaml

# 指定输出目录
python tools/generate.py .committee.yaml --output committee/my-project

# 强制覆盖（忽略手动修改）
python tools/generate.py .committee.yaml --force
```

### 生成内容

| 文件 | 说明 |
|------|------|
| `config.yaml` | 委员会主配置 |
| `topics.yaml` | 议题库 |
| `shared_context/architecture.md` | 系统架构 |
| `shared_context/constraints.md` | 运行时约束 |
| `prompts/architect_review.md` | 架构师提示词 |
| `prompts/<expert>_review.md` | 领域专家提示词 |
| `prompts/critic_attack.md` | 反驳专家提示词 |
| `prompts/auditor_audit.md` | 性能审计师提示词 |
| `prompts/converge.md` | 汇总提示词 |

### 标记系统

生成的文件中可能包含以下标记：

| 标记 | 含义 | 处理方式 |
|------|------|---------|
| `[待确认]` | AI 推断，需要用户确认 | 确认后删除标记 |
| `[待补充]` | 信息缺失，需要用户提供 | 补充后删除标记 |
| `[待讨论]` | 有多种可能，需要委员会讨论 | 讨论后更新 |
| `???` | 完全未知 | 需要用户提供 |

### 手动修改检测

工具会记录生成文件的哈希值（`.generated_hashes.yaml`），用于检测手动修改：

- **首次生成**：覆盖所有文件
- **再次生成**：
  - 未手动修改的文件 → 覆盖更新
  - 已手动修改的文件 → 跳过，打印警告

### 依赖

- Python 3.8+
- PyYAML (`pip install pyyaml`)

---

## 快速开始

### 1. 准备元数据文件

创建 `.committee.yaml`，参考 `template/.committee.yaml.example`。

### 2. 运行生成脚本

```bash
# 在项目目录下运行
python committee/tools/generate.py .committee.yaml

# 或指定路径
python committee/tools/generate.py /path/to/.committee.yaml --output /path/to/.committee
```

### 3. 检查输出

```
============================================================
  Committee config generation completed
============================================================

  Output directory: .committee
  Generated files: 7

  [OK] Generated:
    - config.yaml
    - topics.yaml
    - shared_context/architecture.md
    - shared_context/constraints.md
    - prompts/architect_review.md
    - prompts/domain_expert_review.md
    - prompts/critic_attack.md
    - prompts/auditor_audit.md
    - prompts/converge.md

  [WARN] Pending tags:
    - [待确认]: 3
    - [待补充]: 5

============================================================
```

### 4. 运行委员会

```bash
committee --topic my_topic
```

---

## 完整示例

### 交互式初始化（Claude Code）

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

### 命令行初始化

```bash
# 1. 复制示例元数据
cp committee/template/.committee.yaml.example .committee.yaml

# 2. 编辑元数据（填入项目信息）
vim .committee.yaml

# 3. 生成配置
python committee/tools/generate.py .committee.yaml

# 4. 运行委员会
committee --topic my_topic
```

---

## 工作流

### 阶段 1: AI 提取

```
需求书/参考文件 → AI 分析 → .committee.yaml（带标记）
```

由 Claude Code 完成：
1. 读取需求书
2. 提取关键信息
3. 生成 `.committee.yaml`
4. 逐项询问待确认项

### 阶段 2: 用户确认

```
用户编辑 .committee.yaml → 清除标记 → 确认
```

用户完成：
1. 确认 AI 推断的信息
2. 补充缺失的信息
3. 删除标记

### 阶段 3: 脚本生成

```
.committee.yaml → generate.py → 委员会配置
```

脚本完成：
1. 读取元数据
2. 套用模板生成配置
3. 输出到 `.committee/` 或指定目录

### 阶段 4: 委员会运行

```
委员会配置 → committee run → 辩论结果
```

如发现信息缺失：
1. 补充 `.committee.yaml`
2. 重新运行 `generate.py`
3. 继续委员会运行
