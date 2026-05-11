"""
工具注册完整性测试

验证所有必需的工具都已正确注册到 ToolRegistry。
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))


def test_tool_registration():
    """测试工具注册完整性"""
    print("=" * 70)
    print("工具注册完整性测试")
    print("=" * 70)
    
    # 显式导入所有工具模块（模拟 main_window.py 的行为）
    print("\n1. 导入工具模块...")
    import sdwan_desktop.tools.implementations.system.windows
    import sdwan_desktop.tools.implementations.network.ping
    import sdwan_desktop.tools.implementations.network.dns
    import sdwan_desktop.tools.implementations.network.tcping
    import sdwan_desktop.tools.implementations.network.traceroute
    import sdwan_desktop.tools.implementations.web.har_capture
    print("   ✅ 所有工具模块导入成功")
    
    # 获取工具注册表
    from sdwan_desktop.tools.registry.base import ToolRegistry
    registry = ToolRegistry()
    
    # 列出所有已注册的工具
    tools = registry.list_tools()
    print(f"\n2. 已注册工具列表 ({len(tools)} 个):")
    for tool_name in sorted(tools):
        print(f"   - {tool_name}")
    
    # 验证必需工具是否存在
    print("\n3. 验证必需工具...")
    required_tools = {
        "windows_system": "系统信息采集（一键体检必需）",
        "ping": "网络连通性测试",
        "dns": "DNS解析测试",
        "tcping": "TCP端口测试",
        "traceroute": "路由追踪",
        "har_capture": "HAR采集（业务监测必需）",
    }
    
    missing_tools = []
    for tool_name, description in required_tools.items():
        if tool_name in tools:
            print(f"   ✅ {tool_name:20} - {description}")
        else:
            print(f"   ❌ {tool_name:20} - {description} [缺失]")
            missing_tools.append(tool_name)
    
    # 测试结果
    print("\n" + "=" * 70)
    if missing_tools:
        print(f"❌ 测试失败！缺少 {len(missing_tools)} 个必需工具:")
        for tool in missing_tools:
            print(f"   - {tool}")
        return False
    else:
        print(f"✅ 测试通过！所有 {len(required_tools)} 个必需工具已注册")
        print("=" * 70)
        return True


def test_windows_system_tool():
    """特别测试 windows_system 工具"""
    print("\n" + "=" * 70)
    print("WindowsSystemTool 专项测试")
    print("=" * 70)
    
    try:
        from sdwan_desktop.tools.implementations.system.windows import WindowsSystemTool
        from sdwan_desktop.core.types.tool import ToolRequest
        from sdwan_desktop.core.types.context import FlowContext
        
        # 创建工具实例
        tool = WindowsSystemTool()
        print("✅ WindowsSystemTool 实例化成功")
        
        # 检查是否有 execute 方法
        if hasattr(tool, 'execute'):
            print("✅ WindowsSystemTool.execute 方法存在")
        else:
            print("❌ WindowsSystemTool.execute 方法不存在")
            return False
        
        # 检查装饰器是否正确设置
        if hasattr(tool, '__wrapped__'):
            print("✅ 工具使用了装饰器")
        else:
            print("⚠️  工具可能未正确使用装饰器")
        
        print("\n✅ WindowsSystemTool 测试通过")
        return True
        
    except Exception as e:
        print(f"\n❌ WindowsSystemTool 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_har_capture_tool():
    """特别测试 har_capture 工具"""
    print("\n" + "=" * 70)
    print("HarCaptureTool 专项测试")
    print("=" * 70)
    
    try:
        from sdwan_desktop.tools.implementations.web.har_capture import HarCaptureTool
        from sdwan_desktop.core.types.tool import ToolRequest
        from sdwan_desktop.core.types.context import FlowContext
        
        # 创建工具实例
        tool = HarCaptureTool()
        print("✅ HarCaptureTool 实例化成功")
        
        # 检查是否有 execute 方法
        if hasattr(tool, 'execute'):
            print("✅ HarCaptureTool.execute 方法存在")
        else:
            print("❌ HarCaptureTool.execute 方法不存在")
            return False
        
        print("\n✅ HarCaptureTool 测试通过")
        return True
        
    except Exception as e:
        print(f"\n❌ HarCaptureTool 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print("工具注册完整性验证")
    print("=" * 70 + "\n")
    
    # 测试 1: 工具注册完整性
    test1_passed = test_tool_registration()
    
    # 测试 2: WindowsSystemTool 专项测试
    test2_passed = test_windows_system_tool()
    
    # 测试 3: HarCaptureTool 专项测试
    test3_passed = test_har_capture_tool()
    
    # 汇总结果
    print("\n" + "=" * 70)
    print("测试结果汇总")
    print("=" * 70)
    print(f"{'✅ PASS' if test1_passed else '❌ FAIL'} | 工具注册完整性")
    print(f"{'✅ PASS' if test2_passed else '❌ FAIL'} | WindowsSystemTool 专项测试")
    print(f"{'✅ PASS' if test3_passed else '❌ FAIL'} | HarCaptureTool 专项测试")
    print("=" * 70)
    
    if test1_passed and test2_passed and test3_passed:
        print("🎉 所有测试通过！工具注册完整。")
        return 0
    else:
        print("⚠️  部分测试失败，请检查工具导入和装饰器使用。")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
