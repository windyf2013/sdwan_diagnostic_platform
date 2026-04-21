# 数据契约规范

## 概述
本规范定义SD-WAN诊断平台的核心数据契约，包括基础契约类、探测契约、诊断契约和上下文契约。

## 基础契约类

### BaseContract
所有数据契约的基类，包含通用字段：

```python
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict
import uuid

def utc_now_iso() -> str:
    """返回UTC时间ISO格式字符串"""
    return datetime.now(timezone.utc).isoformat()

@dataclass(slots=True)
class BaseContract:
    """所有数据契约的基类"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=utc_now_iso)

    def to_json_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
        }
```

## 探测相关契约

### ProbeProtocol 枚举
定义支持的探测协议：
- ICMP: ICMP连通性测试
- TCP: TCP端口探测
- UDP: UDP端口探测
- DNS: DNS解析测试
- HTTP: HTTP请求测试
- HTTPS: HTTPS请求测试

### ProbeStatus 枚举
定义探测状态：
- PENDING: 等待执行
- RUNNING: 执行中
- SUCCESS: 成功
- FAILED: 失败
- TIMEOUT: 超时
- PARTIAL: 部分成功

### ProbeTarget
探测目标定义：
- host: 目标主机（IP或域名）
- port: 端口号（可选）
- protocol: 探测协议
- dns_server: DNS服务器（仅DNS探测）
- count: 探测次数
- timeout_seconds: 超时时间
- extra_params: 额外参数

### ProbeMetric
探测指标：
- rtt_min: 最小RTT（毫秒）
- rtt_avg: 平均RTT（毫秒）
- rtt_max: 最大RTT（毫秒）
- rtt_stddev: RTT标准差
- loss_rate: 丢包率（0-1）
- ttl: TTL值
- resolved_ips: DNS解析结果列表
- response_code: HTTP状态码/DNS响应码

### ProbeResult
单次探测结果：
- target: 探测目标
- status: 探测状态
- success: 是否成功
- raw_output: 原始输出（仅内部流转）
- metrics: 探测指标
- error_message: 错误信息
- error_code: 错误码
- duration_ms: 执行耗时

## 诊断相关契约

### Severity 枚举
严重程度：
- INFO: 信息
- WARNING: 警告
- ERROR: 错误
- CRITICAL: 严重

### Confidence 枚举
置信度：
- HIGH: 高（>90%）
- MEDIUM: 中（60-90%）
- LOW: 低（30-60%）
- UNCERTAIN: 不确定（<30%）

### DiagnosisEvidence
诊断证据链：
- step_name: 产生证据的步骤
- description: 证据描述
- probe_results: 探测结果列表
- config_snapshots: 配置快照
- conclusion_hint: 指向的结论

### RootCause
根因分析结果：
- cause_id: 根因ID
- title: 根因标题
- description: 详细描述
- severity: 严重程度
- confidence: 置信度（0-1）
- evidence_refs: 证据ID列表
- matched_rules: 匹配的规则

### Recommendation
诊断建议：
- action: 建议动作
- priority: 优先级（1-5）
- expected_outcome: 预期结果
- risk_level: 操作风险等级
- commands: 可执行命令列表

### DiagnosisResult
最终诊断结果：
- diagnosis_type: 诊断类型（quick_check/deep_dive/waterfall）
- target_description: 诊断目标描述
- severity: 严重程度
- summary: 一句话总结
- root_causes: 根因列表
- evidences: 证据列表
- recommendations: 建议列表
- overall_confidence: 综合置信度
- diagnosis_duration_ms: 诊断耗时
- rule_version: 规则版本

## 上下文与状态契约

### FlowStatus 枚举
流程状态：
- PENDING: 等待
- RUNNING: 运行中
- COMPLETED: 完成
- FAILED: 失败
- CANCELLED: 取消

### StepSnapshot
步骤快照：
- step_id: 步骤ID
- step_name: 步骤名称
- status: 步骤状态
- input_data: 输入数据
- output_data: 输出数据
- error: 错误信息
- start_time: 开始时间
- end_time: 结束时间
- retry_count: 重试次数

### FlowContext
流程上下文：
- flow_id: 流程ID
- flow_name: 流程名称
- status: 流程状态
- data: 共享数据
- steps: 步骤记录列表
- current_step_index: 当前步骤索引
- config: 配置信息

## 工具系统契约

### ToolRequest
工具请求：
- tool_name: 工具名称
- parameters: 参数字典
- timeout_seconds: 超时时间
- retry_count: 重试次数

### ToolResponse
工具响应：
- success: 是否成功
- data: 响应数据
- error_message: 错误信息
- error_code: 错误码
- trace_id: 追踪ID
- duration_ms: 执行耗时

## 接口契约

### AgentInput
Agent输入：
- command: 命令名称
- parameters: 参数字典
- context: 上下文信息
- trace_id: 追踪ID

### AgentOutput
Agent输出：
- success: 是否成功
- result: 结果数据
- error_message: 错误信息
- error_code: 错误码
- trace_id: 追踪ID
- duration_ms: 执行耗时

## 版本控制
- 初始版本：1.0.0
- 变更记录：见CHANGELOG.md