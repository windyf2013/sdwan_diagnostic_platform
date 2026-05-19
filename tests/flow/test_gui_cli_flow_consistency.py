"""
GUI 与 CLI Flow 流程一致性测试

验证 GUI 和 CLI 是否使用统一的 FlowRuntime 执行一键体检流程。
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))


def test_flow_definition_exists():
    """测试 1: 验证 QUICK_CHECK_FLOW 定义存在"""
    print("=" * 70)
    print("测试 1: QUICK_CHECK_FLOW 定义")
    print("=" * 70)
    
    try:
        from sdwan_desktop.flow.definitions.quick_check import QUICK_CHECK_FLOW
        
        print(f"✅ QUICK_CHECK_FLOW 存在")
        print(f"   - ID: {QUICK_CHECK_FLOW.id}")
        print(f"   - Name: {QUICK_CHECK_FLOW.name}")
        print(f"   - Version: {QUICK_CHECK_FLOW.version}")
        print(f"   - Steps: {len(QUICK_CHECK_FLOW.steps)} 个步骤")
        
        for step in QUICK_CHECK_FLOW.steps:
            print(f"     - {step.id}: {step.name} (handler: {step.handler})")
        
        assert len(QUICK_CHECK_FLOW.steps) > 0, "Flow 应该包含至少一个步骤"
        
        print("\n✅ 测试 1 通过\n")
        return True
        
    except Exception as e:
        print(f"❌ 测试 1 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cli_uses_flow_runtime():
    """测试 2: 验证 CLI 使用 FlowRuntime"""
    print("=" * 70)
    print("测试 2: CLI 使用 FlowRuntime")
    print("=" * 70)
    
    try:
        # 读取 CLI quick_check.py 源码
        cli_file = project_root / "src" / "sdwan_desktop" / "interface" / "cli" / "commands" / "quick_check.py"
        content = cli_file.read_text(encoding='utf-8')
        
        # 检查是否导入 FlowRuntime
        if "from sdwan_desktop.runtime.engine import FlowRuntime" not in content:
            print(f"❌ CLI 未导入 FlowRuntime")
            return False
        print(f"✅ CLI 导入了 FlowRuntime")
        
        # 检查是否导入 QUICK_CHECK_FLOW
        if "from sdwan_desktop.flow.definitions.quick_check import QUICK_CHECK_FLOW" not in content:
            print(f"❌ CLI 未导入 QUICK_CHECK_FLOW")
            return False
        print(f"✅ CLI 导入了 QUICK_CHECK_FLOW")
        
        # 检查是否调用 runtime.execute_flow
        if "runtime.execute_flow" not in content and "await runtime.execute_flow" not in content:
            print(f"❌ CLI 未调用 runtime.execute_flow")
            return False
        print(f"✅ CLI 调用了 runtime.execute_flow")
        
        # 检查是否通过共享工厂构建 handlers
        if "build_quick_check_step_handlers" not in content:
            print("❌ CLI 未使用 build_quick_check_step_handlers")
            return False
        print("✅ CLI 使用 build_quick_check_step_handlers")
        
        print("\n✅ 测试 2 通过\n")
        return True
        
    except Exception as e:
        print(f"❌ 测试 2 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_gui_uses_flow_runtime():
    """测试 3: 验证 GUI 使用 FlowRuntime"""
    print("=" * 70)
    print("测试 3: GUI 使用 FlowRuntime")
    print("=" * 70)
    
    try:
        # 读取 GUI quick_check_tab.py 源码
        gui_file = project_root / "src" / "sdwan_desktop" / "interface" / "gui" / "tabs" / "quick_check_tab.py"
        content = gui_file.read_text(encoding='utf-8')
        
        # 检查是否导入 FlowRuntime
        if "from sdwan_desktop.runtime.engine import FlowRuntime" not in content:
            print(f"❌ GUI 未导入 FlowRuntime")
            return False
        print(f"✅ GUI 导入了 FlowRuntime")
        
        # 检查是否导入 QUICK_CHECK_FLOW
        if "from sdwan_desktop.flow.definitions.quick_check import QUICK_CHECK_FLOW" not in content:
            print(f"❌ GUI 未导入 QUICK_CHECK_FLOW")
            return False
        print(f"✅ GUI 导入了 QUICK_CHECK_FLOW")
        
        # 检查是否调用 runtime.execute_flow
        if "runtime.execute_flow" not in content and "await runtime.execute_flow" not in content:
            print(f"❌ GUI 未调用 runtime.execute_flow")
            return False
        print(f"✅ GUI 调用了 runtime.execute_flow")
        
        # 检查是否通过共享工厂构建 handlers
        if "build_quick_check_step_handlers" not in content:
            print("❌ GUI 未使用 build_quick_check_step_handlers")
            return False
        print("✅ GUI 使用 build_quick_check_step_handlers")
        
        print("\n✅ 测试 3 通过\n")
        return True
        
    except Exception as e:
        print(f"❌ 测试 3 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_handler_consistency():
    """测试 4: 验证 CLI 与 GUI 均使用共享的 quick_check 步骤工厂"""
    print("=" * 70)
    print("测试 4: CLI 和 GUI Handlers 一致性")
    print("=" * 70)

    try:
        cli_file = project_root / "src" / "sdwan_desktop" / "interface" / "cli" / "commands" / "quick_check.py"
        gui_file = project_root / "src" / "sdwan_desktop" / "interface" / "gui" / "tabs" / "quick_check_tab.py"
        cli_content = cli_file.read_text(encoding="utf-8")
        gui_content = gui_file.read_text(encoding="utf-8")

        if "build_quick_check_step_handlers" not in cli_content:
            print("❌ CLI 未引用 build_quick_check_step_handlers")
            return False
        if "build_quick_check_step_handlers" not in gui_content:
            print("❌ GUI 未引用 build_quick_check_step_handlers")
            return False

        from unittest.mock import MagicMock

        from sdwan_desktop.flow.definitions.quick_check import QUICK_CHECK_FLOW
        from sdwan_desktop.flow.handlers.quick_check_steps import (
            QuickCheckHandlerDeps,
            QuickCheckHandlersParams,
            build_quick_check_step_handlers,
        )

        dummy = MagicMock()
        deps = QuickCheckHandlerDeps(
            collector=dummy,
            connectivity_tester=dummy,
            dns_split_tester=dummy,
            rule_engine=dummy,
            report_builder=dummy,
        )
        keys = set(build_quick_check_step_handlers(deps, QuickCheckHandlersParams()).keys())
        flow_ids = {s.id for s in QUICK_CHECK_FLOW.steps}
        if keys != flow_ids:
            print(f"❌ 工厂 handlers 与 Flow 步骤不一致: {keys ^ flow_ids}")
            return False

        print(f"✅ 共享工厂覆盖全部 {len(flow_ids)} 个 Flow 步骤")
        print("\n✅ 测试 4 通过\n")
        return True

    except Exception as e:
        print(f"❌ 测试 4 失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_flow_steps_coverage():
    """测试 5: 验证共享工厂 handlers 覆盖所有 Flow 步骤"""
    print("=" * 70)
    print("测试 5: Handlers 覆盖 Flow 步骤")
    print("=" * 70)

    try:
        from unittest.mock import MagicMock

        from sdwan_desktop.flow.definitions.quick_check import QUICK_CHECK_FLOW
        from sdwan_desktop.flow.handlers.quick_check_steps import (
            QuickCheckHandlerDeps,
            QuickCheckHandlersParams,
            build_quick_check_step_handlers,
        )

        flow_step_ids = {step.id for step in QUICK_CHECK_FLOW.steps}
        print(f"Flow 步骤: {sorted(flow_step_ids)}")

        dummy = MagicMock()
        deps = QuickCheckHandlerDeps(
            collector=dummy,
            connectivity_tester=dummy,
            dns_split_tester=dummy,
            rule_engine=dummy,
            report_builder=dummy,
        )
        handler_keys = set(build_quick_check_step_handlers(deps, QuickCheckHandlersParams()).keys())
        print(f"工厂 handlers: {sorted(handler_keys)}")

        missing_handlers = flow_step_ids - handler_keys
        extra_handlers = handler_keys - flow_step_ids

        if missing_handlers:
            print(f"❌ 缺少 handlers: {missing_handlers}")
            return False

        if extra_handlers:
            print(f"⚠️  多余的 handlers: {extra_handlers}")

        print("✅ Handlers 完全覆盖 Flow 步骤")

        print("\n✅ 测试 5 通过\n")
        return True

    except Exception as e:
        print(f"❌ 测试 5 失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print("GUI 与 CLI Flow 流程一致性测试")
    print("=" * 70 + "\n")
    
    tests = [
        ("QUICK_CHECK_FLOW 定义", test_flow_definition_exists),
        ("CLI 使用 FlowRuntime", test_cli_uses_flow_runtime),
        ("GUI 使用 FlowRuntime", test_gui_uses_flow_runtime),
        ("Handlers 一致性", test_handler_consistency),
        ("Handlers 覆盖 Flow 步骤", test_flow_steps_coverage),
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
        print("🎉 所有测试通过！GUI 和 CLI 使用统一的 Flow 流程。")
        print("=" * 70)
        return 0
    else:
        print(f"⚠️  {total - passed} 个测试失败，需要修复。")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
