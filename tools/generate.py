#!/usr/bin/env python3
"""
委员会配置生成工具

读取项目元数据 (.committee.yaml)，生成完整的委员会配置文件。

用法:
    python tools/generate.py <metadata_file> [--output <output_dir>]

示例:
    python tools/generate.py ../uav-fc/.committee.yaml
    python tools/generate.py .committee.yaml --output committee/my-project
"""

import argparse
import hashlib
import sys
from datetime import datetime
from pathlib import Path
from string import Template

import yaml


# ============================================================================
# 标记系统
# ============================================================================

TAG_PENDING_CONFIRM = "[待确认]"
TAG_PENDING补充 = "[待补充]"
TAG_PENDING_DISCUSS = "[待讨论]"
TAG_UNKNOWN = "???"


def has_pending_tag(text: str) -> bool:
    """检查文本是否包含待处理标记"""
    if not isinstance(text, str):
        return False
    return any(tag in text for tag in [TAG_PENDING_CONFIRM, TAG_PENDING补充, TAG_UNKNOWN])


def count_pending_tags(text: str) -> dict[str, int]:
    """统计文本中的待处理标记数量"""
    if not isinstance(text, str):
        return {}
    return {
        "待确认": text.count(TAG_PENDING_CONFIRM),
        "待补充": text.count(TAG_PENDING补充),
        "待讨论": text.count(TAG_PENDING_DISCUSS),
        "???": text.count(TAG_UNKNOWN),
    }


# ============================================================================
# 文件哈希管理（用于检测手动修改）
# ============================================================================

def file_hash(content: str) -> str:
    """计算文件内容的哈希值"""
    return hashlib.md5(content.encode("utf-8")).hexdigest()


