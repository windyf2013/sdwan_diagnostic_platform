"""
打包后HTML报告生成仿真测试

验证一键体检功能在打包环境下的HTML报告生成是否正常：
1. 模板文件能否正确加载
2. DiagnosisResult数据结构是否完整
3. evidences是否正确填充
4. HTML报告内容是否为空
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.core.types.diagnosis import (
    DiagnosisResult, Severity, RootCause, Recommendation, DiagnosisEvidence
)
from sdwan_desktop.services.reporter.html_builder import HtmlReportBuilder
from sdwan_desktop.services.collector.windows_collector import SystemInfoSnapshot, NetworkAdapter, IpConfig
from sdwan_desktop.services.connectivity import ConnectivityTestResult, ProbeResult
from sdwan_desktop.services.dns_split import DnsSplitTestResult, DomainDnsResult


@pytest.fixture
def sample_diagnosis_result():
    """创建完整的诊断结果样本"""
    # 创建系统快照
    adapter = NetworkAdapter(
        name="Ethernet",
        description="Intel Ethernet Connection",
        mac_address="00:11:22:33:44:55",
        ip_addresses=["192.168.1.100"],
        default_gateway="192.168.1.1",
        dhcp_enabled=True,
        is_connected=True,
        speed_mbps=1000
    )
    
    ip_config = IpConfig(
        default_gateway="192.168.1.1",
        dns_servers=["8.8.8.8", "114.114.114.114"]
    )
    
    system_snapshot = SystemInfoSnapshot(
        adapters=[adapter],
        ip_config=ip_config,
        routes=[],
        dns_config=None,
        proxy_config=None,
        firewall_status=None,
        arp_table=[],
        connections=[],
        ipv6_info=None
    )
    
    # 创建连通性证据
    gateway_probe = ProbeResult(
        target=MagicMock(host="192.168.1.1", protocol=MagicMock(value="icmp")),
        success=True,
        rtt_avg=5.2,
        loss_rate=0.0
    )
    
    dns_probe = ProbeResult(
        target=MagicMock(host="8.8.8.8", protocol=MagicMock(value="dns")),
        success=True,
        rtt_avg=15.3,
        loss_rate=0.0
    )
    
    evidence_connectivity = DiagnosisEvidence(
        step_name="connectivity_test",
        description="连通性测试原始探测数据",
        probe_results=[gateway_probe, dns_probe],
        config_snapshots={"system_snapshot": system_snapshot}
    )
    
    # 创建DNS分流证据
    dns_split_result = DnsSplitTestResult(
        domain_results=[
            DomainDnsResult(
                domain="www.baidu.com",
                is_split=True,
                split_description="检测到DNS分流",
                domestic_results={"ips": ["14.215.177.38"]},
                international_results={"ips": ["14.215.177.39"]}
            )
        ],
        split_domains=["www.baidu.com"],
        split_count=1,
        total_domains=1
    )
    
    evidence_dns_split = DiagnosisEvidence(
        step_name="step-dns-split",
        description="DNS分流测试原始数据",
        probe_results=[],
        config_snapshots={"dns_split_result": dns_split_result}
    )
    
    # 创建根因和建议
    root_causes = [
        RootCause(
            cause_id="rule-001",
            title="网关延迟较高",
            description="网关RTT为5.2ms，超过阈值",
            severity=Severity.WARNING,
            confidence=0.85,
            matched_rules=["GATEWAY_HIGH_LATENCY"]
        )
    ]
    
    recommendations = [
        Recommendation(
            action="检查网关设备负载",
            priority=2,
            expected_outcome="降低网关延迟"
        )
    ]
    
    # 创建诊断结果
    diagnosis_result = DiagnosisResult(
        trace_id="test-trace-001",
        diagnosis_type="quick_check",
        summary="检测到 1 个问题",
        severity=Severity.WARNING,
        root_causes=root_causes,
        recommendations=recommendations,
        evidences=[evidence_connectivity, evidence_dns_split],
        overall_confidence=0.85,
        rule_version="1.0.0",
        timestamp=datetime.now().isoformat()
    )
    
    return diagnosis_result


def test_html_report_builder_initialization():
    """测试HTML报告构建器初始化"""
    builder = HtmlReportBuilder()
    
    # 验证模板目录存在
    assert builder.template_dir.exists(), f"模板目录不存在: {builder.template_dir}"
    
    # 验证模板文件存在
    quick_check_template = builder.template_dir / "quick_check.html"
    assert quick_check_template.exists(), f"quick_check.html模板不存在: {quick_check_template}"
    
    print(f"✓ 模板目录: {builder.template_dir}")
    print(f"✓ 模板文件存在: {quick_check_template}")


def test_quick_check_report_generation(sample_diagnosis_result, tmp_path):
    """测试一键体检HTML报告生成"""
    builder = HtmlReportBuilder()
    
    output_path = tmp_path / "test_quick_check_report.html"
    
    # 生成报告
    html_content = builder.build_quick_check_report(
        sample_diagnosis_result,
        output_path=output_path
    )
    
    # 验证点1: HTML内容不为空
    assert len(html_content) > 0, "HTML内容为空"
    assert len(html_content) > 1000, f"HTML内容过短: {len(html_content)}字符"
    
    # 验证点2: 输出文件已生成
    assert output_path.exists(), f"报告文件未生成: {output_path}"
    
    # 验证点3: 文件大小合理
    file_size = output_path.stat().st_size
    assert file_size > 1000, f"报告文件过小: {file_size}字节"
    assert file_size < 10 * 1024 * 1024, f"报告文件过大: {file_size}字节"
    
    # 验证点4: HTML包含关键内容
    assert "SD-WAN 一键体检报告" in html_content, "HTML缺少报告标题"
    assert "test-trace-001" in html_content, "HTML缺少Trace ID"
    assert "网关延迟较高" in html_content, "HTML缺少根因信息"
    assert "检查网关设备负载" in html_content, "HTML缺少建议信息"
    assert "192.168.1.100" in html_content, "HTML缺少系统信息"
    
    print(f"✓ HTML内容长度: {len(html_content)}字符")
    print(f"✓ 报告文件大小: {file_size}字节")
    print(f"✓ 报告路径: {output_path}")


def test_empty_diagnosis_result(tmp_path):
    """测试空诊断结果的报告生成"""
    builder = HtmlReportBuilder()
    
    # 创建空的诊断结果
    empty_result = DiagnosisResult(
        trace_id="empty-trace",
        diagnosis_type="quick_check",
        summary="网络状态正常",
        severity=Severity.INFO,
        root_causes=[],
        recommendations=[],
        evidences=[],
        overall_confidence=1.0
    )
    
    output_path = tmp_path / "test_empty_report.html"
    
    # 生成报告（应该不抛出异常）
    html_content = builder.build_quick_check_report(
        empty_result,
        output_path=output_path
    )
    
    # 验证HTML仍然有效
    assert len(html_content) > 0, "空诊断结果的HTML内容为空"
    assert "网络状态正常" in html_content, "HTML缺少摘要信息"
    
    print(f"✓ 空诊断结果报告生成成功")


def test_evidence_extraction(sample_diagnosis_result):
    """测试从evidences中提取数据"""
    builder = HtmlReportBuilder()
    
    # 提取系统信息
    system_info = builder._extract_system_info(sample_diagnosis_result)
    
    assert len(system_info["adapters"]) > 0, "未提取到网卡信息"
    assert system_info["adapters"][0]["name"] == "Ethernet", "网卡名称错误"
    assert "192.168.1.100" in system_info["adapters"][0]["ips"], "IP地址错误"
    
    # 提取连通性信息
    connectivity = builder._extract_connectivity(sample_diagnosis_result)
    
    assert connectivity["gateway_ip"] == "192.168.1.1", "网关IP错误"
    assert connectivity["dns_split_detected"] == True, "未检测到DNS分流"
    
    print(f"✓ 系统信息提取成功: {len(system_info['adapters'])}个网卡")
    print(f"✓ 连通性信息提取成功: 网关={connectivity['gateway_ip']}")


def test_pyinstaller_frozen_mode():
    """测试PyInstaller打包环境下的路径处理"""
    import sys
    
    # 模拟打包环境
    original_frozen = getattr(sys, 'frozen', False)
    original_meipass = getattr(sys, '_MEIPASS', None)
    
    try:
        # 设置为打包环境
        sys.frozen = True
        sys._MEIPASS = "/tmp/fake_meipass"
        
        # 创建临时模板目录
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            template_dir = tmp_path / "sdwan_desktop" / "reporting" / "templates"
            template_dir.mkdir(parents=True)
            
            # 复制一个简单模板
            from pathlib import Path as StdPath
            src_template = StdPath(__file__).parent.parent.parent / "src" / "sdwan_desktop" / "reporting" / "templates" / "quick_check.html"
            if src_template.exists():
                import shutil
                shutil.copy(src_template, template_dir / "quick_check.html")
                
                # 修改_MEIPASS指向临时目录
                sys._MEIPASS = str(tmp_path)
                
                # 创建构建器
                builder = HtmlReportBuilder()
                
                # 验证路径正确
                assert builder.template_dir.exists(), f"打包环境下模板目录不存在: {builder.template_dir}"
                
                print(f"✓ PyInstaller打包环境路径处理正确")
                print(f"  模板目录: {builder.template_dir}")
    
    finally:
        # 恢复原始状态
        if original_frozen:
            sys.frozen = original_frozen
        else:
            if hasattr(sys, 'frozen'):
                delattr(sys, 'frozen')
        
        if original_meipass:
            sys._MEIPASS = original_meipass
        else:
            if hasattr(sys, '_MEIPASS'):
                delattr(sys, '_MEIPASS')


if __name__ == "__main__":
    # 运行所有测试
    pytest.main([__file__, "-v"])
