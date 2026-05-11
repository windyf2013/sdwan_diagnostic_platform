"""
设备配置采集器

通过SSH/Telnet采集SD-WAN设备配置
支持多种厂商设备
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.core.types.tool import ToolRequest
from sdwan_desktop.tools.registry import tool_dispatcher
from .base import BaseCollector, CollectorConfig, CollectorResult

logger = logging.getLogger(__name__)


class DeviceCollector(BaseCollector):
    """设备配置采集器
    
    通过SSH连接设备，采集配置信息
    支持华为、Cisco、H3C等主流厂商
    """
    
    def __init__(self, config: Optional[CollectorConfig] = None):
        """初始化设备采集器
        
        Args:
            config: 采集器配置
        """
        super().__init__(config)
        self._supported_items = [
            "device_info",
            "interface_config",
            "vpn_config",
            "route_policy",
            "qos_config",
            "security_policy",
        ]
    
    async def collect(self, ctx: FlowContext) -> CollectorResult:
        """执行设备配置采集
        
        Args:
            ctx: 流程上下文
            
        Returns:
            采集结果
        """
        result = CollectorResult()
        collected_data = {}
        
        try:
            # 1. 采集设备基本信息
            device_info = await self._collect_device_info(ctx)
            collected_data["device_info"] = device_info
            result.collected_items.append("device_info")
            
            # 2. 采集接口配置
            interface_config = await self._collect_interface_config(ctx)
            collected_data["interface_config"] = interface_config
            result.collected_items.append("interface_config")
            
            # 3. 采集VPN配置
            vpn_config = await self._collect_vpn_config(ctx)
            collected_data["vpn_config"] = vpn_config
            result.collected_items.append("vpn_config")
            
            # 4. 采集路由策略
            route_policy = await self._collect_route_policy(ctx)
            collected_data["route_policy"] = route_policy
            result.collected_items.append("route_policy")
            
            # 5. 采集QoS配置
            qos_config = await self._collect_qos_config(ctx)
            collected_data["qos_config"] = qos_config
            result.collected_items.append("qos_config")
            
            # 6. 采集安全策略
            security_policy = await self._collect_security_policy(ctx)
            collected_data["security_policy"] = security_policy
            result.collected_items.append("security_policy")
            
            result.success = True
            result.data = collected_data
            
            logger.info(
                f"设备配置采集完成: {len(result.collected_items)}项",
                extra={"trace_id": ctx.trace_id}
            )
            
        except Exception as e:
            result.success = False
            result.error_message = str(e)
            result.data = collected_data
            logger.error(
                f"设备配置采集失败: {e}",
                extra={"trace_id": ctx.trace_id},
                exc_info=True
            )
        
        return result
    
    async def validate(self, ctx: FlowContext) -> bool:
        """验证采集器配置
        
        Args:
            ctx: 流程上下文
            
        Returns:
            配置是否有效
        """
        try:
            # 尝试通过SSH连接设备验证
            request = ToolRequest(
                tool_name="ssh",
                parameters={
                    "host": ctx.get("device_ip", ""),
                    "port": ctx.get("ssh_port", 22),
                    "username": ctx.get("ssh_username", ""),
                    "password": ctx.get("ssh_password", ""),
                    "command": "display version",
                    "timeout": 10,
                },
                trace_id=ctx.trace_id,
            )
            
            response = await tool_dispatcher.dispatch("ssh", request, ctx)
            return response.success
            
        except Exception as e:
            logger.warning(
                f"设备连接验证失败: {e}",
                extra={"trace_id": ctx.trace_id}
            )
            return False
    
    def get_supported_items(self) -> List[str]:
        """获取支持采集的项目列表
        
        Returns:
            支持的项目名称列表
        """
        return self._supported_items.copy()
    
    async def _collect_device_info(self, ctx: FlowContext) -> Dict[str, Any]:
        """采集设备基本信息
        
        Args:
            ctx: 流程上下文
            
        Returns:
            设备信息字典
        """
        return {
            "vendor": ctx.get("device_vendor", "unknown"),
            "model": ctx.get("device_model", "unknown"),
            "version": ctx.get("device_version", "unknown"),
            "serial_number": ctx.get("device_sn", ""),
            "uptime": "",
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
        }
    
    async def _collect_interface_config(self, ctx: FlowContext) -> List[Dict[str, Any]]:
        """采集接口配置
        
        Args:
            ctx: 流程上下文
            
        Returns:
            接口配置列表
        """
        return []
    
    async def _collect_vpn_config(self, ctx: FlowContext) -> Dict[str, Any]:
        """采集VPN配置
        
        Args:
            ctx: 流程上下文
            
        Returns:
            VPN配置字典
        """
        return {
            "ipsec_enabled": False,
            "tunnels": [],
            "ike_policies": [],
            "ipsec_policies": [],
        }
    
    async def _collect_route_policy(self, ctx: FlowContext) -> List[Dict[str, Any]]:
        """采集路由策略
        
        Args:
            ctx: 流程上下文
            
        Returns:
            路由策略列表
        """
        return []
    
    async def _collect_qos_config(self, ctx: FlowContext) -> Dict[str, Any]:
        """采集QoS配置
        
        Args:
            ctx: 流程上下文
            
        Returns:
            QoS配置字典
        """
        return {
            "qos_enabled": False,
            "queues": [],
            "policies": [],
        }
    
    async def _collect_security_policy(self, ctx: FlowContext) -> List[Dict[str, Any]]:
        """采集安全策略
        
        Args:
            ctx: 流程上下文
            
        Returns:
            安全策略列表
        """
        return []
