# 错误模型规范

## 概述
本规范定义SD-WAN诊断平台的统一错误模型，包括错误分类、错误码体系、错误处理策略和错误传播机制。

## 错误分类

### BaseError
所有错误的基类：

```python
from dataclasses import dataclass
from typing import Dict, Any

@dataclass(slots=True)
class BaseError(Exception):
    """错误基类"""
    error_code: str
    message: str
    context: Dict[str, Any]
    trace_id: str

    def __init__(self, error_code: str, message: str, context: Dict[str, Any], trace_id: str):
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.context = context
        self.trace_id = trace_id

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "context": self.context,
            "trace_id": self.trace_id,
            "error_type": self.__class__.__name__
        }
```

### ValidationError
输入与契约校验错误：

```python
@dataclass(slots=True)
class ValidationError(BaseError):
    """校验错误"""
    field_name: str
    field_value: Any
    validation_rule: str

    def __init__(self, error_code: str, message: str, context: Dict[str, Any], 
                 trace_id: str, field_name: str, field_value: Any, validation_rule: str):
        super().__init__(error_code, message, context, trace_id)
        self.field_name = field_name
        self.field_value = field_value
        self.validation_rule = validation_rule
```

### ToolError
外部工具调用错误：

```python
@dataclass(slots=True)
class ToolError(BaseError):
    """工具错误"""
    tool_name: str
    tool_version: str
    retry_count: int

    def __init__(self, error_code: str, message: str, context: Dict[str, Any], 
                 trace_id: str, tool_name: str, tool_version: str, retry_count: int = 0):
        super().__init__(error_code, message, context, trace_id)
        self.tool_name = tool_name
        self.tool_version = tool_version
        self.retry_count = retry_count
```

### FlowError
编排与状态迁移错误：

```python
@dataclass(slots=True)
class FlowError(BaseError):
    """流程错误"""
    flow_id: str
    step_id: str
    step_name: str

    def __init__(self, error_code: str, message: str, context: Dict[str, Any], 
                 trace_id: str, flow_id: str, step_id: str, step_name: str):
        super().__init__(error_code, message, context, trace_id)
        self.flow_id = flow_id
        self.step_id = step_id
        self.step_name = step_name
```

### TimeoutError
超时错误：

```python
@dataclass(slots=True)
class TimeoutError(BaseError):
    """超时错误"""
    timeout_seconds: float
    operation_name: str

    def __init__(self, error_code: str, message: str, context: Dict[str, Any], 
                 trace_id: str, timeout_seconds: float, operation_name: str):
        super().__init__(error_code, message, context, trace_id)
        self.timeout_seconds = timeout_seconds
        self.operation_name = operation_name
```

### SystemError
未分类系统错误：

```python
@dataclass(slots=True)
class SystemError(BaseError):
    """系统错误"""
    component_name: str
    resource_type: str

    def __init__(self, error_code: str, message: str, context: Dict[str, Any], 
                 trace_id: str, component_name: str, resource_type: str):
        super().__init__(error_code, message, context, trace_id)
        self.component_name = component_name
        self.resource_type = resource_type
```

## 错误码体系

### 错误码格式
错误码格式：`类别_序号`
- 类别：3-4个大写字母
- 序号：3位数字，从001开始

### 错误码分类

#### VAL_*: 输入与契约校验错误
- VAL_001: 必填字段缺失
- VAL_002: 字段格式错误
- VAL_003: 字段值超出范围
- VAL_004: 枚举值无效
- VAL_005: 正则表达式不匹配
- VAL_006: 数据类型不匹配
- VAL_007: 数组长度不符合要求
- VAL_008: 对象结构不匹配
- VAL_009: 依赖字段缺失
- VAL_010: 交叉校验失败

#### TOOL_*: 外部工具调用错误
- TOOL_001: 工具执行超时
- TOOL_002: 工具执行失败
- TOOL_003: 工具未注册
- TOOL_004: 工具参数错误
- TOOL_005: 工具资源不足
- TOOL_006: 工具权限不足
- TOOL_007: 工具版本不兼容
- TOOL_008: 工具连接失败
- TOOL_009: 工具认证失败
- TOOL_010: 工具配置错误

