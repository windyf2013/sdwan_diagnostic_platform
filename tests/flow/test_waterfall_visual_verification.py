"""
Waterfall瀑布流时序图可视化验证脚本

生成一个包含多种场景的测试报告，直观验证时序正确性
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))


def create_visual_test():
    """创建可视化测试报告"""
    print("=" * 70)
    print("Waterfall瀑布流时序图 - 可视化验证")
    print("=" * 70)
    
    from sdwan_desktop.services.reporter.report_generator import ReportGenerator
    from sdwan_desktop.core.types.waterfall import WaterfallResult, ResourceTiming
    
    # 创建4种典型场景的资源
    resources = [
        # 场景1: 首屏HTML（包含所有5个阶段）
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
        ),
        
        # 场景2: CSS文件（复用连接，仅有Wait+Download）
        ResourceTiming(
            url="https://www.baidu.com/css/style.css",
            dns_time=0.0,
            connect_time=0.0,
            ssl_time=0.0,
            wait_time=100.0,
            download_time=50.0,
            total_time=150.0,
            content_size=10000,
            mime_type="text/css",
            is_render_blocking=True
        ),
        
        # 场景3: JS文件（复用连接，仅有Wait+Download）
        ResourceTiming(
            url="https://www.baidu.com/js/app.js",
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
        
        # 场景4: 图片资源（新连接，包含DNS+TCP+SSL+Wait+Download）
        ResourceTiming(
            url="https://img.baidu.com/logo.png",
            dns_time=45.0,
            connect_time=25.0,
            ssl_time=70.0,
            wait_time=150.0,
            download_time=300.0,
            total_time=590.0,
            content_size=150000,
            mime_type="image/png"
        ),
    ]
    
    waterfall_result = WaterfallResult(
        target_url="https://www.baidu.com",
        page_load_time=590.0,
        total_requests=4,
        resources=resources
    )
    
    try:
        # 生成报告
        generator = ReportGenerator()
        output_path = "waterfall_visual_test.html"
        
        print(f"\n正在生成可视化测试报告...")
        html_content = generator.generate_waterfall_report(waterfall_result, [], output_path)
        
        # 验证报告文件是否生成
        if Path(output_path).exists():
            file_size = Path(output_path).stat().st_size
            print(f"✅ 报告生成成功!")
            print(f"   📁 文件路径: {Path(output_path).absolute()}")
            print(f"   📊 文件大小: {file_size} bytes")
            
            # 读取并分析HTML内容
            with open(output_path, 'r', encoding='utf-8') as f:
                html = f.read()
            
            # 统计各阶段的出现次数
            import re
            segments = re.findall(r'class="bar-segment (\w+)"', html)
            
            print(f"\n📈 阶段统计:")
            stage_counts = {}
            for seg in segments:
                stage_counts[seg] = stage_counts.get(seg, 0) + 1
            
            stage_names = {
                'dns': 'DNS查询',
                'connect': 'TCP连接',
                'ssl': 'SSL握手',
                'wait': '等待响应',
                'download': '内容下载'
            }
            
            for stage, count in stage_counts.items():
                name = stage_names.get(stage, stage)
                bar = "█" * count
                print(f"   {name:8s}: {count}个  {bar}")
            
            # 验证实例1的时序
            print(f"\n🔍 实例验证 (index.html):")
            pattern = r'<div class="resource-name"[^>]*>https://www\.baidu\.com/index\.html</div>.*?<div class="timeline-bar">(.*?)</div>'
            match = re.search(pattern, html, re.DOTALL)
            
            if match:
                timeline_html = match.group(1)
                bars = re.findall(r'class="bar-segment (\w+)" style="left: ([\d.]+)%; width: ([\d.]+)%;"', timeline_html)
                
                print(f"   找到 {len(bars)} 个阶段:")
                for i, (stage, left, width) in enumerate(bars):
                    name = stage_names.get(stage, stage)
                    print(f"   {i+1}. {name:8s} - left={left:>6s}%, width={width:>6s}%")
                
                # 验证时序是否正确（left值应该递增）
                left_values = [float(left) for _, left, _ in bars]
                is_sorted = all(left_values[i] < left_values[i+1] for i in range(len(left_values)-1))
                
                if is_sorted:
                    print(f"   ✅ 时序顺序: 正确（left值递增）")
                else:
                    print(f"   ❌ 时序顺序: 错误")
            else:
                print(f"   ⚠️  未找到index.html的时间轴数据")
            
            print(f"\n💡 请在浏览器中打开报告查看视觉效果:")
            print(f"   {Path(output_path).absolute()}")
            print(f"\n预期效果:")
            print(f"   • index.html: 5个彩色分段（蓝→橙→紫→黄→绿）")
            print(f"   • style.css:  2个分段（黄→绿，无DNS/TCP/SSL）")
            print(f"   • app.js:     2个分段（黄→绿，无DNS/TCP/SSL）")
            print(f"   • logo.png:   5个彩色分段（蓝→橙→紫→黄→绿）")
            
            return True
        else:
            print(f"❌ 报告文件未生成")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = create_visual_test()
    sys.exit(0 if success else 1)
