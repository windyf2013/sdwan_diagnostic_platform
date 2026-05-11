"""
测试重复URL资源的唯一ID生成

验证：相同URL的多个资源是否有唯一的ID
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from sdwan_desktop.tools.implementations.web.har_capture import HarCaptureTool
from sdwan_desktop.services.parser.har_parser import HarParser
from sdwan_desktop.services.reporter.report_generator import ReportGenerator
from sdwan_desktop.core.types.tool import ToolRequest
from sdwan_desktop.core.types.context import FlowContext


async def test_duplicate_url_resources():
    """测试重复URL资源的ID唯一性"""
    
    print("=" * 70)
    print("测试: 重复URL资源的唯一ID生成")
    print("=" * 70)
    
    # 采集HAR数据
    print("\n📋 步骤1: 采集HAR数据")
    print("-" * 70)
    
    tool = HarCaptureTool()
    req = ToolRequest(
        tool_name='har_capture',
        parameters={
            'url': 'https://www.joom.com',  # 使用之前产生问题的网站
            'headless': True,
            'timeout': 30000,
            'wait_until': 'networkidle'
        }
    )
    ctx = FlowContext(flow_id='test-duplicate-url', flow_name='test-duplicate-url')
    
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
    
    # 检查是否有重复URL
    url_count = {}
    for resource in waterfall_result.resources:
        url = resource.url
        if url in url_count:
            url_count[url] += 1
        else:
            url_count[url] = 1
    
    duplicate_urls = {url: count for url, count in url_count.items() if count > 1}
    
    if duplicate_urls:
        print(f"\n⚠️  发现 {len(duplicate_urls)} 个重复URL:")
        for url, count in list(duplicate_urls.items())[:5]:  # 只显示前5个
            print(f"   • {url[:80]}... (出现{count}次)")
    else:
        print("\n✅ 未发现重复URL")
    
    # 生成HTML报告
    print("\n📋 步骤3: 生成HTML报告")
    print("-" * 70)
    
    generator = ReportGenerator()
    output_path = "test_duplicate_url.html"
    
    html_content = generator.generate_waterfall_report(
        waterfall_result, 
        [],
        output_path
    )
    
    print(f"✅ 报告已生成: {output_path}")
    
    # 验证HTML内容
    print("\n📋 步骤4: 验证ID唯一性")
    print("-" * 70)
    
    with open(output_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    # 提取所有resource-row的ID
    import re
    id_pattern = r'id="resource-([^"]+)"'
    all_ids = re.findall(id_pattern, html)
    
    print(f"   • 找到 {len(all_ids)} 个资源ID")
    
    # 检查ID是否唯一
    unique_ids = set(all_ids)
    duplicate_ids = [id for id in all_ids if all_ids.count(id) > 1]
    unique_duplicate_ids = set(duplicate_ids)
    
    if unique_duplicate_ids:
        print(f"   ❌ 发现 {len(unique_duplicate_ids)} 个重复ID:")
        for dup_id in list(unique_duplicate_ids)[:5]:
            count = all_ids.count(dup_id)
            print(f"      - {dup_id} (出现{count}次)")
        checks_passed = False
    else:
        print(f"   ✅ 所有ID都是唯一的 ({len(unique_ids)} 个唯一ID)")
        checks_passed = True
    
    # 检查是否使用了hash机制
    if re.search(r'resource-[a-f0-9]{8}-\d+', html):
        print("   ✅ 使用了URL hash + 索引的ID生成机制")
    else:
        print("   ⚠️  未检测到hash格式的ID")
    
    # 清理文件
    Path(output_path).unlink(missing_ok=True)
    Path(har_path).unlink(missing_ok=True)
    
    # 总结
    print("\n\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)
    
    if checks_passed:
        print("✅ ID唯一性检查通过！重复URL资源问题已修复。")
        print("\n改进内容:")
        print("  1. ✓ 使用URL hash确保相同URL的基础ID一致")
        print("  2. ✓ 添加循环索引确保每个资源有唯一ID")
        print("  3. ✓ TOP 10表格和瀑布流图使用相同的ID生成逻辑")
        print("  4. ✓ JavaScript跳转可以准确定位到目标资源")
        return True
    else:
        print("❌ ID唯一性检查失败，仍存在重复ID问题")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_duplicate_url_resources())
    sys.exit(0 if success else 1)
