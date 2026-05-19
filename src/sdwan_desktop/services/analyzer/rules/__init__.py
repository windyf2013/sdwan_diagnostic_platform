"""
诊断规则模块 - 所有一键体检规则实现

规则分类：
- gateway.py: 网关连通性规则 (GW-001 ~ GW-003)
- dns.py: DNS解析规则 (DNS-001 ~ DNS-002, SPLIT-001)
- system.py: 系统配置规则 (ADAPTER-001 ~ ADAPTER-002, IP-001 ~ IP-002,
  ROUTE-001 ~ ROUTE-002, PROXY-001 ~ PROXY-002, FW-001, IPV6-001)
- connectivity.py: 互联网连通性规则 (INET-001 ~ INET-003)

产品特性与网络行为分析（厂商分流、Overlay、PBR 口径等）见文档库，**不在本包内以 Rule 对象实现**：
- 总索引：``docs/rules/INDEX.md``
- 产品特性库：``docs/rules/product_features/INDEX.md``（如 Raisecom 5200B：``raisecom_msg5200b_network_analysis.md``）
"""

from sdwan_desktop.services.analyzer.rules.gateway import GATEWAY_RULES
from sdwan_desktop.services.analyzer.rules.dns import DNS_RULES
from sdwan_desktop.services.analyzer.rules.system import SYSTEM_RULES
from sdwan_desktop.services.analyzer.rules.connectivity import CONNECTIVITY_RULES

# 所有规则汇总
ALL_RULES = GATEWAY_RULES + DNS_RULES + SYSTEM_RULES + CONNECTIVITY_RULES

__all__ = [
    "ALL_RULES",
    "GATEWAY_RULES",
    "DNS_RULES",
    "SYSTEM_RULES",
    "CONNECTIVITY_RULES",
]
