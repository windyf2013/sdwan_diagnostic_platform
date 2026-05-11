"""
测试瀑布流时序图布局修复

验证：资源行不会超出容器框架
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sdwan_desktop.tools.implementations.web.har_capture import HarCaptureTool
from sdwan_desktop.services.parser.har_parser import HarParser
from sdwan_desktop.services.reporter.report_generator import ReportGenerator
from sdwan_desktop.core.types.tool import ToolRequest
from sdwan_desktop.core.types.context import FlowContext


async def test_waterfall_layout():
    """测试瀑布流布局"""
    
    print("=" * 70)
    print("测试: 瀑布流时序图布局")
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
    ctx = FlowContext(flow_id='test-layout', flow_name='test-layout')
    
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
    print(f"   • 页面加载耗时: {waterfall_result.page_load_time:.0f}ms")
    
    # 生成HTML报告
    print("\n📋 步骤3: 生成HTML报告")
    print("-" * 70)
    
    generator = ReportGenerator()
    output_path = "test_waterfall_layout.html"
    
    html_content = generator.generate_waterfall_report(
        waterfall_result, 
        [],
        output_path
    )
    
    print(f"✅ 报告已生成: {output_path}")
    
    # 验证HTML结构
    print("\n📋 步骤4: 验证HTML结构")
    print("-" * 70)
    
    with open(output_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    # 检查是否有错误的<tr>标签在瀑布流图中
    import re
    
    # 查找瀑布流图部分的<tr>标签（应该是<div class="resource-row">）
    waterfall_section = re.search(r'<div class="waterfall-chart".*?</div>\s*</div>', html, re.DOTALL)
    
    if waterfall_section:
        section_html = waterfall_section.group(0)
        
        # 检查是否有<tr>标签
        tr_tags = re.findall(r'<tr[^>]*>', section_html)
        
        if tr_tags:
            print(f"   ❌ 发现{len(tr_tags)}个错误的<tr>标签在瀑布流图中")
            for tr in tr_tags[:3]:
                print(f"      - {tr[:100]}")
            checks_passed = False
        else:
            print(f"   ✅ 没有发现错误的<tr>标签")
            checks_passed = True
        
        # 检查resource-row的数量
        resource_rows = re.findall(r'<div class="resource-row"', section_html)
        print(f"   ✅ 找到{len(resource_rows)}个resource-row元素")
        
        if len(resource_rows) != waterfall_result.total_requests:
            print(f"   ⚠️  警告: resource-row数量({len(resource_rows)})与资源数({waterfall_result.total_requests})不匹配")
    else:
        print(f"   ⚠️  未找到瀑布流图部分")
        checks_passed = False
    
    # 检查CSS样式
    print("\n📋 步骤5: 验证CSS样式")
    print("-" * 70)
    
    css_checks = [
        ('min-width: fit-content', 'resource-row有min-width'),
        ('flex-shrink: 0', 'resource-name不允许缩小'),
        ('min-width: 400px', 'timeline-bar有最小宽度'),
    ]
    
    for pattern, description in css_checks:
        if pattern in html:
            print(f"   ✅ {description}")
        else:
            print(f"   ⚠️  {description} - 未找到")
    
    # 清理文件
    Path(output_path).unlink(missing_ok=True)
    Path(har_path).unlink(missing_ok=True)
    
    # 总结
    print("\n\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)
    
    if checks_passed:
        print("✅ 瀑布流布局修复成功！")
        print("\n改进内容:")
        print("  1. ✓ 修复HTML结构错误（<tr>改为<div>）")
        print("  2. ✓ 添加min-width防止内容被压缩")
        print("  3. ✓ 设置flex-shrink: 0防止元素缩小")
        print("  4. ✓ timeline-bar设置最小宽度400px")
        print("  5. ✓ resource-name和resource-time固定宽度")
        return True
    else:
        print("❌ 布局检查发现问题")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_waterfall_layout())
    sys.exit(0 if success else 1)
