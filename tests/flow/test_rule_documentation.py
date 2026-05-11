"""
测试Waterfall性能诊断规则说明功能

验证：性能诊断结论部分是否包含详细的规则说明表格
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


async def test_rule_documentation():
    """测试规则说明功能"""
    
    print("=" * 70)
    print("测试: Waterfall性能诊断规则说明")
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
    ctx = FlowContext(flow_id='test-rule-doc', flow_name='test-rule-doc')
    
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
    print(f"   • 页面加载时间: {waterfall_result.page_load_time:.0f}ms")
    
    # 生成HTML报告（带模拟的性能问题）
    print("\n📋 步骤3: 生成HTML报告")
    print("-" * 70)
    
    # 创建模拟的性能问题
    mock_issues = [
        {
            "rule_id": "PERF-001",
            "severity": "warning",
            "message": f"页面总加载时间过长: {waterfall_result.page_load_time:.0f}ms"
        },
        {
            "rule_id": "PERF-005",
            "severity": "warning",
            "message": "服务器响应等待时间(TTFB)过长: https://example.com/api"
        }
    ]
    
    generator = ReportGenerator()
    output_path = "test_rule_documentation.html"
    
    html_content = generator.generate_waterfall_report(
        waterfall_result, 
        mock_issues, 
        output_path
    )
    
    print(f"✅ 报告已生成: {output_path}")
    
    # 验证HTML内容
    print("\n📋 步骤4: 验证规则说明内容")
    print("-" * 70)
    
    with open(output_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    checks = []
    
    # 检查1: 是否存在规则说明标题
    if "📖 诊断规则说明" in html or "诊断规则说明" in html:
        print("   ✓ 包含规则说明标题")
        checks.append(True)
    else:
        print("   ❌ 缺少规则说明标题")
        checks.append(False)
    
    # 检查2: 是否包含规则表格
    if "<table" in html and "规则ID" in html:
        print("   ✓ 包含规则说明表格")
        checks.append(True)
    else:
        print("   ❌ 缺少规则说明表格")
        checks.append(False)
    
    # 检查3: 是否包含所有7个规则的说明
    rule_ids = ["PERF-001", "PERF-002", "PERF-003", "PERF-004", "PERF-005", "PERF-006", "PERF-007"]
    found_rules = [rule_id for rule_id in rule_ids if rule_id in html]
    
    if len(found_rules) == len(rule_ids):
        print(f"   ✓ 包含所有{len(rule_ids)}个规则的说明")
        checks.append(True)
    else:
        print(f"   ⚠️  只找到{len(found_rules)}/{len(rule_ids)}个规则")
        missing = set(rule_ids) - set(found_rules)
        print(f"      缺失: {', '.join(missing)}")
        checks.append(False)
    
    # 检查4: 是否包含阈值标准
    threshold_keywords = ["3000ms", "200ms", "300ms", "500ms", "600ms", "2000ms"]
    found_thresholds = [kw for kw in threshold_keywords if kw in html]
    
    if len(found_thresholds) >= 5:  # 至少找到5个阈值
        print(f"   ✓ 包含阈值标准 ({len(found_thresholds)}/{len(threshold_keywords)})")
        checks.append(True)
    else:
        print(f"   ❌ 缺少阈值标准")
        checks.append(False)
    
    # 检查5: 是否包含严重级别说明
    severity_keywords = ["警告", "信息", "⚠️", "ℹ️"]
    found_severity = [kw for kw in severity_keywords if kw in html]
    
    if found_severity:
        print(f"   ✓ 包含严重级别说明")
        checks.append(True)
    else:
        print(f"   ❌ 缺少严重级别说明")
        checks.append(False)
    
    # 检查6: 是否包含提示框
    if "💡 提示" in html or "提示：" in html:
        print("   ✓ 包含优化提示")
        checks.append(True)
    else:
        print("   ⚠️  缺少优化提示（可选）")
        checks.append(True)  # 不影响整体判断
    
    # 清理文件
    Path(output_path).unlink(missing_ok=True)
    Path(har_path).unlink(missing_ok=True)
    
    # 总结
    print("\n\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)
    
    if all(checks):
        print("✅ 所有检查通过！规则说明功能已正确实现。")
        print("\n改进内容:")
        print("  1. ✓ 添加诊断规则说明章节")
        print("  2. ✓ 包含7个性能检测规则的详细说明")
        print("  3. ✓ 显示每个规则的阈值标准")
        print("  4. ✓ 标注严重级别（警告/信息）")
        print("  5. ✓ 提供优化建议和提示")
        return True
    else:
        passed = sum(checks)
        total = len(checks)
        print(f"⚠️  {passed}/{total} 检查通过")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_rule_documentation())
    sys.exit(0 if success else 1)
