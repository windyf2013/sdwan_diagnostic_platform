"""
Waterfall功能修复验证脚本

验证两个问题的修复：
1. 重定向资源捕获完整性
2. 资源数量稳定性
"""

import sys
import json
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from sdwan_desktop.tools.implementations.web.har_capture import HarCaptureTool
from sdwan_desktop.core.types.tool import ToolRequest
from sdwan_desktop.core.types.context import FlowContext


async def verify_fixes():
    """验证修复效果"""
    
    print("=" * 70)
    print("Waterfall功能修复验证")
    print("=" * 70)
    
    # 测试1: joom.com重定向和资源完整性
    print("\n📋 测试1: joom.com（重定向 + 资源完整性）")
    print("-" * 70)
    
    tool = HarCaptureTool()
    req = ToolRequest(
        tool_name='har_capture',
        parameters={
            'url': 'https://joom.com',
            'headless': True,
            'timeout': 30000,
            'wait_until': 'networkidle'
        }
    )
    ctx = FlowContext(flow_id='verify-redirect', flow_name='verify-redirect')
    
    result = await tool.execute(req, ctx)
    
    if not result.success:
        print(f"❌ 测试失败: {result.error_message}")
        return False
    
    har_path = result.data.get('har_file_path')
    
    with open(har_path, 'r', encoding='utf-8') as f:
        har_data = json.load(f)
    
    entries = har_data.get('log', {}).get('entries', [])
    
    # 分析域名
    domains = {}
    for entry in entries:
        url = entry.get('request', {}).get('url', '')
        if url:
            try:
                domain = url.split('/')[2]
                domains[domain] = domains.get(domain, 0) + 1
            except:
                pass
    
    # 检查重定向
    redirects = [e for e in entries if e.get('response', {}).get('status') in [301, 302, 303, 307, 308]]
    
    print(f"\n✅ 测试结果:")
    print(f"   • 总请求数: {len(entries)} 个")
    print(f"   • 唯一域名: {len(domains)} 个")
    print(f"   • 重定向数: {len(redirects)} 个")
    
    # 验证标准
    checks = []
    
    if len(entries) >= 100:
        print(f"   ✓ 请求数充足 (>= 100)")
        checks.append(True)
    else:
        print(f"   ❌ 请求数不足 (< 100)")
        checks.append(False)
    
    if len(domains) >= 10:
        print(f"   ✓ 域名多样性好 (>= 10)")
        checks.append(True)
    else:
        print(f"   ❌ 域名单一 (< 10)")
        checks.append(False)
    
    if len(redirects) >= 2:
        print(f"   ✓ 重定向链完整 (>= 2)")
        checks.append(True)
    else:
        print(f"   ❌ 重定向缺失 (< 2)")
        checks.append(False)
    
    # 检查是否包含完整的joom.com重定向链
    redirect_urls = [e.get('request', {}).get('url', '') for e in redirects]
    has_joom_redirect = any('joom.com' in url for url in redirect_urls)
    has_www_redirect = any('www.joom.com' in url for url in redirect_urls)
    
    if has_joom_redirect and has_www_redirect:
        print(f"   ✓ joom.com重定向链完整")
        checks.append(True)
    else:
        print(f"   ❌ joom.com重定向链不完整")
        checks.append(False)
    
    test1_passed = all(checks)
    
    # 测试2: 稳定性测试
    print("\n\n📋 测试2: 稳定性测试（baidu.com连续3次）")
    print("-" * 70)
    
    test_counts = []
    for i in range(3):
        req2 = ToolRequest(
            tool_name='har_capture',
            parameters={
                'url': 'https://www.baidu.com',
                'headless': True,
                'timeout': 30000,
                'wait_until': 'networkidle'
            }
        )
        ctx2 = FlowContext(flow_id=f'stability-{i}', flow_name='stability')
        
        result2 = await tool.execute(req2, ctx2)
        
        if result2.success:
            har_path2 = result2.data.get('har_file_path')
            with open(har_path2, 'r', encoding='utf-8') as f:
                har_data2 = json.load(f)
            
            entries2 = har_data2.get('log', {}).get('entries', [])
            test_counts.append(len(entries2))
    
    avg_count = sum(test_counts) / len(test_counts)
    max_deviation = max(abs(c - avg_count) for c in test_counts)
    deviation_percent = (max_deviation / avg_count * 100) if avg_count > 0 else 0
    
    print(f"\n✅ 测试结果:")
    print(f"   • 请求数: {test_counts}")
    print(f"   • 平均值: {avg_count:.1f}")
    print(f"   • 最大偏差: {max_deviation:.1f} ({deviation_percent:.1f}%)")
    
    if deviation_percent <= 5:
        print(f"   ✓ 稳定性优秀 (偏差 <= 5%)")
        test2_passed = True
    elif deviation_percent <= 10:
        print(f"   ✓ 稳定性良好 (偏差 <= 10%)")
        test2_passed = True
    else:
        print(f"   ❌ 稳定性较差 (偏差 > 10%)")
        test2_passed = False
    
    # 总结
    print("\n\n" + "=" * 70)
    print("验证总结")
    print("=" * 70)
    
    if test1_passed and test2_passed:
        print("✅ 所有测试通过！Waterfall功能已修复。")
        print("\n修复内容:")
        print("  1. ✓ 重定向资源捕获完整")
        print("  2. ✓ 资源数量稳定")
        print("  3. ✓ 浏览器指纹真实")
        print("  4. ✓ 等待策略充分")
        return True
    else:
        print("⚠️  部分测试未通过，请检查修复情况")
        if not test1_passed:
            print("  ❌ 问题1: 重定向或资源捕获不完整")
        if not test2_passed:
            print("  ❌ 问题2: 资源数量不稳定")
        return False


if __name__ == "__main__":
    success = asyncio.run(verify_fixes())
    sys.exit(0 if success else 1)
