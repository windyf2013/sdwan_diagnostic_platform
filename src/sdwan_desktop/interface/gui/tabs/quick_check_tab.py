import json
import os
import uuid
import asyncio
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar, QFileDialog
)
from PySide6.QtCore import Qt, Signal, QThread

from sdwan_desktop.core.types.diagnosis import DiagnosisResult, Severity, RootCause, Recommendation, DiagnosisEvidence
from sdwan_desktop.services.reporter.html_builder import HtmlReportBuilder


class QuickCheckWorker(QThread):
    """一键体检后台工作线程"""
    progress_updated = Signal(int, str)  # (百分比, 状态文本)
    diagnosis_completed = Signal(object)  # DiagnosisResult
    diagnosis_failed = Signal(str)

    def __init__(self):
        super().__init__()
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    async def _run_async(self):
        """使用统一的 FlowRuntime 执行一键体检流程"""
        from sdwan_desktop.flow.definitions.quick_check import QUICK_CHECK_FLOW
        from sdwan_desktop.runtime.engine import FlowRuntime
        from sdwan_desktop.core.types.context import FlowContext
        
        # 初始化服务（与 CLI 保持一致）
        from sdwan_desktop.services.collector.windows_collector import WindowsCollector
        from sdwan_desktop.services.connectivity import ConnectivityTester
        from sdwan_desktop.services.dns_split import DnsSplitTester
        from sdwan_desktop.services.analyzer.rule_engine import RuleEngine
        from sdwan_desktop.services.analyzer.rules import GATEWAY_RULES, DNS_RULES, SYSTEM_RULES, CONNECTIVITY_RULES
        from sdwan_desktop.services.reporter.html_builder import HtmlReportBuilder
        
        trace_id = str(uuid.uuid4())
        ctx = FlowContext(trace_id=trace_id)
        
        collector = WindowsCollector()
        connectivity_tester = ConnectivityTester()
        dns_split_tester = DnsSplitTester()
        rule_engine = RuleEngine()
        rule_engine.register_rules(GATEWAY_RULES)
        rule_engine.register_rules(DNS_RULES)
        rule_engine.register_rules(SYSTEM_RULES)
        rule_engine.register_rules(CONNECTIVITY_RULES)
        report_builder = HtmlReportBuilder()
        
        # 定义步骤处理器映射（与 CLI 完全一致）
        from sdwan_desktop.services.analyzer.rule_context import QuickCheckContext
        from sdwan_desktop.services.connectivity import ConnectivityTestResult
        from sdwan_desktop.services.dns_split import DnsSplitTestResult
        
        async def step_collect(ctx: FlowContext):
            if self._is_cancelled: return
            self.progress_updated.emit(10, "正在采集系统信息...")
            snapshot = await collector.collect(ctx)
            ctx.set("system_snapshot", snapshot)
            return snapshot

        async def step_gateway(ctx: FlowContext):
            if self._is_cancelled: return
            self.progress_updated.emit(30, "正在测试网关连通性...")
            snapshot = ctx.get("system_snapshot")
            gateway_ip = None
            if snapshot and snapshot.ip_config:
                gateway_ip = snapshot.ip_config.default_gateway
            
            # 如果 ip_config 中没有，尝试从 primary_adapter 获取
            if not gateway_ip and snapshot and snapshot.primary_adapter:
                gateway_ip = snapshot.primary_adapter.default_gateway
                
            result = None
            if gateway_ip:
                result = await connectivity_tester.test_gateway(gateway_ip, ctx)
            ctx.set("gateway_ping_result", result)
            return result

        async def step_dns(ctx: FlowContext):
            if self._is_cancelled: return
            self.progress_updated.emit(50, "正在测试 DNS 解析...")
            snapshot = ctx.get("system_snapshot")
            dns_servers = []
            if snapshot and snapshot.ip_config:
                dns_servers = snapshot.ip_config.dns_servers
            
            # 如果 ip_config 中没有DNS服务器，使用默认值
            if not dns_servers:
                dns_servers = ["114.114.114.114"]
            
            results = await connectivity_tester.test_domestic_dns(dns_servers, ctx)
            ctx.set("dns_results", results)
            return results

        async def step_internet(ctx: FlowContext):
            if self._is_cancelled: return
            self.progress_updated.emit(70, "正在测试互联网连通性...")
            
            # ✅ 使用统一域名集（与CLI保持一致）
            from sdwan_desktop.flow.definitions.quick_check import DEFAULT_TEST_DOMAINS
            from sdwan_desktop.services.connectivity import ConnectivityTester
            
            connectivity_tester = ConnectivityTester()
            
            # ✅ 调用优化后的方法，自动分类域名
            result = await connectivity_tester.test_internet_optimized(
                domains=DEFAULT_TEST_DOMAINS,
                ctx=ctx,
                use_cache=True
            )
            
            ctx.set("internet_connectivity_result", result)
            return result

        async def step_dns_split(ctx: FlowContext):
            if self._is_cancelled: return
            
            # ✅ 检查连通性是否失败，失败则跳过
            connectivity_failed = ctx.get("connectivity_failed", False)
            if connectivity_failed:
                self.progress_updated.emit(80, "跳过DNS分流测试（连通性失败）")
                from sdwan_desktop.services.dns_split import DnsSplitTestResult
                result = DnsSplitTestResult(
                    total_domains=0,
                    errors=["连通性测试失败，跳过DNS分流测试"]
                )
                ctx.set("dns_split_result", result)
                return result
            
            self.progress_updated.emit(80, "正在测试DNS分流...")
            
            snapshot = ctx.get("system_snapshot")
            system_dns_servers = []
            if snapshot and snapshot.ip_config:
                system_dns_servers = snapshot.ip_config.dns_servers
            
            # ✅ 按需求：仅使用系统默认DNS和8.8.8.8
            domestic_dns = system_dns_servers[:1] if system_dns_servers else ["114.114.114.114"]
            international_dns = ["8.8.8.8"]
            
            # ✅ 使用统一域名集（3个核心域名）
            from sdwan_desktop.flow.definitions.quick_check import DEFAULT_TEST_DOMAINS
            test_domains = DEFAULT_TEST_DOMAINS
            
            try:
                import asyncio
                
                # ✅ 内部超时保护：60秒（比 Flow 的 60 秒一致）
                result = await asyncio.wait_for(
                    dns_split_tester.test_optimized(
                        domains=test_domains,  # ✅ 使用统一的精简域名集
                        domestic_dns=domestic_dns,
                        international_dns=international_dns,
                        ctx=ctx,
                        use_cache=True  # ✅ 启用结果缓存复用
                    ),
                    timeout=60  # ✅ 双层保护：Flow层60秒
                )
                
                ctx.set("dns_split_result", result)
                return result
                
            except asyncio.TimeoutError:
                logger.error(
                    f"DNS分流测试内部超时（60秒），已完成部分测试",
                    extra={"trace_id": ctx.trace_id}
                )
                # ✅ 创建错误结果并保存到Context，确保数据链路完整
                from sdwan_desktop.services.dns_split import DnsSplitTestResult, DomainDnsResult
                result = DnsSplitTestResult(
                    total_domains=len(test_domains),
                    errors=[f"DNS分流测试超时（60秒），可能原因：DNS服务器响应慢或网络延迟高"]
                )
                # 为未完成的域名创建空结果
                for domain in test_domains:
                    empty_result = DomainDnsResult(domain=domain)
                    empty_result.is_split = False
                    empty_result.split_description = "测试超时，未完成"
                    result.domain_results.append(empty_result)
                
                ctx.set("dns_split_result", result)
                return result

        async def step_cpe_link_routing(ctx: FlowContext):
            if self._is_cancelled: return
            
            # ✅ 检查连通性是否失败，失败则跳过
            connectivity_failed = ctx.get("connectivity_failed", False)
            if connectivity_failed:
                self.progress_updated.emit(85, "跳过CPE链路追踪（连通性失败）")
                from sdwan_desktop.services.dns_split import CpeLinkRouteResult
                result = CpeLinkRouteResult(
                    total_domains_tested=0,
                    domain_results=[],
                    detected_links=[],
                    link_distribution={},
                    is_multi_link=False,
                    multi_link_count=0,
                    errors=["连通性测试失败，跳过CPE链路追踪"]
                )
                ctx.set("cpe_link_routing_result", result)
                return result
            
            self.progress_updated.emit(85, "正在检测CPE链路分流（精简版，约100-110秒）...")
            
            try:
                import asyncio
                
                # ✅ 使用精简域名集（4个核心域名）
                from sdwan_desktop.flow.definitions.quick_check import DEFAULT_TEST_DOMAINS
                test_domains = DEFAULT_TEST_DOMAINS
                
                # ✅ 检查并展示缓存使用情况
                dns_cache_dict = ctx.get("dns_resolution_cache")
                if dns_cache_dict:
                    print(f"   ℹ️ 检测到DNS解析缓存: {len(dns_cache_dict)}个域名可用")
                
                # ✅ 内部超时保护：110秒（按规范：7跳×5秒×3次+缓冲）
                result = await asyncio.wait_for(
                    dns_split_tester.test_cpe_link_routing_optimized(
                        domains=test_domains,
                        max_hops=7,  # ✅ 固定7跳
                        cpe_exit_hop=2,
                        ctx=ctx,
                        use_cache=True  # ✅ 启用结果缓存复用
                    ),
                    timeout=110  # ✅ 按规范：105秒+5秒缓冲
                )
                
                ctx.set("cpe_link_routing_result", result)
                return result
                
            except asyncio.TimeoutError:
                # ✅ 关键修复：内部超时后，存入错误结果并返回，避免 Flow 引擎强制中断
                from sdwan_desktop.services.dns_split import CpeLinkRouteResult
                
                error_result = CpeLinkRouteResult(
                    total_domains_tested=0,
                    domain_results=[],
                    detected_links=[],
                    link_distribution={},
                    is_multi_link=False,
                    multi_link_count=0,
                    errors=[f"CPE链路分流测试超时（70秒限制）"]
                )
                
                ctx.set("cpe_link_routing_result", error_result)
                
                # 记录详细错误日志
                import logging
                logger = logging.getLogger(__name__)
                logger.error(
                    f"CPE链路分流测试超时: 70秒内未完成",
                    extra={"trace_id": ctx.trace_id},
                    exc_info=True
                )
                
                return error_result
                
            except Exception as e:
                # ✅ 其他异常处理
                from sdwan_desktop.services.dns_split import CpeLinkRouteResult
                
                error_result = CpeLinkRouteResult(
                    total_domains_tested=0,
                    domain_results=[],
                    detected_links=[],
                    link_distribution={},
                    is_multi_link=False,
                    multi_link_count=0,
                    errors=[f"CPE链路分流测试失败: {str(e)}"]
                )
                
                ctx.set("cpe_link_routing_result", error_result)
                
                # 记录详细错误日志
                import logging
                logger = logging.getLogger(__name__)
                logger.error(
                    f"CPE链路分流测试异常: {e}",
                    extra={"trace_id": ctx.trace_id},
                    exc_info=True
                )
                
                return error_result

        async def step_analyze(ctx: FlowContext):
            if self._is_cancelled: return
            self.progress_updated.emit(90, "正在分析诊断结果...")
            
            # ✅ 使用共用的QuickCheckAnalyzer服务（与CLI保持一致）
            from sdwan_desktop.services.analyzer.quick_check_analyzer import QuickCheckAnalyzer
            
            await QuickCheckAnalyzer.analyze(ctx, rule_engine)
            
            return ctx.get("rule_results")

        async def step_conclusion(ctx: FlowContext):
            if self._is_cancelled: return
            
            rule_results = ctx.get("rule_results")
            if not rule_results:
                return
                
            root_causes = []
            recommendations = []
            confidence = 1.0
            
            for rr in rule_results.results:
                if rr.triggered:
                    root_causes.append(RootCause(
                        cause_id=rr.rule_id,
                        title=rr.name,
                        description=rr.message,
                        severity=rr.severity,
                        confidence=rr.confidence,
                        matched_rules=[rr.rule_id]
                    ))
                    if rr.suggestion:
                        recommendations.append(Recommendation(
                            action=rr.suggestion,
                            priority=1 if rr.severity in [Severity.CRITICAL, Severity.ERROR] else 2,
                            expected_outcome=rr.message
                        ))
                    confidence = min(confidence, rr.confidence)
            
            # 如果没有触发任何规则，说明网络正常
            if not root_causes:
                confidence = 1.0
            
            # 获取证据链（与CLI保持一致）
            evidence_connectivity = ctx.get("evidence_connectivity")
            evidences = [evidence_connectivity] if evidence_connectivity else []
                    
            diagnosis_result = DiagnosisResult(
                trace_id=ctx.trace_id,
                diagnosis_type="quick_check",
                summary=f"检测到 {len(root_causes)} 个问题" if root_causes else "网络状态正常",
                severity=root_causes[0].severity if root_causes else Severity.INFO,
                root_causes=root_causes,
                recommendations=recommendations,
                evidences=evidences,  # 添加证据链
                overall_confidence=confidence,
                timestamp=datetime.now().isoformat()
            )
            
            ctx.set("diagnosis_result", diagnosis_result)
            return diagnosis_result

        async def step_report(ctx: FlowContext):
            if self._is_cancelled: return
            self.progress_updated.emit(100, "生成报告...")
            
            diagnosis_result = ctx.get("diagnosis_result")
            if not diagnosis_result:
                return
            
            # ✅ 显式将 DNS 服务器连通性测试结果存入证据的 probe_results（与CLI保持一致）
            dns_results = ctx.get("dns_results")
            if dns_results and diagnosis_result:
                from sdwan_desktop.core.types.diagnosis import DiagnosisEvidence
                from sdwan_desktop.core.types.probe import ProbeTarget, ProbeProtocol, ProbeResult, ProbeMetric, ProbeStatus
                
                # 查找或创建对应的 Evidence
                target_evidence = None
                for ev in diagnosis_result.evidences:
                    if hasattr(ev, 'probe_results'):
                        target_evidence = ev
                        break
                
                if not target_evidence:
                    target_evidence = DiagnosisEvidence(
                        step_name="step-dns",
                        description="DNS服务器连通性测试原始数据"
                    )
                    diagnosis_result.evidences.append(target_evidence)
                
                if hasattr(target_evidence, 'probe_results'):
                    # 将 ConnectivityProbeResult 转换为 ProbeResult 格式
                    for dns_res in dns_results:
                        probe_result = ProbeResult(
                            target=ProbeTarget(host=dns_res.target, protocol=ProbeProtocol.DNS),
                            status=ProbeStatus.SUCCESS if dns_res.success else ProbeStatus.FAILED,
                            success=dns_res.success,
                            metrics=ProbeMetric(
                                rtt_avg=dns_res.metrics.rtt_avg if dns_res.metrics else None,
                                resolved_ips=[]
                            ),
                            duration_ms=dns_res.duration_ms if hasattr(dns_res, 'duration_ms') else 0.0
                        )
                        target_evidence.probe_results.append(probe_result)
            
            # 显式将 DNS 分流结果存入证据的 config_snapshots，确保 HTML 构建器能抓取到（与CLI保持一致）
            dns_split_result = ctx.get("dns_split_result")
            if dns_split_result and diagnosis_result:
                target_evidence = None
                for ev in diagnosis_result.evidences:
                    if hasattr(ev, 'config_snapshots'):
                        target_evidence = ev
                        break
                
                if not target_evidence:
                    target_evidence = DiagnosisEvidence(
                        step_name="step-dns-split",
                        description="DNS分流测试原始数据"
                    )
                    diagnosis_result.evidences.append(target_evidence)
                
                if hasattr(target_evidence, 'config_snapshots'):
                    target_evidence.config_snapshots["dns_split_result"] = dns_split_result

            # 将 CPE 链路分流结果存入证据
            cpe_link_result = ctx.get("cpe_link_routing_result")
            if cpe_link_result and diagnosis_result:
                target_evidence = None
                for ev in diagnosis_result.evidences:
                    if hasattr(ev, 'config_snapshots'):
                        target_evidence = ev
                        break
                
                if not target_evidence:
                    target_evidence = DiagnosisEvidence(
                        step_name="step-cpe-link-routing",
                        description="CPE链路分流检测原始数据"
                    )
                    diagnosis_result.evidences.append(target_evidence)
                
                if hasattr(target_evidence, 'config_snapshots'):
                    target_evidence.config_snapshots["cpe_link_routing_result"] = cpe_link_result
            
            # 生成 HTML 报告
            output_path = f"./reports/quick_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            
            report_builder.build_quick_check_report(diagnosis_result, Path(output_path))
            ctx.set("report_path", output_path)
            return output_path

        # 导入flow_control handler
        from sdwan_desktop.flow.handlers.flow_control import check_connectivity
        
        handlers = {
            "step-collect": step_collect,
            "step-gateway": step_gateway,
            "step-dns": step_dns,
            "step-internet": step_internet,
            "step-connectivity-check": check_connectivity,  # ✅ 新增：连通性检查
            "step-dns-split": step_dns_split,
            "step-cpe-link-routing": step_cpe_link_routing,
            "step-analyze": step_analyze,
            "step-conclusion": step_conclusion,
            "step-report": step_report
        }
        
        # 执行 Flow
        runtime = FlowRuntime()
        await runtime.execute_flow(QUICK_CHECK_FLOW, ctx, handlers)
        
        # 获取诊断结果
        diagnosis_result = ctx.get("diagnosis_result")
        if diagnosis_result:
            self.diagnosis_completed.emit(diagnosis_result)
        else:
            self.diagnosis_failed.emit("诊断流程未生成结果")

    def run(self):
        try:
            asyncio.run(self._run_async())
        except Exception as e:
            self.diagnosis_failed.emit(str(e))


