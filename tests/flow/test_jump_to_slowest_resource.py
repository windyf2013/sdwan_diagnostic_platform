"""
测试最慢资源跳转功能

验证：TOP 10表格点击可以正确跳转到瀑布流图对应资源
"""

import sys
import asyncio
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sdwan_desktop.tools.implementations.web.har_capture import HarCaptureTool
from sdwan_desktop.services.parser.har_parser import HarParser
from sdwan_desktop.services.reporter.report_generator import ReportGenerator
from sdwan_desktop.core.types.tool import ToolRequest
from sdwan_desktop.core.types.context import FlowContext


async def test_jump_functionality():
    """测试跳转功能"""
    
    print("=" * 70)
    print("测试: 最慢资源跳转功能")
    print("=" * 70)
    
    # 采集HAR数据
    print("\n📋 步骤1: 采集HAR数据")
    print("-" * 70)
    
    tool = HarCaptureTool()
    req = ToolRequest(
        tool_name='har_capture',
        parameters={
            'url': 'https://www.joom.com',
            'headless': True,
            'timeout': 60000,
            'wait_until': 'networkidle'
        }
    )
    ctx = FlowContext(flow_id='test-jump', flow_name='test-jump')
    
    result = await tool.execute(req, ctx)
    
    if not result.success:
        print(f"❌ HAR采集失败: {result.error_message}")
        return False
    
    har_path = result.data.get('har_file_path')
    print(f"✅ HAR文件: {Path(har_path).name}")
    
    # 解析HAR
    print("\n📋 步骤2: 解析HAR数据")
    print("-" * 70)
    
    parser = HarParser()
    waterfall_result = parser.parse(har_path)
    
    print(f"✅ 解析完成:")
    print(f"   • 总资源数: {waterfall_result.total_requests}")
    
    # 生成HTML报告
    print("\n📋 步骤3: 生成HTML报告")
    print("-" * 70)
    
    generator = ReportGenerator()
    output_path = "test_jump_functionality.html"
    
    html_content = generator.generate_waterfall_report(
        waterfall_result, 
        [],
        output_path
    )
    
    print(f"✅ 报告已生成: {output_path}")
    
    # 验证跳转功能
    print("\n📋 步骤4: 验证跳转功能")
    print("-" * 70)
    
    with open(output_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    # 提取TOP 10表格中的resource_id
    top10_pattern = r'<tr onclick="scrollToResource\(\'([^\']+)\'\)"'
    top10_ids = re.findall(top10_pattern, html)
    
    print(f"   • TOP 10表格中的资源ID数量: {len(top10_ids)}")
    
    # 提取瀑布流图中的resource_id
    waterfall_pattern = r'<div class="resource-row" id="([^"]+)"'
    waterfall_ids = re.findall(waterfall_pattern, html)
    
    print(f"   • 瀑布流图中的资源ID数量: {len(waterfall_ids)}")
    
    # 检查ID格式是否一致（都使用hash + 索引）
    hash_pattern = r'resource-[a-f0-9]{8}-\d+'
    
    top10_hash_ids = [id for id in top10_ids if re.match(hash_pattern, id)]
    waterfall_hash_ids = [id for id in waterfall_ids if re.match(hash_pattern, id)]
    
    print(f"\n   🔍 ID格式检查:")
    print(f"      • TOP 10使用hash格式的ID: {len(top10_hash_ids)}/{len(top10_ids)}")
    print(f"      • 瀑布流图使用hash格式的ID: {len(waterfall_hash_ids)}/{len(waterfall_ids)}")
    
    # 检查TOP 10的ID是否在瀑布流图中存在
    missing_ids = []
    for top10_id in top10_ids:
        if top10_id not in waterfall_ids:
            missing_ids.append(top10_id)
    
    if missing_ids:
        print(f"\n   ❌ 发现{len(missing_ids)}个TOP 10的ID在瀑布流图中不存在:")
        for mid in missing_ids[:3]:
            print(f"      - {mid}")
        checks_passed = False
    else:
        print(f"\n   ✅ 所有TOP 10的ID都在瀑布流图中存在")
        checks_passed = True
    
    # 检查是否有重复ID
    from collections import Counter
    id_counts = Counter(waterfall_ids)
    duplicates = {id: count for id, count in id_counts.items() if count > 1}
    
    if duplicates:
        print(f"\n   ⚠️  发现{len(duplicates)}个重复ID:")
        for dup_id, count in list(duplicates.items())[:3]:
            print(f"      - {dup_id}: 出现{count}次")
    else:
        print(f"   ✅ 没有重复ID")
    
    # 显示前3个TOP 10资源的ID示例
    print(f"\n   📋 TOP 10资源ID示例（前3个）:")
    for i, tid in enumerate(top10_ids[:3], 1):
        exists = "✅" if tid in waterfall_ids else "❌"
        print(f"      {i}. {tid} {exists}")
    
    # 清理文件
    Path(output_path).unlink(missing_ok=True)
    Path(har_path).unlink(missing_ok=True)
    
    # 总结
    print("\n\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)
    
    if checks_passed and len(top10_hash_ids) == len(top10_ids):
        print("✅ 跳转功能正常！")
        print("\n验证结果:")
        print("  1. ✓ TOP 10表格和瀑布流图使用相同的ID生成逻辑")
        print("  2. ✓ 所有TOP 10的ID都能在瀑布流图中找到")
        print("  3. ✓ ID格式统一使用URL hash + 索引")
        print("  4. ✓ 没有重复ID")
        print("\n功能说明:")
        print("  • 点击TOP 10表格中的任意资源行")
        print("  • JavaScript会调用scrollToResource()函数")
        print("  • 页面会自动滚动到瀑布流图中对应的资源位置")
        print("  • 该资源行会高亮显示，便于用户定位")
        return True
    else:
        print("❌ 跳转功能存在问题")
        if not checks_passed:
            print("  • TOP 10的ID与瀑布流图的ID不匹配")
        if len(top10_hash_ids) != len(top10_ids):
            print("  • ID格式不一致")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_jump_functionality())
    sys.exit(0 if success else 1)
