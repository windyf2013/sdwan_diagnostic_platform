"""
诊断流程编排器

编排完整的诊断流程，协调各阶段执行
遵循 SDWAN_SPEC.md §2.3 流程规范
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.core.types.tool import ToolRequest, ToolResponse
from sdwan_desktop.tools.registry import tool_dispatcher
from sdwan_desktop.services.collector import DeviceCollector
from sdwan_desktop.services.analyzer.rule_engine import RuleEngine, RuleResult

logger = logging.getLogger(__name__)


class DiagnosticPhase(Enum):
    """诊断阶段"""
    INIT = "init"
    """初始化"""
    COLLECT = "collect"
    """配置采集"""
    CONNECTIVITY = "connectivity"
    """连通性测试"""
    DNS_TEST = "dns_test"
    """DNS测试"""
    ANALYSIS = "analysis"
    """规则分析"""
    REPORT = "report"
    """报告生成"""
    COMPLETED = "completed"
    """完成"""
    FAILED = "failed"
    """失败"""


@dataclass
class DiagnosticResult:
    """诊断结果"""
    success: bool = False
    """是否成功"""
    trace_id: str = ""
    """追踪ID"""
    start_time: Optional[datetime] = None
    """开始时间"""
    end_time: Optional[datetime] = None
    """结束时间"""
    phases: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    """各阶段结果"""
    rule_results: List[RuleResult] = field(default_factory=list)
    """规则执行结果"""
    summary: str = ""
    """诊断摘要"""
    recommendations: List[str] = field(default_factory=list)
    """建议列表"""
    errors: List[str] = field(default_factory=list)
    """错误列表"""


class DiagnosticFlow:
    """诊断流程编排器
    
    编排完整的诊断流程：
    1. 初始化阶段 - 准备环境和参数
    2. 配置采集阶段 - 采集设备配置
    3. 连通性测试阶段 - 测试网络连通性
    4. DNS测试阶段 - 测试DNS解析
    5. 规则分析阶段 - 执行诊断规则
    6. 报告生成阶段 - 生成诊断报告
    """
    
    def __init__(self, rule_engine: Optional[RuleEngine] = None):
        """初始化诊断流程
        
        Args:
            rule_engine: 规则引擎实例
        """
        self.rule_engine = rule_engine or RuleEngine()
        self._current_phase = DiagnosticPhase.INIT
        self._collector = DeviceCollector()
    
    async def execute(self, ctx: FlowContext) -> DiagnosticResult:
        """执行完整诊断流程
        
        Args:
            ctx: 流程上下文
            
        Returns:
            诊断结果
        """
        result = DiagnosticResult(
            trace_id=ctx.trace_id,
            start_time=datetime.now(),
        )
        
        try:
            # 阶段1: 初始化
            self._current_phase = DiagnosticPhase.INIT
            logger.info(f"开始诊断流程: trace_id={ctx.trace_id}", extra={"trace_id": ctx.trace_id})
            
            # 阶段2: 配置采集
            self._current_phase = DiagnosticPhase.COLLECT
            collect_result = await self._execute_collect_phase(ctx)
            result.phases["collect"] = {
                "success": collect_result.success,
                "items": collect_result.collected_items,
            }
            
            # 阶段3: 连通性测试
            self._current_phase = DiagnosticPhase.CONNECTIVITY
            connectivity_data = await self._execute_connectivity_phase(ctx)
            result.phases["connectivity"] = connectivity_data
            
            # 阶段4: DNS测试
            self._current_phase = DiagnosticPhase.DNS_TEST
            dns_data = await self._execute_dns_phase(ctx)
            result.phases["dns_test"] = dns_data
            
            # 阶段5: 规则分析
            self._current_phase = DiagnosticPhase.ANALYSIS
            analysis_data = await self._execute_analysis_phase(
                ctx, collect_result, connectivity_data, dns_data
            )
            result.rule_results = analysis_data.get("rule_results", [])
            result.phases["analysis"] = analysis_data
            
            # 阶段6: 报告生成
            self._current_phase = DiagnosticPhase.REPORT
            report_data = await self._execute_report_phase(ctx, result)
            result.summary = report_data.get("summary", "")
            result.recommendations = report_data.get("recommendations", [])
            result.phases["report"] = report_data
            
            # 完成
            self._current_phase = DiagnosticPhase.COMPLETED
            result.success = True
            
            logger.info(
                f"诊断流程完成: trace_id={ctx.trace_id}, "
                f"规则通过={sum(1 for r in result.rule_results if r.passed)}/"
                f"{len(result.rule_results)}",
                extra={"trace_id": ctx.trace_id}
            )
            
        except Exception as e:
            self._current_phase = DiagnosticPhase.FAILED
            result.success = False
            result.errors.append(str(e))
            logger.error(
                f"诊断流程失败: {e}",
                extra={"trace_id": ctx.trace_id},
                exc_info=True
            )
        
        finally:
            result.end_time = datetime.now()
        
        return result
    
    def get_current_phase(self) -> DiagnosticPhase:
        """获取当前阶段
        
        Returns:
            当前阶段
        """
        return self._current_phase
    
    async def _execute_collect_phase(self, ctx: FlowContext) -> Any:
        """执行配置采集阶段
        
        Args:
            ctx: 流程上下文
            
        Returns:
            采集结果
        """
        logger.info("阶段2: 开始配置采集", extra={"trace_id": ctx.trace_id})
        
        # 采集系统信息
        system_request = ToolRequest(
            tool_name="windows_system",
            parameters={
                "collect_adapters": True,
                "collect_routes": True,
                "collect_dns": True,
                "collect_proxy": True,
                "collect_firewall": True,
                "collect_arp": True,
                "collect_connections": False,
                "collect_ipv6": True,
            },
            trace_id=ctx.trace_id,
        )
        
        system_response = await tool_dispatcher.dispatch("windows_system", system_request, ctx)
        
        if system_response.success:
            ctx.set("system_snapshot", system_response.data.get("snapshot", {}))
        
        # 采集设备配置
        device_result = await self._collector.collect(ctx)
        
        return device_result
    
    async def _execute_connectivity_phase(self, ctx: FlowContext) -> Dict[str, Any]:
        """执行连通性测试阶段
        
        Args:
            ctx: 流程上下文
            
        Returns:
            连通性测试数据
        """
        logger.info("阶段3: 开始连通性测试", extra={"trace_id": ctx.trace_id})
        
        connectivity_data = {
            "gateway_ping": {},
            "target_ping": {},
            "tcp_ports": [],
        }
        
        # 获取默认网关
        gateway = ctx.get("default_gateway", "8.8.8.8")
        
        # Ping网关
        gateway_request = ToolRequest(
            tool_name="ping",
            parameters={
                "host": gateway,
                "count": 4,
                "timeout": 5,
            },
            trace_id=ctx.trace_id,
        )
        
        gateway_response = await tool_dispatcher.dispatch("ping", gateway_request, ctx)
        connectivity_data["gateway_ping"] = gateway_response.data if gateway_response.success else {
            "success": False,
            "error_message": gateway_response.error_message,
        }
        
        # Ping目标地址
        target = ctx.get("target_host", "8.8.8.8")
        if target != gateway:
            target_request = ToolRequest(
                tool_name="ping",
                parameters={
                    "host": target,
                    "count": 4,
                    "timeout": 5,
                },
                trace_id=ctx.trace_id,
            )
            
            target_response = await tool_dispatcher.dispatch("ping", target_request, ctx)
            connectivity_data["target_ping"] = target_response.data if target_response.success else {
                "success": False,
                "error_message": target_response.error_message,
            }
        
        # TCP端口测试
        tcp_targets = ctx.get("tcp_targets", [])
        for tcp_target in tcp_targets:
            port_request = ToolRequest(
                tool_name="tcp_port",
                parameters={
                    "host": tcp_target.get("host", target),
                    "port": tcp_target.get("port", 443),
                    "timeout": 5,
                },
                trace_id=ctx.trace_id,
            )
            
            port_response = await tool_dispatcher.dispatch("tcp_port", port_request, ctx)
            connectivity_data["tcp_ports"].append({
                "target": tcp_target,
                "result": port_response.data if port_response.success else {
                    "success": False,
                    "error_message": port_response.error_message,
                },
            })
        
        return connectivity_data
    
    async def _execute_dns_phase(self, ctx: FlowContext) -> Dict[str, Any]:
        """执行DNS测试阶段
        
        Args:
            ctx: 流程上下文
            
        Returns:
            DNS测试数据
        """
        logger.info("阶段4: 开始DNS测试", extra={"trace_id": ctx.trace_id})
        
        dns_data = {
            "results": [],
        }
        
        # 获取要解析的域名列表
        domains = ctx.get("dns_domains", [
            "www.baidu.com",
            "www.google.com",
        ])
        
        for domain in domains:
            dns_request = ToolRequest(
                tool_name="dns",
                parameters={
                    "domain": domain,
                    "record_type": "A",
                    "timeout": 5,
                },
                trace_id=ctx.trace_id,
            )
            
            dns_response = await tool_dispatcher.dispatch("dns", dns_request, ctx)
            dns_data["results"].append({
                "domain": domain,
                "result": dns_response.data if dns_response.success else {
                    "success": False,
                    "error_message": dns_response.error_message,
                },
            })
        
        return dns_data
    
    async def _execute_analysis_phase(
        self,
        ctx: FlowContext,
        collect_result: Any,
        connectivity_data: Dict[str, Any],
        dns_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行规则分析阶段
        
        Args:
            ctx: 流程上下文
            collect_result: 采集结果
            connectivity_data: 连通性数据
            dns_data: DNS数据
            
        Returns:
            分析结果
        """
        logger.info("阶段5: 开始规则分析", extra={"trace_id": ctx.trace_id})
        
        # 构建分析数据
        analysis_data = {
            "system_info": ctx.get("system_snapshot", {}),
            "device_config": collect_result.data if hasattr(collect_result, 'data') else {},
        }
        
        # 合并连通性数据
        analysis_data.update(connectivity_data)
        
        # 合并DNS数据
        if dns_data.get("results"):
            analysis_data["dns_result"] = dns_data["results"][0].get("result", {})
        
        # 执行规则评估
        rule_results = await self.rule_engine.evaluate_all(analysis_data, ctx)
        
        return {
            "rule_results": rule_results,
            "passed_count": sum(1 for r in rule_results if r.passed),
            "failed_count": sum(1 for r in rule_results if not r.passed),
            "total_count": len(rule_results),
        }
    
    async def _execute_report_phase(
        self,
        ctx: FlowContext,
        result: DiagnosticResult
    ) -> Dict[str, Any]:
        """执行报告生成阶段
        
        Args:
            ctx: 流程上下文
            result: 诊断结果
            
        Returns:
            报告数据
        """
        logger.info("阶段6: 开始报告生成", extra={"trace_id": ctx.trace_id})
        
        # 生成摘要
        total_rules = len(result.rule_results)
        passed_rules = sum(1 for r in result.rule_results if r.passed)
        failed_rules = total_rules - passed_rules
        
        if failed_rules == 0:
            summary = f"诊断完成：所有 {total_rules} 项检查通过，网络状态正常。"
        else:
            summary = f"诊断完成：{total_rules} 项检查中 {passed_rules} 项通过，{failed_rules} 项异常。"
        
        # 收集建议
        recommendations = []
        for rule_result in result.rule_results:
            if not rule_result.passed:
                recommendations.extend(rule_result.suggestions)
        
        # 去重
        recommendations = list(dict.fromkeys(recommendations))
        
        return {
            "summary": summary,
            "recommendations": recommendations,
            "total_rules": total_rules,
            "passed_rules": passed_rules,
            "failed_rules": failed_rules,
        }
