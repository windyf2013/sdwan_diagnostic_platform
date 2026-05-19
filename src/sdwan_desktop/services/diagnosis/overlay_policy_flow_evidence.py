"""Raisecom 等 CPE 上 SD-WAN 业务分流：Overlay 与策略路由（fwmark / 多路由表）证据链归纳。

与 ``templates/whole_config_5200b.txt`` 及计划文档一致的分析要点：

- **可断言的转发面**：FIB 选路命中 ``vxlan*`` 三层面出接口 → ``bind tunnel*`` 的 ``type vxlan`` 封装；
  **不**从 running-config 断言 L2TP / IPsec / VXLAN UDP 的线序封装链（以实现 / 抓包 / 厂商文档为准）。
- **策略命中链（典型 urlaccelerate 场景）**：DNS / url-group → ipset 目的集 + security-ip 源集 →
  iptables mangle MARK → ``ip rule fwmark`` → 独立默认路由表（如 table 99/100）。
- **组网形态**：根据解析接口名与原始输出关键词枚举单 VXLAN、单 IPsec、VXLAN over IPsec、
  VXLAN over L2TP、组合等标签，供报告与人工核对。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


_VXLAN_IF = re.compile(r"vxlan", re.I)
_L2TP = re.compile(r"l2tp|l2tpc", re.I)
_IPSEC = re.compile(r"ipsec|vti|crypto\s+map", re.I)
_URL_GROUP = re.compile(r"url-group|urlaccelerate|plugin\s+install\s+urlaccelerate", re.I)
_IP_RULE = re.compile(r"ip\s+rule|fwmark", re.I)
_IPSET = re.compile(r"ipset", re.I)
_MANGLE = re.compile(r"mangle|MARK\s+set|fwmark", re.I)


@dataclass(slots=True)
class OverlayPolicyFlowEvidence:
    """Overlay / 策略分流分析结论（供报告模板与 JSON 序列化）。"""

    trace_id: str
    status: str
    scenario_tags: List[str]
    scenario_label: str
    checklist: List[str]
    forwarding_note: str
    probe_evidence_notes: List[str]
    error: Optional[str] = None

    def to_template_dict(self) -> Dict[str, Any]:
        """转为模板友好的扁平 dict。"""
        return {
            "trace_id": self.trace_id,
            "status": self.status,
            "scenario_tags": list(self.scenario_tags),
            "scenario_label": self.scenario_label,
            "checklist": list(self.checklist),
            "forwarding_note": self.forwarding_note,
            "probe_evidence_notes": list(self.probe_evidence_notes),
            "error": self.error,
        }


def _concat_raw(cfg: Any, targeted_probe: Optional[Dict[str, Any]]) -> str:
    chunks: List[str] = []
    if cfg is not None:
        ro = getattr(cfg, "raw_outputs", None) or {}
        if isinstance(ro, dict):
            for _k, v in ro.items():
                if isinstance(v, str) and v.strip():
                    chunks.append(v[:200_000])
    if isinstance(targeted_probe, dict):
        data = targeted_probe.get("data") if isinstance(targeted_probe.get("data"), dict) else {}
        raw = data.get("raw_outputs") if isinstance(data, dict) else None
        if isinstance(raw, dict):
            for _k, v in raw.items():
                if isinstance(v, str) and v.strip():
                    chunks.append(v[:80_000])
    return "\n".join(chunks)


def _iface_signals(cfg: Any) -> Dict[str, bool]:
    out = {"vxlan_iface": False, "l2tp_iface": False, "ipsec_hint": False}
    if cfg is None:
        return out
    for iface in getattr(cfg, "interfaces", None) or []:
        name = (getattr(iface, "name", None) or "").strip()
        if not name:
            continue
        if _VXLAN_IF.search(name):
            out["vxlan_iface"] = True
        if _L2TP.search(name):
            out["l2tp_iface"] = True
    return out


def _classify_scenario(tags: List[str]) -> str:
    if not tags:
        return "未识别到典型 Overlay 特征（可能为纯 underlay 或未解析到接口关键字）"
    if "vxlan" in tags and "l2tp" in tags and "ipsec" in tags:
        return "VXLAN + L2TP + IPsec 组合（VTEP 与隧道接口并存；**线序以实现为准**）"
    if "vxlan" in tags and "l2tp" in tags:
        return "VXLAN over L2TP（VTEP 常落在 l2tpc 地址空间）"
    if "vxlan" in tags and "ipsec" in tags:
        return "VXLAN over IPsec（或 IPsec 保护 VXLAN 承载；需与具体绑定接口核对）"
    if "vxlan" in tags:
        return "单 / 多 VXLAN 业务面（underlay 可为直连 WAN 等）"
    if "ipsec" in tags:
        return "以 IPsec 为主的隧道面（未同时识别 vxlan 逻辑口）"
    return "混合或未分类（请结合原始配置核对）"


def build_overlay_policy_flow_evidence(
    *,
    trace_id: str,
    cpe_configuration: Any,
    targeted_probe: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """根据已解析 CPE 配置与拓扑后探测输出，生成 Overlay / 策略分流证据链摘要。

    Args:
        trace_id: 追踪 ID。
        cpe_configuration: ``CpeConfiguration`` 或 ``None``。
        targeted_probe: ``{status, data, error}`` 拓扑后探测信封，可为 ``None``。

    Returns:
        ``{status, data, error}``：``data`` 为 ``OverlayPolicyFlowEvidence.to_template_dict()``。
    """
    try:
        blob = _concat_raw(cpe_configuration, targeted_probe)
        sig = _iface_signals(cpe_configuration)

        tags: List[str] = []
        if sig["vxlan_iface"]:
            tags.append("vxlan")
        if sig["l2tp_iface"]:
            tags.append("l2tp")
        if _L2TP.search(blob):
            tags.append("l2tp")
        if sig.get("ipsec_hint") or _IPSEC.search(blob):
            tags.append("ipsec")
        tags = list(dict.fromkeys(tags))

        probe_notes: List[str] = []
        if isinstance(targeted_probe, dict):
            data = targeted_probe.get("data") if isinstance(targeted_probe.get("data"), dict) else {}
            raw = data.get("raw_outputs") if isinstance(data, dict) else None
            if isinstance(raw, dict):
                for key in ("diagnose:ipset --list", "show link-protect status", "show url-group all domain all"):
                    if key in raw and isinstance(raw[key], str) and raw[key].strip():
                        probe_notes.append(f"拓扑后探测已采集: {key}")
        if _IPSET.search(blob) and not any("ipset" in n for n in probe_notes):
            probe_notes.append("原始采集中出现 ipset 相关输出（可对照 url-group 动态表项）")
        if _IP_RULE.search(blob):
            probe_notes.append("原始采集中出现 ip rule / fwmark 相关输出（策略选表依据）")
        if _MANGLE.search(blob):
            probe_notes.append("原始采集中出现 mangle / MARK 相关输出（命中 MARK 与业务集）")
        if _URL_GROUP.search(blob):
            probe_notes.append("配置或采集中出现 url-group / urlaccelerate（DNS 驱动业务集）")

        checklist = [
            "策略面：确认 ``ip rule`` 中 fwmark 与路由表（如 99/100）对应关系；**table 内 metric 小者优先** 主备默认路由。",
            "标记面：对照 ``iptables -t mangle`` PREROUTING 与 **ipset 源/目的** 规则顺序（多 url-group 时注意 **priority / 链内顺序**）。",
            "转发面（可配置断言）：命中策略时 ``ip route`` 的 **dev** 为 ``vxlan*`` → 经 **bind** 的 ``tunnel type vxlan`` 做封装。",
            "Underlay：**不**将 ``tunnel → l2tp → ipsec → ge1`` 等线序写死；若需证明封装顺序请 **WAN 抓包** 或查阅 **RCIOS** 说明。",
            "组网核对：根据 ``scenario_tags`` 区分单 VXLAN、单 IPsec、VXLAN over IPsec、VXLAN over L2TP、组合等形态。",
        ]

        forwarding = (
            "抽象出向：策略表选路 → **vxlan 三层口** → **tunnel(type vxlan) 绑定封装** → "
            "**underlay 组合（L2TP/IPsec/物理 WAN 等，线序以实现为准）**。"
        )

        label = _classify_scenario(tags)
        st = "ok" if cpe_configuration is not None or blob.strip() else "partial"
        ev = OverlayPolicyFlowEvidence(
            trace_id=trace_id,
            status=st,
            scenario_tags=tags,
            scenario_label=label,
            checklist=checklist,
            forwarding_note=forwarding,
            probe_evidence_notes=probe_notes
            or [
                "（无拓扑后 ipset / link-protect / url-group 采样的强提示；可检查主采集是否含 diagnose 输出）"
            ],
            error=None,
        )
        return {"status": "ok", "data": ev.to_template_dict(), "error": None}
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("overlay_policy_flow 归纳失败: %s", exc, exc_info=True)
        return {
            "status": "error",
            "data": OverlayPolicyFlowEvidence(
                trace_id=trace_id,
                status="error",
                scenario_tags=[],
                scenario_label="分析失败",
                checklist=[],
                forwarding_note="",
                probe_evidence_notes=[],
                error=str(exc),
            ).to_template_dict(),
            "error": str(exc),
        }


async def run_overlay_policy_flow_step(ctx: Any) -> Dict[str, Any]:
    """Flow 步骤：从 ``FlowContext`` 读取 ``cpe_result`` / ``targeted_probe`` 并写回 ``overlay_policy_flow``。"""
    trace_id = getattr(ctx, "trace_id", "") or ""
    cpe_result = ctx.get("cpe_result")
    cfg = None
    if cpe_result is not None and getattr(cpe_result, "success", False):
        data = getattr(cpe_result, "data", None)
        if isinstance(data, dict):
            cfg = data.get("cpe_configuration")
    tp = ctx.get("targeted_probe")
    envelope = build_overlay_policy_flow_evidence(
        trace_id=trace_id,
        cpe_configuration=cfg,
        targeted_probe=tp if isinstance(tp, dict) else None,
    )
    ctx.set("overlay_policy_flow", envelope)
    return envelope
