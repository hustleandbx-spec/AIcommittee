"""
Committee Debate Engine — 项目无关的架构委员会引擎。

用法:
    from engine.graph import build_graph
    graph, meta = build_graph(config)
"""

import re
import json
from typing import Dict, Any, List, Callable, Literal

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import MessagesState


# ============================================================================
# 内置提示词模板
# ============================================================================

DEFAULT_PROMPTS = {
    "review": """\
你是 {project_name} 平台的【{role_desc}】。

## 共享事实层 (唯一真理源)
{shared_context}

## 核心原则
- 高内聚、低耦合、开闭原则 (OCP)
- 能力驱动设计 (Capability-driven), 非模型代码硬编码
- 严格遵守运行时否决条件 (见下方)
- 解耦必须产生实际价值

## 运行时否决条件
{redlines}

## 当前议题
{current_topic}
{revision_context}

## 输出格式
### 1. 设计决策审计 (首轮) / 修正方案 (第N轮)
逐条分析, 附充分性评级 [充分 / 有缺口 / 未论证]

### 2. 潜在缺口
指出你认为最大的设计风险

### 3. 需要攻击方重点攻击的方向
你对自己方案的哪些部分没有信心?
""",

    "attack": """\
你是 {project_name} 平台的【{role_desc}】。
你的唯一任务是粉碎温床, 找出设计缺陷。严禁赞美。

## 攻击方法: 崩溃倒推法
从以下场景倒推, 找到当前设计的根因:

{attack_scenarios}

## 输出格式
每个漏洞必须包含:

### A-{round}N: [漏洞标题] — [Blocker / Critical / Warning]

- **崩溃推演**: (从用户可见的崩溃现象 → 从现象往上游推导 → 定位到当前设计的哪一处)
- **受影响的设计**: 引用设计文档的具体章节
- **根因**: 为什么这个设计会导致上述崩溃
- **修正建议**: 如果当前轮次是第 N 轮且之前已提过此漏洞, 注明评审方是否已修正及你的判断

## 评级标准
[Blocker]  = 不改则系统必然崩溃或核心功能无法工作
[Critical] = 不改则性能/可维护性严重退化, 或在特定条件下崩溃
[Warning]  = 潜在风险, 当前条件下不会触发但设计不够健壮

## 共享事实层
{shared_context}
""",

    "audit": """\
你是 {project_name} 平台的【{role_desc}】。
你审查设计如同编译器优化 pass — 精确、量化、无情。

## 审计维度
{audit_dimensions}

## 硬性否决条件 (违反任一条即当场否决)
{redlines}

## 输出格式
每个性能问题:

### P-{round}N: [问题标题]
- **量化影响**: 延迟增量 X ms | 带宽增量 Y MB/s | 显存增量 Z MB
- **触发条件**: 在哪个精确场景下会触发
- **与硬性约束的关系**: 是否违反否决条件

你必须在报告中给出具体的数字估算, 不接受纯定性描述。

## 共享事实层
{shared_context}
""",

    "converge": """\
你是 {project_name} 平台的【{role_desc}】。整场 {round} 轮辩论**已经彻底结束**。
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
""",
}


# ============================================================================
# 状态定义
# ============================================================================

class CommitteeState(MessagesState):
    current_topic: str = ""
    round: int = 0
    max_rounds: int = 3
    json_output_path: str = ""

    blocker_ids: List[str] = []
    critical_ids: List[str] = []
    total_vulns_found: int = 0
    force_finalize: bool = False

    decision_line: str = ""
    action_items: dict = {}


# ============================================================================
# 节点工厂
# ============================================================================

