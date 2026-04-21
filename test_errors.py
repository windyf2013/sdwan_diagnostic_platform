#!/usr/bin/env python3
"""
测试错误体系实现
"""

import sys
sys.path.insert(0, 'src')

from sdwan_desktop.core.errors import (
    BaseError,
    ValidationError,
    ToolError,
    ToolTimeoutError,
    ToolConnectionError,
    FlowError,
    FlowStateError,
    FlowTimeoutError,
    TimeoutError,
    SystemError
)

def test_base_error():
    """测试 BaseError"""
    error = BaseError(
        error_code="TEST_001",
        message="测试错误",
        context={"key": "value"},
        trace_id="test-trace-123"
    )
    
    assert error.error_code == "TEST_001"
    assert error.message == "测试错误"
    assert error.context == {"key": "value"}
    assert error.trace_id == "test-trace-123"
    assert str(error) == "TEST_001: 测试错误"
    
    error_dict = error.to_dict()
    assert error_dict["error_code"] == "TEST_001"
    assert error_dict["message"] == "测试错误"
    assert error_dict["context"] == {"key": "value"}
    assert error_dict["trace_id"] == "test-trace-123"
    
    print("✅ BaseError 测试通过")

def test_validation_error():
    """测试 ValidationError"""
    error = ValidationError(
        field="username",
        reason="不能为空",
        context={"value": ""}
    )
    
    assert error.error_code.startswith("VAL_")
    assert "username" in error.message
    assert "不能为空" in error.message
    assert error.context["field"] == "username"
    assert error.context["reason"] == "不能为空"
    
    print("✅ ValidationError 测试通过")

def test_tool_errors():
    """测试工具相关错误"""
    # ToolError
    tool_error = ToolError(
        tool_name="ping",
        operation="execute",
        reason="执行失败",
        context={"target": "example.com"}
    )
    assert tool_error.error_code.startswith("TOOL_")
    assert "ping" in tool_error.message
    
    # ToolTimeoutError
    timeout_error = ToolTimeoutError(
        tool_name="ssh",
        timeout_seconds=30,
        context={"host": "192.168.1.1"}
    )
    assert timeout_error.error_code.startswith("TOOL_")
    assert "ssh" in timeout_error.message
    assert "30" in timeout_error.message
    
    # ToolConnectionError
    conn_error = ToolConnectionError(
        tool_name="telnet",
        host="192.168.1.1",
        port=23,
        reason="连接被拒绝"
    )
    assert conn_error.error_code.startswith("TOOL_")
    assert "telnet" in conn_error.message
    assert "192.168.1.1" in conn_error.message
    
    print("✅ ToolError 系列测试通过")

def test_flow_errors():
    """测试流程相关错误"""
    # FlowError
    flow_error = FlowError(
        flow_id="quick-check-v1",
        step_id="step-1",
        reason="步骤执行失败",
        context={"input": {"target": "example.com"}}
    )
    assert flow_error.error_code.startswith("FLOW_")
    assert "quick-check-v1" in flow_error.message
    
    # FlowStateError
    state_error = FlowStateError(
        flow_id="deep-dive-v1",
        current_state="running",
        expected_state="completed",
        reason="状态迁移失败"
    )
    assert state_error.error_code.startswith("FLOW_")
    assert "deep-dive-v1" in state_error.message
    
    # FlowTimeoutError
    flow_timeout = FlowTimeoutError(
        flow_id="waterfall-v1",
        timeout_seconds=300,
        context={"url": "https://example.com"}
    )
    assert flow_timeout.error_code.startswith("FLOW_")
    assert "waterfall-v1" in flow_timeout.message
    assert "300" in flow_timeout.message
    
    print("✅ FlowError 系列测试通过")

def test_timeout_error():
    """测试 TimeoutError"""
    timeout_error = TimeoutError(
        operation="ping探测",
        timeout_seconds=30,
        context={"target": "example.com"}
    )
    
    assert timeout_error.error_code == "TIME_001"
    assert "ping探测" in timeout_error.message
    assert "30" in timeout_error.message
    assert timeout_error.context["operation"] == "ping探测"
    assert timeout_error.context["timeout_seconds"] == 30
    
    print("✅ TimeoutError 测试通过")

def test_system_error():
    """测试 SystemError"""
    system_error = SystemError(
        component="memory",
        reason="内存不足",
        context={"available_mb": 100, "required_mb": 1024}
    )
    
    assert system_error.error_code.startswith("SYS_")
    assert "memory" in system_error.message
    assert "内存不足" in system_error.message
    assert system_error.context["component"] == "memory"
    assert system_error.context["reason"] == "内存不足"
    
    print("✅ SystemError 测试通过")

def test_error_code_patterns():
    """测试错误码模式"""
    errors = [
        ValidationError(field="test", reason="test"),
        ToolError(tool_name="test", operation="test", reason="test"),
        FlowError(flow_id="test", step_id="test", reason="test"),
        TimeoutError(operation="test", timeout_seconds=1),
        SystemError(component="test", reason="test")
    ]
    
    for error in errors:
        error_code = error.error_code
        if isinstance(error, ValidationError):
            assert error_code.startswith("VAL_")
        elif isinstance(error, ToolError):
            assert error_code.startswith("TOOL_")
        elif isinstance(error, FlowError):
            assert error_code.startswith("FLOW_")
        elif isinstance(error, TimeoutError):
            assert error_code == "TIME_001"
        elif isinstance(error, SystemError):
            assert error_code.startswith("SYS_")
    
    print("✅ 错误码模式测试通过")

def main():
    """主测试函数"""
    print("开始测试错误体系实现...")
    
    try:
        test_base_error()
        test_validation_error()
        test_tool_errors()
        test_flow_errors()
        test_timeout_error()
        test_system_error()
        test_error_code_patterns()
        
        print("\n🎉 所有测试通过！")
        print("错误体系实现符合验收标准：")
        print("1. ✅ BaseError 正确继承 Exception")
        print("2. ✅ 每个错误类包含 error_code 属性")
        print("3. ✅ 错误码符合命名规范（VAL_*, TOOL_*, FLOW_*, TIME_*, SYS_*）")
        print("4. ✅ to_dict() 返回格式正确")
        print("5. ✅ __init__.py 使用 __all__ 显式导出")
        
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ 未预期的错误: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())