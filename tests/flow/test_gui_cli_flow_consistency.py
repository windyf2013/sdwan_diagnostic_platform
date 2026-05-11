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
        
        # 检查是否定义了 handlers
        if "handlers = {" not in content:
            print(f"❌ CLI 未定义 handlers")
            return False
        print(f"✅ CLI 定义了 handlers")
        
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
        
        # 检查是否定义了 handlers
        if "handlers = {" not in content:
            print(f"❌ GUI 未定义 handlers")
            return False
        print(f"✅ GUI 定义了 handlers")
        
        print("\n✅ 测试 3 通过\n")
        return True
        
    except Exception as e:
        print(f"❌ 测试 3 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_handler_consistency():
    """测试 4: 验证 CLI 和 GUI 的 handlers 一致性"""
    print("=" * 70)
    print("测试 4: CLI 和 GUI Handlers 一致性")
    print("=" * 70)
    
    try:
        # 读取 CLI 和 GUI 源码
        cli_file = project_root / "src" / "sdwan_desktop" / "interface" / "cli" / "commands" / "quick_check.py"
        gui_file = project_root / "src" / "sdwan_desktop" / "interface" / "gui" / "tabs" / "quick_check_tab.py"
        
        cli_content = cli_file.read_text(encoding='utf-8')
        gui_content = gui_file.read_text(encoding='utf-8')
        
        # 提取 CLI handlers 键名
        import re
        cli_handlers_match = re.search(r'handlers\s*=\s*\{([^}]+)\}', cli_content, re.DOTALL)
        gui_handlers_match = re.search(r'handlers\s*=\s*\{([^}]+)\}', gui_content, re.DOTALL)
        
        if not cli_handlers_match:
            print(f"❌ 无法提取 CLI handlers")
            return False
        
        if not gui_handlers_match:
            print(f"❌ 无法提取 GUI handlers")
            return False
        
        # 提取 handler 键名
        cli_keys = set(re.findall(r'"([^"]+)":\s*\w+', cli_handlers_match.group(1)))
        gui_keys = set(re.findall(r'"([^"]+)":\s*\w+', gui_handlers_match.group(1)))
        
        print(f"CLI handlers: {sorted(cli_keys)}")
        print(f"GUI handlers: {sorted(gui_keys)}")
        
        # 检查一致性
        if cli_keys != gui_keys:
            missing_in_gui = cli_keys - gui_keys
            missing_in_cli = gui_keys - cli_keys
            if missing_in_gui:
                print(f"❌ GUI 缺少 handlers: {missing_in_gui}")
            if missing_in_cli:
                print(f"❌ CLI 缺少 handlers: {missing_in_cli}")
            return False
        
        print(f"✅ CLI 和 GUI handlers 完全一致 ({len(cli_keys)} 个)")
        
        print("\n✅ 测试 4 通过\n")
        return True
        
    except Exception as e:
        print(f"❌ 测试 4 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_flow_steps_coverage():
    """测试 5: 验证 handlers 覆盖所有 Flow 步骤"""
    print("=" * 70)
    print("测试 5: Handlers 覆盖 Flow 步骤")
    print("=" * 70)
    
    try:
        from sdwan_desktop.flow.definitions.quick_check import QUICK_CHECK_FLOW
        
        # 获取 Flow 中定义的步骤 ID
        flow_step_ids = {step.id for step in QUICK_CHECK_FLOW.steps}
        print(f"Flow 步骤: {sorted(flow_step_ids)}")
        
        # 读取 GUI handlers
        gui_file = project_root / "src" / "sdwan_desktop" / "interface" / "gui" / "tabs" / "quick_check_tab.py"
        gui_content = gui_file.read_text(encoding='utf-8')
        
        import re
        gui_handlers_match = re.search(r'handlers\s*=\s*\{([^}]+)\}', gui_content, re.DOTALL)
        if not gui_handlers_match:
            print(f"❌ 无法提取 GUI handlers")
            return False
        
        gui_keys = set(re.findall(r'"([^"]+)":\s*\w+', gui_handlers_match.group(1)))
        print(f"GUI handlers: {sorted(gui_keys)}")
        
        # 检查覆盖
        missing_handlers = flow_step_ids - gui_keys
        extra_handlers = gui_keys - flow_step_ids
        
        if missing_handlers:
            print(f"❌ 缺少 handlers: {missing_handlers}")
            return False
        
        if extra_handlers:
            print(f"⚠️  多余的 handlers: {extra_handlers}")
        
        print(f"✅ Handlers 完全覆盖 Flow 步骤")
        
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
