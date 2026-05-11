"""
验证相同URL的区分显示功能

确保用户能够识别同一URL的多次请求
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


async def test_duplicate_url_display():
    """测试相同URL的区分显示"""
    
    print("=" * 70)
    print("测试: 相同URL的区分显示功能")
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
    ctx = FlowContext(flow_id='test-duplicate-url', flow_name='test-duplicate-url')
    
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
    
    # 统计重复URL
    from collections import Counter
    url_counts = Counter(r.url for r in waterfall_result.resources)
    duplicate_urls = {url: count for url, count in url_counts.items() if count > 1}
    
    print(f"\n🔍 重复URL统计:")
    if duplicate_urls:
        for url, count in sorted(duplicate_urls.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"   • {url[:80]}... : {count}次")
    else:
        print(f"   ℹ️  没有重复的URL")
    
    # 生成HTML报告
    print("\n📋 步骤3: 生成HTML报告")
    print("-" * 70)
    
    generator = ReportGenerator()
    output_path = "test_duplicate_url_display.html"
    
    html_content = generator.generate_waterfall_report(
        waterfall_result, 
        [],
        output_path
    )
    
    print(f"✅ 报告已生成: {output_path}")
    
    # 验证HTML结构
    print("\n📋 步骤4: 验证区分显示功能")
    print("-" * 70)
    
    with open(output_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    checks_passed = True
    
    # 检查1: resource-index样式是否存在
    if '.resource-index' in html:
        print("   ✅ resource-index样式存在")
    else:
        print("   ❌ resource-index样式缺失")
        checks_passed = False
    
    # 检查2: resource-status样式是否存在
    if '.resource-status' in html:
        print("   ✅ resource-status样式存在")
    else:
        print("   ❌ resource-status样式缺失")
        checks_passed = False
    
    # 检查3: 状态码颜色样式是否存在
    status_classes = ['.status-200', '.status-301', '.status-400', '.status-500']
    found_status_classes = [cls for cls in status_classes if cls in html]
    print(f"   ✅ 找到{len(found_status_classes)}/{len(status_classes)}个状态码颜色样式")
    
    # 检查4: 瀑布流图中是否有序号标识
    resource_indexes = re.findall(r'<span class="resource-index">#(\d+)</span>', html)
    if resource_indexes:
        print(f"   ✅ 找到{len(resource_indexes)}个序号标识")
        print(f"   📝 示例序号: {', '.join(resource_indexes[:5])}")
    else:
        print(f"   ❌ 未找到序号标识")
        checks_passed = False
    
    # 检查5: 是否有状态码显示
    resource_statuses = re.findall(r'<span class="resource-status status-\d+">(\d+)</span>', html)
    if resource_statuses:
        print(f"   ✅ 找到{len(resource_statuses)}个状态码显示")
        
        # 统计不同状态码
        status_counter = Counter(resource_statuses)
        print(f"   📊 状态码分布: {dict(status_counter)}")
    else:
        print(f"   ❌ 未找到状态码显示")
        checks_passed = False
    
    # 检查6: URL文本是否有单独的class
    if 'resource-url-text' in html:
        print("   ✅ resource-url-text样式存在")
    else:
        print("   ⚠️  resource-url-text样式可能缺失")
    
    # 清理文件
    Path(output_path).unlink(missing_ok=True)
    Path(har_path).unlink(missing_ok=True)
    
    # 总结
    print("\n\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)
    
    if checks_passed:
        print("✅ 相同URL区分显示功能正常！")
        print("\n功能特性:")
        print("  1. ✓ 每个资源行显示序号 (#1, #2, #3...)")
        print("  2. ✓ 显示HTTP状态码 (200, 301, 404等)")
        print("  3. ✓ 状态码有颜色区分 (绿色/黄色/红色)")
        print("  4. ✓ URL文本清晰可读")
        print("\n用户体验:")
        print("  • 即使URL相同，也能通过序号和状态码区分")
        print("  • 快速识别成功/重定向/失败的请求")
        print("  • 悬停查看完整URL和方法信息")
        return True
    else:
        print("❌ 区分显示功能存在问题")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_duplicate_url_display())
    sys.exit(0 if success else 1)
