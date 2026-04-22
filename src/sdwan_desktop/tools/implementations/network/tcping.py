"""
TCP端口探测工具 - TCP连通性测试

遵循 SDWAN_SPEC.md §2.4.1 工具约束
遵循 SDWAN_SPEC_PATCHES.md PATCH-003 装饰器规范
"""

import asyncio
import logging
import socket
import time
from typing import Any, Dict, Optional

from sdwan_desktop.core.types.tool import ToolRequest, ToolResponse
from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.tools.registry.decorator import tool_function

logger = logging.getLogger(__name__)


@tool_function(
    name="tcping",
    description="TCP端口连通性测试，测量连接建立时间",
    timeout=10,
    retry_count=1,
    input_schema={
        "type": "object",
        "properties": {
            "host": {"type": "string", "description": "目标主机IP或域名"},
            "port": {"type": "integer", "minimum": 1, "maximum": 65535, "description": "目标端口"},
            "timeout": {"type": "integer", "minimum": 1, "maximum": 30, "default": 5},
            "count": {"type": "integer", "minimum": 1, "maximum": 10, "default": 3},
            "source_ip": {"type": "string", "description": "源IP地址（可选）"},
            "source_port": {"type": "integer", "minimum": 1, "maximum": 65535, "description": "源端口（可选）"},
        },
        "required": ["host", "port"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "host": {"type": "string", "description": "目标主机"},
            "port": {"type": "integer", "description": "目标端口"},
            "port_open": {"type": "boolean", "description": "端口是否开放"},
            "resolved_ip": {"type": "string", "description": "解析后的IP地址"},
            "response_times": {
                "type": "array",
                "items": {"type": "number"},
                "description": "每次探测的响应时间(ms)"
            },
            "response_time_min": {"type": "number", "description": "最小响应时间(ms)"},
            "response_time_avg": {"type": "number", "description": "平均响应时间(ms)"},
            "response_time_max": {"type": "number", "description": "最大响应时间(ms)"},
            "response_time_stddev": {"type": "number", "description": "响应时间标准差"},
            "loss_rate": {"type": "number", "description": "丢包率(0-1)"},
            "total_probes": {"type": "integer", "description": "总探测次数"},
            "successful_probes": {"type": "integer", "description": "成功次数"},
            "error_message": {"type": "string", "description": "错误信息"},
            "banner": {"type": "string", "description": "服务banner（如果获取到）"},
        },
        "required": ["success", "host", "port", "port_open", "response_times"],
    },
)
class TcpPortTool:
    """TCP端口探测工具
    
    通过TCP三次握手测试端口连通性
    支持多次探测统计响应时间和丢包率
    """
    
    async def execute(self, request: ToolRequest, ctx: FlowContext) -> ToolResponse:
        """执行TCP端口探测
        
        Args:
            request: 工具请求，parameters包含:
                - host: str (必填) 目标主机
                - port: int (必填) 目标端口
                - timeout: int (可选) 超时秒数，默认5
                - count: int (可选) 探测次数，默认3
                - source_ip: str (可选) 源IP地址
                - source_port: int (可选) 源端口
            ctx: 流程上下文
            
        Returns:
            ToolResponse: 探测结果
        """
        # 1. 参数解析
        params = request.parameters
        host = params.get("host")
        port = params.get("port")
        timeout = params.get("timeout", 5)
        count = params.get("count", 3)
        source_ip = params.get("source_ip")
        source_port = params.get("source_port")
        
        # 2. 参数校验
        if not host:
            return ToolResponse(
                success=False,
                error_code="VAL_002",
                error_message="缺少必填参数: host",
                trace_id=ctx.trace_id
            )
        
        if not port or not isinstance(port, int) or port < 1 or port > 65535:
            return ToolResponse(
                success=False,
                error_code="VAL_001",
                error_message="port参数必须是1-65535之间的整数",
                trace_id=ctx.trace_id
            )
        
        if not isinstance(count, int) or count < 1 or count > 10:
            return ToolResponse(
                success=False,
                error_code="VAL_001",
                error_message="count参数必须是1-10之间的整数",
                trace_id=ctx.trace_id
            )
        
        # 3. 执行探测
        try:
            logger.info(
                f"开始TCP端口探测: {host}:{port}, count={count}, timeout={timeout}s",
                extra={"trace_id": ctx.trace_id}
            )
            
            start_time = asyncio.get_event_loop().time()
            
            # 解析主机名
            resolved_ip = await self._resolve_hostname(host)
            if not resolved_ip:
                return ToolResponse(
                    success=False,
                    error_code="TOOL_002",
                    error_message=f"无法解析主机名: {host}",
                    trace_id=ctx.trace_id
                )
            
            # 执行多次探测
            results = await self._probe_port(
                resolved_ip, port, count, timeout, source_ip, source_port
            )
            
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            
            # 4. 计算统计信息
            stats = self._calculate_statistics(results)
            
            # 5. 构建响应
            result = {
                "success": True,
                "host": host,
                "port": port,
                "port_open": stats["port_open"],
                "resolved_ip": resolved_ip,
                "response_times": stats["response_times"],
                "response_time_min": stats["response_time_min"],
                "response_time_avg": stats["response_time_avg"],
                "response_time_max": stats["response_time_max"],
                "response_time_stddev": stats["response_time_stddev"],
                "loss_rate": stats["loss_rate"],
                "total_probes": count,
                "successful_probes": stats["successful_probes"],
                "banner": stats.get("banner"),
            }
            
            logger.info(
                f"TCP端口探测完成: {host}:{port}, "
                f"开放={stats['port_open']}, "
                f"平均响应时间={stats['response_time_avg'] if stats['response_time_avg'] is not None else 'N/A'}ms, "
                f"丢包率={stats['loss_rate']:.1%}",
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
                f"TCP端口探测 {host}:{port} 超时", 
                extra={"trace_id": ctx.trace_id}
            )
            return ToolResponse(
                success=False,
                error_code="TOOL_TIMEOUT",
                error_message=f"TCP端口探测 {host}:{port} 超时",
                trace_id=ctx.trace_id
            )
        except Exception as e:
            logger.error(
                f"TCP端口探测失败: {e}", 
                extra={"trace_id": ctx.trace_id}
            )
            return ToolResponse(
                success=False,
                error_code="TOOL_002",
                error_message=str(e),
                trace_id=ctx.trace_id
            )
    
    async def _resolve_hostname(self, hostname: str) -> Optional[str]:
        """解析主机名获取IP地址
        
        Args:
            hostname: 主机名
            
        Returns:
            IP地址，解析失败返回None
        """
        try:
            loop = asyncio.get_event_loop()
            addrinfo = await loop.getaddrinfo(
                hostname, None, 
                family=socket.AF_INET,  # 优先IPv4
                type=socket.SOCK_STREAM
            )
            if addrinfo:
                return addrinfo[0][4][0]
        except:
            try:
                # 尝试IPv6
                loop = asyncio.get_event_loop()
                addrinfo = await loop.getaddrinfo(
                    hostname, None, 
                    family=socket.AF_INET6,
                    type=socket.SOCK_STREAM
                )
                if addrinfo:
                    return addrinfo[0][4][0]
            except:
                pass
        
        return None
    
    async def _probe_port(
        self,
        ip: str,
        port: int,
        count: int,
        timeout: int,
        source_ip: Optional[str] = None,
        source_port: Optional[int] = None
    ) -> list:
        """执行端口探测
        
        Args:
            ip: 目标IP地址
            port: 目标端口
            count: 探测次数
            timeout: 超时时间(秒)
            source_ip: 源IP地址
            source_port: 源端口
            
        Returns:
            探测结果列表，每个元素为字典:
                - success: bool 是否成功
                - response_time: float 响应时间(ms)
                - error: str 错误信息
                - banner: str 服务banner
        """
        results = []
        
        for i in range(count):
            try:
                start_time = time.perf_counter()
                
                # 创建socket连接
                reader, writer = await asyncio.wait_for(
                    self._create_connection(ip, port, source_ip, source_port),
                    timeout=timeout
                )
                
                response_time = (time.perf_counter() - start_time) * 1000
                
                # 尝试读取banner
                banner = await self._read_banner(reader, timeout)
                
                # 关闭连接
                writer.close()
                await writer.wait_closed()
                
                results.append({
                    "success": True,
                    "response_time": response_time,
                    "error": None,
                    "banner": banner,
                })
                
                logger.debug(
                    f"TCP探测 {i+1}/{count}: {ip}:{port} 成功, "
                    f"响应时间={response_time:.1f}ms",
                    extra={"trace_id": asyncio.current_task().get_name()}
                )
                
            except asyncio.TimeoutError:
                results.append({
                    "success": False,
                    "response_time": None,
                    "error": "连接超时",
                    "banner": None,
                })
                logger.debug(
                    f"TCP探测 {i+1}/{count}: {ip}:{port} 超时",
                    extra={"trace_id": asyncio.current_task().get_name()}
                )
                
            except ConnectionRefusedError:
                results.append({
                    "success": False,
                    "response_time": None,
                    "error": "连接被拒绝",
                    "banner": None,
                })
                logger.debug(
                    f"TCP探测 {i+1}/{count}: {ip}:{port} 被拒绝",
                    extra={"trace_id": asyncio.current_task().get_name()}
                )
                
            except OSError as e:
                results.append({
                    "success": False,
                    "response_time": None,
                    "error": f"网络错误: {e}",
                    "banner": None,
                })
                logger.debug(
                    f"TCP探测 {i+1}/{count}: {ip}:{port} 网络错误: {e}",
                    extra={"trace_id": asyncio.current_task().get_name()}
                )
                
            except Exception as e:
                results.append({
                    "success": False,
                    "response_time": None,
                    "error": str(e),
                    "banner": None,
                })
                logger.debug(
                    f"TCP探测 {i+1}/{count}: {ip}:{port} 异常: {e}",
                    extra={"trace_id": asyncio.current_task().get_name()}
                )
            
            # 如果不是最后一次探测，等待一段时间
            if i < count - 1:
                await asyncio.sleep(0.5)
        
        return results
    
    async def _create_connection(
        self,
        ip: str,
        port: int,
        source_ip: Optional[str] = None,
        source_port: Optional[int] = None
    ):
        """创建TCP连接
        
        Args:
            ip: 目标IP地址
            port: 目标端口
            source_ip: 源IP地址
            source_port: 源端口
            
        Returns:
            (reader, writer) 元组
        """
        # 设置socket选项
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # 绑定源地址（如果指定）
        if source_ip or source_port:
            source_addr = (source_ip or "0.0.0.0", source_port or 0)
            sock.bind(source_addr)
        
        # 创建连接
        loop = asyncio.get_event_loop()
        transport, protocol = await loop.create_connection(
            lambda: asyncio.Protocol(),
            host=ip,
            port=port,
            sock=sock
        )
        
        # 获取reader/writer
        reader = asyncio.StreamReader()
        writer = asyncio.StreamWriter(
            transport, protocol, reader, loop
        )
        
        return reader, writer
    
    async def _read_banner(
        self, 
        reader: asyncio.StreamReader, 
        timeout: int
    ) -> Optional[str]:
        """尝试读取服务banner
        
        Args:
            reader: StreamReader对象
            timeout: 超时时间
            
        Returns:
            banner字符串，读取失败返回None
        """
        try:
            # 设置读取超时
            data = await asyncio.wait_for(
                reader.read(1024),
                timeout=1.0  # banner读取超时较短
            )
            
            if data:
                # 尝试解码为UTF-8，失败则使用latin-1
                try:
                    return data.decode('utf-8', errors='ignore').strip()
                except:
                    return data.decode('latin-1', errors='ignore').strip()
        
        except (asyncio.TimeoutError, ConnectionError):
            # 读取banner超时或连接错误是正常的
            pass
        except Exception:
            # 其他异常忽略
            pass
        
        return None
    
    def _calculate_statistics(self, results: list) -> Dict[str, Any]:
        """计算探测统计信息
        
        Args:
            results: 探测结果列表
            
        Returns:
            统计信息字典
        """
        # 提取成功的响应时间
        response_times = [
            r["response_time"] for r in results 
            if r["success"] and r["response_time"] is not None
        ]
        
        successful_probes = len(response_times)
        total_probes = len(results)
        
        # 计算基本统计
        if response_times:
            response_time_min = min(response_times)
            response_time_max = max(response_times)
            response_time_avg = sum(response_times) / len(response_times)
            
            # 计算标准差
            if len(response_times) > 1:
                variance = sum(
                    (rt - response_time_avg) ** 2 for rt in response_times
                ) / (len(response_times) - 1)
                response_time_stddev = variance ** 0.5
            else:
                response_time_stddev = 0.0
        else:
            response_time_min = None
            response_time_max = None
            response_time_avg = None
            response_time_stddev = None
        
        # 计算丢包率
        loss_rate = (total_probes - successful_probes) / total_probes if total_probes > 0 else 1.0

        
        # 判断端口是否开放（至少成功一次）
        port_open = successful_probes > 0
        
        # 获取banner（从第一次成功探测中获取）
        banner = None
        for result in results:
            if result["success"] and result.get("banner"):
                banner = result["banner"]
                break
        
        return {
            "port_open": port_open,
            "response_times": response_times,
            "response_time_min": response_time_min,
            "response_time_avg": response_time_avg,
            "response_time_max": response_time_max,
            "response_time_stddev": response_time_stddev,
            "loss_rate": loss_rate,
            "successful_probes": successful_probes,
            "banner": banner,
        }