"""
测试HAR解析器对零时序资源的处理

验证：即使所有阶段耗时都为0，也应该有合理的处理方式
"""

import sys
import json
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from sdwan_desktop.tools.implementations.web.har_capture import HarCaptureTool
from sdwan_desktop.services.parser.har_parser import HarParser
from sdwan_desktop.core.types.tool import ToolRequest
from sdwan_desktop.core.types.context import FlowContext


async def test_zero_timing_handling():
    """测试零时序资源的处理"""
    
    print("=" * 70)
    print("测试: HAR解析器对零时序资源的处理")
    print("=" * 70)
    
    # 采集HAR数据
    print("\n📋 步骤1: 采集HAR数据")
    print("-" * 70)
    
    tool = HarCaptureTool()
    req = ToolRequest(
        tool_name='har_capture',
        parameters={
            'url': 'https://www.baidu.com',
            'headless': True,
            'timeout': 30000,
            'wait_until': 'networkidle'
        }
    )
    ctx = FlowContext(flow_id='test-zero-timing', flow_name='test-zero-timing')
    
    result = await tool.execute(req, ctx)
    
    if not result.success:
        print(f"❌ HAR采集失败: {result.error_message}")
        return False
    
    har_path = result.data.get('har_file_path')
    print(f"✅ HAR文件: {har_path}")
    
    # 分析原始HAR数据
    print("\n📋 步骤2: 分析原始HAR数据")
    print("-" * 70)
    
    with open(har_path, 'r', encoding='utf-8') as f:
        har_data = json.load(f)
    
    entries = har_data.get('log', {}).get('entries', [])
    print(f"总请求数: {len(entries)}")
    
    # 查找零时序的请求
    zero_timing_entries = []
    for entry in entries:
        timings = entry.get('timings', {})
        total = sum([
            max(timings.get('dns', -1), 0),
            max(timings.get('connect', -1), 0),
            max(timings.get('ssl', -1), 0),
            max(timings.get('wait', 0), 0),
            max(timings.get('receive', 0), 0)
        ])
        
        if total == 0:
            zero_timing_entries.append(entry)
    
    print(f"\n零时序请求数: {len(zero_timing_entries)}")
    
    if zero_timing_entries:
        print(f"\n示例（前5个）:")
        for i, entry in enumerate(zero_timing_entries[:5]):
            url = entry.get('request', {}).get('url', '')
            status = entry.get('response', {}).get('status', 0)
            time_field = entry.get('time', -1)
            blocked = entry.get('timings', {}).get('blocked', 0)
            
            print(f"  {i+1}. {url[:60]}...")
            print(f"     状态码: {status}, HAR time字段: {time_field}ms, blocked: {blocked}ms")
            print(f"     Timings: {entry.get('timings', {})}")
    
    # 解析HAR
    print("\n\n📋 步骤3: 解析HAR数据")
    print("-" * 70)
    
    parser = HarParser()
    waterfall_result = parser.parse(har_path)
    
    print(f"✅ 解析完成:")
    print(f"   • 总资源数: {waterfall_result.total_requests}")
    print(f"   • 页面加载时间: {waterfall_result.page_load_time:.0f}ms")
    
    # 检查解析后的零时序资源
    zero_timing_resources = [r for r in waterfall_result.resources if r.total_time == 0]
    very_small_timing_resources = [r for r in waterfall_result.resources if 0 < r.total_time < 1]
    
    print(f"\n📊 解析结果分析:")
    print(f"   • 零时序资源 (total_time=0): {len(zero_timing_resources)}个")
    print(f"   • 极小时序资源 (0<total_time<1ms): {len(very_small_timing_resources)}个")
    
    if zero_timing_resources:
        print(f"\n   ⚠️  警告: 仍存在{len(zero_timing_resources)}个零时序资源")
        for i, r in enumerate(zero_timing_resources[:3]):
            print(f"     {i+1}. {r.url[:60]}... (status={r.status_code})")
    else:
        print(f"\n   ✅ 所有资源都有合理的时序数据")
    
    if very_small_timing_resources:
        print(f"\n   ℹ️  {len(very_small_timing_resources)}个资源使用最小值0.1ms表示失败")
        for i, r in enumerate(very_small_timing_resources[:3]):
            print(f"     {i+1}. {r.url[:60]}... (status={r.status_code}, time={r.total_time}ms)")
    
    # 清理文件
    Path(har_path).unlink(missing_ok=True)
    
    # 总结
    print("\n\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)
    
    if len(zero_timing_resources) == 0:
        print("✅ 修复成功！所有资源都有合理的时序数据。")
        print("\n改进内容:")
        print("  1. ✓ 使用HAR的time字段作为后备")
        print("  2. ✓ 考虑blocked时间")
        print("  3. ✓ 失败资源使用最小值0.1ms")
        print("  4. ✓ 详细的日志记录便于调试")
        return True
    else:
        print(f"⚠️  仍有{len(zero_timing_resources)}个零时序资源，可能需要进一步调查")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_zero_timing_handling())
    sys.exit(0 if success else 1)