def _make_review_node(cfg: Dict, stage_cfg: Dict) -> Callable:
    role_key = stage_cfg["role"]
    node_name = stage_cfg["node"]
    role_desc = cfg["roles"][role_key]["description"]
    prompt_template = cfg["prompts"].get(node_name) or cfg["prompts"].get("review", DEFAULT_PROMPTS["review"])

    def node(state: CommitteeState) -> Dict[str, Any]:
        model = _build_model(cfg, role_key)
        round_num = state["round"] + 1
        is_revision = round_num > 1

        revision_context = ""
        if is_revision:
            prev_blockers = state.get("blocker_ids", [])
            prev_criticals = state.get("critical_ids", [])
            revision_context = f"""
## ⚠️ 这是第 {round_num} 轮修正

上一轮攻击方发现了以下未解决问题，你必须逐条给出修正方案:

### 未解决的 Blocker (必须修正):
{[f"- {b}" for b in prev_blockers] if prev_blockers else "无"}

### 未解决的 Critical (应修正):
{[f"- {c}" for c in prev_criticals] if prev_criticals else "无"}

你的任务:
1. 逐条回应上述漏洞 — 接受并修正 / 拒绝并给出理由
2. 给出修正后的设计方案
3. 如果认为某个 Blocker 是误判 (假阳性), 必须提供技术证据
"""

        system_prompt = prompt_template.format(
            project_name=cfg["project_name"],
            role_desc=role_desc,
            shared_context=cfg["shared_context"],
            redlines=cfg.get("redlines", ""),
            current_topic=state["current_topic"],
            revision_context=revision_context,
            round=round_num,
        )

        response = model.invoke(
            [SystemMessage(content=system_prompt)] + state["messages"]
        )
        header = "修正方案" if is_revision else "评审"
        response.content = f"### [{role_desc} — 第 {round_num} 轮{header}]\n\n{response.content}"

        return {"messages": [response]}

    return node


def _make_attack_node(cfg: Dict, stage_cfg: Dict) -> Callable:
    role_key = stage_cfg["role"]
    node_name = stage_cfg["node"]
    role_desc = cfg["roles"][role_key]["description"]
    prompt_template = cfg["prompts"].get(node_name) or cfg["prompts"].get("attack", DEFAULT_PROMPTS["attack"])

    def node(state: CommitteeState) -> Dict[str, Any]:
        model = _build_model(cfg, role_key)
        latest_proposal = state["messages"][-1] if state["messages"] else HumanMessage(content="无历史提案")
        round_num = state["round"] + 1

        system_prompt = prompt_template.format(
            project_name=cfg["project_name"],
            role_desc=role_desc,
            shared_context=cfg["shared_context"],
            attack_scenarios=cfg.get("attack_scenarios", "场景 A — 运行时崩溃\n场景 B — 扩展时断裂\n场景 C — 迁移时失效"),
            round=round_num,
        )

        response = model.invoke(
            [SystemMessage(content=system_prompt), latest_proposal]
        )
        response.content = f"### [{role_desc} — 第 {round_num} 轮攻击报告]\n\n{response.content}"

        content = response.content
        blocker_pattern = re.findall(r'###\s+[ACP]-\d+\S*:\s*.+?\s*[—\-]\s*\[?Blocker\]?', content)
        critical_pattern = re.findall(r'###\s+[ACP]-\d+\S*:\s*.+?\s*[—\-]\s*\[?Critical\]?', content)
        warning_pattern = re.findall(r'###\s+[ACP]-\d+\S*:\s*.+?\s*[—\-]\s*\[?Warning\]?', content)
        # simplified extraction
        blocker_ids = [b.strip()[:80] for b in blocker_pattern] if blocker_pattern else []
        critical_ids = [c.strip()[:80] for c in critical_pattern] if critical_pattern else []

        total_new = len(blocker_pattern) + len(critical_pattern) + len(warning_pattern)

        return {
            "messages": [response],
            "blocker_ids": blocker_ids,
            "critical_ids": critical_ids,
            "total_vulns_found": state.get("total_vulns_found", 0) + total_new,
        }

    return node


def _make_audit_node(cfg: Dict, stage_cfg: Dict) -> Callable:
    role_key = stage_cfg["role"]
    node_name = stage_cfg["node"]
    role_desc = cfg["roles"][role_key]["description"]
    prompt_template = cfg["prompts"].get(node_name) or cfg["prompts"].get("audit", DEFAULT_PROMPTS["audit"])

    def node(state: CommitteeState) -> Dict[str, Any]:
        model = _build_model(cfg, role_key)
        round_num = state["round"] + 1

        dimensions = cfg.get("audit_dimensions", [])
        dim_text = "\n".join(f"{i+1}. {d}" for i, d in enumerate(dimensions)) if dimensions else "待项目定义"

        system_prompt = prompt_template.format(
            project_name=cfg["project_name"],
            role_desc=role_desc,
            shared_context=cfg["shared_context"],
            redlines=cfg.get("redlines", ""),
            audit_dimensions=dim_text,
            round=round_num,
        )

        response = model.invoke(
            [SystemMessage(content=system_prompt)] + state["messages"]
        )
        response.content = f"### [{role_desc} — 第 {round_num} 轮审计]\n\n{response.content}"

        return {
            "messages": [response],
            "round": state["round"] + 1,
        }

    return node


