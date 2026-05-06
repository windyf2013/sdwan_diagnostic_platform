import json
import os
import uuid
import asyncio
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar, QFileDialog
)
from PySide6.QtCore import Qt, Signal, QThread

from sdwan_desktop.core.types.diagnosis import DiagnosisResult, Severity, RootCause, Recommendation
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
        from sdwan_desktop.flow.definitions.quick_check import QUICK_CHECK_FLOW
        from sdwan_desktop.runtime.engine import FlowRuntime
        from sdwan_desktop.core.types.context import FlowContext
        from sdwan_desktop.services.collector.windows_collector import WindowsCollector
        from sdwan_desktop.services.connectivity import ConnectivityTester
        from sdwan_desktop.services.dns_split import DnsSplitTester
        from sdwan_desktop.services.analyzer.rule_engine import RuleEngine
        from sdwan_desktop.services.analyzer.rules import GATEWAY_RULES, DNS_RULES, SYSTEM_RULES, CONNECTIVITY_RULES
        
        trace_id = str(uuid.uuid4())
        ctx = FlowContext(trace_id=trace_id)
        
        # 初始化服务
        collector = WindowsCollector()
        connectivity_tester = ConnectivityTester()
        dns_split_tester = DnsSplitTester()
        rule_engine = RuleEngine()
        rule_engine.register_rules(GATEWAY_RULES)
        rule_engine.register_rules(DNS_RULES)
        rule_engine.register_rules(SYSTEM_RULES)
        rule_engine.register_rules(CONNECTIVITY_RULES)
        
        # 1. 采集系统信息
        if self._is_cancelled: return
        self.progress_updated.emit(10, "正在采集系统信息...")
        snapshot = await collector.collect(ctx)
        ctx.set("system_snapshot", snapshot)
        
        # 2. 网关连通性
        if self._is_cancelled: return
        self.progress_updated.emit(30, "正在测试网关连通性...")
        gateway_ip = snapshot.ip_config.default_gateway if snapshot.ip_config else None
        gateway_result = None
        if gateway_ip:
            gateway_result = await connectivity_tester.test_gateway(gateway_ip, ctx)
        ctx.set("gateway_ping_result", gateway_result)
        
        # 3. DNS 解析
        if self._is_cancelled: return
        self.progress_updated.emit(50, "正在测试 DNS 解析...")
        dns_servers = snapshot.ip_config.dns_servers if snapshot.ip_config else ["114.114.114.114", "223.5.5.5"]
        dns_results = await connectivity_tester.test_domestic_dns(dns_servers, ctx)
        ctx.set("dns_results", dns_results)
        
        # 4. 互联网连通性
        if self._is_cancelled: return
        self.progress_updated.emit(70, "正在测试互联网连通性...")
        domestic_res = await connectivity_tester.test_domestic_targets(ctx)
        international_res = await connectivity_tester.test_international_targets(ctx)
        ctx.set("domestic_connectivity", domestic_res)
        ctx.set("international_connectivity", international_res)
        
        # 5. 分析诊断结果
        if self._is_cancelled: return
        self.progress_updated.emit(90, "正在生成诊断结论...")
        
        from sdwan_desktop.services.analyzer.rule_context import QuickCheckContext
        qc_ctx = QuickCheckContext(
            trace_id=ctx.trace_id,
            system_snapshot=snapshot,
            gateway_ping=gateway_result,
            dns_results=dns_results,
            domestic_connectivity=domestic_res,
            international_connectivity=international_res
        )
        
        rule_results = rule_engine.evaluate(qc_ctx)
        
        # 构建 DiagnosisResult
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
                        reason=rr.message
                    ))
                confidence = min(confidence, rr.confidence)
                
        diagnosis_result = DiagnosisResult(
            trace_id=trace_id,
            diagnosis_type="quick_check",
            summary=f"检测到 {len(root_causes)} 个问题" if root_causes else "网络状态正常",
            severity=root_causes[0].severity if root_causes else Severity.INFO,
            root_causes=root_causes,
            recommendations=recommendations,
            overall_confidence=confidence,
            timestamp=datetime.now().isoformat()
        )
        
        self.progress_updated.emit(100, "体检完成")
        self.diagnosis_completed.emit(diagnosis_result)

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