def load_generated_hashes(output_dir: Path) -> dict[str, str]:
    """加载已生成文件的哈希记录"""
    hash_file = output_dir / ".generated_hashes.yaml"
    if hash_file.exists():
        with open(hash_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def save_generated_hashes(output_dir: Path, hashes: dict[str, str]):
    """保存已生成文件的哈希记录"""
    hash_file = output_dir / ".generated_hashes.yaml"
    with open(hash_file, "w", encoding="utf-8") as f:
        yaml.dump(hashes, f, default_flow_style=False)


def should_overwrite(file_path: Path, new_content: str, old_hashes: dict[str, str]) -> bool:
    """判断是否应该覆盖文件"""
    if not file_path.exists():
        return True

    rel_path = str(file_path.relative_to(file_path.parent.parent))
    old_hash = old_hashes.get(rel_path)

    if old_hash is None:
        # 首次生成，覆盖
        return True

    current_hash = file_hash(file_path.read_text(encoding="utf-8"))
    if current_hash == old_hash:
        # 未被手动修改，覆盖
        return True

    # 已被手动修改，跳过
    return False


# ============================================================================
# 模板渲染
# ============================================================================

def render(template_str: str, **kwargs) -> str:
    """渲染模板字符串"""
    # 支持 ${var} 和 ${var|default} 语法
    class SafeTemplate(Template):
        delimiter = "$"
        pattern = r"""
            \$(?:
                (?P<escaped>\$) |   # Escape sequence of two delimiters
                (?P<named>\w+) |    # delimiter and a Python identifier
                {(?P<braced>\w+)}  # delimiter and a braced identifier
            )
        """

    return SafeTemplate(template_str).safe_substitute(**kwargs)


# ============================================================================
# 生成器
# ============================================================================

class ConfigGenerator:
    """委员会配置生成器"""

    def __init__(self, metadata: dict, output_dir: Path):
        self.metadata = metadata
        self.output_dir = output_dir
        self.old_hashes = load_generated_hashes(output_dir)
        self.new_hashes = {}
        self.skipped_files = []
        self.generated_files = []

    def generate_all(self):
        """生成所有配置文件"""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._generate_config()
        self._generate_topics()
        self._generate_shared_context()
        self._generate_prompts()

        # 保存哈希记录
        save_generated_hashes(self.output_dir, self.new_hashes)

        # 打印摘要
        self._print_summary()

    def _write_file(self, rel_path: str, content: str):
        """写入文件，检查是否应覆盖"""
        file_path = self.output_dir / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)

        if should_overwrite(file_path, content, self.old_hashes):
            file_path.write_text(content, encoding="utf-8")
            self.new_hashes[rel_path] = file_hash(content)
            self.generated_files.append(rel_path)
        else:
            self.skipped_files.append(rel_path)

    def _generate_config(self):
        """生成 config.yaml"""
        project = self.metadata.get("project", {})
        providers = self.metadata.get("providers", {})
        roles = self._build_roles()
        pipeline = self._build_pipeline()

        content = f"""# {project.get('name', 'Project')} 项目配置 — 架构委员会
# 由 generate.py 自动生成，生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}

project_name: "{project.get('name', 'Project')}"

# ---------------------------------------------------------------------------
# API 提供商凭证 (凭证本身在 .env, 此处声明环境变量名)
# ---------------------------------------------------------------------------
providers:
{self._format_providers(providers)}

# ---------------------------------------------------------------------------
# 角色模型配置
# ---------------------------------------------------------------------------
roles:
{roles}

# ---------------------------------------------------------------------------
# 流水线拓扑
# ---------------------------------------------------------------------------
pipeline:
  max_rounds_env: COMMITTEE_MAX_ROUNDS
  max_rounds_default: 3
  converge_role: architect

  debate_stages:
{pipeline}

# ---------------------------------------------------------------------------
# 共享事实文件 (相对路径)
# ---------------------------------------------------------------------------
shared_context:
  files:
{self._format_shared_context_files()}

# ---------------------------------------------------------------------------
# 自定义提示词 (按节点名覆盖引擎内置默认)
# ---------------------------------------------------------------------------
prompts:
{self._format_prompts_mapping()}
"""
        self._write_file("config.yaml", content)

    def _build_roles(self) -> str:
        """构建角色配置"""
        roles = self.metadata.get("roles", {})
        lines = []

        for key, role in roles.items():
            desc = role.get("description", "")
            provider = role.get("provider", "qwen")
            model = role.get("model", "qwen3.7-max-2026-05-17")
            temp = role.get("temperature", 0.3)

            # 检查是否有待确认标记
            tag = ""
            if has_pending_tag(desc) or has_pending_tag(str(role)):
                tag = "  # 包含待确认项"

            lines.append(f"  {key}:")
            lines.append(f'    description: "{desc}"{tag}')
            lines.append(f"    provider: {provider}")
            lines.append(f"    model: {model}")
            lines.append(f"    temperature: {temp}")
            lines.append("")

        return "\n".join(lines)

    def _build_pipeline(self) -> str:
        """构建流水线配置"""
        pipeline = self.metadata.get("pipeline", [])
        lines = []

        for stage in pipeline:
            node = stage.get("node", "")
            role = stage.get("role", "")
            node_type = stage.get("type", "review")

            lines.append(f"    - node: {node}")
            lines.append(f"      role: {role}")
            lines.append(f"      type: {node_type}")
            lines.append("")

        return "\n".join(lines)

    def _format_providers(self, providers: dict) -> str:
        """格式化提供商配置"""
        lines = []
        for key, provider in providers.items():
            lines.append(f"  {key}:")
            lines.append(f"    api_key_env: {provider.get('api_key_env', f'{key.upper()}_API_KEY')}")
            lines.append(f"    base_url_env: {provider.get('base_url_env', f'{key.upper()}_BASE_URL')}")
        return "\n".join(lines)

    def _format_shared_context_files(self) -> str:
        """格式化共享事实文件列表"""
        shared_context = self.metadata.get("shared_context", {})
        files = shared_context.get("files", [])
        if not files:
            files = [
                "shared_context/architecture.md",
                "shared_context/constraints.md",
            ]
        return "\n".join(f"    - {f}" for f in files)

    def _format_prompts_mapping(self) -> str:
        """格式化提示词映射"""
        pipeline = self.metadata.get("pipeline", [])
        lines = []

        for stage in pipeline:
            node = stage.get("node", "")
            lines.append(f"  {node}: prompts/{node}.md")

        # 添加 converge
        lines.append("  converge: prompts/converge.md")

        return "\n".join(lines)

    def _generate_topics(self):
        """生成 topics.yaml"""
        project = self.metadata.get("project", {})
        topics = self.metadata.get("topics", [])

        topics_yaml = "# {} 架构委员会 — 议题库\n".format(project.get("name", "Project"))
        topics_yaml += f"# 由 generate.py 自动生成，生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        topics_yaml += "topics:\n"

        for topic in topics:
            topic_id = topic.get("id", "unknown")
            module = topic.get("module", "unknown")
            summary = topic.get("summary", "")
            attack_angles = topic.get("attack_angles", [])

            topics_yaml += f"  {topic_id}:\n"
            topics_yaml += f"    topic: |\n"
            topics_yaml += f"      审阅 {topic_id} 设计 ({module})。\n"
            topics_yaml += f"      现有方案: {summary}\n"
            topics_yaml += f"\n"
            topics_yaml += f"      攻击角度:\n"

            for i, angle in enumerate(attack_angles, 1):
                topics_yaml += f"      {i}. {angle}\n"

            topics_yaml += f'    desc: "{topic.get("desc", topic_id)}"\n\n'

        self._write_file("topics.yaml", topics_yaml)

    def _generate_shared_context(self):
        """生成 shared_context/"""
        shared_context = self.metadata.get("shared_context", {})
        files = shared_context.get("files", [])

        for file_config in files:
            if isinstance(file_config, str):
                # 简单文件路径，生成默认内容
                if "architecture" in file_config:
                    self._generate_architecture_md(file_config)
                elif "constraints" in file_config:
                    self._generate_constraints_md(file_config)
            elif isinstance(file_config, dict):
                # 自定义文件配置
                file_path = file_config.get("path", "")
                content = file_config.get("content", "")
                if file_path and content:
                    self._write_file(file_path, content)

    def _generate_architecture_md(self, file_path: str):
        """生成 architecture.md"""
        project = self.metadata.get("project", {})
        architecture = self.metadata.get("architecture", {})
        hardware = self.metadata.get("hardware", {})

        content = f"""# {project.get('name', 'System')} — 架构概览

> 来源：项目元数据 (.committee.yaml)
> 本文件是委员会辩论的**唯一事实层**。Agent 不得自行编造系统架构或模块职责。
>
> **标注协议**:
> - `[C]` Constraint — 架构硬性约束，违反即设计无效
> - `[F]` Formula — 基于已知参数的公式推导值，非实测
> - `[R]` Relative — 相对比较值，用于说明改善幅度
> - `[M]` Measured — 在指定硬件平台上的实测值

---

## 1. 系统概述

| 属性 | 值 |
|------|-----|
| 系统类型 | {project.get('type', '[待确认]')} |
| 应用场景 | {project.get('domain', '[待确认]')} |
| 描述 | {project.get('description', '[待补充]')} |

---

## 2. 硬件平台

| 参数 | 值 | 标注 |
|------|-----|------|
| 平台 | {hardware.get('platform', '[待补充]')} | [C] |
| 存储 | Flash: {hardware.get('resources', {}).get('flash', '[待补充]')}, RAM: {hardware.get('resources', {}).get('ram', '[待补充]')} | [C] |

### 2.1 外设

| 名称 | 型号 | 接口 | 频率 | 标注 |
|------|------|------|------|------|
"""

        for p in hardware.get("peripherals", []):
            content += f"| {p.get('name', '')} | {p.get('model', '')} | {p.get('interface', '')} | {p.get('frequency', '')} | [C] |\n"

        content += f"""
---

## 3. 软件架构

| 属性 | 值 |
|------|-----|
| 操作系统 | {architecture.get('os', '[待补充]')} |

### 3.1 模块

| 模块 | 描述 | 位置 |
|------|------|------|
"""

        for m in architecture.get("modules", []):
            content += f"| {m.get('name', '')} | {m.get('description', '')} | {m.get('location', '')} |\n"

        content += f"""
### 3.2 任务

| 任务 | 周期 | 优先级 | WCET | 栈大小 |
|------|------|--------|------|--------|
"""

        for t in architecture.get("tasks", []):
            content += f"| {t.get('name', '')} | {t.get('period', '')} | {t.get('priority', '')} | {t.get('wcet', '')} | {t.get('stack', '')} |\n"

        content += f"""
---

## 4. 已确认的设计决策（委员会不得推翻，除非提供新证据）

| # | 决策 | 原因 |
|---|------|------|
| 1 | [待委员会讨论后补充] | - |

---

## 5. 已知盲区（委员会应重点关注）

- [待委员会运行后补充]
"""

        self._write_file(file_path, content)

    def _generate_constraints_md(self, file_path: str):
        """生成 constraints.md"""
        project = self.metadata.get("project", {})
        constraints = self.metadata.get("constraints", {})

        content = f"""# {project.get('name', 'System')} — 运行时约束

> 来源：项目元数据 (.committee.yaml)
> 本文件定义委员会所有辩论的**物理边界**。违反这些约束的提案一律无效。
>
> **标注协议**:
> - `[C]` Constraint — 架构硬性约束，违反即设计无效
> - `[F]` Formula — 基于已知参数的公式推导值，非实测
> - `[R]` Relative — 相对比较值，用于说明改善幅度
> - `[M]` Measured — 在指定硬件平台上的实测值

---

## 1. 实时性约束

| 约束 | 类型 | 标注 |
|------|------|------|
"""

        for c in constraints.get("realtime", []):
            if isinstance(c, dict):
                content += f"| {c.get('description', '')} | {c.get('type', 'hard')} | [C] |\n"
            else:
                content += f"| {c} | hard | [C] |\n"

        content += f"""
---

## 2. 安全性约束

| 约束 | 标注 |
|------|------|
"""

        for c in constraints.get("safety", []):
            if isinstance(c, dict):
                content += f"| {c.get('description', '')} | [C] |\n"
            else:
                content += f"| {c} | [C] |\n"

        content += f"""
---

## 3. MBD 约束（如适用）

"""

        mbd = constraints.get("mbd", {})
        if mbd.get("enabled", False):
            content += f"""| 属性 | 值 |
|------|-----|
| 求解器 | {mbd.get('solver', '[待补充]')} |
| 目标芯片 | {mbd.get('target', '[待补充]')} |

### 代码生成约束

"""
            for c in mbd.get("constraints", []):
                content += f"- {c}\n"

            content += f"""
### 验证要求

| 层级 | 标准 |
|------|------|
"""
            for v in mbd.get("verification", []):
                if isinstance(v, dict):
                    content += f"| {v.get('level', '')} | {v.get('coverage', '')} |\n"
        else:
            content += "*不适用*\n"

        content += f"""
---

## 4. 已确认的设计决策（委员会不得推翻，除非提供新证据）

| # | 决策 | 原因 |
|---|------|------|
| 1 | [待委员会讨论后补充] | - |

---

## 5. 已知盲区（委员会应重点关注）

- [待委员会运行后补充]
"""

        self._write_file(file_path, content)

    def _generate_prompts(self):
        """生成 prompts/"""
        pipeline = self.metadata.get("pipeline", [])
        experts = self.metadata.get("experts", [])
        attack_scenarios = self.metadata.get("attack_scenarios", [])

        for stage in pipeline:
            node = stage.get("node", "")
            node_type = stage.get("type", "review")
            role_key = stage.get("role", "")

            if node_type == "review":
                # 查找对应的专家配置
                expert_config = next((e for e in experts if e.get("key") == role_key), None)
                self._generate_review_prompt(node, expert_config)
            elif node_type == "attack":
                self._generate_attack_prompt(node, attack_scenarios)
            elif node_type == "audit":
                self._generate_audit_prompt(node)

        # 生成 converge
        self._generate_converge_prompt()

    def _generate_review_prompt(self, node_name: str, expert_config: dict = None):
        """生成 review 类型提示词"""
        project = self.metadata.get("project", {})
        system_type = project.get("type", "系统")
        domain = project.get("domain", "领域")

        if expert_config:
            # 领域专家提示词
            knowledge = expert_config.get("knowledge", [])
            dimensions = expert_config.get("dimensions", [])

            knowledge_text = ""
            for i, k in enumerate(knowledge, 1):
                knowledge_text += f"\n### {i}. {k.get('title', '')}\n\n"
                for point in k.get("points", []):
                    knowledge_text += f"- {point}\n"

            dimensions_text = ""
            for i, d in enumerate(dimensions, 1):
                dimensions_text += f"\n### {i}. {d}\n- [待委员会运行后补充具体审查点]\n"

            content = f"""你是 {{project_name}} 平台的【{{role_desc}}】。
你是一名在{expert_config.get('domain', domain)}深耕多年的专家。
你的唯一任务是审查设计方案的**{expert_config.get('focus', '正确性')}**，不关心{expert_config.get('ignore', '其他方面')}。

## 共享事实层 (唯一真理源)
{{shared_context}}

## 领域知识基线

以下是你作为领域专家应具备的知识背景，审查时应基于这些认知进行判断。
{knowledge_text}

## 审查维度
{dimensions_text}

## 输出格式

### {{前缀}}-{{round}}N: [问题标题] — [Blocker / Critical / Warning]

- **问题推演**: 此设计在哪个场景下会产生错误
- **根因**: 哪一步的假设是错误的
- **领域视角**: 从{domain}角度，此问题的实际影响
- **修正建议**: 正确的做法是什么

## 评级标准
[Blocker]  = 不改则必然错误或核心功能无法工作
[Critical] = 不改则特定场景下严重退化或不可用
[Warning]  = 理论上的边界风险或鲁棒性不足
"""
        else:
            # 通用架构师提示词
            content = f"""你是 {{project_name}} 平台的【{{role_desc}}】。
你是一名首席系统架构师，设计的是**{system_type}**。
你的设计必须从第一性原理出发。

## 共享事实层 (唯一真理源)
{{shared_context}}

## 核心设计原则

### 高内聚、低耦合、开闭原则 (OCP)
- 新增功能不应修改框架核心代码，只扩展接口
- 但解耦必须产生实际价值——为未来"可能的需求"过度抽象是浪费

## 运行时否决条件
{{redlines}}

## 当前议题
{{current_topic}}
{{revision_context}}

## 输出格式

### 1. 设计方案
逐条描述设计决策，附充分性评级 [充分 / 有缺口 / 未论证]

### 2. 关键分析
分析设计方案的关键指标和约束满足情况

### 3. 领域假设声明
列出你设计方案中**隐式依赖的领域假设**，供领域专家精准审查

### 4. 需要领域专家重点审查的部分
你对自己方案的哪些部分没有信心？请明确指出。
"""

        self._write_file(f"prompts/{node_name}.md", content)

    def _generate_attack_prompt(self, node_name: str, scenarios: list):
        """生成 attack 类型提示词"""
        project = self.metadata.get("project", {})
        domain = project.get("domain", "系统")

        scenarios_text = ""
        for i, s in enumerate(scenarios, 1):
            name = s.get("name", f"场景 {i}")
            desc = s.get("description", "")
            extensions = s.get("extensions", [])

            scenarios_text += f"""
### 场景 {chr(64+i)} — {name}
{desc}

**延伸攻击:**
"""
            for ext in extensions:
                scenarios_text += f"- {ext}\n"

        content = f"""你是 {{project_name}} 平台的【{{role_desc}}】。
你是一名极端反驳专家，你的唯一任务是粉碎温床，找出所有设计缺陷。严禁赞美。
你不是在做 code review，你是在模拟系统在真实{domain}中崩溃的全过程——从用户可见的故障现象倒推到设计根因。

## 共享事实层 (唯一真理源)
{{shared_context}}

## 攻击哲学

设计缺陷分为三类，你的攻击必须覆盖全部：

**逻辑缺陷** — 代码/架构层面的错误，可以通过静态分析发现
**领域错配** — 软件工程上正确，但在{domain}场景下物理上不成立
**任务脱节** — 系统能跑，但在实际任务中不可用或不安全

## 攻击方法: 崩溃倒推法

从以下专属场景倒推，找到当前设计的根因:
{scenarios_text}

## 输出格式
每个漏洞必须包含:

### A-{{round}}N: [漏洞标题] — [Blocker / Critical / Warning]

- **崩溃推演**: 从用户可见的故障现象 → 逐步向代码上游推导 → 定位到设计的哪一处
- **受影响的设计**: 引用前面评审方的具体章节或声明
- **根因**: 为什么这个设计会导致上述故障
- **领域视角**: 从{domain}实战角度，此故障的实际影响
- **修正建议**: 如果当前轮次是第 N 轮且之前已提过此漏洞，注明是否已修正

## 评级标准
[Blocker]  = 不改则系统必然崩溃或核心功能无法工作
[Critical] = 不改则性能/可维护性严重退化，或在特定条件下崩溃
[Warning]  = 潜在风险，当前条件下不会触发但设计不够健壮
"""

        self._write_file(f"prompts/{node_name}.md", content)

    def _generate_audit_prompt(self, node_name: str):
        """生成 audit 类型提示词"""
        project = self.metadata.get("project", {})
        system_type = project.get("type", "系统")

        content = f"""你是 {{project_name}} 平台的【{{role_desc}}】。
你是一名底层性能与编译专家，审查设计如同编译器优化 pass——精确、量化、无情。
你审查的不是"这个设计好不好"，而是"这个设计在目标硬件上每秒跑多少帧、每帧花多少毫秒、占多少资源"。

## 共享事实层 (唯一真理源)
{{shared_context}}

## 审计哲学

{system_type}下的性能审计与服务器/桌面完全不同：

**确定性 > 平均性能:**
- 服务器追求吞吐量，{system_type}追求延迟确定性 (WCET)
- 一次超时可能导致系统失效，比平均慢一点更致命

**全链路性能 > 单点优化:**
- 关键路径只是全链路的一环
- 单独优化关键路径无意义，如果其他阶段占用过多时间

## 审计维度

### 1. 延迟预算与全链路分析
- 端到端延迟分解
- 每个阶段的平均延迟和最坏情况延迟
- 全链路延迟总和是否在预算内

### 2. 资源使用分析
- 内存使用（栈、堆、静态分配）
- CPU 利用率
- 带宽使用

### 3. 实时性分析
- WCET 分析
- 中断响应延迟
- 调度抖动

### 4. 长时间运行稳定性
- 资源泄漏
- 温度/降频影响
- 累积误差

## 硬性否决条件 (违反任一条即当场否决)

1. **不破坏实时性** — 关键路径 WCET 必须在截止期限内
2. **不引入不确定性** — 禁止动态内存分配、未绑定的循环
3. **不阻塞关键任务** — 低优先级任务不得阻塞高优先级任务

## 输出格式
每个性能问题:

### P-{{round}}N: [问题标题]

- **量化影响**: 延迟增量 X ms | 带宽增量 Y MB/s | 资源增量 Z KB
- **触发条件**: 在哪个精确场景下会触发
- **与硬性约束的关系**: 是否违反否决条件
- **全链路影响**: 此问题对端到端延迟预算的影响
- **修复收益估算**: 修复后预期改善多少

你必须在报告中给出具体的数字估算，不接受纯定性描述。
"""

        self._write_file(f"prompts/{node_name}.md", content)

    def _generate_converge_prompt(self):
        """生成 converge 提示词"""
        content = """你是 {project_name} 平台的【{role_desc}】。整场 {round} 轮辩论**已经彻底结束**。
你现在不是辩论参与者，而是**会议记录员**。
严禁继续辩论、严禁提出新观点、严禁反驳任何之前的发言。

## 你的唯一任务
基于上面的全部辩论历史，生成两份产物。

## 产物一: 决策摘要 (纯文本)

用 3-5 句话描述最终决策结论。格式:

结论: <一句话结论>
涉及文件: <逗号分隔的文件列表>

## 产物二: 结构化行动项

**必须**在 ```json 代码块中输出:

```json
{{
  "action_items": [
    {{
      "id": "AI-001",
      "priority": "blocker",
      "file": "path/to/file",
      "action": "具体做什么",
      "detail": "为什么这样做",
      "verification": "如何验证完成"
    }}
  ]
}}
```

## 重要提醒
- 不要再辩论任何内容
- JSON 代码块必须可被 json.loads 直接解析
- 如果没有行动项, 输出空数组 []
- 决策摘要和 JSON 之间用 --- 分隔线隔开

## 共享事实层
{shared_context}
"""

        self._write_file("prompts/converge.md", content)

    def _print_summary(self):
        """打印生成摘要"""
        import io
        import sys

        # 设置 stdout 编码为 UTF-8（Windows 兼容）
        if sys.platform == "win32":
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

        print("\n" + "=" * 60)
        print("  Committee config generation completed")
        print("=" * 60)

        print(f"\n  Output directory: {self.output_dir}")
        print(f"  Generated files: {len(self.generated_files)}")

        if self.generated_files:
            print("\n  [OK] Generated:")
            for f in self.generated_files:
                print(f"    - {f}")

        if self.skipped_files:
            print(f"\n  [SKIP] Manually modified: {len(self.skipped_files)}")
            for f in self.skipped_files:
                print(f"    - {f}")

        # 统计待处理标记
        total_pending = {"pending_confirm": 0, "pending补充": 0, "pending_discuss": 0, "unknown": 0}
        for f in self.generated_files:
            file_path = self.output_dir / f
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                for tag, count in count_pending_tags(content).items():
                    if "待确认" in tag:
                        total_pending["pending_confirm"] += count
                    elif "待补充" in tag:
                        total_pending["pending补充"] += count
                    elif "待讨论" in tag:
                        total_pending["pending_discuss"] += count
                    elif "???" in tag:
                        total_pending["unknown"] += count

        if any(v > 0 for v in total_pending.values()):
            print("\n  [WARN] Pending tags:")
            if total_pending["pending_confirm"] > 0:
                print(f"    - [待确认]: {total_pending['pending_confirm']}")
            if total_pending["pending补充"] > 0:
                print(f"    - [待补充]: {total_pending['pending补充']}")
            if total_pending["pending_discuss"] > 0:
                print(f"    - [待讨论]: {total_pending['pending_discuss']}")
            if total_pending["unknown"] > 0:
                print(f"    - [???]: {total_pending['unknown']}")

        print("\n" + "=" * 60)


# ============================================================================
# 主函数
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="委员会配置生成工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python tools/generate.py ../uav-fc/.committee.yaml
  python tools/generate.py .committee.yaml --output committee/my-project
  python tools/generate.py .committee.yaml --force
        """
    )

    parser.add_argument(
        "metadata",
        help="元数据文件路径 (.committee.yaml)"
    )
    parser.add_argument(
        "--output", "-o",
        help="输出目录（默认: .committee/）",
        default=None
    )
    parser.add_argument(
        "--force", "-f",
        help="强制覆盖所有文件（忽略手动修改）",
        action="store_true"
    )

    args = parser.parse_args()

    # 读取元数据
    metadata_path = Path(args.metadata)
    if not metadata_path.exists():
        print(f"错误: 元数据文件不存在: {metadata_path}")
        sys.exit(1)

    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = yaml.safe_load(f)

    # 确定输出目录
    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = Path(".committee")

    # 生成配置
    generator = ConfigGenerator(metadata, output_dir)

    if args.force:
        # 强制模式：清除哈希记录，覆盖所有文件
        generator.old_hashes = {}

    generator.generate_all()


if __name__ == "__main__":
    main()
