"""
Committee — 多项目统一入口。

用法:
    # 外部项目 (推荐): 通过 --project-dir 指定项目配置目录的绝对路径
    python committee.py --project-dir /path/to/project/committee --topic xxx

    # 本地项目: 自动发现引擎目录下的子目录
    python committee.py                         # 交互式: 选择项目 → 选择议题
    python committee.py <project>               # 指定项目 → 选择议题
    python committee.py <project> --topic xxx   # 一键直达
    python committee.py --list-projects         # 列出所有可用项目
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    from engine.cli import main
    import argparse

    committee_root = Path(__file__).resolve().parent

    parser = argparse.ArgumentParser(description="Committee — multi-model design review")
    parser.add_argument("project", type=str, nargs="?", default=None,
                        help="Project directory name under committee/ (e.g. 'odt')")
    parser.add_argument("--project-dir", type=str, default=None,
                        help="Absolute path to project config directory (bypasses local discovery)")
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

    # --project-dir: 直接使用外部项目目录, 跳过本地发现
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
        sys.exit(0)

    # 本地项目发现: 扫描引擎目录下的子目录
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
        sys.exit(0)

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
