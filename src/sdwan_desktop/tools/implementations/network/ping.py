"""
Ping工具 - ICMP连通性测试

遵循 SDWAN_SPEC.md §2.4.1 工具约束
遵循 SDWAN_SPEC_PATCHES.md PATCH-003 装饰器规范
"""

import asyncio
import logging
import re
import subprocess
from typing import Any, Dict, List, Optional

from sdwan_desktop.core.types.tool import ToolRequest, ToolResponse
from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.tools.registry.decorator import tool_function

logger = logging.getLogger(__name__)


@tool_function(
    name="ping",
    description="ICMP连通性测试，返回RTT统计和丢包率",
    timeout=30,
    retry_count=2,
    input_schema={
        "type": "object",
        "properties": {
            "host": {"type": "string", "description": "目标主机IP或域名"},
            "count": {"type": "integer", "minimum": 1, "maximum": 100, "default": 4},
            "timeout": {"type": "integer", "minimum": 1, "maximum": 60, "default": 5},
            "packet_size": {"type": "integer", "minimum": 32, "maximum": 65500, "default": 56},
        },
        "required": ["host"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "rtt_min": {"type": "number", "description": "最小RTT(ms)"},
            "rtt_avg": {"type": "number", "description": "平均RTT(ms)"},
            "rtt_max": {"type": "number", "description": "最大RTT(ms)"},
            "rtt_stddev": {"type": "number", "description": "RTT标准差(ms)"},
            "loss_rate": {"type": "number", "description": "丢包率(0-1)"},
            "ttl": {"type": "integer", "description": "TTL值"},
            "packets_sent": {"type": "integer", "description": "发送包数"},
            "packets_received": {"type": "integer", "description": "接收包数"},
        },
        "required": ["success", "rtt_min", "rtt_avg", "rtt_max", "loss_rate"],
    },
)
class PingTool:
    """ICMP Ping工具
    
    支持Windows和Linux系统，自动检测系统类型
    解析ping命令输出，计算统计指标
    """
    
    def __init__(self):
        self._is_windows = False
        self._detect_os()
    
    def _detect_os(self):
        """检测操作系统类型"""
        import platform
        self._is_windows = platform.system().lower() == "windows"
    
    async def execute(self, request: ToolRequest, ctx: FlowContext) -> ToolResponse:
        """执行Ping探测
        
        Args:
            request: 工具请求，parameters包含:
                - host: str (必填) 目标主机
                - count: int (可选) 发包数量，默认4
                - timeout: int (可选) 超时秒数，默认5
                - packet_size: int (可选) 包大小，默认56
            ctx: 流程上下文
            
        Returns:
            ToolResponse: 探测结果
        """
        # 1. 参数解析
        params = request.parameters
        host = params.get("host")
        count = params.get("count", 4)
        timeout = params.get("timeout", 5)
        packet_size = params.get("packet_size", 56)
        
        # 2. 参数校验
        if not host:
            return ToolResponse(
                success=False,
                error_code="VAL_002",
                error_message="缺少必填参数: host",
                trace_id=ctx.trace_id
            )
        
        if not isinstance(count, int) or count < 1 or count > 100:
            return ToolResponse(
                success=False,
                error_code="VAL_001",
                error_message="count参数必须在1-100之间",
                trace_id=ctx.trace_id
            )
        
        # 3. 执行探测
        try:
            logger.info(f"开始Ping探测: {host}, count={count}", extra={"trace_id": ctx.trace_id})
            
            start_time = asyncio.get_event_loop().time()
            results = await self._ping(host, count, timeout, packet_size)
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            
            # 4. 计算指标
            metrics = self._calculate_metrics(results)
            
            logger.info(
                f"Ping探测完成: {host}, 丢包率={metrics['loss_rate']:.1%}, "
                f"平均RTT={metrics['rtt_avg']:.1f}ms",
                extra={"trace_id": ctx.trace_id}
            )
            
            return ToolResponse(
                success=True,
                data=metrics,
                trace_id=ctx.trace_id,
                duration_ms=duration_ms
            )
            
        except asyncio.TimeoutError:
            logger.warning(f"Ping {host} 超时", extra={"trace_id": ctx.trace_id})
            return ToolResponse(
                success=False,
                error_code="TOOL_TIMEOUT",
                error_message=f"Ping {host} 超时 ({timeout}s)",
                trace_id=ctx.trace_id
            )
        except Exception as e:
            logger.error(f"Ping失败: {e}", extra={"trace_id": ctx.trace_id})
            return ToolResponse(
                success=False,
                error_code="TOOL_002",
                error_message=str(e),
                trace_id=ctx.trace_id
            )
    
    async def _ping(
        self, 
        host: str, 
        count: int, 
        timeout: int,
        packet_size: int
    ) -> List[Dict[str, Any]]:
        """执行ping命令
        
        Args:
            host: 目标主机
            count: 发包数量
            timeout: 超时时间(秒)
            packet_size: 包大小
            
        Returns:
            探测结果列表，每个元素包含:
                - success: bool 是否成功
                - rtt: float RTT时间(ms)，失败时为None
                - ttl: int TTL值，失败时为None
        """
        # 构建ping命令
        if self._is_windows:
            cmd = [
                "ping", "-n", str(count), "-w", str(timeout * 1000),
                "-l", str(packet_size), host
            ]
        else:
            cmd = [
                "ping", "-c", str(count), "-W", str(timeout),
                "-s", str(packet_size), host
            ]
        
        # 执行命令
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout + 2  # 额外2秒缓冲
            )
            
            if process.returncode != 0:
                raise RuntimeError(f"ping命令失败: {stderr.decode('utf-8', errors='ignore')}")
            
            # 解析输出
            output = stdout.decode('utf-8', errors='ignore')
            return self._parse_ping_output(output, self._is_windows)
            
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
    
    def _parse_ping_output(
        self, 
        output: str, 
        is_windows: bool
    ) -> List[Dict[str, Any]]:
        """解析ping命令输出
        
        Args:
            output: ping命令输出文本
            is_windows: 是否为Windows系统
            
        Returns:
            探测结果列表
        """
        results = []
        
        if is_windows:
            # Windows ping输出解析
            # 示例: "来自 8.8.8.8 的回复: 字节=56 时间=10ms TTL=116"
            pattern = r"来自 .+? 的回复: 字节=\d+ 时间=(\d+)ms TTL=(\d+)"
            for match in re.finditer(pattern, output):
                rtt = float(match.group(1))
                ttl = int(match.group(2))
                results.append({"success": True, "rtt": rtt, "ttl": ttl})
            
            # 英文系统格式
            if not results:
                pattern = r"Reply from .+?: bytes=\d+ time=(\d+)ms TTL=(\d+)"
                for match in re.finditer(pattern, output):
                    rtt = float(match.group(1))
                    ttl = int(match.group(2))
                    results.append({"success": True, "rtt": rtt, "ttl": ttl})
        else:
            # Linux ping输出解析
            # 示例: "64 bytes from 8.8.8.8: icmp_seq=1 ttl=116 time=10.1 ms"
            pattern = r"(\d+) bytes from .+?: icmp_seq=\d+ ttl=(\d+) time=([\d.]+) ms"
            for match in re.finditer(pattern, output):
                ttl = int(match.group(2))
                rtt = float(match.group(3))
                results.append({"success": True, "rtt": rtt, "ttl": ttl})
        
        return results
    
    def _calculate_metrics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算统计指标
        
        Args:
            results: 探测结果列表
            
        Returns:
            统计指标字典
        """
        successful_results = [r for r in results if r.get("success")]
        total_packets = len(results)
        received_packets = len(successful_results)
        
        if received_packets == 0:
            return {
                "success": False,
                "rtt_min": 0.0,
                "rtt_avg": 0.0,
                "rtt_max": 0.0,
                "rtt_stddev": 0.0,
                "loss_rate": 1.0,
                "ttl": None,
                "packets_sent": total_packets,
                "packets_received": 0,
            }
        
        # 计算RTT统计
        rtts = [r["rtt"] for r in successful_results]
        rtt_min = min(rtts)
        rtt_max = max(rtts)
        rtt_avg = sum(rtts) / len(rtts)
        
        # 计算标准差
        if len(rtts) > 1:
            variance = sum((x - rtt_avg) ** 2 for x in rtts) / (len(rtts) - 1)
            rtt_stddev = variance ** 0.5
        else:
            rtt_stddev = 0.0
        
        # 计算丢包率
        loss_rate = (total_packets - received_packets) / total_packets
        
        # 计算平均TTL
        ttls = [r.get("ttl") for r in successful_results if r.get("ttl") is not None]
        avg_ttl = sum(ttls) / len(ttls) if ttls else None
        
        return {
            "success": True,
            "rtt_min": rtt_min,
            "rtt_avg": rtt_avg,
            "rtt_max": rtt_max,
            "rtt_stddev": rtt_stddev,
            "loss_rate": loss_rate,
            "ttl": avg_ttl,
            "packets_sent": total_packets,
            "packets_received": received_packets,
        }