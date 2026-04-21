"""
错误码常量定义模块

遵循 SDWAN_SPEC.md §2.5 错误体系规范
"""

from typing import Dict, Any


# ==================== 错误码分类 ====================

# 输入与契约校验错误
VALIDATION_ERRORS = {
    "VAL_001": "输入参数格式错误",
    "VAL_002": "必填参数缺失",
    "VAL_003": "参数值超出允许范围",
    "VAL_004": "参数类型不匹配",
    "VAL_005": "JSON格式解析失败",
    "VAL_006": "YAML格式解析失败",
    "VAL_007": "配置文件校验失败",
    "VAL_008": "环境变量校验失败",
}

# 外部工具调用错误
TOOL_ERRORS = {
    "TOOL_001": "工具执行超时",
    "TOOL_002": "工具执行失败",
    "TOOL_003": "工具未注册",
    "TOOL_004": "SSH连接失败",
    "TOOL_005": "SSH认证失败",
    "TOOL_006": "Telnet连接失败",
    "TOOL_007": "Ping探测失败",
    "TOOL_008": "DNS解析失败",
    "TOOL_009": "TCP端口探测失败",
    "TOOL_010": "HTTP请求失败",
    "TOOL_011": "系统命令执行失败",
    "TOOL_012": "工具参数校验失败",
    "TOOL_013": "工具资源不足",
    "TOOL_014": "工具权限不足",
}

# 编排与状态迁移错误
FLOW_ERRORS = {
    "FLOW_001": "流程步骤执行失败",
    "FLOW_002": "流程依赖不满足",
    "FLOW_003": "流程状态迁移非法",
    "FLOW_004": "流程定义解析失败",
    "FLOW_005": "流程上下文丢失",
    "FLOW_006": "步骤重试次数超限",
    "FLOW_007": "流程分支条件不满足",
    "FLOW_008": "流程回放失败",
    "FLOW_009": "流程超时",
    "FLOW_010": "流程取消",
}

# 超时错误
TIMEOUT_ERRORS = {
    "TIME_001": "流程整体超时",
    "TIME_002": "步骤执行超时",
    "TIME_003": "网络连接超时",
    "TIME_004": "DNS查询超时",
    "TIME_005": "SSH命令执行超时",
    "TIME_006": "HTTP请求超时",
}

# 未分类系统错误
SYSTEM_ERRORS = {
    "SYS_001": "系统资源不足",
    "SYS_002": "权限不足",
    "SYS_003": "文件系统错误",
    "SYS_004": "内存分配失败",
    "SYS_005": "网络不可用",
    "SYS_006": "数据库连接失败",
    "SYS_007": "配置加载失败",
    "SYS_008": "日志系统初始化失败",
    "SYS_009": "序列化/反序列化失败",
    "SYS_010": "未知系统错误",
}

# ==================== 错误码映射 ====================

# 合并所有错误码
ERROR_CODE_MESSAGES: Dict[str, str] = {}
ERROR_CODE_MESSAGES.update(VALIDATION_ERRORS)
ERROR_CODE_MESSAGES.update(TOOL_ERRORS)
ERROR_CODE_MESSAGES.update(FLOW_ERRORS)
ERROR_CODE_MESSAGES.update(TIMEOUT_ERRORS)
ERROR_CODE_MESSAGES.update(SYSTEM_ERRORS)

# 错误码分类映射
ERROR_CODE_CATEGORIES: Dict[str, str] = {
    "VAL_": "validation",
    "TOOL_": "tool",
    "FLOW_": "flow",
    "TIME_": "timeout",
    "SYS_": "system",
}

# 错误严重程度映射
ERROR_SEVERITY_MAP: Dict[str, str] = {
    # 验证错误通常为警告级别
    "VAL_001": "warning",
    "VAL_002": "warning",
    "VAL_003": "warning",
    "VAL_004": "warning",
    "VAL_005": "warning",
    "VAL_006": "warning",
    "VAL_007": "warning",
    "VAL_008": "warning",
    
    # 工具错误通常为错误级别
    "TOOL_001": "error",
    "TOOL_002": "error",
    "TOOL_003": "error",
    "TOOL_004": "error",
    "TOOL_005": "error",
    "TOOL_006": "error",
    "TOOL_007": "error",
    "TOOL_008": "error",
    "TOOL_009": "error",
    "TOOL_010": "error",
    "TOOL_011": "error",
    "TOOL_012": "warning",
    "TOOL_013": "error",
    "TOOL_014": "error",
    
    # 流程错误通常为错误级别
    "FLOW_001": "error",
    "FLOW_002": "error",
    "FLOW_003": "error",
    "FLOW_004": "error",
    "FLOW_005": "error",
    "FLOW_006": "error",
    "FLOW_007": "warning",
    "FLOW_008": "error",
    "FLOW_009": "error",
    "FLOW_010": "info",
    
    # 超时错误通常为错误级别
    "TIME_001": "error",
    "TIME_002": "error",
    "TIME_003": "error",
    "TIME_004": "error",
    "TIME_005": "error",
    "TIME_006": "error",
    
    # 系统错误通常为严重级别
    "SYS_001": "critical",
    "SYS_002": "critical",
    "SYS_003": "error",
    "SYS_004": "critical",
    "SYS_005": "error",
    "SYS_006": "error",
    "SYS_007": "error",
    "SYS_008": "error",
    "SYS_009": "error",
    "SYS_010": "critical",
}

# 错误码建议操作映射
ERROR_ACTION_MAP: Dict[str, str] = {
    "VAL_001": "检查输入参数格式",
    "VAL_002": "补充必填参数",
    "VAL_003": "调整参数值到允许范围",
    "VAL_004": "修正参数类型",
    "TOOL_001": "增加超时时间或检查网络连接",
    "TOOL_002": "检查工具配置和执行环境",
    "TOOL_003": "注册工具或检查工具名称",
    "TOOL_004": "检查SSH服务器状态和网络连接",
    "TOOL_005": "检查SSH凭据和权限",
    "FLOW_001": "检查步骤实现和依赖",
    "FLOW_002": "检查流程依赖关系",
    "TIME_001": "优化流程执行或增加超时时间",
    "SYS_001": "释放系统资源或增加资源限制",
    "SYS_002": "检查用户权限或使用管理员权限",
}