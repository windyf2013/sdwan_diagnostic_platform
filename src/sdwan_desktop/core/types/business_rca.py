"""业务根因分析（RCA）跨层证据契约。

用于 ``ObservationContext`` + ``ProbeBundle`` 输入，经 ``BusinessRCAEngine`` 融合输出 ``RootCause``。
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class PCObservationSummary:
    """从 PC 快照抽取的观测摘要（供假设与融合使用）。"""

    trace_id: str
    hostname: str = ""
    primary_ip: Optional[str] = None
    default_gateway: Optional[str] = None
    dns_servers: List[str] = field(default_factory=list)
    proxy_enabled: bool = False
    connected_adapters: int = 0

    @staticmethod
    def from_snapshot_like(snapshot_obj: Any, trace_id: str) -> Optional[PCObservationSummary]:
        """从 ``SystemInfoSnapshot`` 或可 ``to_dict`` 的快照构建摘要；无效输入返回 ``None``。"""
        if snapshot_obj is None:
            return None
        if isinstance(snapshot_obj, dict):
            if not snapshot_obj:
                return None
            d = snapshot_obj
        elif hasattr(snapshot_obj, "to_dict"):
            d = snapshot_obj.to_dict()
        else:
            return None

        hostname = str(d.get("hostname") or "")
        primary_ip = d.get("primary_ip")
        if primary_ip is not None:
            primary_ip = str(primary_ip) if primary_ip else None

        dg: Optional[str] = None
        dr = d.get("default_route")
        if isinstance(dr, dict):
            dg = dr.get("gateway")
        if not dg:
            dg = d.get("default_gateway")
        if dg is not None:
            dg = str(dg) if dg else None

        dns_flat: List[str] = []
        dc = d.get("dns_config")
        if isinstance(dc, dict):
            for s in dc.get("servers") or []:
                if s and str(s) not in dns_flat:
                    dns_flat.append(str(s))
        for ad in d.get("adapters") or []:
            if not isinstance(ad, dict):
                continue
            for s in ad.get("dns_servers") or []:
                if s and str(s) not in dns_flat:
                    dns_flat.append(str(s))

        proxy = d.get("proxy_config")
        proxy_on = bool(isinstance(proxy, dict) and proxy.get("enabled"))

        connected = 0
        for ad in d.get("adapters") or []:
            if isinstance(ad, dict) and ad.get("is_connected"):
                connected += 1

        return PCObservationSummary(
            trace_id=trace_id,
            hostname=hostname,
            primary_ip=primary_ip,
            default_gateway=dg,
            dns_servers=dns_flat,
            proxy_enabled=proxy_on,
            connected_adapters=connected,
        )


@dataclass(slots=True)
class ObservationContext:
    """一次诊断可获得的观测边界（PC / CPE 是否参与）。"""

    trace_id: str
    pc: Optional[PCObservationSummary] = None
    cpe_evidence_available: bool = False
    cpe_node_id: Optional[str] = None


@dataclass(slots=True)
class ProbeBundle:
    """探针与原始输出集合（与 ``RootCauseEngine`` / 独立 CLI 共用）。"""

    trace_id: str
    business_probes: List[Dict[str, Any]] = field(default_factory=list)
    raw_outputs: Dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class Hypothesis:
    """路径假设（用于报告「假设树」与人工复核）。"""

    hypothesis_id: str
    statement: str
    evidence_refs: List[str] = field(default_factory=list)


@dataclass(slots=True)
class BusinessRCAFinding:
    """融合后的单条结论，可落为 ``RootCause``。"""

    cause: "RootCause"
    disconfirmers: List[str] = field(default_factory=list)
    needs_cpe_evidence: bool = False

    def as_root_cause(self) -> "RootCause":
        """附加已排除假设与 CPE 证据提示到描述末尾。"""
        from sdwan_desktop.core.types.diagnosis import RootCause

        if not isinstance(self.cause, RootCause):
            return self.cause  # type: ignore[return-value]
        parts: List[str] = []
        if self.disconfirmers:
            parts.append("已排查（弱否定）: " + "; ".join(self.disconfirmers[:5]))
        if self.needs_cpe_evidence:
            parts.append("提示: 未纳入 CPE 配置/隧道/策略证据时，结论仅覆盖本机出站段。")
        extra = (" " + " ".join(parts)) if parts else ""
        if not extra.strip():
            return self.cause
        return replace(
            self.cause,
            description=(self.cause.description or "").rstrip() + extra,
        )
