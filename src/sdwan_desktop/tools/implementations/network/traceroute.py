"""
TraceRoute工具 - 路由追踪

遵循 SDWAN_SPEC.md §2.4.1 工具约束
遵循 SDWAN_SPEC_PATCHES.md PATCH-003 装饰器规范
"""

import asyncio
import logging
import re
import ipaddress
import socket
from typing import Any, Dict, List, Optional

from sdwan_desktop.core.types.tool import ToolRequest, ToolResponse
from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.tools.registry.decorator import tool_function

logger = logging.getLogger(__name__)


@tool_function(
    name="traceroute",
    description="路由追踪，显示数据包到达目标主机经过的每一跳",
    timeout=120,
    retry_count=1,
    input_schema={
        "type": "object",
        "properties": {
            "host": {"type": "string", "description": "目标主机IP或域名"},
            "max_hops": {"type": "integer", "minimum": 1, "maximum": 64, "default": 30},
            "timeout": {"type": "integer", "minimum": 1, "maximum": 30, "default": 5},
            "protocol": {"type": "string", "enum": ["icmp", "udp", "tcp"], "default": "icmp"},
        },
        "required": ["host"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "hops": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "hop": {"type": "integer", "description": "跳数"},
                        "ip": {"type": "string", "description": "IP地址"},
                        "hostname": {"type": "string", "description": "主机名"},
                        "rtts": {
                            "type": "array",
                            "items": {"type": "number"},
                            "description": "三次探测的RTT(ms)"
                        },
                        "rtt_min": {"type": "number", "description": "最小RTT(ms)"},
                        "rtt_avg": {"type": "number", "description": "平均RTT(ms)"},
                        "rtt_max": {"type": "number", "description": "最大RTT(ms)"},
                        "loss_rate": {"type": "number", "description": "丢包率(0-1)"},
                        "as_number": {"type": "string", "description": "AS号"},
                        "country": {"type": "string", "description": "国家"},
                        "isp": {"type": "string", "description": "运营商"},
                    },
                    "required": ["hop", "ip", "rtts"],
                },
                "description": "路由跳列表"
            },
            "total_hops": {"type": "integer", "description": "总跳数"},
            "target_reached": {"type": "boolean", "description": "是否到达目标"},
            "target_ip": {"type": "string", "description": "目标IP地址"},
        },
        "required": ["success", "hops", "total_hops", "target_reached"],
    },
)
class TraceRouteTool:
    """路由追踪工具
    
    支持Windows和Linux系统，自动检测系统类型
    解析traceroute/tracert命令输出，提取路由信息
    """
    
    def __init__(self):
        self._is_windows = False
        self._detect_os()
    
    def _detect_os(self):
        """检测操作系统类型"""
        import platform
        self._is_windows = platform.system().lower() == "windows"
    
    async def execute(self, request: ToolRequest, ctx: FlowContext) -> ToolResponse:
        """执行路由追踪
        
        Args:
            request: 工具请求，parameters包含:
                - host: str (必填) 目标主机
                - max_hops: int (可选) 最大跳数，默认30
                - timeout: int (可选) 超时秒数，默认5
                - protocol: str (可选) 协议类型，默认icmp
            ctx: 流程上下文
            
        Returns:
            ToolResponse: 探测结果
        """
        # 1. 参数解析
        params = request.parameters
        host = params.get("host")
        max_hops = params.get("max_hops", 30)
        timeout = params.get("timeout", 5)
        protocol = params.get("protocol", "icmp")
        
        # 2. 参数校验
        if not host:
            return ToolResponse(
                success=False,
                error_code="VAL_002",
                error_message="缺少必填参数: host",
                trace_id=ctx.trace_id
            )
        
        if not isinstance(max_hops, int) or max_hops < 1 or max_hops > 64:
            return ToolResponse(
                success=False,
                error_code="VAL_001",
                error_message="max_hops参数必须在1-64之间",
                trace_id=ctx.trace_id
            )
        
        # 3. 执行探测
        try:
            logger.info(
                f"开始路由追踪: {host}, max_hops={max_hops}, protocol={protocol}",
                extra={"trace_id": ctx.trace_id}
            )
            
            start_time = asyncio.get_event_loop().time()
            hops = await self._traceroute(host, max_hops, timeout, protocol)
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            
            # 4. 计算统计信息
            target_reached = False
            target_ip = None
            
            if hops:
                last_hop = hops[-1]
                # 检查是否到达目标
                if last_hop.get("ip") and last_hop.get("ip") != "*":
                    try:
                        # 尝试解析目标IP
                        target_ip = self._resolve_hostname(host)
                        if target_ip and last_hop["ip"] == target_ip:
                            target_reached = True
                    except:
                        pass
            
            result = {
                "success": True,
                "hops": hops,
                "total_hops": len(hops),
                "target_reached": target_reached,
                "target_ip": target_ip,
            }
            
            logger.info(
                f"路由追踪完成: {host}, 总跳数={len(hops)}, "
                f"到达目标={target_reached}",
                extra={"trace_id": ctx.trace_id}
            )
            
            return ToolResponse(
                success=True,
                data=result,
                trace_id=ctx.trace_id,
                duration_ms=duration_ms
            )
            
        except asyncio.TimeoutError:
            logger.warning(f"路由追踪 {host} 超时", extra={"trace_id": ctx.trace_id})
            return ToolResponse(
                success=False,
                error_code="TOOL_TIMEOUT",
                error_message=f"路由追踪 {host} 超时",
                trace_id=ctx.trace_id
            )
        except Exception as e:
            logger.error(f"路由追踪失败: {e}", extra={"trace_id": ctx.trace_id})
            return ToolResponse(
                success=False,
                error_code="TOOL_002",
                error_message=str(e),
                trace_id=ctx.trace_id
            )
    
    async def _traceroute(
        self, 
        host: str, 
        max_hops: int, 
        timeout: int,
        protocol: str
    ) -> List[Dict[str, Any]]:
        """执行traceroute命令
        
        Args:
            host: 目标主机
            max_hops: 最大跳数
            timeout: 超时时间(秒) - 这是每次探测的超时时间
            protocol: 协议类型
            
        Returns:
            路由跳列表
        """
        # 构建traceroute命令
        if self._is_windows:
            # Windows使用tracert，-d 参数禁用反向DNS解析以缩短每跳查询时间
            # -w 参数指定每次探测的超时时间（毫秒），每跳自动进行3次探测
            cmd = ["tracert", "-d", "-h", str(max_hops), "-w", str(timeout * 1000), host]
        else:
            # Linux使用traceroute
            # -w 参数也是每次探测的超时时间（秒），默认每跳3次探测
            if protocol == "icmp":
                cmd = ["traceroute", "-I", "-n", "-m", str(max_hops), "-w", str(timeout), host]
            elif protocol == "udp":
                cmd = ["traceroute", "-n", "-m", str(max_hops), "-w", str(timeout), host]
            elif protocol == "tcp":
                cmd = ["traceroute", "-T", "-n", "-m", str(max_hops), "-w", str(timeout), host]
            else:
                cmd = ["traceroute", "-n", "-m", str(max_hops), "-w", str(timeout), host]
        
        # ✅ 创建子进程执行命令
        from sdwan_desktop.core.subprocess_platform import create_subprocess_exec_hidden

        process = await create_subprocess_exec_hidden(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        # 执行命令
        try:
            # ✅ 正确的超时计算公式（基于2026-05-02修复记录）
            # 
            # Windows tracert / Linux traceroute 的 -w 参数含义：
            #   - 指定每次探测的超时时间（不是每跳总超时）
            #   - 每跳默认进行3次探测
            #   - 例如：-w 5000 表示每次探测最多等待5秒，每跳最多3×5=15秒
            #
            # 因此总超时 = max_hops × 3次探测 × timeout_per_probe + 缓冲
            # 示例：7跳 × 3次 × 5秒 + 15秒缓冲 = 120秒
            
            probes_per_hop = 3  # 标准配置：每跳3次探测
            internal_timeout = max_hops * probes_per_hop * timeout + 15  # 7×3×5+15=120秒
            
            logger.debug(
                f"Traceroute内部超时配置: max_hops={max_hops}, probes_per_hop={probes_per_hop}, "
                f"timeout_per_probe={timeout}s, internal_timeout={internal_timeout}s (公式: {max_hops}×{probes_per_hop}×{timeout}+15)",
                extra={"trace_id": getattr(self, '_current_trace_id', 'N/A')}
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=internal_timeout
            )
            
            if process.returncode != 0:
                # traceroute可能部分成功，仍尝试解析输出
                error_msg = stderr.decode('utf-8', errors='ignore')
                if not error_msg:
                    error_msg = f"traceroute命令返回码: {process.returncode}"
            
            # 解析输出
            output = stdout.decode('utf-8', errors='ignore')
            hops = self._parse_traceroute_output(output, self._is_windows)
            
            # ✅ 关键修复：为每个跳点查询IP地理位置信息(AS号、国家、运营商)
            hops = await self._enrich_hops_with_geo_info(hops)
            
            # ✅ 关键修复：补全缺失的跳点（处理Windows tracert跳过超时跳点的情况）
            # 注意：只补全到实际解析出的最大跳数，而不是max_hops
            if self._is_windows and hops:
                max_parsed_hop = max(h["hop"] for h in hops)
                hops = self._fill_missing_hops(hops, max_parsed_hop)
            
            # 限制最大跳数
            if len(hops) > max_hops:
                hops = hops[:max_hops]
            
            return hops
            
        except asyncio.TimeoutError:
            # 超时则终止进程
            try:
                process.terminate()
                await asyncio.sleep(0.5)
                if process.returncode is None:
                    process.kill()
                try:
                    await process.wait()
                except Exception:
                    pass
            except Exception:
                pass
            raise
    
    def _parse_traceroute_output(
        self, 
        output: str, 
        is_windows: bool
    ) -> List[Dict[str, Any]]:
        """解析traceroute/tracert命令输出
        
        Args:
            output: 命令输出
            is_windows: 是否为Windows系统
            
        Returns:
            路由跳列表
        """
        hops = []
        lines = output.strip().split('\n')
        
        # ✅ 修复：增强正则表达式，支持多种格式
        # Windows格式1: "  1     1 ms     1 ms     1 ms  192.168.1.1"
        # Windows格式2: "  3     *        *        *     Request timed out."
        # Linux格式1: " 1  192.168.1.1 (192.168.1.1)  1.234 ms  1.345 ms  1.456 ms"
        # Linux格式2: " 3  * * *"
        hop_pattern_windows_with_ip = re.compile(
            r'^\s*(\d+)\s+(\d+(?:\.\d+)?)\s+ms\s+(\d+(?:\.\d+)?)\s+ms\s+(\d+(?:\.\d+)?)\s+ms\s+([\d.]+)'
        )
        hop_pattern_windows_timeout = re.compile(
            r'^\s*(\d+)\s+\*\s+\*\s+\*\s+(?:Request timed out\.|请求超时\.?)'
        )
        hop_pattern_linux_with_ip = re.compile(
            r'^\s*(\d+)\s+([\d.*]+)(?:\s+\(([\d.*]+)\))?\s+([\d.]+)\s+ms\s+([\d.]+)\s+ms\s+([\d.]+)\s+ms'
        )
        hop_pattern_linux_timeout = re.compile(
            r'^\s*(\d+)\s+\*\s+\*\s+\*'
        )
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            matched = False
            
            if is_windows:
                # 尝试匹配Windows格式（带IP）
                match = hop_pattern_windows_with_ip.match(line)
                if match:
                    hop = int(match.group(1))
                    rtt1 = float(match.group(2))
                    rtt2 = float(match.group(3))
                    rtt3 = float(match.group(4))
                    ip = match.group(5)
                    
                    hops.append({
                        "hop": hop,
                        "ip": ip,
                        "hostname": None,
                        "rtts": [rtt1, rtt2, rtt3],
                        "rtt_min": min(rtt1, rtt2, rtt3),
                        "rtt_avg": (rtt1 + rtt2 + rtt3) / 3,
                        "rtt_max": max(rtt1, rtt2, rtt3),
                        "loss_rate": 0.0,
                    })
                    matched = True
                    continue
                
                # 尝试匹配Windows格式（超时）
                match = hop_pattern_windows_timeout.match(line)
                if match:
                    hop = int(match.group(1))
                    hops.append({
                        "hop": hop,
                        "ip": "*",
                        "hostname": None,
                        "rtts": [],
                        "rtt_min": None,
                        "rtt_avg": None,
                        "rtt_max": None,
                        "loss_rate": 1.0,
                    })
                    matched = True
                    continue
            else:
                # Linux格式
                # 先尝试匹配超时格式
                match = hop_pattern_linux_timeout.match(line)
                if match:
                    hop = int(match.group(1))
                    hops.append({
                        "hop": hop,
                        "ip": "*",
                        "hostname": None,
                        "rtts": [],
                        "rtt_min": None,
                        "rtt_avg": None,
                        "rtt_max": None,
                        "loss_rate": 1.0,
                    })
                    matched = True
                    continue
                
                # 再尝试匹配带IP的格式
                match = hop_pattern_linux_with_ip.match(line)
                if match:
                    hop = int(match.group(1))
                    ip_or_hostname = match.group(2)
                    ip_in_paren = match.group(3)  # 括号内的IP
                    rtt1 = float(match.group(4))
                    rtt2 = float(match.group(5))
                    rtt3 = float(match.group(6))
                    
                    # 确定IP地址
                    ip = ip_in_paren if ip_in_paren and ip_in_paren != '*' else ip_or_hostname
                    
                    # 如果IP是*，表示超时
                    if ip == '*':
                        hops.append({
                            "hop": hop,
                            "ip": "*",
                            "hostname": None,
                            "rtts": [],
                            "rtt_min": None,
                            "rtt_avg": None,
                            "rtt_max": None,
                            "loss_rate": 1.0,
                        })
                    else:
                        hostname = ip_or_hostname if ip_or_hostname != ip else None
                        hops.append({
                            "hop": hop,
                            "ip": ip,
                            "hostname": hostname,
                            "rtts": [rtt1, rtt2, rtt3],
                            "rtt_min": min(rtt1, rtt2, rtt3),
                            "rtt_avg": (rtt1 + rtt2 + rtt3) / 3,
                            "rtt_max": max(rtt1, rtt2, rtt3),
                            "loss_rate": 0.0,
                        })
                    matched = True
                    continue
            
            if not matched:
                logger.debug(f"Traceroute行无法解析: {line}", extra={"trace_id": getattr(self, '_current_trace_id', 'N/A')})
        
        return hops
    
    def _fill_missing_hops(
        self, 
        hops: List[Dict[str, Any]], 
        max_hops: int
    ) -> List[Dict[str, Any]]:
        """补全缺失的跳点
        
        Args:
            hops: 当前解析出的路由跳列表
            max_hops: 最大跳数
            
        Returns:
            补全后的路由跳列表
        """
        filled_hops = []
        last_hop = 0
        
        for hop in hops:
            while last_hop < hop["hop"] - 1:
                last_hop += 1
                filled_hops.append({
                    "hop": last_hop,
                    "ip": "*",
                    "rtts": [],
                    "rtt_min": None,
                    "rtt_avg": None,
                    "rtt_max": None,
                    "loss_rate": 1.0,
                })
            filled_hops.append(hop)
            last_hop = hop["hop"]
        
        while last_hop < max_hops:
            last_hop += 1
            filled_hops.append({
                "hop": last_hop,
                "ip": "*",
                "rtts": [],
                "rtt_min": None,
                "rtt_avg": None,
                "rtt_max": None,
                "loss_rate": 1.0,
            })
        
        return filled_hops
    
    async def _enrich_hops_with_geo_info(self, hops: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """为每个跳点查询IP地理位置信息(AS号、国家、运营商)
        
        Args:
            hops: 路由跳列表
            
        Returns:
            填充了地理位置信息的跳点列表
        """
        try:
            # 导入IP地理位置服务
            from sdwan_desktop.services.ip_geo_service import get_ip_geo_service
            
            geo_service = get_ip_geo_service()
            
            for hop in hops:
                # 跳过超时或无效IP
                ip = hop.get("ip")
                if not ip or ip in ["*", "T", "?"]:
                    continue
                
                # 查询IP地理信息
                geo_info = geo_service.query_ip(ip)
                
                if geo_info:
                    # 填充到hop对象
                    hop["as_number"] = geo_info.get("as_number")
                    hop["country"] = geo_info.get("country")
                    hop["isp"] = geo_info.get("isp")
                    
                    logger.debug(
                        f"第{hop['hop']}跳 {ip}: "
                        f"AS{hop.get('as_number', 'N/A')}, "
                        f"{hop.get('country', 'N/A')}, "
                        f"{hop.get('isp', 'N/A')}"
                    )
        except ImportError:
            logger.warning("IPGeoService未安装,跳过ASN信息查询")
        except Exception as e:
            logger.warning(f"查询IP地理位置失败: {e}")
        
        return hops
    
    def _resolve_hostname(self, host: str) -> Optional[str]:
        """解析主机名
        
        Args:
            host: 主机名或IP地址
            
        Returns:
            IP地址
        """
        try:
            return str(ipaddress.ip_address(host))
        except ValueError:
            try:
                return str(ipaddress.ip_address(socket.gethostbyname(host)))
            except Exception:
                return None
