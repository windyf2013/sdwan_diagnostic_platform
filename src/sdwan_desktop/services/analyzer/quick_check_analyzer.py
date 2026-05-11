"""
一键体检分析器（CLI和GUI共用）

提供统一的分析逻辑，避免CLI和GUI代码重复。
"""

from typing import Optional, List
import logging

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.core.types.diagnosis import DiagnosisEvidence
from sdwan_desktop.services.connectivity import ConnectivityTestResult, ProbeResult
from sdwan_desktop.services.dns_split import DnsSplitTestResult
from sdwan_desktop.services.analyzer.rule_context import QuickCheckContext
from sdwan_desktop.services.analyzer.rule_engine import RuleEngine

logger = logging.getLogger(__name__)


class QuickCheckAnalyzer:
    """一键体检分析器
    
    封装CLI和GUI共用的分析逻辑，包括：
    1. 构造QuickCheckContext
    2. 执行规则引擎评估
    3. 构建证据链
    """
    
    @staticmethod
    async def analyze(
        ctx: FlowContext,
        rule_engine: RuleEngine
    ) -> None:
        """执行一键体检分析
        
        Args:
            ctx: 流程上下文，必须包含以下数据：
                - system_snapshot: 系统快照
                - gateway_ping_result: 网关Ping结果
                - dns_results: DNS测试结果列表
                - domestic_connectivity: 国内连通性测试结果
                - international_connectivity: 国际连通性测试结果
                - dns_split_result: DNS分流测试结果
            rule_engine: 规则引擎实例
            
        Returns:
            None（结果通过ctx.set存储）
            
        Note:
            此方法会在ctx中设置：
            - rule_results: 规则评估结果
            - evidence_connectivity: 连通性测试证据
        """
        logger.info("开始执行一键体检分析", extra={"trace_id": ctx.trace_id})
        
        # 1. 从ctx获取所有探测结果（带空值防护）
        system_snapshot = ctx.get("system_snapshot")
        gateway_ping = ctx.get("gateway_ping_result")
        dns_results = ctx.get("dns_results") or []
        domestic_conn = ctx.get("domestic_connectivity") or []
        international_conn = ctx.get("international_connectivity") or []
        
        # DNS分流结果空值处理
        dns_split = ctx.get("dns_split_result")
        if dns_split is None:
            logger.warning(
                "DNS分流测试结果为None，使用默认空结果",
                extra={"trace_id": ctx.trace_id}
            )
            dns_split = DnsSplitTestResult(
                domain_results=[],
                split_domains=[],
                split_count=0,
                total_domains=0
            )
        
        # ✅ CPE链路分流结果空值处理（新增）
        cpe_link_routing = ctx.get("cpe_link_routing_result")
        if cpe_link_routing is None:
            logger.debug(
                "CPE链路分流测试结果未提供（可选步骤）",
                extra={"trace_id": ctx.trace_id}
            )
        
        # 2. 清理DNS结果（只保留有效的ProbeResult对象）
        clean_dns_results: List[ProbeResult] = []
        for r in dns_results:
            if isinstance(r, ProbeResult):
                clean_dns_results.append(r)
            else:
                logger.debug(
                    f"跳过无效的DNS结果类型: {type(r)}",
                    extra={"trace_id": ctx.trace_id}
                )
        
        # 3. 构造ConnectivityTestResult
        conn_result = ConnectivityTestResult(
            gateway_ping=gateway_ping,
            domestic_dns_results=clean_dns_results,
            international_dns_results=[],
            domestic_target_results=(
                domestic_conn if isinstance(domestic_conn, list) else []
            ),
            international_target_results=(
                international_conn if isinstance(international_conn, list) else []
            )
        )
        
        # 4. 构造QuickCheckContext
        qc_ctx = QuickCheckContext(
            system_info=system_snapshot,
            connectivity=conn_result,
            dns_split=dns_split
        )
        
        # 5. 执行规则引擎评估
        logger.info("执行规则引擎评估", extra={"trace_id": ctx.trace_id})
        rule_results = rule_engine.evaluate(qc_ctx)
        ctx.set("rule_results", rule_results)
        logger.info(
            f"规则引擎评估完成，触发{len([r for r in rule_results.results if r.triggered])}条规则",
            extra={"trace_id": ctx.trace_id}
        )
        
        # 6. 构建连通性测试证据链
        all_probes: List[ProbeResult] = []
        
        # 添加网关Ping结果
        if gateway_ping:
            all_probes.append(gateway_ping)
        
        # 添加DNS测试结果
        all_probes.extend(clean_dns_results)
        
        # 添加国内目标连通性结果
        if isinstance(domestic_conn, list):
            all_probes.extend(domestic_conn)
        
        # 添加国际目标连通性结果
        if isinstance(international_conn, list):
            all_probes.extend(international_conn)
        
        # 7. 创建并存储证据
        evidence = DiagnosisEvidence(
            step_name="connectivity_test",
            description="连通性测试原始探测数据",
            probe_results=all_probes,
            config_snapshots={
                "system_snapshot": system_snapshot,
                "dns_split_result": dns_split,
                "cpe_link_routing_result": cpe_link_routing,  # ✅ 新增：添加CPE链路分流结果
            }
        )
        ctx.set("evidence_connectivity", evidence)
        
        logger.info(
            f"一键体检分析完成，收集{len(all_probes)}个探测结果",
            extra={"trace_id": ctx.trace_id}
        )
