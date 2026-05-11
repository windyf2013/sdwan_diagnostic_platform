"""
Waterfall重定向和资源完整性测试

测试场景：
1. 访问会发生重定向的域名（joom.com → joom.com/en）
2. 多次测试同一域名，验证资源数量的一致性
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


async def test_redirect_and_consistency():
    """测试重定向和资源一致性"""
    from sdwan_desktop.tools.implementations.web.har_capture import HarCaptureTool
    from sdwan_desktop.services.parser.har_parser import HarParser
    from sdwan_desktop.core.types.tool import ToolRequest
    from sdwan_desktop.core.types.context import FlowContext
    
    print("=" * 80)
    print("Waterfall功能测试：重定向和资源完整性")
    print("=" * 80)
    
    # 测试URL列表
    test_urls = [
        "https://joom.com",  # 会重定向到 joom.com/en
        "https://www.baidu.com",  # 稳定的国内网站
    ]
    
    for url in test_urls:
        print(f"\n{'='*80}")
        print(f"测试目标: {url}")
        print(f"{'='*80}")
        
        # 进行3次测试，验证一致性
        resource_counts = []
        
        for i in range(3):
            print(f"\n--- 第 {i+1} 次测试 ---")
            
            try:
                # 1. HAR采集
                har_tool = HarCaptureTool()
                
                request = ToolRequest(
                    tool_name="har_capture",
                    parameters={
                        "url": url,
                        "headless": True,
                        "timeout": 60000,
                        "wait_until": "networkidle"
                    }
                )
                
                ctx = FlowContext(
                    flow_id=f"test-{i+1}",
                    flow_name="waterfall-consistency-test"
                )
                
                print(f"开始HAR采集...")
                har_result = await har_tool.execute(request, ctx)
                
                if not har_result or not har_result.success:
                    error_msg = har_result.error_message if har_result else "未知错误"
                    print(f"❌ HAR采集失败: {error_msg}")
                    continue
                
                har_path = har_result.data.get("har_file_path")
                print(f"✅ HAR文件已保存: {har_path}")
                
                # 2. HAR解析
                parser = HarParser()
                waterfall_result = parser.parse(har_path)
                
                print(f"✅ 解析完成:")
                print(f"   - 总资源数: {waterfall_result.total_requests}")
                print(f"   - 页面加载时间: {waterfall_result.page_load_time:.0f}ms")
                
                if hasattr(waterfall_result, 'resources'):
                    # 统计域名分布
                    from urllib.parse import urlparse
                    domain_stats = {}
                    for resource in waterfall_result.resources:
                        try:
                            parsed = urlparse(resource.url)
                            domain = parsed.netloc
                            domain_stats[domain] = domain_stats.get(domain, 0) + 1
                        except:
                            pass
                    
                    print(f"   - 域名分布:")
                    for domain, count in sorted(domain_stats.items(), key=lambda x: x[1], reverse=True)[:10]:
                        print(f"     • {domain}: {count} 个请求")
                
                resource_counts.append(waterfall_result.total_requests)
                
                # 清理HAR文件
                if har_path and Path(har_path).exists():
                    Path(har_path).unlink()
                    print(f"   - 已清理HAR文件")
                
            except Exception as e:
                print(f"❌ 测试失败: {e}")
                import traceback
                traceback.print_exc()
        
        # 分析一致性
        if resource_counts:
            print(f"\n📊 一致性分析:")
            print(f"   - 3次测试的资源数: {resource_counts}")
            print(f"   - 最小值: {min(resource_counts)}")
            print(f"   - 最大值: {max(resource_counts)}")
            print(f"   - 平均值: {sum(resource_counts)/len(resource_counts):.1f}")
            
            if max(resource_counts) - min(resource_counts) <= 2:
                print(f"   ✅ 资源数量稳定（差异≤2）")
            else:
                print(f"   ⚠️  资源数量波动较大（差异={max(resource_counts) - min(resource_counts)}）")
        else:
            print(f"\n❌ 未能完成有效测试")


def main():
    """主函数"""
    try:
        asyncio.run(test_redirect_and_consistency())
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