def _make_converge_node(cfg: Dict) -> Callable:
    converge_role = cfg["pipeline"]["converge_role"]
    role_desc = cfg["roles"][converge_role]["description"]
    prompt_template = cfg["prompts"].get("converge", DEFAULT_PROMPTS["converge"])

    def node(state: CommitteeState) -> Dict[str, Any]:
        model = _build_model(cfg, converge_role)

        system_prompt = prompt_template.format(
            project_name=cfg["project_name"],
            role_desc=role_desc,
            shared_context=cfg["shared_context"],
            current_topic=state["current_topic"][:80],
            round=state["round"],
        )

        response = model.invoke(
            [SystemMessage(content=system_prompt)] + state["messages"]
        )

        json_path = state.get("json_output_path", "")
        action_items = _extract_action_items(response.content)
        if json_path:
            os.makedirs(os.path.dirname(json_path) or ".", exist_ok=True)
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(action_items, f, ensure_ascii=False, indent=2)

        decision_line = _extract_decision_line(response.content, state)
        summary = _build_summary(state, action_items)
        response.content = summary + "\n\n" + response.content

        return {
            "messages": [response],
            "force_finalize": True,
            "decision_line": decision_line,
            "action_items": action_items,
        }

    return node


NODE_FACTORIES: Dict[str, Callable] = {
    "review": _make_review_node,
    "attack": _make_attack_node,
    "audit": _make_audit_node,
}


# ============================================================================
# 模型构建
# ============================================================================

import os

def _require_env(name: str) -> str:
    val = os.environ.get(name, "")
    if not val:
        raise RuntimeError(f"缺少必需的环境变量: {name}")
    return val


def _build_model(cfg: Dict, role_key: str) -> ChatOpenAI:
    role_cfg = cfg["roles"][role_key]
    provider_cfg = cfg["providers"][role_cfg["provider"]]
    kwargs = {
        "model": role_cfg["model"],
        "api_key": _require_env(provider_cfg["api_key_env"]),
        "temperature": role_cfg["temperature"],
    }
    base_url = _require_env(provider_cfg["base_url_env"])
    if base_url:
        kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs)


# ============================================================================
# 辅助函数
# ============================================================================

def _extract_action_items(content: str) -> Dict[str, Any]:
    try:
        match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        if match:
            return json.loads(match.group(1))
    except json.JSONDecodeError:
        pass
    return {"action_items": [], "parse_error": "Failed to extract JSON from ADR"}


def _extract_decision_line(content: str, state: CommitteeState) -> str:
    """从 converge 输出中提取结论摘要，用于追加到 decisions.md。"""
    # 尝试匹配 "结论:" 开头的行
    m = re.search(r'结论:\s*(.+?)(?:\n|$)', content)
    if m:
        return m.group(1).strip()

    # 回退: 匹配 --- 分隔线之前的第一段非空文本
    parts = content.split("---", 1)
    if parts:
        first = parts[0].strip()
        # 取前 120 字符作为摘要
        return first.replace("\n", " ")[:120]

    return state.get("current_topic", "")[:80]


