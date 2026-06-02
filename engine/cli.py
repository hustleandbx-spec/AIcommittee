"""
Committee CLI — 加载项目配置并运行辩论。

用法:
    python -m committee.engine.cli <project_dir> --topic xxx
    python committee/run.py <project_dir> --topic xxx
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

import yaml


def _load_dotenv(path: Path) -> None:
    """加载 .env 文件 (兼容 python-dotenv 和手动解析)。"""
    if not path.exists():
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(path)
        return
    except ImportError:
        pass
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _load_shared_context(project_dir: Path, cfg: dict) -> str:
    """加载项目配置中声明的共享事实文件。"""
    files = cfg.get("shared_context", {}).get("files", [])
    parts = []
    for rel_path in files:
        full_path = project_dir / rel_path
        if full_path.exists():
            text = full_path.read_text(encoding="utf-8")
            parts.append(f"=== {rel_path} ===\n{text}")
        else:
            parts.append(f"=== {rel_path} ===\n[WARNING: not found]")
    return "\n\n".join(parts)


def _load_prompts(project_dir: Path, cfg: dict) -> dict:
    """加载项目自定义提示词模板 (可选)。"""
    prompts = {}
    prompt_map = cfg.get("prompts", {})
    for key, rel_path in prompt_map.items():
        full_path = project_dir / rel_path
        if full_path.exists():
            prompts[key] = full_path.read_text(encoding="utf-8")
    return prompts


def _resolve_topic(topic_arg: str, topics_cfg: dict) -> tuple:
    """解析议题: 预设 key / 自定义文本。"""
    topics = topics_cfg.get("topics", {})
    if topic_arg in topics:
        entry = topics[topic_arg]
        return entry["topic"], entry.get("desc", topic_arg)
    return topic_arg, "自定义议题"


def _append_decisions_log(project_path: Path, json_path: str, topic_desc: str,
                          action_items: dict) -> None:
    """追加一行到项目 decisions.md。"""
    log_path = project_path / "decisions.md"
    ai = action_items.get("action_items", [])
    blockers = sum(1 for a in ai if a.get("priority") == "blocker")
    criticals = sum(1 for a in ai if a.get("priority") == "critical")
    warnings = sum(1 for a in ai if a.get("priority") == "warning")
    json_name = os.path.basename(json_path)
    date_str = datetime.now().strftime("%Y-%m-%d")
    topic_short = topic_desc[:60].replace("\n", " ").replace("|", "/")

    header = "| 日期 | 议题 | Blocker | Critical | Warning | 行动项文件 |\n|------|------|---------|----------|---------|------------|\n"
    if not log_path.exists():
        log_path.write_text(
            "# 委员会决策日志\n\n"
            "> 每行一条决策记录。行动项 JSON 中才有完整内容。\n\n"
            + header,
            encoding="utf-8"
        )

    line = f"| {date_str} | {topic_short} | {blockers} | {criticals} | {warnings} | {json_name} |\n"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line)


def _print_banner(project_name: str, desc: str, max_rounds: int, json_path: str, meta: dict) -> None:
    role_lines = []
    seen = set()
    for stage in meta["debate_stages"]:
        rk = stage["role"]
        if rk not in seen:
            seen.add(rk)
            role_cfg = meta["roles"][rk]
            role_lines.append(f"    {role_cfg['description']}: {role_cfg['model']} ({role_cfg['provider']})")
    ck = meta["converge_role"]
    if ck not in seen:
        role_cfg = meta["roles"][ck]
        role_lines.append(f"    {role_cfg['description']} (汇总): {role_cfg['model']} ({role_cfg['provider']})")

    print(f"""
{'='*60}
  {project_name} — Committee Session
{'='*60}
  Topic: {desc}
  Max rounds: {max_rounds}
  Actions: {json_path}
  Roles:
{chr(10).join(role_lines)}
{'='*60}
""")


def main_cli():
    """CLI 入口点 (供 pyproject.toml scripts 使用)。"""
    parser = argparse.ArgumentParser(description="Committee — multi-model design review")
    parser.add_argument("project", type=str, nargs="?", default=None,
                        help="Project directory name or path")
    parser.add_argument("--project-dir", type=str, default=None,
                        help="Absolute path to project config directory")
    parser.add_argument("--topic", "-t", type=str, default=None,
                        help="Topic key or custom text")
    parser.add_argument("--output", "-o", type=str, default=None,
                        help="Actions JSON output path")
    parser.add_argument("--max-rounds", "-r", type=int, default=None,
                        help="Max debate rounds")
    parser.add_argument("--list", action="store_true",
                        help="List available topics for the selected project")
    parser.add_argument("--json-only", action="store_true",
                        help="Silent mode, no intermediate output")
    parser.add_argument("--list-projects", action="store_true",
                        help="List all available projects")
    args = parser.parse_args()

    # 定位 committee 根目录 (engine 的父目录)
    engine_dir = Path(__file__).resolve().parent
    committee_root = engine_dir.parent

    # --project-dir: 直接使用外部项目目录
    if args.project_dir:
        project_path = Path(args.project_dir).resolve()
        if not (project_path / "config.yaml").exists():
            print(f"[!] config.yaml not found in {project_path}")
            sys.exit(1)
        main(
            project_dir=str(project_path),
            topic_arg=args.topic,
            max_rounds=args.max_rounds,
            output=args.output,
            json_only=args.json_only,
            list_topics=args.list,
        )
        return

    # 自动检测: 当前目录下的 committee/ 子目录
    cwd = Path.cwd()
    local_committee = cwd / "committee"
    if local_committee.is_dir() and (local_committee / "config.yaml").exists():
        print(f"Auto-detected: {local_committee}")
        main(
            project_dir=str(local_committee),
            topic_arg=args.topic,
            max_rounds=args.max_rounds,
            output=args.output,
            json_only=args.json_only,
            list_topics=args.list,
        )
        return

    # 本地项目发现
    projects = {}
    for entry in committee_root.iterdir():
        if entry.is_dir() and (entry / "config.yaml").exists():
            cfg_name = entry.name
            try:
                import yaml
                cfg = yaml.safe_load((entry / "config.yaml").read_text(encoding="utf-8"))
                display = cfg.get("project_name", cfg_name)
            except Exception:
                display = cfg_name
            projects[cfg_name] = display

    if args.list_projects:
        print("Available projects:")
        for key, display in projects.items():
            print(f"  {key}: {display}")
        return

    # 选择项目
    project = args.project
    if project is None:
        keys = list(projects.keys())
        if not keys:
            print("[!] No local projects found.")
            print("    Use --project-dir <path> to specify an external project.")
            sys.exit(1)
        if len(keys) == 1:
            project = keys[0]
            print(f"Auto-selected project: {projects[project]} ({project})")
        else:
            print("Available projects:")
            for i, key in enumerate(keys, 1):
                print(f"  [{i}] {key}: {projects[key]}")
            try:
                choice = input("\nSelect project: ").strip()
                idx = int(choice) - 1
                if 0 <= idx < len(keys):
                    project = keys[idx]
                else:
                    print("Invalid selection.")
                    sys.exit(1)
            except (ValueError, IndexError):
                print("Invalid selection.")
                sys.exit(1)
    elif project not in projects:
        # 如果不是本地项目名，尝试作为路径
        project_path = Path(project)
        if project_path.exists() and (project_path / "config.yaml").exists():
            main(
                project_dir=str(project_path.resolve()),
                topic_arg=args.topic,
                max_rounds=args.max_rounds,
                output=args.output,
                json_only=args.json_only,
                list_topics=args.list,
            )
            return
        print(f"[!] Project '{project}' not found. Available: {', '.join(projects.keys())}")
        print(f"    Use --project-dir <path> to specify an external project.")
        sys.exit(1)

    main(
        project_dir=project,
        topic_arg=args.topic,
        max_rounds=args.max_rounds,
        output=args.output,
        json_only=args.json_only,
        list_topics=args.list,
    )


def main(project_dir: str = None, topic_arg: str = None, max_rounds: int = None,
         output: str = None, json_only: bool = False, list_topics: bool = False) -> None:
    """委员会 CLI 入口。"""
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    # 定位 committee 根目录
    engine_dir = Path(__file__).resolve().parent
    committee_root = engine_dir.parent

    # 加载 .env
    _load_dotenv(committee_root / ".env")
    _load_dotenv(committee_root / ".env.local")

    # 解析 project_dir
    if project_dir is None:
        # 尝试从命令行获取
        print("Usage: python -m committee.engine.cli <project_dir> [--topic ...]")
        sys.exit(1)

    project_path = Path(project_dir)
    if not project_path.is_absolute():
        project_path = committee_root / project_dir
    if not project_path.exists():
        print(f"[!] Project directory not found: {project_path}")
        sys.exit(1)

    # 加载项目配置
    config_path = project_path / "config.yaml"
    if not config_path.exists():
        print(f"[!] config.yaml not found in {project_path}")
        sys.exit(1)
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    # 加载共享事实
    cfg["shared_context"] = _load_shared_context(project_path, cfg)

    # 加载自定义提示词
    cfg["prompts"] = _load_prompts(project_path, cfg)

    # 加载议题
    topics_path = project_path / "topics.yaml"
    topics_cfg = yaml.safe_load(topics_path.read_text(encoding="utf-8")) if topics_path.exists() else {}

    if list_topics:
        print("Available topics:")
        for key, t in topics_cfg.get("topics", {}).items():
            print(f"  {key}: {t.get('desc', '?')}")
        return

    # 解析议题
    if topic_arg:
        topic_text, desc = _resolve_topic(topic_arg, topics_cfg)
    else:
        # 交互式选择
        topic_keys = list(topics_cfg.get("topics", {}).keys())
        if topic_keys:
            print("Available topics:")
            for i, key in enumerate(topic_keys, 1):
                print(f"  [{i}] {key}: {topics_cfg['topics'][key].get('desc', '?')}")
            print("  [0] custom topic")
            try:
                choice = input("\nSelect (default 1): ").strip()
                idx = int(choice) - 1 if choice else 0
                if 0 <= idx < len(topic_keys):
                    entry = topics_cfg["topics"][topic_keys[idx]]
                    topic_text, desc = entry["topic"], entry.get("desc", topic_keys[idx])
                else:
                    topic_text = input("Enter custom topic: ").strip()
                    desc = "自定义议题"
                    if not topic_text:
                        print("No topic entered, exiting.")
                        return
            except (ValueError, IndexError):
                topic_text = input("Enter custom topic: ").strip()
                desc = "自定义议题"
                if not topic_text:
                    print("No topic entered, exiting.")
                    return
        else:
            topic_text = input("Enter topic: ").strip()
            desc = "自定义议题"
            if not topic_text:
                print("No topic entered, exiting.")
                return

    # 输出路径 (仅 JSON 行动项)
    rounds = max_rounds or cfg["pipeline"].get("max_rounds_default", 3)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if output:
        json_path = output if output.endswith(".json") else output + ".json"
    elif topic_arg and topic_arg in topics_cfg.get("topics", {}):
        json_path = str(project_path / "adr" / f"ADR-{topic_arg}.actions.json")
    else:
        json_path = str(project_path / "adr" / f"ADR_custom_{ts}.actions.json")

    # 构建图
    from .graph import build_graph
    graph, meta = build_graph(cfg)

    actual_rounds = max_rounds if max_rounds else meta["max_rounds"]

    _print_banner(cfg.get("project_name", "Project"), desc, actual_rounds, json_path, meta)

    # 初始状态
    from langchain_core.messages import HumanMessage
    initial_state = {
        "messages": [HumanMessage(content=f"启动辩论。\n议题:\n{topic_text}")],
        "current_topic": topic_text,
        "round": 0,
        "max_rounds": actual_rounds,
        "json_output_path": json_path,
        "blocker_ids": [],
        "critical_ids": [],
        "total_vulns_found": 0,
        "force_finalize": False,
    }

    try:
        action_items = {"action_items": []}
        decision_line = ""
        for output in graph.stream(initial_state, stream_mode="updates"):
            for node_name, data in output.items():
                if data.get("action_items"):
                    action_items = data["action_items"]
                if data.get("decision_line"):
                    decision_line = data["decision_line"]
                if json_only:
                    continue
                print(f"\n{'─'*50}")
                print(f"  [{node_name}]")
                print(f"{'─'*50}")
                if data.get("messages"):
                    content = data["messages"][-1].content
                    if len(content) > 1500:
                        print(content[:1500])
                        print(f"\n  ... (truncated, full content → {json_path})")
                    else:
                        print(content)

        print(f"""
{'='*60}
  Committee Session Complete
{'='*60}
  Actions: {json_path}

  Next: read the JSON and implement each action item.
{'='*60}
""")

        _append_decisions_log(project_path, json_path, decision_line or desc, action_items)

        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                actions = json.load(f)
            items = actions.get("action_items", [])
            if items:
                print("─" * 40)
                print("  Action Items Preview")
                print("─" * 40)
                emoji = {"blocker": "🔴", "critical": "🟠", "warning": "🟡"}
                for item in items:
                    e = emoji.get(item.get("priority"), "⚪")
                    print(f"  {e} [{item.get('id', '?')}] {item.get('file', '?')}")
                    print(f"     {item.get('action', '?')}")
                print()
            print(f"  (logged to {project_path / 'decisions.md'})")
            print()

    except KeyboardInterrupt:
        print("\n[!] Interrupted")
        sys.exit(130)
    except Exception as e:
        print(f"\n[!] Committee failed: {e}")
        print("[!] Check API keys and network connection")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Committee — multi-model design review")
    parser.add_argument("project", type=str, help="Project config directory (e.g. 'odt')")
    parser.add_argument("--topic", "-t", type=str, default=None, help="Topic key or custom text")
    parser.add_argument("--output", "-o", type=str, default=None, help="Actions JSON output path")
    parser.add_argument("--max-rounds", "-r", type=int, default=None, help="Max debate rounds")
    parser.add_argument("--list", action="store_true", help="List available topics")
    parser.add_argument("--json-only", action="store_true", help="Silent mode, no intermediate output")
    args = parser.parse_args()

    main(
        project_dir=args.project,
        topic_arg=args.topic,
        max_rounds=args.max_rounds,
        output=args.output,
        json_only=args.json_only,
        list_topics=args.list,
    )
