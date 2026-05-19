"""
HTML 报告生成器

根据诊断结果生成 HTML 格式的一键体检报告。
符合 SDWAN_SPEC §4.3 报告结构要求。
"""

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, FileSystemBytecodeCache, select_autoescape

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.core.types.probe import ProbeProtocol, ProbeTarget
from sdwan_desktop.services.analyzer.rules.system import find_ip_conflicts_from_arp
from sdwan_desktop.services.orchestrator.diagnostic_flow import DiagnosticResult
from sdwan_desktop.core.types.diagnosis import DiagnosisResult, RootCause, Severity
from sdwan_desktop.services.reporter.report_delivery_context import (
    build_business_diagnose_pack,
    build_deep_dive_pack,
    build_quick_check_pack,
    biz_targets_from_business_probes,
)

logger = logging.getLogger(__name__)


class HtmlReportBuilder:
    """HTML 报告生成器"""

    def __init__(self, template_dir: Optional[Path] = None):
        """初始化 HTML 报告生成器

        Args:
            template_dir: 模板目录路径，默认为 reporting/templates
        """
        if template_dir is None:
            # 默认模板目录
            # 支持 PyInstaller 打包环境
            if getattr(sys, "frozen", False):
                # PyInstaller 打包后的环境
                # 模板文件在 _MEIPASS/sdwan_desktop/reporting/templates
                base_path = Path(sys._MEIPASS)
                template_dir = base_path / "sdwan_desktop" / "reporting" / "templates"
            else:
                # 开发环境
                template_dir = Path(__file__).parent.parent.parent / "reporting" / "templates"

        self.template_dir = Path(template_dir)
        
        # 验证模板目录是否存在
        if not self.template_dir.exists():
            logger.warning(f"模板目录不存在: {self.template_dir}")
            logger.warning(f"当前工作目录: {Path.cwd()}")
            logger.warning(f"sys.frozen: {getattr(sys, 'frozen', False)}")
            if getattr(sys, 'frozen', False):
                logger.warning(f"sys._MEIPASS: {getattr(sys, '_MEIPASS', 'N/A')}")
        
        # 性能优化：启用字节码缓存以加速模板编译
        cache_dir = Path.home() / ".sdwan_cache" / "jinja"
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True,
            bytecode_cache=FileSystemBytecodeCache(str(cache_dir))
        )

    def build_quick_check_report(
        self,
        result: DiagnosisResult,
        output_path: Optional[Path] = None
    ) -> str:
        """构建一键体检 HTML 报告

        Args:
            result: 诊断结果
            output_path: 输出文件路径（可选，如提供则写入文件）

        Returns:
            HTML 内容字符串
        """
        try:
            template = self.env.get_template("quick_check.html")

            gen_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            report_pack = build_quick_check_pack(
                result=result, generated_at_iso=gen_iso
            ).as_template_dict()
            connectivity = self._extract_connectivity(result)
            context = {
                "report_id": result.id,
                "trace_id": result.trace_id,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "diagnosis_type": result.diagnosis_type,
                "rule_version": result.rule_version,
                "severity": result.severity,
                "summary": result.summary,
                "confidence": int(result.overall_confidence * 100),
                "root_causes": result.root_causes,
                "executive_summary": self._build_executive_summary(result, connectivity),
                "evidence_sections": self._format_evidences_for_display(result.evidences or []),
                "system_info": self._extract_system_info(result),
                "connectivity": connectivity,
                "report_pack": report_pack,
            }

            html_content = template.render(**context)
            
            # 资源内联优化（预留接口）
            html_content = self._inline_static_resources(html_content)

            # 如果提供了输出路径，写入文件
            if output_path:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                # 性能优化：对于大文件使用流式写入缓冲
                with open(output_path, 'w', encoding='utf-8', buffering=8192) as f:
                    f.write(html_content)
                logger.info(f"HTML 报告已保存至: {output_path}")

            return html_content

        except Exception as e:
            logger.error(f"HTML 报告生成失败: {e}", exc_info=True)
            raise

    def build_deep_dive_report(
        self,
        result: DiagnosisResult,
        topology_data: dict,
        output_path: Optional[Path] = None
    ) -> str:
        """构建深度诊断 HTML 报告

        Args:
            result: 诊断结果
            topology_data: 网络拓扑数据（用于渲染拓扑图）
            output_path: 输出文件路径（可选，如提供则写入文件）

        Returns:
            HTML 内容字符串
        """
        try:
            # 联合业务等场景写入 topology.report_html_h1 时使用独立模板，便于验收期与 deep_dive.html 并存。
            template_name = (
                "deep_dive_joint_ux.html"
                if isinstance(topology_data, dict) and topology_data.get("report_html_h1")
                else "deep_dive.html"
            )
            template = self.env.get_template(template_name)
            logger.debug("深度诊断 HTML 使用模板: %s", template_name)

            if not isinstance(topology_data, dict):
                topology_data = {}

            gen_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            existing_pack = topology_data.get("report_pack")
            if isinstance(existing_pack, dict) and existing_pack:
                report_pack = existing_pack
            else:
                has_bp = False
                if isinstance(topology_data, dict):
                    tp = topology_data.get("targeted_probe")
                    if isinstance(tp, dict):
                        data = tp.get("data")
                        if isinstance(data, dict) and data.get("business_probes"):
                            has_bp = True
                report_pack = build_deep_dive_pack(
                    result=result,
                    has_business_probe=has_bp,
                    generated_at_iso=gen_iso,
                ).as_template_dict()

            business_probes: List[Dict[str, Any]] = []
            probe_status = "unknown"
            tp_env = topology_data.get("targeted_probe")
            if isinstance(tp_env, dict):
                probe_status = str(tp_env.get("status") or "unknown")
                tp_data = tp_env.get("data")
                if isinstance(tp_data, dict):
                    bp = tp_data.get("business_probes")
                    if isinstance(bp, list):
                        business_probes = [r for r in bp if isinstance(r, dict)]

            # 准备模板数据
            context = {
                "report_id": result.id,
                "trace_id": result.trace_id,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "diagnosis_type": result.diagnosis_type,
                "rule_version": result.rule_version,
                "severity": result.severity,
                "summary": result.summary,
                "confidence": int(result.overall_confidence * 100),
                "root_causes": result.root_causes,
                "recommendations": result.recommendations,
                "evidences": result.evidences,
                "topology": topology_data,
                "report_pack": report_pack,
                "business_probes": business_probes,
                "probe_status": probe_status,
            }

            html_content = template.render(**context)
            
            # 资源内联优化（预留接口）
            html_content = self._inline_static_resources(html_content)

            # 如果提供了输出路径，写入文件
            if output_path:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                # 性能优化：对于大文件使用流式写入缓冲
                with open(output_path, 'w', encoding='utf-8', buffering=8192) as f:
                    f.write(html_content)
                logger.info(f"深度诊断 HTML 报告已保存至: {output_path}")

            return html_content

        except Exception as e:
            logger.error(f"深度诊断 HTML 报告生成失败: {e}", exc_info=True)
            raise

    def build_business_diagnosis_report(
        self,
        result: DiagnosisResult,
        business_probes: List[Dict[str, Any]],
        output_path: Optional[Path] = None,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """构建本机业务不通诊断 HTML 报告（独立 CLI 使用）。

        Args:
            result: 诊断结果（含根因列表）。
            business_probes: ``orchestrate_business_domain_port_diagnosis`` 返回的探测行（含可选 ``trace``）。
            output_path: 输出文件路径（可选）。
            extra_context: 附加模板变量（如 ``aggregate_error``、``pc_snapshot``）。

        Returns:
            HTML 内容字符串。
        """
        try:
            template = self.env.get_template("business_diagnosis.html")
            gen_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            joint = False
            if extra_context and isinstance(extra_context.get("joint_mode"), bool):
                joint = extra_context["joint_mode"]
            targets = biz_targets_from_business_probes(business_probes or [])
            report_pack = build_business_diagnose_pack(
                result=result,
                joint_mode=joint,
                biz_targets=targets,
                generated_at_iso=gen_iso,
            ).as_template_dict()
            ctx: dict = {
                "report_id": result.id,
                "trace_id": result.trace_id,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "diagnosis_type": result.diagnosis_type,
                "rule_version": result.rule_version,
                "severity": result.severity,
                "summary": result.summary,
                "confidence": int(result.overall_confidence * 100),
                "root_causes": result.root_causes,
                "recommendations": result.recommendations,
                "evidences": result.evidences,
                "business_probes": business_probes or [],
                "report_pack": report_pack,
            }
            if extra_context:
                ctx.update(extra_context)

            html_content = template.render(**ctx)
            html_content = self._inline_static_resources(html_content)

            if output_path:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "w", encoding="utf-8", buffering=8192) as f:
                    f.write(html_content)
                logger.info("业务诊断 HTML 报告已保存至: %s", output_path)

            return html_content

        except Exception as e:
            logger.error("业务诊断 HTML 报告生成失败: %s", e, exc_info=True)
            raise

    def _get_severity_text(self, severity: Severity) -> str:
        """获取严重程度的文本表示

        Args:
            severity: 严重程度枚举

        Returns:
            文本字符串
        """
        severity_map = {
            Severity.CRITICAL: "严重",
            Severity.ERROR: "错误",
            Severity.WARNING: "警告",
            Severity.INFO: "信息",
        }
        return severity_map.get(severity, "未知")

    def _get_severity_color(self, severity: Severity) -> str:
        """获取严重程度对应的颜色类

        Args:
            severity: 严重程度枚举

        Returns:
            CSS 颜色类名
        """
        color_map = {
            Severity.CRITICAL: "critical",
            Severity.ERROR: "error",
            Severity.WARNING: "warning",
            Severity.INFO: "info",
        }
        return color_map.get(severity, "info")

    def _extract_connectivity(self, result: DiagnosisResult) -> dict:
        """从诊断结果中提取连通性信息

        Args:
            result: 诊断结果

        Returns:
            连通性信息字典
        """
        connectivity = {
            "gateway_status": "unknown",
            "gateway_ip": "N/A",
            "domestic_success_rate": 0,
            "international_success_rate": 0,
            "gateway_rtt": 0.0,
            "gateway_loss_rate": 0.0,
            "dns_results": [],
            "internet_targets": [],
            "cpe_link_routing": None,
        }

        dns_by_server: Dict[str, dict] = {}

        # 1. 尝试从证据中获取原始探测数据 (最详细的数据源)
        for evidence in result.evidences:
            if hasattr(evidence, 'probe_results') and evidence.probe_results:
                for probe in evidence.probe_results:
                    target_host = self._probe_target_host(probe)
                    
                    # 网关信息
                    if probe.target.protocol == ProbeProtocol.ICMP:
                        # 简单匹配：如果丢包率 < 1.0 且 RTT > 0，或者 success 为 True，则认为是网关探测
                        if probe.success or (probe.metrics and probe.metrics.loss_rate < 1.0):
                            connectivity["gateway_status"] = "ok" if probe.success else "packet_loss"
                            connectivity["gateway_ip"] = target_host
                            connectivity["gateway_rtt"] = probe.metrics.rtt_avg or 0.0
                            connectivity["gateway_loss_rate"] = probe.metrics.loss_rate or 0.0
                    
                    # DNS 信息（按服务器去重，避免报告阶段重复写入）
                    elif probe.target.protocol == ProbeProtocol.DNS:
                        if target_host.startswith("ProbeTarget("):
                            continue
                        resolved_ips = []
                        if probe.metrics and hasattr(probe.metrics, 'resolved_ips'):
                            resolved_ips = probe.metrics.resolved_ips or []
                        row = {
                            "server": target_host,
                            "success": probe.success,
                            "rtt": probe.metrics.rtt_avg or 0.0,
                            "resolved_ips": ", ".join(resolved_ips) if resolved_ips else "无解析记录",
                        }
                        prev = dns_by_server.get(target_host)
                        if prev is None or (row["success"] and not prev["success"]):
                            dns_by_server[target_host] = row
                    
                    # 互联网目标
                    elif probe.target.protocol in [ProbeProtocol.HTTP, ProbeProtocol.HTTPS, ProbeProtocol.TCP]:
                        category = "domestic" if any(d in target_host for d in ["baidu", "qq", "aliyun"]) else "international"
                        rtt_val = 0.0
                        if probe.metrics:
                            rtt_val = probe.metrics.rtt_avg or 0.0
                        
                        connectivity["internet_targets"].append({
                            "host": target_host,
                            "category": category,
                            "success": probe.success,
                            "rtt": rtt_val
                        })

            if hasattr(evidence, 'config_snapshots') and evidence.config_snapshots:
                logger.debug(
                    f"证据链 config_snapshots keys: {list(evidence.config_snapshots.keys())}",
                    extra={"trace_id": result.trace_id}
                )

                # 2. 提取 CPE 链路分流检测结果
                cpe_routing_result = evidence.config_snapshots.get("cpe_link_routing_result")
                
                # ✅ 调试日志：记录是否找到 CPE 链路分流数据
                if cpe_routing_result:
                    logger.info(
                        f"✅ 找到 CPE 链路分流结果: {type(cpe_routing_result).__name__}",
                        extra={"trace_id": result.trace_id}
                    )
                    
                    # 将 CpeLinkRoutingTestResult 对象转换为字典格式供模板使用
                    connectivity["cpe_link_routing"] = {
                        "domain_results": [],
                        "detected_links": getattr(cpe_routing_result, 'detected_links', []),
                        "link_distribution": getattr(cpe_routing_result, 'link_distribution', {}),
                        "is_multi_link": getattr(cpe_routing_result, 'is_multi_link', False),
                        "multi_link_count": getattr(cpe_routing_result, 'multi_link_count', 0),
                        "total_domains_tested": getattr(cpe_routing_result, 'total_domains_tested', 0),
                        "errors": getattr(cpe_routing_result, 'errors', []),
                    }
                    
                    # 转换每个域名的路径分析结果
                    domain_results = getattr(cpe_routing_result, 'domain_results', [])
                    logger.info(f"   - 域名结果数: {len(domain_results)}", extra={"trace_id": result.trace_id})
                    
                    for dr in domain_results:
                        if isinstance(dr, dict):
                            connectivity["cpe_link_routing"]["domain_results"].append(dr)
                        else:
                            # 转换 TracerouteHopInfo 列表
                            full_path = []
                            for hop in getattr(dr, 'full_path', []):
                                if isinstance(hop, dict):
                                    full_path.append(hop)
                                else:
                                    full_path.append({
                                        "hop_number": getattr(hop, 'hop_number', 0),
                                        "ip_addresses": getattr(hop, 'ip_addresses', []),
                                        "hostnames": getattr(hop, 'hostnames', []),  # ✅ 添加 hostnames 字段
                                        "rtts": getattr(hop, 'rtts', []),
                                        "is_timeout": getattr(hop, 'is_timeout', False),
                                    })
                            
                            post_cpe_hops = []
                            for hop in getattr(dr, 'post_cpe_hops', []):
                                if isinstance(hop, dict):
                                    post_cpe_hops.append(hop)
                                else:
                                    post_cpe_hops.append({
                                        "hop_number": getattr(hop, 'hop_number', 0),
                                        "ip_addresses": getattr(hop, 'ip_addresses', []),
                                        "hostnames": getattr(hop, 'hostnames', []),  # ✅ 添加 hostnames 字段
                                        "rtts": getattr(hop, 'rtts', []),
                                        "is_timeout": getattr(hop, 'is_timeout', False),
                                    })
                            
                            connectivity["cpe_link_routing"]["domain_results"].append({
                                "domain": getattr(dr, 'domain', "N/A"),
                                "resolved_ip": getattr(dr, 'resolved_ip', "N/A"),
                                "full_path": full_path,
                                "cpe_exit_hop": getattr(dr, 'cpe_exit_hop', 2),
                                "post_cpe_hops": post_cpe_hops,
                                "path_fingerprint": getattr(dr, 'path_fingerprint', ""),
                                "link_category": getattr(dr, 'link_category', "unknown"),
                                "confidence": getattr(dr, 'confidence', 0.0),
                            })
                else:
                    # ✅ 关键调试：记录为什么没有 CPE 数据
                    logger.warning(
                        f"⚠️ 证据链中未找到 cpe_link_routing_result",
                        extra={"trace_id": result.trace_id}
                    )
                    logger.debug(
                        f"   config_snapshots keys: {list(evidence.config_snapshots.keys())}",
                        extra={"trace_id": result.trace_id}
                    )

        connectivity["dns_results"] = list(dns_by_server.values())

        # 3. 计算成功率
        domestic_targets = [t for t in connectivity["internet_targets"] if t["category"] == "domestic"]
        international_targets = [t for t in connectivity["internet_targets"] if t["category"] == "international"]
        
        if domestic_targets:
            success_count = sum(1 for t in domestic_targets if t["success"])
            connectivity["domestic_success_rate"] = int((success_count / len(domestic_targets)) * 100)
        
        if international_targets:
            success_count = sum(1 for t in international_targets if t["success"])
            connectivity["international_success_rate"] = int((success_count / len(international_targets)) * 100)

        return connectivity

    def _filter_key_routes(self, routes: list, dns_servers: list = None) -> list:
        """筛选关键路由表项

        基于SD-WAN诊断场景的业务优先级排序：
        1. **所有**默认路由 (0.0.0.0/0) — 必须全量展示，多默认路由是常见根因
        2. CPE网关路由 - 指向SD-WAN设备的关键路径
        3. DNS服务器路由 - 确保DNS解析可达性
        4. 低Metric静态路由 - 策略路由和业务分流规则

        Args:
            routes: 原始路由列表
            dns_servers: DNS服务器IP列表（用于识别DNS路由）

        Returns:
            按优先级排序的关键路由列表（字典格式，包含 interface/protocol）
        """
        if not routes:
            return []

        default_routes = []
        gateway_routes = []
        dns_routes = []
        static_routes = []

        for route in routes:
            dest = getattr(route, 'destination', '')
            mask = getattr(route, 'netmask', '')
            gw = getattr(route, 'gateway', '')
            metric = getattr(route, 'metric', 999)
            protocol = getattr(route, 'protocol', '')

            if dest == "0.0.0.0" and mask == "0.0.0.0":
                default_routes.append(route)
                continue

            if gw and (gw.startswith("192.168.") or gw.startswith("10.")):
                gateway_routes.append(route)
                continue

            if dns_servers and any(dns_ip in dest for dns_ip in dns_servers):
                dns_routes.append(route)
                continue

            if metric < 100 and protocol in ["static", "local", "bgp", "ospf"]:
                static_routes.append(route)
                continue

        # 全量保留默认路由（按 metric 升序便于辨认主备）；其他类别仍做截断
        default_routes_sorted = sorted(
            default_routes,
            key=lambda r: (getattr(r, "metric", 0) if getattr(r, "metric", None) is not None else 999),
        )
        key_routes = []
        key_routes.extend(default_routes_sorted)
        key_routes.extend(gateway_routes[:2])
        key_routes.extend(dns_routes[:2])
        key_routes.extend(static_routes[:2])

        # 上限放宽以容纳多默认路由场景；若仅 1 条默认路由则总体仍很精简
        max_rows = max(6, len(default_routes_sorted) + 4)
        return [
            {
                "dest": r.destination,
                "mask": r.netmask,
                "gw": r.gateway,
                "metric": r.metric,
                "interface": getattr(r, "interface", "") or "",
                "protocol": getattr(r, "protocol", "") or "",
            }
            for r in key_routes[:max_rows]
        ]

    def _extract_system_info(self, result: DiagnosisResult) -> dict:
        """从诊断结果中提取系统信息

        Args:
            result: 诊断结果

        Returns:
            系统信息字典
        """
        system_info = {
            "adapters": [],
            "ip_config": {},
            "routes": [],
            "firewall": "未知",
            "proxy": "未启用",
            "ip_conflicts": [],
        }

        for evidence in (result.evidences or []):
            if not hasattr(evidence, 'config_snapshots'):
                continue
            if "system_snapshot" in evidence.config_snapshots:
                snapshot = evidence.config_snapshots["system_snapshot"]
                
                # 网卡信息
                if hasattr(snapshot, 'adapters'):
                    system_info["adapters"] = [
                        {
                            "name": adapter.description or adapter.name,
                            "ips": adapter.ip_addresses if adapter.ip_addresses else ["N/A"],  # 保留所有IP
                            "ip_display": ", ".join(adapter.ip_addresses) if adapter.ip_addresses else "N/A",  # 用于显示的字符串
                            "mac": adapter.mac_address or "N/A",
                            "status": "已连接" if adapter.is_connected else "未连接",
                            "gateway": adapter.default_gateway or "N/A",
                            "speed": f"{adapter.speed_mbps} Mbps" if adapter.speed_mbps else "N/A",
                            "dhcp": "DHCP" if adapter.dhcp_enabled else "静态",
                        }
                        for adapter in snapshot.adapters
                    ]
                
                # 默认路由清单（用于关键路由表项 / 默认网关多值场景）
                default_routes_dicts: List[dict] = []
                if hasattr(snapshot, 'routes') and snapshot.routes:
                    for r in snapshot.routes:
                        if getattr(r, "destination", "") == "0.0.0.0" and getattr(r, "netmask", "") == "0.0.0.0":
                            default_routes_dicts.append({
                                "dest": r.destination,
                                "mask": r.netmask,
                                "gw": r.gateway or "on-link",
                                "metric": r.metric if r.metric is not None else "?",
                                "interface": getattr(r, "interface", "") or "",
                                "protocol": getattr(r, "protocol", "") or "",
                            })
                    default_routes_dicts.sort(
                        key=lambda d: (d["metric"] if isinstance(d["metric"], int) else 999)
                    )

                # IP 配置
                if hasattr(snapshot, 'ip_config') and snapshot.ip_config:
                    primary_gw = snapshot.ip_config.default_gateway or "N/A"
                    # default_gateways：去重保序，包含主默认网关 + 所有默认路由网关
                    seen = set()
                    gw_list: List[str] = []
                    def _add_gw(g: Optional[str]) -> None:
                        if g and g != "N/A" and g not in seen:
                            seen.add(g)
                            gw_list.append(g)
                    _add_gw(snapshot.ip_config.default_gateway)
                    for d in default_routes_dicts:
                        _add_gw(d.get("gw"))
                    system_info["ip_config"] = {
                        "gateway": primary_gw,
                        "default_gateways": gw_list,
                        "dns_servers": ", ".join(snapshot.ip_config.dns_servers) if snapshot.ip_config.dns_servers else "N/A",
                    }

                # 路由信息 (智能筛选关键路由 + 全量默认路由)
                if hasattr(snapshot, 'routes'):
                    dns_servers = []
                    if hasattr(snapshot, 'ip_config') and snapshot.ip_config:
                        dns_servers = snapshot.ip_config.dns_servers or []

                    system_info["routes"] = self._filter_key_routes(
                        snapshot.routes,
                        dns_servers
                    )
                    # 单独透出「默认路由清单」便于模板高亮多默认路由
                    system_info["default_routes"] = default_routes_dicts
                    system_info["default_route_count"] = len(default_routes_dicts)
                    system_info["routes_total"] = len(snapshot.routes or [])

                # 防火墙与代理状态
                if hasattr(snapshot, 'firewall_status') and snapshot.firewall_status:
                    fw = snapshot.firewall_status
                    # FirewallInfo 是 dataclass，直接访问属性
                    system_info["firewall"] = "开启" if getattr(fw, 'enabled', False) else "关闭"
                
                if hasattr(snapshot, 'proxy_config') and snapshot.proxy_config:
                    px = snapshot.proxy_config
                    # ProxyInfo 也是 dataclass
                    system_info["proxy"] = "启用" if getattr(px, 'enabled', False) else "未启用"

                if hasattr(snapshot, "arp_table") and snapshot.arp_table:
                    system_info["ip_conflicts"] = find_ip_conflicts_from_arp(snapshot.arp_table)
                
                break

        return system_info

    def _build_executive_summary(self, result: DiagnosisResult, connectivity: dict) -> dict:
        """构建执行摘要：健康结论 + 连通性一览 + 优先处置项。"""
        causes = result.root_causes or []
        sev_counts = {"critical": 0, "error": 0, "warning": 0, "info": 0}
        for c in causes:
            s = c.severity.value if hasattr(c.severity, "value") else str(c.severity)
            sev_counts[s] = sev_counts.get(s, 0) + 1

        deductions = (
            sev_counts["critical"] * 30
            + sev_counts["error"] * 20
            + sev_counts["warning"] * 10
            + sev_counts["info"] * 5
        )
        health_score = max(0, 100 - deductions)

        gw_ok = connectivity.get("gateway_status") == "ok"
        dns_list = connectivity.get("dns_results") or []
        dns_ok = sum(1 for d in dns_list if d.get("success"))
        dns_total = len(dns_list)
        dom_rate = connectivity.get("domestic_success_rate", 0)
        intl_rate = connectivity.get("international_success_rate", 0)
        internet_targets = connectivity.get("internet_targets") or []
        failed_probes = [
            {
                "host": t.get("host", "?"),
                "category": "国内" if t.get("category") == "domestic" else "国际",
            }
            for t in internet_targets
            if not t.get("success")
        ]
        probe_total = len(internet_targets)
        probe_ok = probe_total - len(failed_probes)

        priority_actions: List[str] = []
        for c in sorted(
            causes,
            key=lambda x: (
                0 if (x.severity.value if hasattr(x.severity, "value") else "") == "critical" else
                1 if (x.severity.value if hasattr(x.severity, "value") else "") == "error" else 2
            ),
        ):
            if c.remediation and c.remediation not in priority_actions:
                priority_actions.append(f"[{c.cause_id}] {c.remediation}")
            if len(priority_actions) >= 3:
                break

        verdict = "正常"
        if sev_counts["critical"] or sev_counts["error"]:
            verdict = "需处理"
        elif sev_counts["warning"] or failed_probes:
            verdict = "需关注"

        return {
            "health_score": health_score,
            "verdict": verdict,
            "issue_count": len(causes),
            "severity_breakdown": sev_counts,
            "gateway_ok": gw_ok,
            "gateway_ip": connectivity.get("gateway_ip", "N/A"),
            "dns_ok": dns_ok,
            "dns_total": dns_total,
            "domestic_success_rate": dom_rate,
            "international_success_rate": intl_rate,
            "probe_ok": probe_ok,
            "probe_total": probe_total,
            "failed_probes": failed_probes,
            "priority_actions": priority_actions,
        }

    def _format_evidences_for_display(self, evidences: list) -> List[dict]:
        """将证据链转为模板友好的结构化块（表格为主）。"""
        sections: List[dict] = []
        for ev in evidences:
            step_name = getattr(ev, "step_name", "unknown")
            evidence_type = self._guess_evidence_type(step_name)
            block: dict = {
                "step_name": step_name,
                "description": getattr(ev, "description", ""),
                "evidence_type": evidence_type,
                "probe_results": getattr(ev, "probe_results", None) or [],
                "snapshot_tables": [],
            }
            snapshots = getattr(ev, "config_snapshots", None) or {}
            for key, value in snapshots.items():
                if key == "system_snapshot" and value is not None:
                    block["snapshot_tables"].append(
                        self._snapshot_table_system(value, title="系统配置快照")
                    )
                    # 默认路由证据表（多默认路由的关键证据）
                    routes_table = self._snapshot_table_default_routes(value)
                    if routes_table["rows"]:
                        block["snapshot_tables"].append(routes_table)
                elif key == "cpe_link_routing_result" and value is not None:
                    block["snapshot_tables"].extend(
                        self._snapshot_tables_cpe_routing(value)
                    )
            sections.append(block)
        return sections

    @staticmethod
    def _guess_evidence_type(step_name: str) -> str:
        """根据 ``step_name`` 给出更具体的证据类型标签，避免一律显示「通用」。"""
        if not step_name:
            return "通用"
        n = str(step_name).lower()
        if "connectivity" in n:
            return "连通性探测"
        if "gateway" in n:
            return "网关探测"
        if "dns" in n:
            return "DNS 探测"
        if "internet" in n:
            return "互联网可达性"
        if "cpe" in n or "routing" in n or "traceroute" in n:
            return "链路追踪"
        if "system" in n or "collect" in n:
            return "系统快照"
        return "通用"

    def _snapshot_table_system(self, snapshot: Any, *, title: str) -> dict:
        rows: List[dict] = []
        if hasattr(snapshot, "ip_config") and snapshot.ip_config:
            ic = snapshot.ip_config
            rows.append({"项": "默认网关", "值": ic.default_gateway or "N/A"})
            dns = ", ".join(ic.dns_servers) if ic.dns_servers else "N/A"
            rows.append({"项": "DNS 服务器", "值": dns})
        if hasattr(snapshot, "primary_adapter") and snapshot.primary_adapter:
            pa = snapshot.primary_adapter
            rows.append({
                "项": "主网卡",
                "值": f"{pa.description or pa.name} | 连接={pa.is_connected} | 网关={pa.default_gateway or 'N/A'}",
            })
        if hasattr(snapshot, "routes"):
            routes = snapshot.routes or []
            default_count = sum(
                1 for r in routes
                if getattr(r, "destination", "") == "0.0.0.0" and getattr(r, "netmask", "") == "0.0.0.0"
            )
            rows.append({"项": "路由表项数（总/默认）", "值": f"{len(routes)} / {default_count}"})
        if hasattr(snapshot, "arp_table"):
            rows.append({"项": "ARP 表项数", "值": str(len(snapshot.arp_table or []))})
        return {"title": title, "rows": rows}

    def _snapshot_table_default_routes(self, snapshot: Any) -> dict:
        """证据附录中的「默认路由清单」表（每条路由一行，2 列结构）。

        若存在多条默认路由，此表是 ROUTE-001/002 根因结论最直接的原始证据。
        采用「序号 → 路由文本」的 2 列结构，与证据附录的其它快照表保持一致渲染。
        """
        rows: List[dict] = []
        routes = getattr(snapshot, "routes", None) or []
        defaults = [
            r for r in routes
            if getattr(r, "destination", "") == "0.0.0.0" and getattr(r, "netmask", "") == "0.0.0.0"
        ]
        defaults.sort(
            key=lambda r: (getattr(r, "metric", 0) if getattr(r, "metric", None) is not None else 999)
        )
        for idx, r in enumerate(defaults, 1):
            gw = getattr(r, "gateway", "") or "on-link"
            iface = getattr(r, "interface", "") or "N/A"
            metric = getattr(r, "metric", None)
            metric_repr = "?" if metric is None else str(metric)
            protocol = getattr(r, "protocol", "") or ""
            proto_repr = f" [{protocol}]" if protocol else ""
            rows.append({
                "项": f"默认路由 #{idx}",
                "值": f"0.0.0.0/0 via {gw} dev \"{iface}\" metric {metric_repr}{proto_repr}",
            })
        if rows:
            rows.insert(0, {"项": "默认路由总数", "值": str(len(defaults))})
        return {"title": "默认路由清单", "rows": rows}

    def _snapshot_tables_cpe_routing(self, cpe: Any) -> List[dict]:
        tables: List[dict] = []
        dist = getattr(cpe, "link_distribution", None) or {}
        if dist:
            rows = [{"路径指纹": fp, "域名": ", ".join(domains)} for fp, domains in dist.items()]
            tables.append({"title": "CPE 链路分布", "rows": rows})
        domain_results = getattr(cpe, "domain_results", None) or []
        if domain_results:
            rows = []
            for dr in domain_results[:10]:
                if isinstance(dr, dict):
                    rows.append({
                        "域名": dr.get("domain", "N/A"),
                        "解析 IP": dr.get("resolved_ip", "N/A"),
                        "链路": dr.get("link_category", "N/A"),
                    })
                else:
                    rows.append({
                        "域名": getattr(dr, "domain", "N/A"),
                        "解析 IP": getattr(dr, "resolved_ip", "N/A"),
                        "链路": getattr(dr, "link_category", "N/A"),
                    })
            tables.append({"title": "域名路径摘要", "rows": rows})
        return tables

    @staticmethod
    def _probe_target_host(probe: Any) -> str:
        """从探测结果中解析目标主机（DNS 服务器 IP 等）。"""
        target = getattr(probe, "target", None)
        if target is None:
            return "Unknown"
        if isinstance(target, ProbeTarget):
            host = target.host
            return host if isinstance(host, str) else str(host)
        if isinstance(target, str):
            return target
        return str(target)

    def _inline_static_resources(self, html_content: str) -> str:
        """将关键的 CSS/JS 资源内联到 HTML 中，减少 HTTP 请求并提升单文件便携性
        
        Args:
            html_content: 原始 HTML 内容
            
        Returns:
            处理后的 HTML 内容
        """
        # 简单实现：在实际生产中可以使用 minify 库压缩内容或替换外链标签
        # 此处预留接口，暂直接返回
        return html_content

