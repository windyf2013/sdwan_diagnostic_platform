"""
智能路径分析器集成测试框架

功能：
1. 批量测试不同网络环境的路径分析
2. 统计CPE识别准确率
3. A/B对比测试（Phase 1 vs Phase 2）
4. 性能基准测试
5. 生成测试报告

使用方法：
    python tests/integration/test_smart_path_analyzer.py --domains-file test_domains.json
"""

import sys
import os
import json
import time
import asyncio
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from sdwan_desktop.services.smart_path_analyzer import SmartPathAnalyzer
from sdwan_desktop.services.dns_split import TracerouteHopInfo


@dataclass
class TestCase:
    """测试用例"""
    name: str
    description: str
    hops: List[TracerouteHopInfo]
    expected_cpe_hop: int  # 期望的CPE跳数
    expected_deployment_mode: str  # 期望的部署模式
    notes: str = ""  # 备注说明


@dataclass
class TestResult:
    """测试结果"""
    test_case: TestCase
    actual_cpe_hop: int
    actual_deployment_mode: str
    confidence: float
    reasoning: List[str]
    is_correct: bool
    execution_time_ms: float
    phase: str  # "phase1" or "phase2"


@dataclass
class TestReport:
    """测试报告"""
    total_tests: int
    correct_count: int
    accuracy: float
    avg_confidence: float
    avg_execution_time_ms: float
    failed_cases: List[Dict[str, Any]]
    timestamp: str


