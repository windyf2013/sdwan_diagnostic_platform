"""
智能路径分析器 - 复杂场景仿真测试

测试目标：
1. 覆盖边缘情况和异常场景
2. 验证降级策略的有效性
3. 测试性能边界
4. 发现潜在逻辑缺陷

测试场景分类：
- 正常场景（已覆盖）
- 异常场景（超时、空路径、无效IP等）
- 边界场景（极短/极长路径、全私网等）
- 性能场景（大量跳点、并发查询）
"""

import sys
from pathlib import Path
from typing import List, Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sdwan_desktop.services.smart_path_analyzer import SmartPathAnalyzer
from sdwan_desktop.services.dns_split import TracerouteHopInfo


class ComplexScenarioTester:
    """复杂场景测试器"""
    
    def __init__(self):
        self.analyzer = SmartPathAnalyzer()
        self.test_results: List[Dict[str, Any]] = []
    
    def run_test(self, name: str, hops: List[TracerouteHopInfo], 
                 expect_success: bool = True, description: str = ""):
        """运行单个测试场景"""
        print(f"\n{'='*60}")
        print(f"测试: {name}")
        if description:
            print(f"描述: {description}")
        print(f"{'='*60}")
        
        try:
            result = self.analyzer.analyze(hops)
            
            success = (result is not None and 
                      hasattr(result, 'cpe_hop') and
                      result.cpe_hop > 0)
            
            status = "✅ PASS" if success == expect_success else "❌ FAIL"
            
            print(f"状态: {status}")
            print(f"CPE位置: 第{result.cpe_hop}跳")
            print(f"部署模式: {result.deployment_mode}")
            print(f"置信度: {result.confidence:.2f}")
            print(f"推理过程:")
            for reason in result.reasoning:
                print(f"  - {reason}")
            
            self.test_results.append({
                "name": name,
                "success": success,
                "expected": expect_success,
                "cpe_hop": result.cpe_hop,
                "confidence": result.confidence,
                "mode": result.deployment_mode
            })
            
            return result
        
        except Exception as e:
            print(f"❌ EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
            
            self.test_results.append({
                "name": name,
                "success": False,
                "expected": expect_success,
                "error": str(e)
            })
            
            return None
    
    def test_empty_path(self):
        """测试1: 空路径"""
        print("\n📋 测试1: 空路径")
        self.run_test(
            "空路径",
            [],
            expect_success=True,
            description="应触发降级策略，返回默认值"
        )
    
    def test_single_hop(self):
        """测试2: 单跳路径"""
        print("\n📋 测试2: 单跳路径")
        hops = [
            TracerouteHopInfo(
                hop_number=1,
                ip_addresses=["192.168.1.1"],
                rtts=[1.0]
            )
        ]
        self.run_test(
            "单跳路径",
            hops,
            expect_success=True,
            description="仅一跳，应识别为PC侧或直接连接"
        )
    
    def test_all_timeout_hops(self):
        """测试3: 全部超时"""
        print("\n📋 测试3: 全部超时")
        hops = [
            TracerouteHopInfo(
                hop_number=i+1,
                ip_addresses=[],
                hostnames=[],
                rtts=[],
                is_timeout=True
            )
            for i in range(5)
        ]
        self.run_test(
            "全部超时",
            hops,
            expect_success=True,
            description="所有跳点都超时，应使用降级策略"
        )
    
    def test_invalid_ip_addresses(self):
        """测试4: 无效IP地址"""
        print("\n📋 测试4: 无效IP地址")
        hops = [
            TracerouteHopInfo(
                hop_number=1,
                ip_addresses=["invalid_ip"],
                rtts=[1.0]
            ),
            TracerouteHopInfo(
                hop_number=2,
                ip_addresses=["999.999.999.999"],
                rtts=[2.0]
            ),
        ]
        self.run_test(
            "无效IP地址",
            hops,
            expect_success=True,
            description="IP地址格式错误，应优雅处理"
        )
    
    def test_very_long_path(self):
        """测试5: 超长路径"""
        print("\n📋 测试5: 超长路径（20跳）")
        hops = []
        for i in range(20):
            if i < 5:
                # 前5跳：私网
                ip = f"192.168.{i}.{i+1}"
            elif i < 10:
                # 中间5跳：运营商内网
                ip = f"10.{i}.{i+1}.{i+2}"
            else:
                # 后10跳：公网
                ip = f"203.0.{i}.{i+1}"
            
            hops.append(TracerouteHopInfo(
                hop_number=i+1,
                ip_addresses=[ip],
                rtts=[float(i+1)]
            ))
        
        self.run_test(
            "超长路径",
            hops,
            expect_success=True,
            description="20跳路径，应能正确识别CPE位置"
        )
    
    def test_mixed_ipv4_ipv6(self):
        """测试6: IPv4和IPv6混合"""
        print("\n📋 测试6: IPv4和IPv6混合路径")
        hops = [
            TracerouteHopInfo(
                hop_number=1,
                ip_addresses=["192.168.1.1"],
                rtts=[1.0]
            ),
            TracerouteHopInfo(
                hop_number=2,
                ip_addresses=["2001:db8::1"],  # IPv6地址
                rtts=[2.0]
            ),
            TracerouteHopInfo(
                hop_number=3,
                ip_addresses=["203.0.113.1"],
                rtts=[25.0]
            ),
        ]
        self.run_test(
            "IPv4/IPv6混合",
            hops,
            expect_success=True,
            description="混合协议栈路径，应能处理IPv6地址"
        )
    
    def test_duplicate_ips(self):
        """测试7: 重复IP地址"""
        print("\n📋 测试7: 重复IP地址")
        hops = [
            TracerouteHopInfo(
                hop_number=1,
                ip_addresses=["192.168.1.1"],
                rtts=[1.0]
            ),
            TracerouteHopInfo(
                hop_number=2,
                ip_addresses=["192.168.1.1"],  # 重复
                rtts=[1.0]
            ),
            TracerouteHopInfo(
                hop_number=3,
                ip_addresses=["192.168.1.1"],  # 再次重复
                rtts=[1.0]
            ),
            TracerouteHopInfo(
                hop_number=4,
                ip_addresses=["203.0.113.1"],
                rtts=[25.0]
            ),
        ]
        self.run_test(
            "重复IP地址",
            hops,
            expect_success=True,
            description="同一IP出现在多跳，可能是路由环路"
        )
    
    def test_no_public_ip(self):
        """测试8: 无公网IP（全私网）"""
        print("\n📋 测试8: 全私网路径")
        hops = [
            TracerouteHopInfo(
                hop_number=i+1,
                ip_addresses=[f"192.168.{i}.1"],
                rtts=[float(i+1)]
            )
            for i in range(5)
        ]
        self.run_test(
            "全私网路径",
            hops,
            expect_success=True,
            description="没有公网IP，应识别为内网环境"
        )
    
    def test_extreme_rtt_values(self):
        """测试9: 极端RTT值"""
        print("\n📋 测试9: 极端RTT值")
        hops = [
            TracerouteHopInfo(
                hop_number=1,
                ip_addresses=["192.168.1.1"],
                rtts=[0.001]  # 极低延迟
            ),
            TracerouteHopInfo(
                hop_number=2,
                ip_addresses=["10.1.1.1"],
                rtts=[999.999]  # 极高延迟
            ),
            TracerouteHopInfo(
                hop_number=3,
                ip_addresses=["203.0.113.1"],
                rtts=[50.0]
            ),
        ]
        self.run_test(
            "极端RTT值",
            hops,
            expect_success=True,
            description="RTT从0.001ms突增到999.999ms，再降到50ms"
        )
    
    def test_missing_hop_numbers(self):
        """测试10: 跳数不连续"""
        print("\n📋 测试10: 跳数不连续")
        hops = [
            TracerouteHopInfo(
                hop_number=1,
                ip_addresses=["192.168.1.1"],
                rtts=[1.0]
            ),
            TracerouteHopInfo(
                hop_number=5,  # 跳过2,3,4
                ip_addresses=["203.0.113.1"],
                rtts=[25.0]
            ),
            TracerouteHopInfo(
                hop_number=10,  # 跳过6-9
                ip_addresses=["198.51.100.1"],
                rtts=[30.0]
            ),
        ]
        self.run_test(
            "跳数不连续",
            hops,
            expect_success=True,
            description="跳数跳跃式增长（1→5→10），Windows tracert常见情况"
        )
    
    def test_high_confidence_scenario(self):
        """测试11: 高置信度场景"""
        print("\n📋 测试11: 高置信度场景（多重证据）")
        hops = [
            TracerouteHopInfo(
                hop_number=1,
                ip_addresses=["192.168.1.100"],
                rtts=[1.0]
            ),
            TracerouteHopInfo(
                hop_number=2,
                ip_addresses=["192.168.1.1"],
                hostnames=["gateway.local"],
                rtts=[2.0]
            ),
            TracerouteHopInfo(
                hop_number=3,
                ip_addresses=["10.164.176.1"],
                hostnames=["cpe-router.isp.com"],
                rtts=[5.0],
                as_number="64512"
            ),
            TracerouteHopInfo(
                hop_number=4,
                ip_addresses=["221.183.49.134"],
                rtts=[25.0],
                as_number="4837",
                country="CN",
                isp="China Unicom"
            ),
        ]
        result = self.run_test(
            "高置信度场景",
            hops,
            expect_success=True,
            description="Hostname + AS变更 + IP段变化 + RTT突变，四重证据"
        )
        
        if result and result.confidence >= 0.8:
            print("✅ 置信度符合预期（>=0.8）")
        else:
            print(f"⚠️ 置信度偏低: {result.confidence if result else 'N/A'}")
    
    def test_low_confidence_scenario(self):
        """测试12: 低置信度场景"""
        print("\n📋 测试12: 低置信度场景（单一弱证据）")
        hops = [
            TracerouteHopInfo(
                hop_number=1,
                ip_addresses=["192.168.1.1"],
                rtts=[1.0]
            ),
            TracerouteHopInfo(
                hop_number=2,
                ip_addresses=["203.0.113.1"],
                rtts=[25.0]  # 仅有RTT突变
            ),
        ]
        result = self.run_test(
            "低置信度场景",
            hops,
            expect_success=True,
            description="仅有RTT突变，无其他证据"
        )
        
        if result and result.confidence < 0.5:
            print("✅ 置信度符合预期（<0.5）")
        else:
            print(f"⚠️ 置信度偏高: {result.confidence if result else 'N/A'}")
    
    def generate_summary_report(self):
        """生成测试总结报告"""
        print(f"\n{'='*60}")
        print("测试总结报告")
        print(f"{'='*60}")
        
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r["success"] == r["expected"])
        failed = total - passed
        
        print(f"总测试数: {total}")
        print(f"通过数: {passed}")
        print(f"失败数: {failed}")
        print(f"通过率: {passed/total*100:.2f}%")
        
        if failed > 0:
            print(f"\n失败的测试:")
            for i, result in enumerate(self.test_results, 1):
                if result["success"] != result["expected"]:
                    print(f"  {i}. {result['name']}")
                    if "error" in result:
                        print(f"     错误: {result['error']}")
        
        print(f"\n{'='*60}")
        
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": passed/total*100
        }


def main():
    """主函数"""
    print("="*60)
    print("智能路径分析器 - 复杂场景仿真测试")
    print("="*60)
    
    tester = ComplexScenarioTester()
    
    # 运行所有测试场景
    tester.test_empty_path()
    tester.test_single_hop()
    tester.test_all_timeout_hops()
    tester.test_invalid_ip_addresses()
    tester.test_very_long_path()
    tester.test_mixed_ipv4_ipv6()
    tester.test_duplicate_ips()
    tester.test_no_public_ip()
    tester.test_extreme_rtt_values()
    tester.test_missing_hop_numbers()
    tester.test_high_confidence_scenario()
    tester.test_low_confidence_scenario()
    
    # 生成总结报告
    summary = tester.generate_summary_report()
    
    # 退出码
    if summary["pass_rate"] >= 90:
        print("✅ 测试通过！通过率 >= 90%")
        sys.exit(0)
    else:
        print(f"⚠️  测试警告！通过率 {summary['pass_rate']:.2f}% < 90%")
        sys.exit(1)


if __name__ == "__main__":
    main()
