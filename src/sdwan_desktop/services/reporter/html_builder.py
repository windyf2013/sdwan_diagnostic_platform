"""
HTML 报告生成器

根据诊断结果生成 HTML 格式的一键体检报告。
符合 SDWAN_SPEC §4.3 报告结构要求。
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, FileSystemBytecodeCache, select_autoescape

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.core.types.probe import ProbeProtocol
from sdwan_desktop.services.orchestrator.diagnostic_flow import DiagnosticResult
from sdwan_desktop.core.types.diagnosis import DiagnosisResult, RootCause, Severity

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
            import sys
            if getattr(sys, 'frozen', False):
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
                "system_info": self._extract_system_info(result),
                "connectivity": self._extract_connectivity(result),
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
            template = self.env.get_template("deep_dive.html")

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
            "dns_split_detected": False,
            "gateway_rtt": 0.0,
            "gateway_loss_rate": 0.0,
            "dns_results": [],
            "internet_targets": [],
            "dns_split_details": [],
            "cpe_link_routing": None,
        }

        # 1. 尝试从证据中获取原始探测数据 (最详细的数据源)
        for evidence in result.evidences:
            if hasattr(evidence, 'probe_results') and evidence.probe_results:
                for probe in evidence.probe_results:
                    target_host = probe.target.host if hasattr(probe, 'target') and probe.target else "Unknown"
                    
                    # 网关信息
                    if probe.target.protocol == ProbeProtocol.ICMP:
                        # 简单匹配：如果丢包率 < 1.0 且 RTT > 0，或者 success 为 True，则认为是网关探测
                        if probe.success or (probe.metrics and probe.metrics.loss_rate < 1.0):
                            connectivity["gateway_status"] = "ok" if probe.success else "packet_loss"
                            connectivity["gateway_ip"] = target_host
                            connectivity["gateway_rtt"] = probe.metrics.rtt_avg or 0.0
                            connectivity["gateway_loss_rate"] = probe.metrics.loss_rate or 0.0
                    
                    # DNS 信息
                    elif probe.target.protocol == ProbeProtocol.DNS:
                        resolved_ips = []
                        if probe.metrics and hasattr(probe.metrics, 'resolved_ips'):
                            resolved_ips = probe.metrics.resolved_ips or []
                        
                        connectivity["dns_results"].append({
                            "server": target_host,
                            "success": probe.success,
                            "rtt": probe.metrics.rtt_avg or 0.0,
                            "resolved_ips": ", ".join(resolved_ips) if resolved_ips else "无解析记录"
                        })
                    
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

            # 2. 提取 DNS 分流测试详情
            if hasattr(evidence, 'config_snapshots') and evidence.config_snapshots:
                # ✅ 调试日志：记录所有可用的 config_snapshots keys
                logger.debug(
                    f"证据链 config_snapshots keys: {list(evidence.config_snapshots.keys())}",
                    extra={"trace_id": result.trace_id}
                )
                
                split_result = evidence.config_snapshots.get("dns_split_result")
                if split_result:
                    logger.info(
                        f"✅ 找到 DNS 分流结果: {type(split_result).__name__}",
                        extra={"trace_id": result.trace_id}
                    )
                    
                    # 兼容 DnsSplitTestResult 对象和字典格式
                    domain_results = getattr(split_result, 'domain_results', [])
                    if not domain_results and isinstance(split_result, dict):
                        domain_results = split_result.get("domain_results", [])

                    logger.debug(
                        f"   - DNS分流域名结果数: {len(domain_results)}",
                        extra={"trace_id": result.trace_id}
                    )

                    for dr in domain_results:
                        # 兼容 DomainDnsResult 对象和字典格式
                        if isinstance(dr, dict):
                            domain = dr.get("domain", "N/A")
                            is_split = dr.get("is_split", False)
                            description = dr.get("split_description", "")
                            domestic_res = dr.get("domestic_results", {})
                            international_res = dr.get("international_results", {})
                        else:
                            domain = getattr(dr, 'domain', "N/A")
                            is_split = getattr(dr, 'is_split', False)
                            description = getattr(dr, 'split_description', "")
                            domestic_res = getattr(dr, 'domestic_results', {})
                            international_res = getattr(dr, 'international_results', {})

                        # ✅ 优化：从结果中提取 IP 列表（而非整个对象）
                        def extract_ips(res_dict):
                            """从 DNS 解析结果字典中提取 IP 地址字符串
            
                            Args:
                                res_dict: DNS解析结果字典 {dns_server: [ip_list]} 或字符串
            
                            Returns:
                                str: IP地址字符串，多个IP用逗号分隔
                            """
                            if isinstance(res_dict, dict):
                                # 字典格式：{dns_server: [ip_list]}
                                all_ips = []
                                for dns_server, ip_list in res_dict.items():
                                    if isinstance(ip_list, list):
                                        # 过滤掉错误信息
                                        valid_ips = [ip for ip in ip_list if not ip.startswith("ERROR:")]
                                        all_ips.extend(valid_ips)
                                    elif isinstance(ip_list, str) and ip_list:
                                        all_ips.append(ip_list)
                                
                                return ", ".join(all_ips) if all_ips else "无解析记录"
                            elif isinstance(res_dict, str):
                                return res_dict
                            elif isinstance(res_dict, list):
                                # 兼容旧版列表格式
                                ips = []
                                for item in res_dict:
                                    if isinstance(item, dict):
                                        ip = item.get("resolved_ip", "")
                                        if ip:
                                            ips.append(ip)
                                    elif hasattr(item, "resolved_ip"):
                                        ip = getattr(item, "resolved_ip", "")
                                        if ip:
                                            ips.append(ip)
                                return ", ".join(ips) if ips else "无解析记录"
                            else:
                                return "无解析记录"
                        
                        domestic_ips_str = extract_ips(domestic_res)
                        international_ips_str = extract_ips(international_res)

                        connectivity["dns_split_details"].append({
                            "domain": domain,
                            "is_split": is_split,
                            "description": description,
                            "domestic_ips": domestic_ips_str,
                            "international_ips": international_ips_str,
                        })
                        if is_split:
                            connectivity["dns_split_detected"] = True

                # 3. 提取 CPE 链路分流检测结果
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

        # 4. 计算成功率
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
        1. 默认路由 (0.0.0.0/0) - 最高优先级，决定流量出口
        2. CPE网关路由 - 指向SD-WAN设备的关键路径
        3. DNS服务器路由 - 确保DNS解析可达性
        4. 低Metric静态路由 - 策略路由和业务分流规则
        
        Args:
            routes: 原始路由列表
            dns_servers: DNS服务器IP列表（用于识别DNS路由）
            
        Returns:
            按优先级排序的关键路由列表（最多4条）
        """
        if not routes:
            return []
        
        # 分类收集路由
        default_routes = []      # 默认路由
        gateway_routes = []      # 网关路由
        dns_routes = []          # DNS路由
        static_routes = []       # 静态/策略路由
        
        for route in routes:
            dest = getattr(route, 'destination', '')
            mask = getattr(route, 'netmask', '')
            gw = getattr(route, 'gateway', '')
            metric = getattr(route, 'metric', 999)
            protocol = getattr(route, 'protocol', '')
            
            # 1. 默认路由（最高优先级）
            if dest == "0.0.0.0" and mask == "0.0.0.0":
                default_routes.append(route)
                continue
            
            # 2. CPE网关路由（假设CPE在192.168.x.x或10.x.x.x私有网段）
            if gw and (gw.startswith("192.168.") or gw.startswith("10.")):
                gateway_routes.append(route)
                continue
            
            # 3. DNS服务器路由
            if dns_servers and any(dns_ip in dest for dns_ip in dns_servers):
                dns_routes.append(route)
                continue
            
            # 4. 低Metric静态路由（策略路由）
            if metric < 100 and protocol in ["static", "local", "bgp", "ospf"]:
                static_routes.append(route)
                continue
        
        # 按优先级合并（只保留真正关键的路由，不补充其他路由）
        key_routes = []
        key_routes.extend(default_routes[:1])           # 最多1条默认路由
        key_routes.extend(gateway_routes[:2])           # 最多2条网关路由
        key_routes.extend(dns_routes[:1])               # 最多1条DNS路由
        key_routes.extend(static_routes[:1])            # 最多1条静态路由
        
        # 转换为字典格式
        return [
            {
                "dest": r.destination,
                "mask": r.netmask,
                "gw": r.gateway,
                "metric": r.metric,
            }
            for r in key_routes[:4]  # 最终限制为4条
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
                
                # IP 配置
                if hasattr(snapshot, 'ip_config') and snapshot.ip_config:
                    system_info["ip_config"] = {
                        "gateway": snapshot.ip_config.default_gateway or "N/A",
                        "dns_servers": ", ".join(snapshot.ip_config.dns_servers) if snapshot.ip_config.dns_servers else "N/A",
                    }
                
                # 路由信息 (智能筛选关键路由)
                if hasattr(snapshot, 'routes'):
                    # 提取DNS服务器列表用于路由筛选
                    dns_servers = []
                    if hasattr(snapshot, 'ip_config') and snapshot.ip_config:
                        dns_servers = snapshot.ip_config.dns_servers or []
                    
                    system_info["routes"] = self._filter_key_routes(
                        snapshot.routes, 
                        dns_servers
                    )

                # 防火墙与代理状态
                if hasattr(snapshot, 'firewall_status') and snapshot.firewall_status:
                    fw = snapshot.firewall_status
                    # FirewallInfo 是 dataclass，直接访问属性
                    system_info["firewall"] = "开启" if getattr(fw, 'enabled', False) else "关闭"
                
                if hasattr(snapshot, 'proxy_config') and snapshot.proxy_config:
                    px = snapshot.proxy_config
                    # ProxyInfo 也是 dataclass
                    system_info["proxy"] = "启用" if getattr(px, 'enabled', False) else "未启用"
                
                break

        return system_info

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

