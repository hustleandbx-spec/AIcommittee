"""
Committee Debate Engine — 项目无关的架构委员会引擎。

用法:
    from engine.graph import build_graph
    graph, meta = build_graph(config)
"""

from .graph import build_graph, CommitteeState

__all__ = ["build_graph", "CommitteeState"]
