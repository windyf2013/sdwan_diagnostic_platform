"""
TraceRoute工具 - 路由追踪

遵循 SDWAN_SPEC.md §2.4.1 工具约束
遵循 SDWAN_SPEC_PATCHES.md PATCH-003 装饰器规范
"""

import asyncio
import logging
import re
import ipaddress
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
            timeout: 超时时间(秒)
            protocol: 协议类型
            
        Returns:
            路由跳列表
        """
        # 构建traceroute命令
        if self._is_windows:
            # Windows使用tracert
            cmd = ["tracert", "-h", str(max_hops), "-w", str(timeout * 1000), host]
        else:
            # Linux使用traceroute
            if protocol == "icmp":
                cmd = ["traceroute", "-I", "-m", str(max_hops), "-w", str(timeout), host]
            elif protocol == "udp":
                cmd = ["traceroute", "-m", str(max_hops), "-w", str(timeout), host]
            elif protocol == "tcp":
                cmd = ["traceroute", "-T", "-m", str(max_hops), "-w", str(timeout), host]
            else:
                cmd = ["traceroute", "-m", str(max_hops), "-w", str(timeout), host]
        
        # 执行命令
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout * max_hops + 10  # 每跳超时+额外缓冲
            )
            
            if process.returncode != 0:
                # traceroute可能部分成功，仍尝试解析输出
                error_msg = stderr.decode('utf-8', errors='ignore')
                if not error_msg:
                    error_msg = f"traceroute命令返回码: {process.returncode}"
            
            # 解析输出
            output = stdout.decode('utf-8', errors='ignore')
            hops = self._parse_traceroute_output(output, self._is_windows)
            
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
            except:
                pass
            raise
    
    def _parse_traceroute_output(
        self, 
        output: str, 
        is_windows: bool
    ) -> List[Dict[str, Any]]:
        """解析traceroute命令输出
        
        Args:
            output: traceroute命令输出文本
            is_windows: 是否为Windows系统
            
        Returns:
            路由跳列表
        """
        hops = []
        
        if is_windows:
            # Windows tracert输出解析
            # 示例: "  1     1 ms     1 ms     1 ms  192.168.1.1"
            pattern = r"^\s*(\d+)\s+([\d*]+)\s+ms\s+([\d*]+)\s+ms\s+([\d*]+)\s+ms\s+([^\s]+)"
            
            for line in output.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                match = re.match(pattern, line)
                if match:
                    hop_num = int(match.group(1))
                    rtt1 = self._parse_rtt(match.group(2))
                    rtt2 = self._parse_rtt(match.group(3))
                    rtt3 = self._parse_rtt(match.group(4))
                    target = match.group(5)
                    
                    # 解析IP和主机名
                    ip, hostname = self._parse_target(target)
                    
                    # 计算统计
                    rtts = [rtt for rtt in [rtt1, rtt2, rtt3] if rtt is not None]
                    stats = self._calculate_hop_stats(rtts)
                    
                    hop = {
                        "hop": hop_num,
                        "ip": ip,
                        "hostname": hostname,
                        "rtts": rtts,
                        **stats,
                    }
                    hops.append(hop)
        else:
            # Linux traceroute输出解析
            # 示例: " 1  192.168.1.1 (192.168.1.1)  1.234 ms  1.345 ms  1.456 ms"
            pattern = r"^\s*(\d+)\s+([^\s]+)\s+\(([^)]+)\)\s+([\d.*]+)\s+ms\s+([\d.*]+)\s+ms\s+([\d.*]+)\s+ms"
            
            for line in output.split('\n'):
                line = line.strip()
                if not line or line.startswith("traceroute"):
                    continue
                
                match = re.match(pattern, line)
                if match:
                    hop_num = int(match.group(1))
                    hostname = match.group(2)
                    ip = match.group(3)
                    rtt1 = self._parse_rtt(match.group(4))
                    rtt2 = self._parse_rtt(match.group(5))
                    rtt3 = self._parse_rtt(match.group(6))
                    
                    # 计算统计
                    rtts = [rtt for rtt in [rtt1, rtt2, rtt3] if rtt is not None]
                    stats = self._calculate_hop_stats(rtts)
                    
                    hop = {
                        "hop": hop_num,
                        "ip": ip,
                        "hostname": hostname if hostname != ip else None,
                        "rtts": rtts,
                        **stats,
                    }
                    hops.append(hop)
        
        return hops
    
    def _parse_rtt(self, rtt_str: str) -> Optional[float]:
        """解析RTT字符串
        
        Args:
            rtt_str: RTT字符串，如 "1.234" 或 "*"
            
        Returns:
            RTT值(ms)，解析失败返回None
        """
        if not rtt_str or rtt_str == "*":
            return None
        
        try:
            return float(rtt_str)
        except ValueError:
            return None
    
    def _parse_target(self, target: str) -> tuple:
        """解析目标字符串，提取IP和主机名
        
        Args:
            target: 目标字符串，如 "192.168.1.1" 或 "router.local [192.168.1.1]"
            
        Returns:
            (ip, hostname) 元组
        """
        # 检查是否为IP地址
        try:
            ipaddress.ip_address(target)
            return target, None
        except ValueError:
            pass
        
        # 尝试从格式 "hostname [ip]" 中提取
        match = re.match(r"([^\s]+)\s+\[([^\]]+)\]", target)
        if match:
            hostname = match.group(1)
            ip = match.group(2)
            return ip, hostname
        
        # 其他情况
        return None, target
    
    def _calculate_hop_stats(self, rtts: List[float]) -> Dict[str, Any]:
        """计算单跳的统计信息
        
        Args:
            rtts: RTT值列表
            
        Returns:
            统计信息字典
        """
        if not rtts:
            return {
                "rtt_min": None,
                "rtt_avg": None,
                "rtt_max": None,
                "loss_rate": 1.0,
            }
        
        # 计算RTT统计
        rtt_min = min(rtts)
        rtt_max = max(rtts)
        rtt_avg = sum(rtts) / len(rtts)
        
        # 计算丢包率（假设每个跳探测3次）
        total_probes = 3
        loss_rate = (total_probes - len(rtts)) / total_probes
        
        return {
            "rtt_min": rtt_min,
            "rtt_avg": rtt_avg,
            "rtt_max": rtt_max,
            "loss_rate": loss_rate,
        }
    
    def _resolve_hostname(self, hostname: str) -> Optional[str]:
        """解析主机名获取IP地址
        
        Args:
            hostname: 主机名
            
        Returns:
            IP地址，解析失败返回None
        """
        try:
            import socket
            return socket.gethostbyname(hostname)
        except:
            return None