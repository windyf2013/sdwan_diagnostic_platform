"""
快速验证脚本：检查waterfall模板中各阶段是否显示时间文本
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


def verify_timeline_display():
    """验证时序图各阶段的时间显示"""
    print("=" * 70)
    print("验证: Waterfall时序图各阶段时间显示")
    print("=" * 70)
    
    from sdwan_desktop.services.reporter.report_generator import ReportGenerator
    from sdwan_desktop.core.types.waterfall import WaterfallResult, ResourceTiming
    
    # 创建测试数据
    resources = [
        ResourceTiming(
            url="https://www.baidu.com/index.html",
            dns_time=50.0,
            connect_time=30.0,
            ssl_time=80.0,
            wait_time=200.0,
            download_time=150.0,
            total_time=510.0,
            content_size=50000,
            mime_type="text/html"
        )
    ]
    
    result = WaterfallResult(
        target_url="https://www.baidu.com",
        page_load_time=510.0,
        total_requests=1,
        resources=resources
    )
    
    try:
        # 生成报告
        generator = ReportGenerator()
        output_path = "verify_all_stages.html"
        
        print(f"\n正在生成测试报告...")
        html_content = generator.generate_waterfall_report(result, [], output_path)
        
        # 验证文件
        if Path(output_path).exists():
            with open(output_path, 'r', encoding='utf-8') as f:
                html = f.read()
            
            # 提取所有阶段的时间文本
            import re
            pattern = r'class="bar-segment (\w+)"[^>]*>(\d+ms)</div>'
            matches = re.findall(pattern, html)
            
            print(f"\n✅ 报告生成成功!")
            print(f"   📁 文件: {Path(output_path).absolute()}")
            print(f"\n📊 各阶段时间显示:")
            
            stage_names = {
                'dns': 'DNS查询',
                'connect': 'TCP连接',
                'ssl': 'SSL握手',
                'wait': '等待响应(TTFB)',
                'download': '内容下载'
            }
            
            expected_stages = ['dns', 'connect', 'ssl', 'wait', 'download']
            found_stages = {stage: time for stage, time in matches}
            
            all_correct = True
            for stage in expected_stages:
                name = stage_names.get(stage, stage)
                if stage in found_stages:
                    time_text = found_stages[stage]
                    print(f"   ✓ {name:15s}: {time_text}")
                else:
                    print(f"   ❌ {name:15s}: 未找到时间文本")
                    all_correct = False
            
            # 验证数值正确性
            print(f"\n🔍 数值验证:")
            expected_values = {
                'dns': '50ms',
                'connect': '30ms',
                'ssl': '80ms',
                'wait': '200ms',
                'download': '150ms'
            }
            
            for stage, expected in expected_values.items():
                if stage in found_stages:
                    actual = found_stages[stage]
                    if actual == expected:
                        print(f"   ✓ {stage:10s}: {actual} (正确)")
                    else:
                        print(f"   ⚠️  {stage:10s}: {actual} (期望{expected})")
                        all_correct = False
            
            # 清理文件
            Path(output_path).unlink()
            print(f"\n✓ 测试文件已清理")
            
            if all_correct:
                print(f"\n🎉 所有阶段时间显示正确!")
                return True
            else:
                print(f"\n⚠️  部分阶段存在问题，请检查")
                return False
        else:
            print(f"❌ 报告文件未生成")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = verify_timeline_display()
    sys.exit(0 if success else 1)