#### FLOW_*: 编排与状态迁移错误
- FLOW_001: 流程步骤执行失败
- FLOW_002: 流程依赖不满足
- FLOW_003: 流程状态迁移非法
- FLOW_004: 流程分支条件不满足
- FLOW_005: 流程上下文数据缺失
- FLOW_006: 流程配置错误
- FLOW_007: 流程版本不兼容
- FLOW_008: 流程并发冲突
- FLOW_009: 流程资源锁定失败
- FLOW_010: 流程回放失败

#### TIME_*: 超时错误
- TIME_001: 流程整体超时
- TIME_002: 步骤执行超时
- TIME_003: 工具调用超时
- TIME_004: 网络连接超时
- TIME_005: 数据库操作超时
- TIME_006: 文件操作超时
- TIME_007: 外部API调用超时
- TIME_008: 资源等待超时
- TIME_009: 锁获取超时
- TIME_010: 缓存操作超时

#### SYS_*: 未分类系统错误
- SYS_001: 系统资源不足
- SYS_002: 权限不足
- SYS_003: 文件系统错误
- SYS_004: 网络错误
- SYS_005: 数据库错误
- SYS_006: 内存错误
- SYS_007: 磁盘空间不足
- SYS_008: 进程管理错误
- SYS_009: 线程管理错误
- SYS_010: 系统配置错误

## 错误处理策略

### 错误传播
1. **工具层错误**：ToolError → Service层
2. **服务层错误**：ValidationError/SystemError → Orchestration层
3. **编排层错误**：FlowError/TimeoutError → Interface层
4. **接口层错误**：转换为用户友好的错误信息

### 错误恢复
1. **可重试错误**：TOOL_001, TOOL_008, TIME_*
   - 自动重试（最多3次）
   - 指数退避策略
   - 重试后记录重试次数

2. **不可重试错误**：VAL_*, TOOL_003, TOOL_009
   - 立即失败
   - 记录详细错误信息
   - 提供修复建议

3. **降级处理**：TOOL_002, TOOL_005
   - 使用备用工具
   - 返回部分结果
   - 降低置信度

### 错误日志
1. **日志级别**：
   - ERROR：所有错误
   - WARNING：可恢复错误
   - INFO：错误处理过程

2. **日志字段**：
   - timestamp：时间戳
   - level：日志级别
   - trace_id：追踪ID
   - error_code：错误码
   - error_type：错误类型
   - component：组件名称
   - operation：操作名称
   - context：错误上下文

3. **敏感信息脱敏**：
   - 密码、密钥、Token：替换为`***`
   - IP地址：保留前三段
   - 主机名：保留域名部分

## 错误映射

### 用户友好错误信息
| 错误码 | 用户信息 | 建议动作 |
|--------|----------|----------|
| VAL_001 | 缺少必要参数 | 请检查输入参数 |
| VAL_002 | 参数格式错误 | 请参考API文档 |
| TOOL_001 | 操作超时 | 请稍后重试 |
| TOOL_002 | 服务暂时不可用 | 请检查网络连接 |
| FLOW_001 | 流程执行失败 | 请联系技术支持 |
| TIME_001 | 请求处理超时 | 请简化请求或稍后重试 |
| SYS_001 | 系统资源不足 | 请稍后重试 |

### HTTP状态码映射
| 错误类别 | HTTP状态码 | 说明 |
|----------|------------|------|
| VAL_* | 400 | 客户端错误 |
| TOOL_* | 502 | 网关错误 |
| FLOW_* | 500 | 服务器错误 |
| TIME_* | 504 | 网关超时 |
| SYS_* | 503 | 服务不可用 |

## 错误测试

### 单元测试要求
1. **错误路径测试**：覆盖所有错误分支
2. **错误恢复测试**：验证重试和降级逻辑
3. **错误传播测试**：验证错误在层间传播
4. **错误日志测试**：验证日志格式和内容

### 集成测试要求
1. **端到端错误处理**：验证完整错误处理流程
2. **错误边界测试**：验证极端情况下的错误处理
3. **性能测试**：验证错误处理对性能的影响

## 版本控制
- 初始版本：1.0.0
- 变更记录：见CHANGELOG.md