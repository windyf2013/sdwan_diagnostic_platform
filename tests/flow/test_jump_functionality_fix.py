"""
验证跳转功能修复

测试：点击TOP 10中的资源，应该跳转到该资源在瀑布流图中的实际位置
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
from sdwan_desktop.services.reporter.report_generator import ReportGenerator


def generate_resource_id(url):
    """生成资源的唯一ID（与Jinja2模板逻辑一致）"""
    safe_url = url.replace('https://', '').replace('http://', '')
    safe_url = safe_url.replace('/', '-').replace('.', '-').replace(':', '-')
    safe_url = safe_url.replace('?', '-').replace('&', '-').replace('=', '-')
    safe_url = safe_url.replace('_', '-').replace('%', '-')
    return "resource-" + safe_url[:100]


async def verify_jump_functionality():
    """验证跳转功能"""
    
    print("=" * 70)
    print("验证: TOP 10跳转功能修复")
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
            'timeout': 30000
        }
    )
    ctx = FlowContext(flow_id='verify-jump', flow_name='verify-jump')
    
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
    
    # 找出最慢的10个资源
    sorted_resources = sorted(waterfall_result.resources, key=lambda x: x.total_time, reverse=True)
    top10 = sorted_resources[:10]
    
    print(f"\n📊 最慢资源 TOP 10:")
    for i, resource in enumerate(top10, 1):
        resource_id = generate_resource_id(resource.url)
        # 找到该资源在原始列表中的位置
        actual_index = waterfall_result.resources.index(resource) + 1
        print(f"   {i}. #{actual_index} - {resource.total_time:.0f}ms - {resource.url[:60]}...")
        print(f"      Resource ID: {resource_id[:50]}...")
    
    # 生成HTML报告
    print("\n📋 步骤3: 生成HTML报告")
    print("-" * 70)
    
    generator = ReportGenerator()
    output_path = "jump_functionality_test.html"
    
    html_content = generator.generate_waterfall_report(
        waterfall_result, 
        [], 
        output_path
    )
    
    print(f"✅ 报告已生成: {output_path}")
    
    # 验证HTML内容
    print("\n📋 步骤4: 验证HTML内容")
    print("-" * 70)
    
    with open(output_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    checks = []
    
    # 检查1: 资源行使用URL生成的ID
    if 'resource-' in html and 'id="resource-' in html:
        print("   ✓ 资源行包含基于URL的ID")
        checks.append(True)
    else:
        print("   ❌ 资源行ID生成有问题")
        checks.append(False)
    
    # 检查2: TOP 10表格使用相同的ID生成逻辑
    if 'scrollToResource(' in html:
        # 检查是否传递的是字符串ID而不是数字索引
        import re
        scroll_calls = re.findall(r'scrollToResource\([\'"]([^\'"]+)[\'"]\)', html)
        if scroll_calls:
            # 检查第一个调用是否是URL-based ID
            first_call = scroll_calls[0]
            if first_call.startswith('resource-') and not first_call.replace('resource-', '').isdigit():
                print(f"   ✓ TOP 10使用URL-based ID跳转")
                print(f"      示例: scrollToResource('{first_call[:50]}...')")
                checks.append(True)
            else:
                print(f"   ❌ TOP 10仍使用数字索引: {first_call}")
                checks.append(False)
        else:
            print("   ❌ 未找到scrollToResource调用")
            checks.append(False)
    else:
        print("   ❌ 缺少scrollToResource函数调用")
        checks.append(False)
    
    # 检查3: JavaScript函数接受字符串参数
    if 'function scrollToResource(resourceId)' in html:
        print("   ✓ JavaScript函数使用resourceId参数")
        checks.append(True)
    else:
        print("   ❌ JavaScript函数参数有问题")
        checks.append(False)
    
    # 检查4: 验证ID一致性
    # 随机选择一个TOP 10资源，检查其ID在瀑布流图和TOP 10中是否一致
    if top10:
        test_resource = top10[0]
        expected_id = generate_resource_id(test_resource.url)
        
        # 检查该ID是否在HTML中出现至少2次（一次在资源行，一次在TOP 10）
        id_count = html.count(expected_id)
        if id_count >= 2:
            print(f"   ✓ ID一致性验证通过 (ID出现{ id_count}次)")
            checks.append(True)
        else:
            print(f"   ❌ ID一致性验证失败 (ID只出现{id_count}次)")
            print(f"      期望ID: {expected_id[:50]}...")
            checks.append(False)
    
    # 清理文件
    Path(output_path).unlink(missing_ok=True)
    Path(har_path).unlink(missing_ok=True)
    
    # 总结
    print("\n\n" + "=" * 70)
    print("验证总结")
    print("=" * 70)
    
    if all(checks):
        print("✅ 所有检查通过！跳转功能已正确修复。")
        print("\n修复内容:")
        print("  1. ✓ 资源行使用基于URL的唯一ID")
        print("  2. ✓ TOP 10表格使用相同的ID生成逻辑")
        print("  3. ✓ JavaScript函数接受字符串ID参数")
        print("  4. ✓ ID在瀑布流图和TOP 10中保持一致")
        print("\n效果:")
        print("  • 点击TOP 10中的任意资源")
        print("  • 跳转到该资源在瀑布流图中的实际位置")
        print("  • 无论该资源是第几行，都能准确定位")
        return True
    else:
        passed = sum(checks)
        total = len(checks)
        print(f"⚠️  {passed}/{total} 检查通过，部分功能可能未正确实现")
        return False


if __name__ == "__main__":
    success = asyncio.run(verify_jump_functionality())
    sys.exit(0 if success else 1)
