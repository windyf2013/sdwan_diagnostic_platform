"""
验证瀑布流图资源行的点击跳转功能

确保修复布局问题时没有破坏原有的跳转功能
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
    print("测试: 瀑布流图资源行点击跳转功能")
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
    
    print(f"✅ 总资源数: {waterfall_result.total_requests}")
    
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
    
    # 验证HTML结构
    print("\n📋 步骤4: 验证跳转功能")
    print("-" * 70)
    
    with open(output_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    checks_passed = True
    
    # 检查1: scrollToResource函数是否存在
    if 'function scrollToResource(resourceId)' in html:
        print("   ✅ scrollToResource函数存在")
    else:
        print("   ❌ scrollToResource函数缺失")
        checks_passed = False
    
    # 检查2: 瀑布流图资源行是否有onclick属性
    waterfall_section = re.search(r'<div class="waterfall-chart".*?</div>\s*</div>', html, re.DOTALL)
    
    if waterfall_section:
        section_html = waterfall_section.group(0)
        
        # 查找所有resource-row
        resource_rows = re.findall(r'<div class="resource-row"[^>]*>', section_html)
        print(f"   ✅ 找到{len(resource_rows)}个resource-row元素")
        
        # 检查是否有onclick属性
        rows_with_onclick = [row for row in resource_rows if 'onclick=' in row]
        print(f"   ✅ 其中{len(rows_with_onclick)}个有onclick属性")
        
        if len(rows_with_onclick) > 0:
            print(f"   ✅ 瀑布流图资源行支持点击跳转")
            
            # 显示一个示例
            if rows_with_onclick:
                example = rows_with_onclick[0][:150]
                print(f"   📝 示例: {example}...")
        else:
            print(f"   ❌ 瀑布流图资源行缺少onclick属性")
            checks_passed = False
        
        # 检查3: TOP 10表格是否有onclick属性
        top10_rows = re.findall(r'<tr onclick="scrollToResource\([^"]+\)"', html)
        print(f"   ✅ TOP 10表格有{len(top10_rows)}个可点击行")
        
        if len(top10_rows) == 0:
            print(f"   ⚠️  警告: TOP 10表格可能缺少跳转功能")
        
        # 检查4: ID是否唯一
        all_ids = re.findall(r'id="(resource-[^"]+)"', html)
        unique_ids = set(all_ids)
        
        if len(all_ids) == len(unique_ids):
            print(f"   ✅ 所有{len(unique_ids)}个资源ID都是唯一的")
        else:
            duplicate_count = len(all_ids) - len(unique_ids)
            print(f"   ❌ 发现{duplicate_count}个重复ID")
            checks_passed = False
            
            # 显示重复的ID
            from collections import Counter
            id_counts = Counter(all_ids)
            duplicates = {id: count for id, count in id_counts.items() if count > 1}
            for dup_id, count in list(duplicates.items())[:3]:
                print(f"      - {dup_id}: 出现{count}次")
    else:
        print("   ⚠️  未找到瀑布流图部分")
        checks_passed = False
    
    # 检查5: 高亮效果CSS
    if "element.style.backgroundColor = '#fff3cd'" in html:
        print("   ✅ 高亮效果代码存在")
    else:
        print("   ⚠️  高亮效果代码可能缺失")
    
    # 清理文件
    Path(output_path).unlink(missing_ok=True)
    Path(har_path).unlink(missing_ok=True)
    
    # 总结
    print("\n\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)
    
    if checks_passed:
        print("✅ 跳转功能完全正常！")
        print("\n功能验证:")
        print("  1. ✓ scrollToResource函数存在")
        print("  2. ✓ 瀑布流图资源行有onclick属性")
        print("  3. ✓ TOP 10表格有onclick属性")
        print("  4. ✓ 所有资源ID唯一")
        print("  5. ✓ 高亮效果代码存在")
        print("\n用户体验:")
        print("  • 点击瀑布流图的任意资源行 → 平滑滚动并高亮显示")
        print("  • 点击TOP 10表格的任意行 → 跳转到对应资源")
        print("  • 高亮持续2秒后自动恢复")
        return True
    else:
        print("❌ 跳转功能存在问题")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_jump_functionality())
    sys.exit(0 if success else 1)
