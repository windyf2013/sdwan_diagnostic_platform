"""验证零时序资源的修复效果"""

import sys
import json
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from sdwan_desktop.tools.implementations.web.har_capture import HarCaptureTool
from sdwan_desktop.services.parser.har_parser import HarParser
from sdwan_desktop.core.types.tool import ToolRequest
from sdwan_desktop.core.types.context import FlowContext


async def verify_zero_timing_fix():
    """验证零时序资源修复"""
    
    print("=" * 70)
    print("验证零时序资源修复")
    print("=" * 70)
    
    # 采集HAR
    print("\n📋 步骤1: 采集HAR数据")
    print("-" * 70)
    
    tool = HarCaptureTool()
    req = ToolRequest(
        tool_name='har_capture',
        parameters={
            'url': 'https://www.baidu.com',
            'headless': True,
            'timeout': 30000
        }
    )
    ctx = FlowContext(flow_id='verify-fix', flow_name='verify-fix')
    
    result = await tool.execute(req, ctx)
    
    if not result.success:
        print(f"❌ HAR采集失败: {result.error_message}")
        return False
    
    har_path = result.data.get('har_file_path')
    print(f"✅ HAR文件: {har_path}")
    
    # 解析HAR
    print("\n📋 步骤2: 解析HAR数据")
    print("-" * 70)
    
    parser = HarParser()
    waterfall_result = parser.parse(har_path)
    
    print(f"✅ 解析完成:")
    print(f"   • 总资源数: {waterfall_result.total_requests}")
    
    # 检查是否有total_time为0的资源
    zero_total_resources = [r for r in waterfall_result.resources if r.total_time == 0]
    failed_resources = [r for r in waterfall_result.resources if r.status_code == -1 or r.status_code >= 400]
    
    print(f"\n📊 资源状态分析:")
    print(f"   • total_time=0的资源: {len(zero_total_resources)}个")
    print(f"   • 失败资源(status=-1或>=400): {len(failed_resources)}个")
    
    if zero_total_resources:
        print(f"\n❌ 问题: 仍有{len(zero_total_resources)}个资源的total_time为0")
        print(f"   示例（前3个）:")
        for i, r in enumerate(zero_total_resources[:3]):
            print(f"     {i+1}. {r.url[:60]}... (status={r.status_code})")
        return False
    else:
        print(f"\n✅ 修复成功: 没有total_time=0的资源")
    
    # 检查失败资源是否有合理的时间
    if failed_resources:
        print(f"\n🔍 失败资源时间分析:")
        
        has_valid_time = all(r.total_time > 0 for r in failed_resources)
        
        if has_valid_time:
            print(f"   ✅ 所有失败资源都有合理的时间")
            
            min_time = min(r.total_time for r in failed_resources)
            max_time = max(r.total_time for r in failed_resources)
            avg_time = sum(r.total_time for r in failed_resources) / len(failed_resources)
            
            print(f"   • 最小时间: {min_time:.1f}ms")
            print(f"   • 最大时间: {max_time:.1f}ms")
            print(f"   • 平均时间: {avg_time:.1f}ms")
            
            # 显示示例
            print(f"\n   示例（前3个）:")
            for i, r in enumerate(failed_resources[:3]):
                print(f"     {i+1}. {r.url[:60]}...")
                print(f"        status={r.status_code}, total_time={r.total_time:.1f}ms, wait_time={r.wait_time:.1f}ms")
        else:
            print(f"   ❌ 部分失败资源时间为0")
            invalid = [r for r in failed_resources if r.total_time == 0]
            for r in invalid[:3]:
                print(f"     - {r.url[:60]}... (status={r.status_code})")
            return False
    
    # 清理
    Path(har_path).unlink(missing_ok=True)
    
    print("\n\n" + "=" * 70)
    print("✅ 验证通过！零时序资源问题已修复")
    print("=" * 70)
    print("\n修复内容:")
    print("  1. ✓ 失败的请求不再被过滤掉")
    print("  2. ✓ 使用HAR的time字段作为fallback")
    print("  3. ✓ 没有time字段时使用1ms最小值")
    print("  4. ✓ 所有资源都有合理的total_time")
    
    return True


if __name__ == "__main__":
    success = asyncio.run(verify_zero_timing_fix())
    sys.exit(0 if success else 1)
