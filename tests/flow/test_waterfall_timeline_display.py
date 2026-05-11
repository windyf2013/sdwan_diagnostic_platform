"""
Waterfall瀑布流时序图显示验证脚本

验证修复后的HTML模板是否正确显示5个阶段的分段条形图
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))


def test_waterfall_timeline_display():
    """测试瀑布流时序图的分段显示"""
    print("=" * 60)
    print("测试: Waterfall瀑布流时序图分段显示")
    print("=" * 60)
    
    from sdwan_desktop.services.reporter.report_generator import ReportGenerator
    from sdwan_desktop.core.types.waterfall import WaterfallResult, ResourceTiming
    
    # 创建包含各阶段耗时的模拟数据
    resources = [
        ResourceTiming(
            url="https://www.baidu.com/index.html",
            dns_time=50.0,      # DNS查询
            connect_time=30.0,  # TCP连接
            ssl_time=80.0,      # SSL握手
            wait_time=200.0,    # 等待响应(TTFB)
            download_time=150.0, # 内容下载
            total_time=510.0,
            content_size=50000,
            mime_type="text/html"
        ),
        ResourceTiming(
            url="https://www.baidu.com/style.css",
            dns_time=0.0,       # 复用连接，无DNS
            connect_time=0.0,   # 复用连接，无TCP
            ssl_time=0.0,       # 复用连接，无SSL
            wait_time=100.0,    # TTFB
            download_time=50.0, # 下载CSS
            total_time=150.0,
            content_size=10000,
            mime_type="text/css",
            is_render_blocking=True
        ),
        ResourceTiming(
            url="https://www.baidu.com/script.js",
            dns_time=0.0,
            connect_time=0.0,
            ssl_time=0.0,
            wait_time=80.0,
            download_time=120.0,
            total_time=200.0,
            content_size=20000,
            mime_type="application/javascript",
            is_render_blocking=True
        ),
    ]
    
    waterfall_result = WaterfallResult(
        target_url="https://www.baidu.com",
        page_load_time=510.0,
        total_requests=3,
        resources=resources
    )
    
    try:
        # 生成报告
        generator = ReportGenerator()
        output_path = "test_waterfall_timeline.html"
        
        print(f"\n正在生成报告到: {output_path}")
        html_content = generator.generate_waterfall_report(waterfall_result, [], output_path)
        
        # 验证报告文件是否生成
        if Path(output_path).exists():
            file_size = Path(output_path).stat().st_size
            print(f"✅ 报告生成成功!")
            print(f"   - 文件路径: {Path(output_path).absolute()}")
            print(f"   - 文件大小: {file_size} bytes")
            
            # 读取HTML内容进行详细分析
            with open(output_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # 调试：打印前2000个字符查看实际格式
            print(f"\n   🔍 HTML片段预览:")
            preview_start = html_content.find('timeline-bar')
            if preview_start > 0:
                preview = html_content[preview_start:preview_start+1500]
                print(preview[:500])
            
            # 检查HTML内容是否包含各阶段的条形图
            checks = {
                "DNS阶段": 'class="bar-segment dns"',
                "TCP阶段": 'class="bar-segment connect"',
                "SSL阶段": 'class="bar-segment ssl"',
                "Wait阶段": 'class="bar-segment wait"',
                "Download阶段": 'class="bar-segment download"',
                "宽度计算": 'width:',
                "DNS提示": 'title="DNS:',
                "TCP提示": 'title="TCP:',
                "SSL提示": 'title="SSL:',
                "TTFB提示": 'title="TTFB:',
                "Download提示": 'title="Download:',
            }
            
            all_passed = True
            for check_name, check_pattern in checks.items():
                if check_pattern in html_content:
                    print(f"   ✓ {check_name}: 找到")
                else:
                    print(f"   ❌ {check_name}: 未找到")
                    all_passed = False
            
            # 检查时序正确性（left偏移量）
            print("\n   📊 时序正确性检查:")
            
            # 提取第一个资源的条形图数据
            import re
            bar_segments = re.findall(r'<div class="bar-segment (\w+)" style="left: ([\d.]+)%; width: ([\d.]+)%;"', html_content)
            
            if bar_segments:
                print(f"   ✓ 找到 {len(bar_segments)} 个条形段")
                
                # 检查第一个资源的时序
                first_resource_segments = bar_segments[:5]  # 取前5个（第一个资源的所有阶段）
                expected_order = ['dns', 'connect', 'ssl', 'wait', 'download']
                
                actual_order = [seg[0] for seg in first_resource_segments]
                print(f"   - 实际顺序: {' → '.join(actual_order)}")
                print(f"   - 期望顺序: {' → '.join(expected_order)}")
                
                if actual_order == expected_order:
                    print(f"   ✓ 时序顺序: 正确")
                else:
                    print(f"   ❌ 时序顺序: 错误")
                    all_passed = False
                
                # 检查left偏移量是否递增
                left_values = [float(seg[1]) for seg in first_resource_segments]
                print(f"   - Left偏移: {left_values}")
                
                is_increasing = all(left_values[i] <= left_values[i+1] for i in range(len(left_values)-1))
                if is_increasing:
                    print(f"   ✓ Left偏移递增: 正确")
                else:
                    print(f"   ❌ Left偏移递增: 错误")
                    all_passed = False
            else:
                print(f"   ❌ 未找到条形段数据")
                all_passed = False
            
            # 清理测试文件
            Path(output_path).unlink()
            print(f"\n✓ 测试文件已清理")
            
            if all_passed:
                print("\n🎉 所有检查通过！瀑布流时序图分段显示功能正常。")
                return True
            else:
                print("\n⚠️  部分检查失败，请查看上述结果。")
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
    success = test_waterfall_timeline_display()
    sys.exit(0 if success else 1)
