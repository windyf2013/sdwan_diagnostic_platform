"""
MTR工具 - 综合路由追踪与丢包统计

遵循 SDWAN_SPEC.md §2.4.1 工具约束
遵循 SDWAN_SPEC_PATCHES.md PATCH-003 装饰器规范
"""

import asyncio
import logging
import statistics
from typing import Any, Dict, List, Optional

from sdwan_desktop.core.types.tool import ToolRequest, ToolResponse
from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.tools.registry.decorator import tool_function
from sdwan_desktop.tools.registry.base import ToolDispatcher

logger = logging.getLogger(__name__)


@tool_function(
    name="mtr",
    description="综合路由追踪工具，结合traceroute和ping统计每跳丢包率和延迟",
    timeout=180,
    retry_count=0,
    input_schema={
        "type": "object",
        "properties": {
            "host": {"type": "string", "description": "目标主机IP或域名"},
            "max_hops": {"type": "integer", "minimum": 1, "maximum": 64, "default": 30},
            "count": {"type": "integer", "minimum": 1, "maximum": 20, "default": 10},
            "interval": {"type": "number", "minimum": 0.1, "maximum": 5.0, "default": 1.0},
            "timeout": {"type": "integer", "minimum": 1, "maximum": 30, "default": 5},
            "packet_size": {"type": "integer", "minimum": 32, "maximum": 1500, "default": 56},
        },
        "required": ["host"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "host": {"type": "string", "description": "目标主机"},
            "resolved_ip": {"type": "string", "description": "解析后的IP地址"},
            "hops": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "hop": {"type": "integer", "description": "跳数"},
                        "ip": {"type": "string", "description": "IP地址"},
                        "hostname": {"type": "string", "description": "主机名"},
                        "loss_rate": {"type": "number", "description": "丢包率(0-1)"},
                        "rtt_min": {"type": "number", "description": "最小RTT(ms)"},
                        "rtt_avg": {"type": "number", "description": "平均RTT(ms)"},
                        "rtt_max": {"type": "number", "description": "最大RTT(ms)"},
                        "rtt_stddev": {"type": "number", "description": "RTT标准差"},
                        "rtt_samples": {
                            "type": "array",
                            "items": {"type": "number"},
                            "description": "RTT样本值"
                        },
                        "asn": {"type": "string", "description": "AS号码"},
                        "country": {"type": "string", "description": "国家代码"},
                        "isp": {"type": "string", "description": "ISP名称"},
                    },
                },
                "description": "逐跳统计信息"
            },
            "total_hops": {"type": "integer", "description": "总跳数"},
            "total_loss_rate": {"type": "number", "description": "总丢包率"},
            "total_rtt_avg": {"type": "number", "description": "总平均RTT"},
            "bottleneck_hops": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "瓶颈跳数（丢包率>10%或延迟突增）"
            },
            "path_complete": {"type": "boolean", "description": "路径是否完整到达目标"},
            "error_message": {"type": "string", "description": "错误信息"},
        },
        "required": ["success", "host", "hops", "total_hops"],
    },
)
class MtrTool:
    """MTR综合路由追踪工具
    
    组合使用traceroute和ping工具，对每一跳进行多次探测
    统计每跳的丢包率、延迟分布和路径质量
    """
    
    def __init__(self, dispatcher: Optional[ToolDispatcher] = None):
        """初始化MTR工具
        
        Args:
            dispatcher: 工具调度器，如果为None则创建新实例
        """
        self.dispatcher = dispatcher or ToolDispatcher()
    
    async def execute(self, request: ToolRequest, ctx: FlowContext) -> ToolResponse:
        """执行MTR探测
        
        Args:
            request: 工具请求，parameters包含:
                - host: str (必填) 目标主机
                - max_hops: int (可选) 最大跳数，默认30
                - count: int (可选) 每跳探测次数，默认10
                - interval: float (可选) 探测间隔(秒)，默认1.0
                - timeout: int (可选) 超时秒数，默认5
                - packet_size: int (可选) 包大小，默认56
            ctx: 流程上下文
            
        Returns:
            ToolResponse: 探测结果
        """
        # 1. 参数解析
        params = request.parameters
        host = params.get("host")
        max_hops = params.get("max_hops", 30)
        count = params.get("count", 10)
        interval = params.get("interval", 1.0)
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
        
        if not isinstance(count, int) or count < 1 or count > 20:
            return ToolResponse(
                success=False,
                error_code="VAL_001",
                error_message="count参数必须是1-20之间的整数",
                trace_id=ctx.trace_id
            )
        
        # 3. 执行探测
        try:
            logger.info(
                f"开始MTR探测: {host}, max_hops={max_hops}, count={count}, "
                f"interval={interval}s",
                extra={"trace_id": ctx.trace_id}
            )
            
            start_time = asyncio.get_event_loop().time()
            
            # 3.1 获取路径信息
            path_info = await self._get_path_info(host, max_hops, timeout, ctx)
            if not path_info["success"]:
                return ToolResponse(
                    success=False,
                    error_code=path_info.get("error_code", "TOOL_002"),
                    error_message=path_info.get("error_message", "获取路径信息失败"),
                    trace_id=ctx.trace_id
                )
            
            hops = path_info["hops"]
            resolved_ip = path_info.get("resolved_ip", host)
            
            # 3.2 对每一跳进行ping统计
            hop_stats = await self._probe_hops(
                hops, count, interval, timeout, packet_size, ctx
            )
            
            # 3.3 分析路径质量
            analysis = self._analyze_path(hop_stats)
            
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            
            # 4. 构建响应
            result = {
                "success": True,
                "host": host,
                "resolved_ip": resolved_ip,
                "hops": hop_stats,
                "total_hops": len(hop_stats),
                "total_loss_rate": analysis["total_loss_rate"],
                "total_rtt_avg": analysis["total_rtt_avg"],
                "bottleneck_hops": analysis["bottleneck_hops"],
                "path_complete": analysis["path_complete"],
            }
            
            logger.info(
                f"MTR探测完成: {host}, 跳数={len(hop_stats)}, "
                f"总丢包率={analysis['total_loss_rate']:.1%}, "
                f"总平均RTT={analysis['total_rtt_avg']:.1f}ms",
                extra={"trace_id": ctx.trace_id}
            )
            
            return ToolResponse(
                success=True,
                data=result,
                trace_id=ctx.trace_id,
                duration_ms=duration_ms
            )
            
        except asyncio.TimeoutError:
            logger.warning(
                f"MTR探测 {host} 超时", 
                extra={"trace_id": ctx.trace_id}
            )
            return ToolResponse(
                success=False,
                error_code="TOOL_TIMEOUT",
                error_message=f"MTR探测 {host} 超时",
                trace_id=ctx.trace_id
            )
        except Exception as e:
            logger.error(
                f"MTR探测失败: {e}", 
                extra={"trace_id": ctx.trace_id}
            )
            return ToolResponse(
                success=False,
                error_code="TOOL_002",
                error_message=str(e),
                trace_id=ctx.trace_id
            )
    
    async def _get_path_info(
        self, 
        host: str, 
        max_hops: int, 
        timeout: int,
        ctx: FlowContext
    ) -> Dict[str, Any]:
        """获取路径信息（使用traceroute）
        
        Args:
            host: 目标主机
            max_hops: 最大跳数
            timeout: 超时时间
            ctx: 流程上下文
            
        Returns:
            路径信息字典
        """
        try:
            # 调用traceroute工具
            traceroute_request = ToolRequest(
                parameters={
                    "host": host,
                    "max_hops": max_hops,
                    "timeout": timeout,
                },
                trace_id=ctx.trace_id
            )
            
            traceroute_response = await self.dispatcher.dispatch(
                "traceroute", traceroute_request, ctx
            )
            
            if not traceroute_response.success:
                return {
                    "success": False,
                    "error_code": traceroute_response.error_code,
                    "error_message": traceroute_response.error_message,
                }
            
            # 解析traceroute结果
            traceroute_data = traceroute_response.data
            hops = []
            
            for hop_info in traceroute_data.get("hops", []):
                hop = hop_info.get("hop")
                ip = hop_info.get("ip")
                hostname = hop_info.get("hostname")
                
                if ip and ip != "*":
                    hops.append({
                        "hop": hop,
                        "ip": ip,
                        "hostname": hostname,
                        "rtt_samples": [],  # 初始化为空，后续填充
                    })
            
            return {
                "success": True,
                "hops": hops,
                "resolved_ip": traceroute_data.get("resolved_ip", host),
            }
            
        except Exception as e:
            logger.error(f"获取路径信息失败: {e}", extra={"trace_id": ctx.trace_id})
            return {
                "success": False,
                "error_code": "TOOL_002",
                "error_message": f"获取路径信息失败: {e}",
            }
    
    async def _probe_hops(
        self,
        hops: List[Dict[str, Any]],
        count: int,
        interval: float,
        timeout: int,
        packet_size: int,
        ctx: FlowContext
    ) -> List[Dict[str, Any]]:
        """对每一跳进行ping统计
        
        Args:
            hops: 跳信息列表
            count: 每跳探测次数
            interval: 探测间隔
            timeout: 超时时间
            packet_size: 包大小
            ctx: 流程上下文
            
        Returns:
            每跳统计信息列表
        """
        if not hops:
            return []
        
        hop_stats = []
        
        for hop_info in hops:
            ip = hop_info["ip"]
            hop_num = hop_info["hop"]
            
            logger.debug(
                f"开始探测跳 {hop_num}: {ip}", 
                extra={"trace_id": ctx.trace_id}
            )
            
            # 对当前跳进行多次ping
            rtt_samples = []
            successful_probes = 0
            
            for probe_num in range(count):
                try:
                    # 调用ping工具
                    ping_request = ToolRequest(
                        parameters={
                            "host": ip,
                            "count": 1,  # 每次探测只发一个包
                            "timeout": timeout,
                            "packet_size": packet_size,
                        },
                        trace_id=ctx.trace_id
                    )
                    
                    ping_response = await self.dispatcher.dispatch(
                        "ping", ping_request, ctx
                    )
                    
                    if ping_response.success:
                        ping_data = ping_response.data
                        if ping_data.get("success"):
                            rtt = ping_data.get("rtt_avg")
                            if rtt:
                                rtt_samples.append(rtt)
                                successful_probes += 1
                    
                    # 等待间隔
                    if probe_num < count - 1:
                        await asyncio.sleep(interval)
                        
                except Exception as e:
                    logger.debug(
                        f"跳 {hop_num} 探测 {probe_num+1}/{count} 失败: {e}",
                        extra={"trace_id": ctx.trace_id}
                    )
            
            # 计算统计信息
            stats = self._calculate_hop_stats(
                hop_num, ip, hop_info.get("hostname"), 
                rtt_samples, successful_probes, count
            )
            
            hop_stats.append(stats)
            
            logger.debug(
                f"跳 {hop_num} 探测完成: 丢包率={stats['loss_rate']:.1%}, "
                f"平均RTT={stats['rtt_avg'] or 0:.1f}ms",
                extra={"trace_id": ctx.trace_id}
            )
        
        return hop_stats
    
    def _calculate_hop_stats(
        self,
        hop: int,
        ip: str,
        hostname: Optional[str],
        rtt_samples: List[float],
        successful_probes: int,
        total_probes: int
    ) -> Dict[str, Any]:
        """计算单跳统计信息
        
        Args:
            hop: 跳数
            ip: IP地址
            hostname: 主机名
            rtt_samples: RTT样本值
            successful_probes: 成功探测次数
            total_probes: 总探测次数
            
        Returns:
            跳统计信息字典
        """
        # 计算丢包率
        loss_rate = (total_probes - successful_probes) / total_probes
        
        # 计算RTT统计
        if rtt_samples:
            rtt_min = min(rtt_samples)
            rtt_max = max(rtt_samples)
            rtt_avg = statistics.mean(rtt_samples)
            
            if len(rtt_samples) > 1:
                rtt_stddev = statistics.stdev(rtt_samples)
            else:
                rtt_stddev = 0.0
        else:
            rtt_min = None
            rtt_max = None
            rtt_avg = None
            rtt_stddev = None
        
        # TODO: 添加地理位置和ASN信息（需要外部API）
        # 这里可以集成IP地理位置查询服务
        
        return {
            "hop": hop,
            "ip": ip,
            "hostname": hostname,
            "loss_rate": loss_rate,
            "rtt_min": rtt_min,
            "rtt_avg": rtt_avg,
            "rtt_max": rtt_max,
            "rtt_stddev": rtt_stddev,
            "rtt_samples": rtt_samples,
            "asn": None,  # 预留字段
            "country": None,  # 预留字段
            "isp": None,  # 预留字段
        }
    
    def _analyze_path(self, hop_stats: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析路径质量
        
        Args:
            hop_stats: 每跳统计信息
            
        Returns:
            路径分析结果
        """
        if not hop_stats:
            return {
                "total_loss_rate": 1.0,
                "total_rtt_avg": None,
                "bottleneck_hops": [],
                "path_complete": False,
            }
        
        # 计算总丢包率（最后一跳的丢包率）
        total_loss_rate = hop_stats[-1]["loss_rate"] if hop_stats else 1.0
        
        # 计算总平均RTT（最后一跳的平均RTT）
        total_rtt_avg = hop_stats[-1]["rtt_avg"] if hop_stats else None
        
        # 识别瓶颈跳
        bottleneck_hops = []
        
        for i, hop in enumerate(hop_stats):
            # 条件1: 丢包率 > 10%
            if hop["loss_rate"] > 0.10:
                bottleneck_hops.append(hop["hop"])
                continue
            
            # 条件2: 延迟突增（比前一跳增加 > 50%）
            if i > 0:
                prev_hop = hop_stats[i-1]
                if (prev_hop["rtt_avg"] and hop["rtt_avg"] and 
                    prev_hop["rtt_avg"] > 0):
                    increase_ratio = (hop["rtt_avg"] - prev_hop["rtt_avg"]) / prev_hop["rtt_avg"]
                    if increase_ratio > 0.5:
                        bottleneck_hops.append(hop["hop"])
        
        # 判断路径是否完整（最后一跳有RTT数据）
        path_complete = hop_stats[-1]["rtt_avg"] is not None if hop_stats else False
        
        return {
            "total_loss_rate": total_loss_rate,
            "total_rtt_avg": total_rtt_avg,
            "bottleneck_hops": bottleneck_hops,
            "path_complete": path_complete,
        }
    
    async def _get_geo_info(self, ip: str) -> dict:
        """获取IP地理位置信息（占位符实现）
        
        Args:
            ip: IP地址
            
        Returns:
            包含地理位置信息的字典
        """
        # 这是一个占位符实现，实际项目中可以集成IP地理位置服务
        # 例如：ip-api.com, ipinfo.io, maxmind等
        return {
            "ip": ip,
            "country": "Unknown",
            "region": "Unknown",
            "city": "Unknown",
            "isp": "Unknown",
            "asn": "Unknown"
        }
