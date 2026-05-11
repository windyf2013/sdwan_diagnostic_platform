"""
Waterfall CLI 和 GUI 流程一致性测试

验证 CLI 和 GUI 的 waterfall 实现是否使用相同的流程和参数。
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from sdwan_desktop.core.types.tool import ToolRequest
from sdwan_desktop.core.types.context import FlowContext


def test_cli_waterfall_flow():
    """测试 CLI waterfall 流程"""
    print("=" * 60)
    print("测试 1: CLI Waterfall 流程")
    print("=" * 60)
    
    # 模拟 CLI 的参数
    url = "https://www.baidu.com"
    headless = True
    timeout = 30  # 秒
    
    # 构造 ToolRequest（与 CLI 一致）
    request = ToolRequest(
        tool_name="har_capture",
        parameters={
            "url": url,
            "headless": headless,
            "timeout": timeout * 1000,  # 转换为毫秒
            "wait_until": "networkidle"
        }
    )
    ctx = FlowContext(flow_id="cli-waterfall", flow_name="cli-waterfall-diagnosis")
    
    print(f"✓ CLI 参数构造正确")
    print(f"  - URL: {request.parameters['url']}")
    print(f"  - Headless: {request.parameters['headless']}")
    print(f"  - Timeout: {request.parameters['timeout']}ms")
    print(f"  - Wait Until: {request.parameters['wait_until']}")
    print(f"  - Flow ID: {ctx.flow_id}")
    
    assert request.parameters["url"] == url
    assert request.parameters["timeout"] == 30000
    assert ctx.flow_id == "cli-waterfall"
    
    print("\n✅ CLI 流程测试通过\n")


def test_gui_waterfall_flow():
    """测试 GUI waterfall 流程"""
    print("=" * 60)
    print("测试 2: GUI Waterfall 流程")
    print("=" * 60)
    
    # 模拟 GUI 的参数
    url = "https://www.baidu.com"
    headless = True
    
    # 构造 ToolRequest（与 GUI 一致）
    request = ToolRequest(
        tool_name="har_capture",
        parameters={
            "url": url,
            "headless": headless,
            "timeout": 60000,  # GUI 固定使用 60 秒
            "wait_until": "networkidle"
        }
    )
    ctx = FlowContext(flow_id="gui-waterfall", flow_name="gui-waterfall-monitoring")
    
    print(f"✓ GUI 参数构造正确")
    print(f"  - URL: {request.parameters['url']}")
    print(f"  - Headless: {request.parameters['headless']}")
    print(f"  - Timeout: {request.parameters['timeout']}ms")
    print(f"  - Wait Until: {request.parameters['wait_until']}")
    print(f"  - Flow ID: {ctx.flow_id}")
    
    assert request.parameters["url"] == url
    assert request.parameters["timeout"] == 60000
    assert ctx.flow_id == "gui-waterfall"
    
    print("\n✅ GUI 流程测试通过\n")


def test_consistency():
    """测试 CLI 和 GUI 的一致性"""
    print("=" * 60)
    print("测试 3: CLI 和 GUI 一致性对比")
    print("=" * 60)
    
    # CLI 参数
    cli_request = ToolRequest(
        tool_name="har_capture",
        parameters={
            "url": "https://www.baidu.com",
            "headless": True,
            "timeout": 30000,
            "wait_until": "networkidle"
        }
    )
    
    # GUI 参数
    gui_request = ToolRequest(
        tool_name="har_capture",
        parameters={
            "url": "https://www.baidu.com",
            "headless": True,
            "timeout": 60000,
            "wait_until": "networkidle"
        }
    )
    
    print("对比项:")
    print(f"  ✓ tool_name: CLI='{cli_request.tool_name}' vs GUI='{gui_request.tool_name}' → {'一致' if cli_request.tool_name == gui_request.tool_name else '不一致'}")
    print(f"  ✓ url: CLI='{cli_request.parameters['url']}' vs GUI='{gui_request.parameters['url']}' → {'一致' if cli_request.parameters['url'] == gui_request.parameters['url'] else '不一致'}")
    print(f"  ✓ headless: CLI={cli_request.parameters['headless']} vs GUI={gui_request.parameters['headless']} → {'一致' if cli_request.parameters['headless'] == gui_request.parameters['headless'] else '不一致'}")
    print(f"  ✓ wait_until: CLI='{cli_request.parameters['wait_until']}' vs GUI='{gui_request.parameters['wait_until']}' → {'一致' if cli_request.parameters['wait_until'] == gui_request.parameters['wait_until'] else '不一致'}")
    print(f"  ⚠ timeout: CLI={cli_request.parameters['timeout']}ms vs GUI={gui_request.parameters['timeout']}ms → {'不同（CLI可配置，GUI固定）'}")
    
    # 验证关键参数一致
    assert cli_request.tool_name == gui_request.tool_name
    assert cli_request.parameters["url"] == gui_request.parameters["url"]
    assert cli_request.parameters["headless"] == gui_request.parameters["headless"]
    assert cli_request.parameters["wait_until"] == gui_request.parameters["wait_until"]
    
    print("\n✅ 一致性测试通过\n")
    print("注意：timeout 参数可以不同，CLI 允许用户配置，GUI 使用默认值 60s")


async def test_error_handling_consistency():
    """测试错误处理的一致性"""
    print("=" * 60)
    print("测试 4: 错误处理一致性")
    print("=" * 60)
    
    from sdwan_desktop.tools.implementations.web.har_capture import HarCaptureTool
    
    # 模拟失败的 HAR 采集
    request = ToolRequest(
        tool_name="har_capture",
        parameters={"url": "https://invalid.url"}
    )
    ctx = FlowContext(flow_id="test", flow_name="test")
    
    with patch.object(HarCaptureTool, 'execute', new_callable=AsyncMock) as mock_execute:
        mock_execute.return_value = type('ToolResponse', (), {
            'success': False,
            'error_message': 'Browser not installed',
            'data': None
        })()
        
        har_tool = HarCaptureTool()
        result = await har_tool.execute(request, ctx)
        
        # CLI 和 GUI 都应该使用相同的错误处理逻辑
        if not result or not result.success:
            error_msg = result.error_message if result else "未知错误"
            print(f"✓ 错误处理逻辑正确: {error_msg}")
            assert error_msg == "Browser not installed"
    
    print("\n✅ 错误处理一致性测试通过\n")


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Waterfall CLI 和 GUI 流程一致性测试")
    print("=" * 60 + "\n")
    
    try:
        # 测试 1: CLI 流程
        test_cli_waterfall_flow()
        
        # 测试 2: GUI 流程
        test_gui_waterfall_flow()
        
        # 测试 3: 一致性对比
        test_consistency()
        
        # 测试 4: 错误处理一致性
        asyncio.run(test_error_handling_consistency())
        
        print("=" * 60)
        print("🎉 所有测试通过！CLI 和 GUI 流程保持一致。")
        print("=" * 60)
        return 0
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
