"""
Waterfall 报告生成测试

验证 waterfall.html 模板是否能正确渲染。
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))


def test_waterfall_template():
    """测试 waterfall 模板渲染"""
    print("=" * 60)
    print("测试: Waterfall 模板渲染")
    print("=" * 60)
    
    from sdwan_desktop.services.reporter.report_generator import ReportGenerator
    from sdwan_desktop.core.types.waterfall import WaterfallResult, ResourceTiming
    
    # 创建模拟数据
    resources = [
        ResourceTiming(url="https://www.baidu.com/index.html", total_time=1500, content_size=50000),
        ResourceTiming(url="https://www.baidu.com/style.css", total_time=200, content_size=10000),
        ResourceTiming(url="https://www.baidu.com/script.js", total_time=300, content_size=20000),
        ResourceTiming(url="https://www.baidu.com/logo.png", total_time=100, content_size=5000),
        ResourceTiming(url="https://www.baidu.com/api/data", total_time=800, content_size=30000),
    ]
    
    waterfall_result = WaterfallResult(
        target_url="https://www.baidu.com",
        page_load_time=2900,
        total_requests=5,
        resources=resources
    )
    
    # 模拟性能问题
    all_issues = [
        {
            "severity": 2,
            "message": "页面加载时间过长",
            "suggestion": "优化资源加载"
        },
        {
            "severity": 1,
            "message": "DNS 解析较慢",
            "suggestion": "使用更快的 DNS 服务器"
        }
    ]
    
    try:
        # 生成报告
        generator = ReportGenerator()
        output_path = "test_waterfall_report.html"
        
        print(f"\n正在生成报告到: {output_path}")
        html_content = generator.generate_waterfall_report(waterfall_result, all_issues, output_path)
        
        # 验证报告文件是否生成
        if Path(output_path).exists():
            file_size = Path(output_path).stat().st_size
            print(f"✅ 报告生成成功!")
            print(f"   - 文件路径: {Path(output_path).absolute()}")
            print(f"   - 文件大小: {file_size} bytes")
            print(f"   - HTML 内容长度: {len(html_content)} characters")
            
            # 检查 HTML 内容是否包含关键部分
            if "waterfall-chart" in html_content:
                print(f"   ✓ 包含瀑布流图表")
            if "top-resources" in html_content or "资源列表" in html_content:
                print(f"   ✓ 包含资源列表")
            if "性能问题" in html_content or "performance-issues" in html_content:
                print(f"   ✓ 包含性能问题分析")
            
            # 清理测试文件
            Path(output_path).unlink()
            print(f"\n✓ 测试文件已清理")
            
            return True
        else:
            print(f"❌ 报告文件未生成")
            return False
            
    except Exception as e:
        print(f"\n❌ 模板渲染失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行测试"""
    print("\n" + "=" * 60)
    print("Waterfall 报告生成测试")
    print("=" * 60 + "\n")
    
    success = test_waterfall_template()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 测试通过！Waterfall 模板修复成功。")
    else:
        print("❌ 测试失败！请检查模板语法。")
    print("=" * 60)
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
