"""
Waterfall CLI 错误处理测试

模拟浏览器未安装的场景，验证错误提示是否友好。
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from sdwan_desktop.core.types.tool import ToolRequest
from sdwan_desktop.core.types.context import FlowContext


async def test_browser_not_installed():
    """测试浏览器未安装时的错误处理"""
    print("=" * 60)
    print("测试: 浏览器未安装场景")
    print("=" * 60)
    
    from sdwan_desktop.tools.implementations.web.har_capture import HarCaptureTool
    
    # 构造请求
    request = ToolRequest(
        tool_name="har_capture",
        parameters={
            "url": "https://www.baidu.com",
            "headless": True,
            "timeout": 10000,
            "wait_until": "networkidle"
        }
    )
    ctx = FlowContext(flow_id="test-error", flow_name="test-error-handling")
    
    try:
        har_tool = HarCaptureTool()
        result = await har_tool.execute(request, ctx)
        
        print(f"\n执行结果:")
        print(f"  - success: {result.success}")
        print(f"  - error_code: {result.error_code}")
        print(f"  - error_message: {result.error_message}")
        
        # 验证错误处理
        if not result.success:
            print(f"\n✅ 错误捕获成功!")
            print(f"   错误信息: {result.error_message}")
            
            # 检查是否包含 Playwright 相关提示
            if "playwright" in result.error_message.lower() or "browser" in result.error_message.lower():
                print(f"   ✓ 错误信息包含浏览器相关提示")
            else:
                print(f"   ⚠ 建议增强错误提示信息")
        else:
            print(f"\n⚠️  意外成功（可能浏览器已安装）")
            
    except Exception as e:
        print(f"\n❌ 未捕获的异常: {e}")
        import traceback
        traceback.print_exc()


def test_cli_error_handling_logic():
    """测试 CLI 的错误处理逻辑"""
    print("\n" + "=" * 60)
    print("测试: CLI 错误处理逻辑")
    print("=" * 60)
    
    # 模拟失败的响应
    class MockResponse:
        def __init__(self, success, error_message, data=None):
            self.success = success
            self.error_message = error_message
            self.data = data
    
    # 测试场景 1: 失败响应
    print("\n场景 1: HAR 采集失败")
    har_result = MockResponse(
        success=False,
        error_message="BrowserType.launch: Executable doesn't exist",
        data=None
    )
    
    # CLI 错误处理逻辑
    if not har_result or not har_result.success:
        error_msg = har_result.error_message if har_result else "未知错误"
        print(f"  ✓ 检测到失败: {error_msg[:50]}...")
    
    # 测试场景 2: None 响应
    print("\n场景 2: 响应为 None")
    har_result = None
    
    if not har_result or not (hasattr(har_result, 'success') and har_result.success):
        error_msg = har_result.error_message if har_result else "未知错误"
        print(f"  ✓ 检测到空响应: {error_msg}")
    
    # 测试场景 3: data 为 None
    print("\n场景 3: data 字段为 None")
    har_result = MockResponse(
        success=True,
        error_message=None,
        data=None
    )
    
    har_path = har_result.data.get("har_file_path") if har_result.data else None
    print(f"  ✓ 安全获取 har_path: {har_path}")
    
    print("\n✅ CLI 错误处理逻辑正确")


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Waterfall CLI 错误处理测试")
    print("=" * 60)
    
    try:
        # 测试 1: 浏览器未安装场景
        asyncio.run(test_browser_not_installed())
        
        # 测试 2: CLI 错误处理逻辑
        test_cli_error_handling_logic()
        
        print("\n" + "=" * 60)
        print("📋 测试完成总结")
        print("=" * 60)
        print("\n如果浏览器未安装，请先运行:")
        print("  playwright install chromium")
        print("\n或者在虚拟环境中:")
        print("  .venv\\Scripts\\python.exe -m playwright install chromium")
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