class SmartPathAnalyzerTester:
    """智能路径分析器测试器"""
    
    def __init__(self):
        self.analyzer = SmartPathAnalyzer()
        self.results: List[TestResult] = []
    
    def load_test_cases(self, file_path: str) -> List[TestCase]:
        """从JSON文件加载测试用例"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        test_cases = []
        for case_data in data.get("test_cases", []):
            hops = []
            for hop_data in case_data["hops"]:
                hop = TracerouteHopInfo(
                    hop_number=hop_data["hop_number"],
                    ip_addresses=hop_data.get("ip_addresses", []),
                    hostnames=hop_data.get("hostnames", []),
                    rtts=hop_data.get("rtts", []),
                    is_timeout=hop_data.get("is_timeout", False),
                    as_number=hop_data.get("as_number"),
                    country=hop_data.get("country"),
                    isp=hop_data.get("isp")
                )
                hops.append(hop)
            
            test_case = TestCase(
                name=case_data["name"],
                description=case_data["description"],
                hops=hops,
                expected_cpe_hop=case_data["expected_cpe_hop"],
                expected_deployment_mode=case_data["expected_deployment_mode"],
                notes=case_data.get("notes", "")
            )
            test_cases.append(test_case)
        
        return test_cases
    
    def run_single_test(self, test_case: TestCase, phase: str = "phase2") -> TestResult:
        """运行单个测试用例"""
        start_time = time.time()
        
        # 执行分析
        result = self.analyzer.analyze(test_case.hops)
        
        end_time = time.time()
        execution_time_ms = (end_time - start_time) * 1000
        
        # 判断是否正确
        is_correct = (result.cpe_hop == test_case.expected_cpe_hop and 
                     result.deployment_mode == test_case.expected_deployment_mode)
        
        test_result = TestResult(
            test_case=test_case,
            actual_cpe_hop=result.cpe_hop,
            actual_deployment_mode=result.deployment_mode,
            confidence=result.confidence,
            reasoning=result.reasoning,
            is_correct=is_correct,
            execution_time_ms=execution_time_ms,
            phase=phase
        )
        
        self.results.append(test_result)
        return test_result
    
    def run_batch_tests(self, test_cases: List[TestCase], phase: str = "phase2") -> TestReport:
        """批量运行测试"""
        print(f"\n{'='*60}")
        print(f"开始批量测试 (Phase: {phase})")
        print(f"测试用例数: {len(test_cases)}")
        print(f"{'='*60}\n")
        
        correct_count = 0
        total_confidence = 0.0
        total_execution_time = 0.0
        failed_cases = []
        
        for i, test_case in enumerate(test_cases, 1):
            result = self.run_single_test(test_case, phase)
            
            if result.is_correct:
                correct_count += 1
                status = "✅ PASS"
            else:
                status = "❌ FAIL"
                failed_cases.append({
                    "name": test_case.name,
                    "expected_cpe": test_case.expected_cpe_hop,
                    "actual_cpe": result.actual_cpe_hop,
                    "expected_mode": test_case.expected_deployment_mode,
                    "actual_mode": result.actual_deployment_mode,
                    "confidence": result.confidence,
                    "reasoning": result.reasoning
                })
            
            total_confidence += result.confidence
            total_execution_time += result.execution_time_ms
            
            # 打印进度
            print(f"[{i}/{len(test_cases)}] {status} - {test_case.name}")
            print(f"       期望CPE={test_case.expected_cpe_hop}, 实际CPE={result.actual_cpe_hop}")
            print(f"       置信度={result.confidence:.2f}, 耗时={result.execution_time_ms:.1f}ms\n")
        
        # 生成报告
        accuracy = correct_count / len(test_cases) if test_cases else 0
        avg_confidence = total_confidence / len(test_cases) if test_cases else 0
        avg_execution_time = total_execution_time / len(test_cases) if test_cases else 0
        
        report = TestReport(
            total_tests=len(test_cases),
            correct_count=correct_count,
            accuracy=accuracy,
            avg_confidence=avg_confidence,
            avg_execution_time_ms=avg_execution_time,
            failed_cases=failed_cases,
            timestamp=datetime.now().isoformat()
        )
        
        return report
    
    def print_report(self, report: TestReport, phase: str):
        """打印测试报告"""
        print(f"\n{'='*60}")
        print(f"测试报告 (Phase: {phase})")
        print(f"{'='*60}")
        print(f"总测试数: {report.total_tests}")
        print(f"通过数: {report.correct_count}")
        print(f"失败数: {report.total_tests - report.correct_count}")
        print(f"准确率: {report.accuracy*100:.2f}%")
        print(f"平均置信度: {report.avg_confidence:.2f}")
        print(f"平均耗时: {report.avg_execution_time_ms:.1f}ms")
        print(f"测试时间: {report.timestamp}")
        print(f"{'='*60}\n")
        
        if report.failed_cases:
            print("失败的测试用例:")
            for i, case in enumerate(report.failed_cases, 1):
                print(f"\n{i}. {case['name']}")
                print(f"   期望CPE={case['expected_cpe']}, 实际CPE={case['actual_cpe']}")
                print(f"   期望模式={case['expected_mode']}, 实际模式={case['actual_mode']}")
                print(f"   置信度={case['confidence']:.2f}")
                print(f"   推理过程: {'; '.join(case['reasoning'])}")
            print()
    
    def save_report(self, report: TestReport, phase: str, output_dir: str = "tests/reports"):
        """保存测试报告到文件"""
        os.makedirs(output_dir, exist_ok=True)
        
        report_file = Path(output_dir) / f"smart_path_analyzer_{phase}_report.json"
        
        report_data = {
            "phase": phase,
            "total_tests": report.total_tests,
            "correct_count": report.correct_count,
            "accuracy": report.accuracy,
            "avg_confidence": report.avg_confidence,
            "avg_execution_time_ms": report.avg_execution_time_ms,
            "timestamp": report.timestamp,
            "failed_cases": report.failed_cases
        }
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        print(f"报告已保存到: {report_file}")


def create_sample_test_cases() -> List[TestCase]:
    """创建示例测试用例（用于快速验证）"""
    
    # 测试用例1: 传统网关部署
    case1 = TestCase(
        name="传统网关部署",
        description="PC → Switch → CPE → ISP Router → Internet",
        hops=[
            TracerouteHopInfo(hop_number=1, ip_addresses=["192.168.1.100"], rtts=[1.0]),
            TracerouteHopInfo(hop_number=2, ip_addresses=["192.168.1.1"], hostnames=["gateway.local"], rtts=[2.0]),
            TracerouteHopInfo(hop_number=3, ip_addresses=["10.164.176.1"], hostnames=["cpe-router.isp.com"], rtts=[5.0]),
            TracerouteHopInfo(hop_number=4, ip_addresses=["221.183.49.134"], rtts=[25.0], as_number="4837", country="CN", isp="China Unicom"),
            TracerouteHopInfo(hop_number=5, ip_addresses=["202.97.1.1"], rtts=[30.0], as_number="4134", country="CN", isp="China Telecom"),
        ],
        expected_cpe_hop=3,
        expected_deployment_mode="gateway",
        notes="CPE在第3跳，有Hostname匹配和AS号变更双重证据"
    )
    
    # 测试用例2: PC侧分流
    case2 = TestCase(
        name="PC侧分流",
        description="PC → 虚拟网卡 → Internet",
        hops=[
            TracerouteHopInfo(hop_number=1, ip_addresses=["10.8.0.1"], hostnames=["vpn-gateway"], rtts=[1.0]),
            TracerouteHopInfo(hop_number=2, ip_addresses=["203.0.113.1"], rtts=[20.0], as_number="4134", country="CN", isp="China Telecom"),
            TracerouteHopInfo(hop_number=3, ip_addresses=["198.51.100.1"], rtts=[25.0]),
        ],
        expected_cpe_hop=1,
        expected_deployment_mode="pc_side",
        notes="CPE在第1跳（虚拟网卡），私网直接到公网"
    )
    
    # 测试用例3: 运营商级部署
    case3 = TestCase(
        name="运营商级部署",
        description="PC → Access → Aggregation → BRAS → SD-WAN Gateway → Internet",
        hops=[
            TracerouteHopInfo(hop_number=1, ip_addresses=["192.168.1.100"], rtts=[1.0]),
            TracerouteHopInfo(hop_number=2, ip_addresses=["10.1.1.1"], rtts=[2.0]),
            TracerouteHopInfo(hop_number=3, ip_addresses=["10.2.2.2"], rtts=[3.0]),
            TracerouteHopInfo(hop_number=4, ip_addresses=["10.3.3.3"], rtts=[4.0]),
            TracerouteHopInfo(hop_number=5, ip_addresses=["172.16.0.1"], hostnames=["sdwan-gateway"], rtts=[5.0]),
            TracerouteHopInfo(hop_number=6, ip_addresses=["203.0.113.1"], rtts=[30.0], as_number="4134", country="CN", isp="China Telecom"),
        ],
        expected_cpe_hop=5,
        expected_deployment_mode="upstream",
        notes="CPE在第5跳，前面有多个私网跳点"
    )
    
    return [case1, case2, case3]


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="智能路径分析器集成测试")
    parser.add_argument("--domains-file", type=str, help="测试用例JSON文件路径")
    parser.add_argument("--sample", action="store_true", help="使用示例测试用例")
    parser.add_argument("--phase", type=str, default="phase2", choices=["phase1", "phase2"], help="测试阶段")
    parser.add_argument("--output-dir", type=str, default="tests/reports", help="报告输出目录")
    
    args = parser.parse_args()
    
    tester = SmartPathAnalyzerTester()
    
    # 加载测试用例
    if args.sample:
        test_cases = create_sample_test_cases()
        print(f"使用示例测试用例: {len(test_cases)}个")
    elif args.domains_file:
        test_cases = tester.load_test_cases(args.domains_file)
        print(f"从文件加载测试用例: {len(test_cases)}个")
    else:
        print("错误: 请指定 --sample 或 --domains-file 参数")
        sys.exit(1)
    
    # 运行测试
    report = tester.run_batch_tests(test_cases, phase=args.phase)
    
    # 打印报告
    tester.print_report(report, phase=args.phase)
    
    # 保存报告
    tester.save_report(report, phase=args.phase, output_dir=args.output_dir)
    
    # 退出码
    if report.accuracy >= 0.9:
        print("✅ 测试通过！准确率 >= 90%")
        sys.exit(0)
    else:
        print(f"⚠️  测试警告！准确率 {report.accuracy*100:.2f}% < 90%")
        sys.exit(1)


if __name__ == "__main__":
    main()
