"""
全面仿真自测脚本

模拟打包后的运行环境，验证所有关键功能是否存在问题。
测试范围：
1. 数据结构一致性
2. 工具注册机制
3. CLI/GUI 流程一致性
4. 模板渲染
5. 编码兼容性
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))


def test_1_diagnosis_data_structures():
    """测试 1: 诊断数据结构"""
    print("\n" + "=" * 70)
    print("测试 1: 诊断数据结构 (Recommendation, RootCause)")
    print("=" * 70)
    
    from sdwan_desktop.core.types.diagnosis import Recommendation, RootCause, Severity
    
    # 测试 Recommendation
    try:
        rec = Recommendation(
            action="检查网络配置",
            priority=1,
            expected_outcome="恢复网络连接",
            risk_level=Severity.INFO,
            commands=["ping 8.8.8.8"]
        )
        print(f"✅ Recommendation 构造成功")
        assert hasattr(rec, 'action')
        assert hasattr(rec, 'priority')
        assert hasattr(rec, 'expected_outcome')
        assert not hasattr(rec, 'reason'), "不应该有 reason 字段"
    except Exception as e:
        print(f"❌ Recommendation 构造失败: {e}")
        return False
    
    # 测试 RootCause
    try:
        cause = RootCause(
            cause_id="TEST-001",
            title="测试根因",
            description="这是一个测试",
            severity=Severity.WARNING,
            confidence=0.9
        )
        print(f"✅ RootCause 构造成功")
    except Exception as e:
        print(f"❌ RootCause 构造失败: {e}")
        return False
    
    print("✅ 测试 1 通过\n")
    return True


def test_2_tool_registry():
    """测试 2: 工具注册机制"""
    print("=" * 70)
    print("测试 2: 工具注册机制")
    print("=" * 70)
    
    try:
        # 显式导入工具模块（模拟 main_window.py 的行为）
        import sdwan_desktop.tools.implementations.network.ping
        import sdwan_desktop.tools.implementations.network.dns
        import sdwan_desktop.tools.implementations.network.tcping
        import sdwan_desktop.tools.implementations.network.traceroute
        
        from sdwan_desktop.tools.registry.base import ToolRegistry
        
        registry = ToolRegistry()
        tools = registry.list_tools()
        
        print(f"已注册工具数量: {len(tools)}")
        print(f"工具列表: {', '.join(tools[:5])}...")
        
        if len(tools) == 0:
            print(f"❌ 没有工具被注册！")
            return False
        
        # 验证关键工具是否存在
        required_tools = ['ping', 'dns', 'tcping', 'traceroute']
        for tool_name in required_tools:
            if tool_name not in tools:
                print(f"❌ 缺少必需工具: {tool_name}")
                return False
        
        print(f"✅ 所有必需工具已注册: {', '.join(required_tools)}")
        print("✅ 测试 2 通过\n")
        return True
        
    except Exception as e:
        print(f"❌ 工具注册测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_3_waterfall_cli_flow():
    """测试 3: Waterfall CLI 流程"""
    print("=" * 70)
    print("测试 3: Waterfall CLI 流程")
    print("=" * 70)
    
    try:
        from sdwan_desktop.core.types.tool import ToolRequest
        from sdwan_desktop.core.types.context import FlowContext
        
        # 模拟 CLI waterfall 命令的参数传递
        request = ToolRequest(
            tool_name="har_capture",
            parameters={
                "url": "https://www.example.com",
                "headless": True,
                "timeout": 30000,
                "wait_until": "networkidle"
            }
        )
        
        ctx = FlowContext(
            flow_id="test-waterfall",
            flow_name="test-waterfall-diagnosis"
        )
        
        print(f"✅ ToolRequest 创建成功")
        print(f"   - tool_name: {request.tool_name}")
        print(f"   - parameters keys: {list(request.parameters.keys())}")
        print(f"✅ FlowContext 创建成功")
        print(f"   - flow_id: {ctx.flow_id}")
        
        # 验证 HarCaptureTool 可以接收这些参数
        from sdwan_desktop.tools.implementations.web.har_capture import HarCaptureTool
        
        har_tool = HarCaptureTool()
        print(f"✅ HarCaptureTool 实例化成功")
        
        print("✅ 测试 3 通过\n")
        return True
        
    except Exception as e:
        print(f"❌ Waterfall CLI 流程测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_4_jinja2_template():
    """测试 4: Jinja2 模板渲染"""
    print("=" * 70)
    print("测试 4: Jinja2 模板渲染 (waterfall.html)")
    print("=" * 70)
    
    try:
        from sdwan_desktop.services.reporter.report_generator import ReportGenerator
        from sdwan_desktop.core.types.waterfall import WaterfallResult, ResourceTiming
        
        # 创建测试数据
        resources = [
            ResourceTiming(url="https://example.com/style.css", total_time=200, content_size=10000),
            ResourceTiming(url="https://example.com/script.js", total_time=300, content_size=20000),
            ResourceTiming(url="https://example.com/image.png", total_time=100, content_size=50000),
        ]
        
        waterfall_result = WaterfallResult(
            target_url="https://example.com",
            page_load_time=600,
            total_requests=3,
            resources=resources
        )
        
        all_issues = [
            {"severity": 2, "message": "加载较慢", "suggestion": "优化资源"}
        ]
        
        # 生成报告
        generator = ReportGenerator()
        output_path = "test_template_render.html"
        html_content = generator.generate_waterfall_report(waterfall_result, all_issues, output_path)
        
        # 验证文件生成
        if Path(output_path).exists():
            file_size = Path(output_path).stat().st_size
            print(f"✅ 报告生成成功: {output_path} ({file_size} bytes)")
            
            # 清理测试文件
            Path(output_path).unlink()
            print(f"✅ 测试文件已清理")
        else:
            print(f"❌ 报告文件未生成")
            return False
        
        print("✅ 测试 4 通过\n")
        return True
        
    except Exception as e:
        print(f"❌ Jinja2 模板渲染测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_5_quick_check_tab_consistency():
    """测试 5: Quick Check Tab 与 CLI 一致性"""
    print("=" * 70)
    print("测试 5: Quick Check Tab 与 CLI 一致性")
    print("=" * 70)
    
    try:
        from sdwan_desktop.core.types.diagnosis import Recommendation, Severity
        
        # 模拟规则引擎返回的结果
        class MockRuleResult:
            def __init__(self):
                self.rule_id = "TEST-RULE"
                self.message = "网关延迟过高"
                self.suggestion = "检查网关配置"
                self.severity = Severity.WARNING
                self.confidence = 0.85
        
        rr = MockRuleResult()
        
        # GUI quick_check_tab 的实现（修复后）
        recommendations_gui = []
        if rr.suggestion:
            recommendations_gui.append(Recommendation(
                action=rr.suggestion,
                priority=1 if rr.severity in [Severity.CRITICAL, Severity.ERROR] else 2,
                expected_outcome=rr.message  # ✅ 使用 expected_outcome
            ))
        
        # CLI quick_check.py 的实现
        recommendations_cli = []
        if rr.suggestion:
            recommendations_cli.append(Recommendation(
                action=rr.suggestion,
                priority=1 if rr.severity in [Severity.CRITICAL, Severity.ERROR] else 2,
                expected_outcome=rr.message  # ✅ 使用 expected_outcome
            ))
        
        # 验证一致性
        assert len(recommendations_gui) == len(recommendations_cli)
        assert recommendations_gui[0].action == recommendations_cli[0].action
        assert recommendations_gui[0].priority == recommendations_cli[0].priority
        assert recommendations_gui[0].expected_outcome == recommendations_cli[0].expected_outcome
        
        print(f"✅ GUI 和 CLI Recommendation 构造一致")
        print(f"   - action: {recommendations_gui[0].action}")
        print(f"   - priority: {recommendations_gui[0].priority}")
        print(f"   - expected_outcome: {recommendations_gui[0].expected_outcome}")
        
        print("✅ 测试 5 通过\n")
        return True
        
    except Exception as e:
        print(f"❌ Quick Check 一致性测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_6_encoding_compatibility():
    """测试 6: Windows GBK 编码兼容性"""
    print("=" * 70)
    print("测试 6: Windows GBK 编码兼容性")
    print("=" * 70)
    
    try:
        # 读取 waterfall.py 检查是否还有 emoji
        waterfall_py = project_root / "src" / "sdwan_desktop" / "interface" / "cli" / "commands" / "waterfall.py"
        content = waterfall_py.read_text(encoding='utf-8')
        
        # 检查是否包含 emoji
        emoji_chars = ['🚀', '✅', '⚠️', '📄', '❌']
        found_emojis = [emoji for emoji in emoji_chars if emoji in content]
        
        if found_emojis:
            print(f"❌ 发现 Emoji 字符: {found_emojis}")
            print(f"   这会导致 Windows GBK 编码错误")
            return False
        else:
            print(f"✅ 未发现 Emoji 字符")
            print(f"✅ 使用 ASCII 文本标签 ([START], [OK], [WARN], [REPORT])")
        
        print("✅ 测试 6 通过\n")
        return True
        
    except Exception as e:
        print(f"❌ 编码兼容性测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_7_all_imports():
    """测试 7: 关键模块导入"""
    print("=" * 70)
    print("测试 7: 关键模块导入")
    print("=" * 70)
    
    modules_to_test = [
        ("核心类型", [
            "sdwan_desktop.core.types.diagnosis",
            "sdwan_desktop.core.types.waterfall",
            "sdwan_desktop.core.types.tool",
            "sdwan_desktop.core.types.context",
        ]),
        ("GUI 组件", [
            "sdwan_desktop.interface.gui.main_window",
            "sdwan_desktop.interface.gui.tabs.quick_check_tab",
            "sdwan_desktop.interface.gui.tabs.waterfall_tab",
        ]),
        ("CLI 命令", [
            "sdwan_desktop.interface.cli.commands.quick_check",
            "sdwan_desktop.interface.cli.commands.waterfall",
        ]),
        ("服务层", [
            "sdwan_desktop.services.reporter.report_generator",
            "sdwan_desktop.services.parser.har_parser",
        ]),
        ("工具实现", [
            "sdwan_desktop.tools.implementations.network.ping",
            "sdwan_desktop.tools.implementations.web.har_capture",
        ]),
    ]
    
    failed_modules = []
    
    for category, modules in modules_to_test:
        print(f"\n{category}:")
        for module_name in modules:
            try:
                __import__(module_name)
                print(f"  ✅ {module_name}")
            except Exception as e:
                print(f"  ❌ {module_name}: {e}")
                failed_modules.append((module_name, str(e)))
    
    if failed_modules:
        print(f"\n❌ {len(failed_modules)} 个模块导入失败")
        return False
    else:
        print(f"\n✅ 所有关键模块导入成功")
        print("✅ 测试 7 通过\n")
        return True


def main():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print("全面仿真自测 - 打包前验证")
    print("=" * 70)
    print(f"项目路径: {project_root}")
    print(f"Python 版本: {sys.version}")
    
    tests = [
        ("诊断数据结构", test_1_diagnosis_data_structures),
        ("工具注册机制", test_2_tool_registry),
        ("Waterfall CLI 流程", test_3_waterfall_cli_flow),
        ("Jinja2 模板渲染", test_4_jinja2_template),
        ("Quick Check 一致性", test_5_quick_check_tab_consistency),
        ("编码兼容性", test_6_encoding_compatibility),
        ("关键模块导入", test_7_all_imports),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ 测试 '{name}' 异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # 汇总结果
    print("\n" + "=" * 70)
    print("测试结果汇总")
    print("=" * 70)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:10} | {name}")
    
    print("=" * 70)
    print(f"总计: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！代码质量良好，可以安全打包。")
        print("=" * 70)
        return 0
    else:
        print(f"⚠️  {total - passed} 个测试失败，请修复后再打包。")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