def _build_summary(state: CommitteeState, action_items: Dict) -> str:
    ai = action_items.get("action_items", [])
    blockers = [a for a in ai if a.get("priority") == "blocker"]
    criticals = [a for a in ai if a.get("priority") == "critical"]
    warnings = [a for a in ai if a.get("priority") == "warning"]

    lines = [
        "",
        "=" * 60,
        "  Committee — Final Report",
        "=" * 60,
        f"  Rounds: {state['round']}",
        f"  Issues found: {state.get('total_vulns_found', 0)}",
        f"  Actions: {len(blockers)} Blocker, {len(criticals)} Critical, {len(warnings)} Warning",
        f"  JSON: {state.get('json_output_path', 'N/A')}",
        "=" * 60,
    ]

    if blockers:
        lines.append("\n## [BLOCKER]")
        for a in blockers:
            lines.append(f"  - [{a['id']}] {a['file']}: {a['action']}")

    if criticals:
        lines.append("\n## [CRITICAL]")
        for a in criticals:
            lines.append(f"  - [{a['id']}] {a['file']}: {a['action']}")

    if warnings:
        lines.append("\n## [WARNING]")
        for a in warnings:
            lines.append(f"  - [{a['id']}] {a['file']}: {a['action']}")

    lines.append(f"\n>>> Actions written to {state.get('json_output_path', '')}")
    lines.append(">>> Claude Code: read the JSON file and implement each action item.")

    return "\n".join(lines)


# ============================================================================
# 自适应路由
# ============================================================================

def _make_router(cfg: Dict) -> Callable:
    max_rounds = cfg["pipeline"].get("max_rounds_default", 3)

    def should_continue(state: CommitteeState) -> Literal["loop", "finalize"]:
        if state.get("force_finalize", False):
            return "finalize"

        round_num = state["round"]
        max_r = state.get("max_rounds", max_rounds)

        if round_num >= max_r:
            print(f"  [router] max rounds ({max_r}) reached → finalize")
            return "finalize"

        has_blockers = len(state.get("blocker_ids", [])) > 0
        has_criticals = len(state.get("critical_ids", [])) > 0

        if has_blockers:
            print(f"  [router] {len(state['blocker_ids'])} Blocker(s) → round {round_num+1}")
            return "loop"

        if has_criticals and round_num < max_r - 1:
            print(f"  [router] {len(state['critical_ids'])} Critical(s) → round {round_num+1}")
            return "loop"

        print("  [router] no unresolved Blockers/Criticals → finalize")
        return "finalize"

    return should_continue


# ============================================================================
# 图构建 (唯一公开入口)
# ============================================================================

def build_graph(cfg: Dict) -> tuple:
    """根据配置构建 LangGraph 辩论图。

    Args:
        cfg: 完整配置字典, 包含:
            - project_name
            - roles: {key: {description, model_env, api_key_env, base_url_env, temperature}}
            - pipeline: {max_rounds_default, converge_role, debate_stages: [{node, role, type}]}
            - shared_context: str
            - redlines: str
            - attack_scenarios: str
            - audit_dimensions: [str]
            - prompts: {review, attack, audit, converge} (可选, 不提供则用内置默认)

    Returns:
        (compiled_graph, meta_dict)
    """
    # 填充 prompts 默认值
    if "prompts" not in cfg:
        cfg["prompts"] = {}
    for key in ["review", "attack", "audit", "converge"]:
        if key not in cfg["prompts"]:
            cfg["prompts"][key] = DEFAULT_PROMPTS[key]

    max_rounds_env = cfg["pipeline"].get("max_rounds_env", "")
    max_rounds_default = cfg["pipeline"].get("max_rounds_default", 3)
    max_rounds = int(os.environ.get(max_rounds_env, max_rounds_default)) if max_rounds_env else max_rounds_default

    debate_stages = cfg["pipeline"]["debate_stages"]

    workflow = StateGraph(CommitteeState)

    node_names = []
    for stage in debate_stages:
        node_name = stage["node"]
        node_type = stage["type"]
        factory = NODE_FACTORIES[node_type]
        workflow.add_node(node_name, factory(cfg, stage))
        node_names.append(node_name)

    workflow.add_node("chief_converge", _make_converge_node(cfg))

    workflow.add_edge(START, node_names[0])
    for i in range(len(node_names) - 1):
        workflow.add_edge(node_names[i], node_names[i + 1])

    router = _make_router(cfg)
    workflow.add_conditional_edges(
        node_names[-1],
        router,
        {"loop": node_names[0], "finalize": "chief_converge"},
    )
    workflow.add_edge("chief_converge", END)

    graph = workflow.compile()

    meta = {
        "roles": cfg["roles"],
        "debate_stages": debate_stages,
        "converge_role": cfg["pipeline"]["converge_role"],
        "max_rounds": max_rounds,
    }

    return graph, meta