class QuickCheckTab(QWidget):
    def __init__(self):
        super().__init__()
        self.current_result = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        
        # 说明标签
        info_label = QLabel("一键体检将自动检查您的网络配置、网关连通性及 DNS 解析情况。")
        layout.addWidget(info_label)
        
        # 按钮区
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("开始体检")
        self.start_btn.clicked.connect(self.on_start_check)
        self.save_btn = QPushButton("保存报告")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.on_save_report)
        
        btn_layout.addWidget(self.start_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)
        
        # 进度区
        self.progress_bar = QProgressBar()
        self.status_label = QLabel("就绪")
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        
        # 结果表格
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(3)
        self.result_table.setHorizontalHeaderLabels(["检测项", "状态", "详情"])
        self.result_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.result_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        layout.addWidget(self.result_table)
        
        self.setLayout(layout)

    def on_start_check(self):
        self.start_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.result_table.setRowCount(0)
        self.progress_bar.setValue(0)
        
        self.worker = QuickCheckWorker()
        self.worker.progress_updated.connect(self.on_progress)
        self.worker.diagnosis_completed.connect(self.on_completed)
        self.worker.diagnosis_failed.connect(self.on_failed)
        self.worker.finished.connect(lambda: self.start_btn.setEnabled(True))
        self.worker.start()

    def on_progress(self, percent, text):
        self.progress_bar.setValue(percent)
        self.status_label.setText(text)

    def on_completed(self, result: DiagnosisResult):
        self.current_result = result
        self.status_label.setText(f"体检完成 - {result.summary}")
        self.save_btn.setEnabled(True)
        
        # 填充表格
        self.result_table.setRowCount(len(result.root_causes) if result.root_causes else 1)
        
        if not result.root_causes:
            item_status = QTableWidgetItem("正常")
            item_status.setForeground(Qt.green)
            self.result_table.setItem(0, 1, item_status)
            self.result_table.setItem(0, 0, QTableWidgetItem("基础配置"))
            self.result_table.setItem(0, 2, QTableWidgetItem("未发现明显异常"))
        else:
            for i, cause in enumerate(result.root_causes):
                self.result_table.setItem(i, 0, QTableWidgetItem(cause.title))
                
                status_item = QTableWidgetItem(cause.severity.value.upper())
                color = Qt.red if cause.severity == Severity.CRITICAL else (Qt.yellow if cause.severity == Severity.WARNING else Qt.black)
                status_item.setForeground(color)
                self.result_table.setItem(i, 1, status_item)
                
                self.result_table.setItem(i, 2, QTableWidgetItem(cause.description))

    def on_failed(self, msg):
        self.status_label.setText(f"体检失败: {msg}")
        self.start_btn.setEnabled(True)

    def on_save_report(self):
        if not self.current_result:
            return
            
        file_path, _ = QFileDialog.getSaveFileName(self, "保存报告", "", "HTML Files (*.html);;All Files (*)")
        if file_path:
            try:
                builder = HtmlReportBuilder()
                html_content = builder.build_quick_check_report(self.current_result)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                self.status_label.setText(f"报告已保存至: {os.path.basename(file_path)}")
            except Exception as e:
                self.status_label.setText(f"保存失败: {str(e)}")
