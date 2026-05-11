"""
Topology 模块公共 API

导出所有拓扑相关类和接口。
"""

from sdwan_desktop.services.topology.topology import (
    Edge,
    LinkType,
    NetworkTopology,
    Node,
    NodeType,
)
from sdwan_desktop.services.topology.topology_builder import TopologyBuilder

__all__ = [
    "Node",
    "NodeType",
    "Edge",
    "LinkType",
    "NetworkTopology",
    "TopologyBuilder",
]
