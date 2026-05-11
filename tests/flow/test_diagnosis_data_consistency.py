"""
诊断数据结构一致性测试

验证所有 Recommendation 和 RootCause 的构造参数是否正确。
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from sdwan_desktop.core.types.diagnosis import Recommendation, RootCause, Severity


def test_recommendation_creation():
    """测试 Recommendation 的正确构造"""
    print("=" * 60)
    print("测试 1: Recommendation 构造")
    print("=" * 60)
    
    # 正确的构造方式
    rec = Recommendation(
        action="检查网络连接",
        priority=1,
        expected_outcome="恢复网络连通性",
        risk_level=Severity.INFO,
        commands=["ping 8.8.8.8"]
    )
    
    print(f"✓ Recommendation 创建成功")
    print(f"  - action: {rec.action}")
    print(f"  - priority: {rec.priority}")
    print(f"  - expected_outcome: {rec.expected_outcome}")
    print(f"  - risk_level: {rec.risk_level}")
    print(f"  - commands: {rec.commands}")
    
    assert rec.action == "检查网络连接"
    assert rec.priority == 1
    assert rec.expected_outcome == "恢复网络连通性"
    
    print("\n✅ Recommendation 构造测试通过\n")


def test_root_cause_creation():
    """测试 RootCause 的正确构造"""
    print("=" * 60)
    print("测试 2: RootCause 构造")
    print("=" * 60)
    
    # 正确的构造方式
    cause = RootCause(
        cause_id="NET-001",
        title="网关不可达",
        description="默认网关 ping 测试失败",
        severity=Severity.ERROR,
        confidence=0.95,
        evidence_refs=["evidence-1"],
        matched_rules=["rule-gateway-ping"]
    )
    
    print(f"✓ RootCause 创建成功")
    print(f"  - cause_id: {cause.cause_id}")
    print(f"  - title: {cause.title}")
    print(f"  - description: {cause.description}")
    print(f"  - severity: {cause.severity}")
    print(f"  - confidence: {cause.confidence}")
    
    assert cause.cause_id == "NET-001"
    assert cause.severity == Severity.ERROR
    assert cause.confidence == 0.95
    
    print("\n✅ RootCause 构造测试通过\n")


def test_quick_check_tab_usage():
    """验证 quick_check_tab 中的使用方式"""
    print("=" * 60)
    print("测试 3: Quick Check Tab 使用方式")
    print("=" * 60)
    
    # 模拟规则引擎返回的结果
    class MockRuleResult:
        def __init__(self):
            self.rule_id = "TEST-001"
            self.message = "网关延迟过高"
            self.suggestion = "检查网关配置"
            self.severity = Severity.WARNING
            self.confidence = 0.85
    
    rr = MockRuleResult()
    
    # 正确的构造方式（与修复后的代码一致）
    recommendations = []
    if rr.suggestion:
        recommendations.append(Recommendation(
            action=rr.suggestion,
            priority=1 if rr.severity in [Severity.CRITICAL, Severity.ERROR] else 2,
            expected_outcome=rr.message
        ))
    
    print(f"✓ Recommendation 从规则结果创建成功")
    print(f"  - action: {recommendations[0].action}")
    print(f"  - priority: {recommendations[0].priority}")
    print(f"  - expected_outcome: {recommendations[0].expected_outcome}")
    
    assert recommendations[0].action == "检查网关配置"
    assert recommendations[0].expected_outcome == "网关延迟过高"
    
    print("\n✅ Quick Check Tab 使用方式测试通过\n")


def test_waterfall_tab_usage():
    """验证 waterfall_tab 中的使用方式"""
    print("=" * 60)
    print("测试 4: Waterfall Tab 使用方式")
    print("=" * 60)
    
    # 模拟性能问题
    all_issues = [
        {
            "severity": 2,
            "message": "页面加载时间过长",
            "suggestion": "优化资源加载顺序"
        },
        {
            "severity": 1,
            "message": "DNS 解析较慢",
            "suggestion": "使用更快的 DNS 服务器"
        }
    ]
    
    recommendations = []
    for issue in all_issues:
        recommendations.append(Recommendation(
            action=issue.get("message", "未知问题"),
            priority=issue.get("severity", 2),
            expected_outcome=issue.get("suggestion", "优化性能")
        ))
    
    print(f"✓ 创建了 {len(recommendations)} 个 Recommendation")
    for i, rec in enumerate(recommendations, 1):
        print(f"  [{i}] action: {rec.action}, priority: {rec.priority}")
    
    assert len(recommendations) == 2
    assert recommendations[0].action == "页面加载时间过长"
    assert recommendations[0].expected_outcome == "优化资源加载顺序"
    
    print("\n✅ Waterfall Tab 使用方式测试通过\n")


def test_invalid_parameter():
    """测试错误的参数名会被拒绝"""
    print("=" * 60)
    print("测试 5: 验证错误参数被拒绝")
    print("=" * 60)
    
    try:
        # 尝试使用错误的参数名
        rec = Recommendation(
            action="测试",
            priority=1,
            reason="这是错误的参数"  # type: ignore
        )
        print(f"❌ 错误：不应该接受 reason 参数")
        return False
    except TypeError as e:
        print(f"✓ 正确拒绝了错误参数: {e}")
        print("\n✅ 错误参数验证测试通过\n")
        return True


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("诊断数据结构一致性测试")
    print("=" * 60 + "\n")
    
    try:
        # 测试 1: Recommendation 构造
        test_recommendation_creation()
        
        # 测试 2: RootCause 构造
        test_root_cause_creation()
        
        # 测试 3: Quick Check Tab 使用方式
        test_quick_check_tab_usage()
        
        # 测试 4: Waterfall Tab 使用方式
        test_waterfall_tab_usage()
        
        # 测试 5: 验证错误参数被拒绝
        test_invalid_parameter()
        
        print("=" * 60)
        print("🎉 所有测试通过！诊断数据结构使用正确。")
        print("=" * 60)
        return 0
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
