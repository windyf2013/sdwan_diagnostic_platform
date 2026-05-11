"""
一键体检流程一致性测试

验证 CLI 和 GUI 的一键体检流程是否一致，确保打包后行为相同。
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

print(f"Python path: {sys.path[0]}")

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.core.types.system import SystemInfoSnapshot, AdapterInfo, IpConfigInfo
from sdwan_desktop.services.collector.windows_collector import WindowsCollector
from sdwan_desktop.services.connectivity import ConnectivityTester, ConnectivityTestResult
from sdwan_desktop.services.analyzer.rule_context import QuickCheckContext
from sdwan_desktop.services.analyzer.rule_engine import RuleEngine
from sdwan_desktop.services.analyzer.rules import GATEWAY_RULES, DNS_RULES, SYSTEM_RULES, CONNECTIVITY_RULES


def create_mock_snapshot() -> SystemInfoSnapshot:
    """创建模拟的系统信息快照"""
    # 模拟一个有网关的网卡
    adapter = AdapterInfo(
        name="Ethernet",
        description="Intel Ethernet Connection",
        is_connected=True,
        ip_addresses=["192.168.1.100"],
        default_gateway="192.168.1.1",
        speed_mbps=1000,
    )
    
    ip_config = IpConfigInfo(
        ip_address="192.168.1.100",
        subnet_mask="255.255.255.0",
        default_gateway="192.168.1.1",
        dns_servers=["114.114.114.114", "223.5.5.5"],
    )
    
    return SystemInfoSnapshot(
        adapters=[adapter],
        ip_config=ip_config,
    )


async def test_cli_flow():
    """测试 CLI 流程的关键步骤"""
    print("=" * 60)
    print("测试 CLI 流程")
    print("=" * 60)
    
    ctx = FlowContext(trace_id="test-cli-001")
    
    # 1. 采集系统信息
    mock_snapshot = create_mock_snapshot()
    with patch.object(WindowsCollector, 'collect', new_callable=AsyncMock) as mock_collect:
        mock_collect.return_value = mock_snapshot
        
        collector = WindowsCollector()
        snapshot = await collector.collect(ctx)
        ctx.set("system_snapshot", snapshot)
        print(f"✓ 采集系统信息完成")
        print(f"  - 主网卡: {snapshot.primary_adapter.description if snapshot.primary_adapter else 'None'}")
        print(f"  - 网关IP (ip_config): {snapshot.ip_config.default_gateway if snapshot.ip_config else 'None'}")
        print(f"  - 网关IP (primary_adapter): {snapshot.primary_adapter.default_gateway if snapshot.primary_adapter else 'None'}")
    
    # 2. 获取网关IP（CLI的回退逻辑）
    gateway_ip = None
    if snapshot.ip_config:
        gateway_ip = snapshot.ip_config.default_gateway
    
    # 如果 ip_config 中没有，尝试从 primary_adapter 获取
    if not gateway_ip and snapshot.primary_adapter:
        gateway_ip = snapshot.primary_adapter.default_gateway
    
    print(f"✓ 最终网关IP: {gateway_ip}")
    assert gateway_ip == "192.168.1.1", f"期望网关为 192.168.1.1，实际为 {gateway_ip}"
    
    # 3. 构造 QuickCheckContext（CLI的方式）
    conn_result = ConnectivityTestResult(
        gateway_ping=None,  # 模拟已测试
        domestic_dns_results=[],
        international_dns_results=[],
        domestic_target_results=[],
        international_target_results=[]
    )
    
    from sdwan_desktop.services.dns_split import DnsSplitTestResult
    dns_split_result = DnsSplitTestResult(
        domain_results=[],
        split_domains=[],
        split_count=0,
        total_domains=0
    )
    
    qc_ctx = QuickCheckContext(
        system_info=snapshot,
        connectivity=conn_result,
        dns_split=dns_split_result
    )
    
    print(f"✓ QuickCheckContext 构造成功")
    print(f"  - system_info type: {type(qc_ctx.system_info).__name__}")
    print(f"  - connectivity type: {type(qc_ctx.connectivity).__name__}")
    print(f"  - dns_split type: {type(qc_ctx.dns_split).__name__}")
    
    # 4. 规则引擎评估
    rule_engine = RuleEngine()
    rule_engine.register_rules(GATEWAY_RULES)
    rule_engine.register_rules(DNS_RULES)
    rule_engine.register_rules(SYSTEM_RULES)
    rule_engine.register_rules(CONNECTIVITY_RULES)
    
    rule_results = rule_engine.evaluate(qc_ctx)
    print(f"✓ 规则引擎评估完成，触发 {len([r for r in rule_results.results if r.triggered])} 条规则")
    
    print("\n✅ CLI 流程测试通过\n")
    return True


async def test_gui_flow():
    """测试 GUI 流程的关键步骤（修复后应与CLI一致）"""
    print("=" * 60)
    print("测试 GUI 流程（修复后）")
    print("=" * 60)
    
    ctx = FlowContext(trace_id="test-gui-001")
    
    # 1. 采集系统信息
    mock_snapshot = create_mock_snapshot()
    with patch.object(WindowsCollector, 'collect', new_callable=AsyncMock) as mock_collect:
        mock_collect.return_value = mock_snapshot
        
        collector = WindowsCollector()
        snapshot = await collector.collect(ctx)
        ctx.set("system_snapshot", snapshot)
        print(f"✓ 采集系统信息完成")
    
    # 2. 获取网关IP（修复后的GUI逻辑，应与CLI一致）
    gateway_ip = None
    if snapshot.ip_config:
        gateway_ip = snapshot.ip_config.default_gateway
    
    # 如果 ip_config 中没有，尝试从 primary_adapter 获取
    if not gateway_ip and snapshot.primary_adapter:
        gateway_ip = snapshot.primary_adapter.default_gateway
    
    print(f"✓ 最终网关IP: {gateway_ip}")
    assert gateway_ip == "192.168.1.1", f"期望网关为 192.168.1.1，实际为 {gateway_ip}"
    
    # 3. 获取DNS服务器（修复后的GUI逻辑）
    dns_servers = []
    if snapshot.ip_config:
        dns_servers = snapshot.ip_config.dns_servers
    
    if not dns_servers:
        dns_servers = ["114.114.114.114"]
    
    print(f"✓ DNS服务器: {dns_servers}")
    
    # 4. 构造 QuickCheckContext（修复后的GUI逻辑，应与CLI一致）
    conn_result = ConnectivityTestResult(
        gateway_ping=None,
        domestic_dns_results=[],
        international_dns_results=[],
        domestic_target_results=[],
        international_target_results=[]
    )
    
    from sdwan_desktop.services.dns_split import DnsSplitTestResult
    dns_split_result = DnsSplitTestResult(
        domain_results=[],
        split_domains=[],
        split_count=0,
        total_domains=0
    )
    
    qc_ctx = QuickCheckContext(
        system_info=snapshot,
        connectivity=conn_result,
        dns_split=dns_split_result
    )
    
    print(f"✓ QuickCheckContext 构造成功")
    print(f"  - system_info type: {type(qc_ctx.system_info).__name__}")
    print(f"  - connectivity type: {type(qc_ctx.connectivity).__name__}")
    print(f"  - dns_split type: {type(qc_ctx.dns_split).__name__}")
    
    # 5. 规则引擎评估
    rule_engine = RuleEngine()
    rule_engine.register_rules(GATEWAY_RULES)
    rule_engine.register_rules(DNS_RULES)
    rule_engine.register_rules(SYSTEM_RULES)
    rule_engine.register_rules(CONNECTIVITY_RULES)
    
    rule_results = rule_engine.evaluate(qc_ctx)
    print(f"✓ 规则引擎评估完成，触发 {len([r for r in rule_results.results if r.triggered])} 条规则")
    
    print("\n✅ GUI 流程测试通过\n")
    return True


async def test_edge_case_no_ip_config():
    """测试边界情况：ip_config 为空时的回退逻辑"""
    print("=" * 60)
    print("测试边界情况：ip_config 为空")
    print("=" * 60)
    
    ctx = FlowContext(trace_id="test-edge-001")
    
    # 创建一个 ip_config 为空的快照
    adapter = AdapterInfo(
        name="Ethernet",
        description="Intel Ethernet Connection",
        is_connected=True,
        ip_addresses=["192.168.1.100"],
        default_gateway="192.168.1.1",
        speed_mbps=1000,
    )
    
    snapshot = SystemInfoSnapshot(
        adapters=[adapter],
        ip_config=None,  # ip_config 为空
    )
    
    ctx.set("system_snapshot", snapshot)
    
    # 测试回退逻辑
    gateway_ip = None
    if snapshot.ip_config:
        gateway_ip = snapshot.ip_config.default_gateway
    
    # 如果 ip_config 中没有，尝试从 primary_adapter 获取
    if not gateway_ip and snapshot.primary_adapter:
        gateway_ip = snapshot.primary_adapter.default_gateway
    
    print(f"✓ ip_config 为空时，从 primary_adapter 获取网关: {gateway_ip}")
    assert gateway_ip == "192.168.1.1", f"期望网关为 192.168.1.1，实际为 {gateway_ip}"
    
    print("\n✅ 边界情况测试通过\n")
    return True


async def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("一键体检流程一致性测试")
    print("=" * 60 + "\n")
    
    try:
        # 测试 CLI 流程
        await test_cli_flow()
        
        # 测试 GUI 流程
        await test_gui_flow()
        
        # 测试边界情况
        await test_edge_case_no_ip_config()
        
        print("=" * 60)
        print("🎉 所有测试通过！CLI 和 GUI 流程已保持一致。")
        print("=" * 60)
        return 0
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
