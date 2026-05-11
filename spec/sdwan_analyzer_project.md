# SD-WAN桌面诊断专家 - 项目实施方案

**文档版本**: v1.0.0-alpha  
**创建日期**: 2026-04-20  
**适用规范**: SDWAN_SPEC.md + SDWAN_SPEC_PATCHES.md v1.0  
**项目代号**: SDWAN-Desktop-Diagnostic-Expert

---

## 目录

1. [项目概述](#1-项目概述)
2. [架构设计](#2-架构设计)
3. [核心数据契约](#3-核心数据契约)
4. [功能模块详细设计](#4-功能模块详细设计)
5. [工具层实现规范](#5-工具层实现规范)
6. [流程编排设计](#6-流程编排设计)
7. [报告生成系统](#7-报告生成系统)
8. [客户端技术方案](#8-客户端技术方案)
9. [安全与合规](#9-安全与合规)
10. [开发阶段与里程碑](#10-开发阶段与里程碑)

---

## 1. 项目概述

### 1.1 项目目标

开发一款面向Windows客户端的SD-WAN业务分析诊断平台，提供以下核心能力：

| 功能模块 | 能力描述 | 输出物 | 优先级 |
|---------|---------|--------|--------|
| 基础工具集 | ping/tracert/tcping/dns/mtr/ssh/telnet | 实时探测结果 | P0 |
| 一键体检 | Windows配置检查 + 基础连通性分析 | HTML诊断报告 | P0 |
| 深度诊断 | PC+CPE联合分析 + 网络拓扑 + 根因定位 | HTML专业报告 | P1 |
| 业务监测 | 单次URL访问Waterfall分析 | HAR可视化报告 | P1 |

### 1.2 核心诊断场景

| 场景 | 描述 | 关键检测点 |
|------|------|-----------|
| Overlay故障 | SD-WAN隧道建立失败或中断 | CPE配置、隧道状态、证书有效性 |
| 多级NAT穿透 | 流量未正确进入CPE隧道 | PC路由表、CPE NAT策略、端口映射 |
| DNS分流异常 | 解析结果与路由策略不匹配 | DNS服务器配置、域名解析IP归属地 |
| 跨境链路质量 | 国际链路丢包、延迟、抖动 | 端到端RTT、路径MTU、运营商AS路径 |
| 应用访问慢 | 特定业务响应时间长 | Waterfall时序、TCP握手、SSL协商 |

### 1.3 技术约束与环境要求

| 约束项 | 要求 | 说明 |
|--------|------|------|
| 操作系统 | Windows 10/11 x64 | 支持Windows Server 2019+ |
| Python版本 | 3.10 及以上 | 使用asyncio新特性 |
| 打包格式 | PyInstaller onefile / MSI | 单文件便于分发 |
| 权限要求 | 管理员权限(部分功能) | tracert/修改路由需要提权 |
| 网络依赖 | 基础功能可离线运行 | 首次使用需下载OUI数据库 |
| 磁盘空间 | 200MB | 含依赖和报告存储 |

---

## 2. 架构设计

### 2.1 分层架构图

```mermaid
┌─────────────────────────────────────────────────────────────────┐
│ Interface Layer │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐ │
│ │ CLI入口 │ │ GUI窗口 │ │ AgentEntry (API适配) │ │
│ │ agentctl │ │ PySide6 │ │ 结构化输入输出 │ │
│ └──────┬──────┘ └──────┬──────┘ └───────────┬─────────────┘ │
│ │ │ │ │
│ └────────────────┼──────────────────────┘ │
│ │ │
├──────────────────────────┼────────────────────────────────────────┤
│ ▼ │
│ Orchestration Layer │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ Flow Executor │ │
│ │ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ │ │
│ │ │PipelineEngine│ │ DAGScheduler │ │StateMachine │ │ │
│ │ └──────────────┘ └──────────────┘ └──────────────┘ │ │
│ └─────────────────────────────────────────────────────────────┘ │
│ │ │
├──────────────────────────┼────────────────────────────────────────┤
│ ▼ │
│ Service Layer │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ │
│ │TopologyBuilder│ │RootCauseEngine│ │RuleEvaluator │ │
│ └──────────────┘ └──────────────┘ └──────────────┘ │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ │
│ │ConfigParser │ │EvidenceFusion│ │ReportBuilder │ │
│ └──────────────┘ └──────────────┘ └──────────────┘ │
│ │ │
├──────────────────────────┼────────────────────────────────────────┤
│ ▼ │
│ Tool Layer │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ Tool Registry │ │
│ │ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ │ │
│ │ │PingTool│ │TraceTool│ │DnsTool │ │TcpTool │ │SshTool │ │ │
│ │ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ │ │
│ │ ┌────────┐ ┌────────┐ ┌────────┐ │ │
│ │ │WinSys │ │HttpTool│ │MtrTool │ │ │
│ │ └────────┘ └────────┘ └────────┘ │ │
│ └─────────────────────────────────────────────────────────────┘ │
│ │ │
├──────────────────────────┼────────────────────────────────────────┤
│ ▼ │
│ Core Layer │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ DiagnosisResult │ ProbeTarget │ Evidence │ FlowState │ │
│ │ ToolRequest │ ToolResponse │ Context │ ErrorCode │ │
│ └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 目录结构
```bash
    sdwan_diagnostic_platform/
    │
    ├── spec/ # 规范层 (PATCH-005 最小集)
    │ ├── 00_core/
    │ │ ├── data_contract.md # 数据契约定义
    │ │ ├── error_model.md # 错误码体系
    │ │ └── state_context.md # 上下文状态机
    │ ├── 10_architecture/
    │ │ └── layering_model.md # 分层依赖关系
    │ ├── 20_domain/
    │ │ ├── probe/
    │ │ │ ├── probe_icmp.md # ICMP探测规范
    │ │ │ ├── probe_tcp.md # TCP端口探测
    │ │ │ └── probe_dns.md # DNS解析探测
    │ │ └── reporting/
    │ │ └── report_schema.md # 报告输出Schema
    │ └── 50_execution/
    │ └── pipeline_engine.md # 流程执行引擎
    │
    ├── src/
    │ └── sdwan_desktop/ # Python包根目录
    │ │
    │ ├── core/ # 基础层
    │ │ ├── types/ # 数据类型定义
    │ │ │ ├── base.py # BaseContract基类
    │ │ │ ├── diagnosis.py # DiagnosisResult等
    │ │ │ ├── probe.py # ProbeTarget/ProbeResult
    │ │ │ └── context.py # Context/FlowState
    │ │ ├── errors/ # 错误定义
    │ │ │ ├── base.py # BaseError
    │ │ │ ├── validation.py # ValidationError
    │ │ │ ├── tool.py # ToolError
    │ │ │ └── flow.py # FlowError
    │ │ └── constants/ # 常量定义
    │ │ ├── error_codes.py
    │ │ └── severity.py
    │ │
    │ ├── runtime/ # 执行引擎层
    │ │ ├── engine.py # FlowRuntime核心
    │ │ ├── executor.py # StepExecutor
    │ │ ├── scheduler.py # TaskScheduler (异步)
    │ │ └── dispatcher.py # ToolDispatcher
    │ │
    │ ├── flow/ # 流程定义层
    │ │ ├── definitions/ # Flow定义
    │ │ │ ├── quick_check.py # 一键体检Flow
    │ │ │ ├── deep_dive.py # 深度诊断Flow
    │ │ │ └── waterfall.py # 业务监测Flow
    │ │ ├── pipelines/ # Pipeline实现
    │ │ │ ├── base.py
    │ │ │ └── linear.py
    │ │ └── dags/ # DAG实现
    │ │ ├── base.py
    │ │ └── graph.py
    │ │
    │ ├── services/ # 业务逻辑层
    │ │ ├── analyzer/ # 分析器
    │ │ │ ├── topology_builder.py # 拓扑构建
    │ │ │ ├── root_cause.py # 根因分析
    │ │ │ └── rule_engine.py # 规则引擎
    │ │ ├── parser/ # 解析器
    │ │ │ ├── config_parser.py # CPE配置解析
    │ │ │ └── route_parser.py # 路由表解析
    │ │ └── reporter/ # 报告服务
    │ │ ├── html_builder.py # HTML生成
    │ │ └── evidence_fusion.py # 证据融合
    │ │
    │ ├── tools/ # 工具层
    │ │ ├── registry/ # 工具注册
    │ │ │ ├── base.py # ToolRegistry
    │ │ │ └── decorator.py # tool_function装饰器
    │ │ ├── implementations/ # 工具实现
    │ │ │ ├── network/ # 网络工具
    │ │ │ │ ├── ping.py # PingTool
    │ │ │ │ ├── traceroute.py # TraceRouteTool
    │ │ │ │ ├── tcping.py # TcpPortTool
    │ │ │ │ ├── dns.py # DnsTool
    │ │ │ │ └── mtr.py # MtrTool
    │ │ │ ├── system/ # 系统工具
    │ │ │ │ └── windows.py # WindowsSystemTool
    │ │ │ ├── remote/ # 远程工具
    │ │ │ │ ├── ssh.py # SshAdapter
    │ │ │ │ └── telnet.py # TelnetAdapter
    │ │ │ └── web/ # Web工具
    │ │ │ └── har_capture.py # HarCaptureTool
    │ │ └── adapters/ # 第三方适配器
    │ │ ├── paramiko_adapter.py
    │ │ └── playwright_adapter.py
    │ │
    │ ├── interface/ # 入口层
    │ │ ├── cli/ # CLI入口
    │ │ │ ├── main.py # agentctl主命令
    │ │ │ └── commands.py # 子命令定义
    │ │ ├── gui/ # GUI入口
    │ │ │ ├── main_window.py # 主窗口
    │ │ │ ├── widgets/ # UI组件
    │ │ │ └── workers/ # 后台工作线程
    │ │ └── agent_entry.py # 统一入口适配器
    │ │
    │ ├── reporting/ # 报告模板
    │ │ ├── templates/ # HTML模板
    │ │ │ ├── base.html
    │ │ │ ├── quick_check.html
    │ │ │ ├── deep_dive.html
    │ │ │ └── waterfall.html
    │ │ ├── assets/ # 静态资源
    │ │ │ ├── css/
    │ │ │ ├── js/
    │ │ │ └── images/
    │ │ └── exports/ # 导出目录(运行时)
    │ │
    │ ├── config/ # 配置管理
    │ │ ├── settings.py # 配置类定义
    │ │ ├── loader.py # 配置加载器
    │ │ └── defaults.py # 默认配置
    │ │
    │ └── bootstrap/ # 启动引导
    │ ├── app.py # Application入口
    │ └── initializer.py # 初始化逻辑
    │
    ├── tests/ # 测试目录
    │ ├── unit/ # 单元测试
    │ │ ├── test_core/
    │ │ ├── test_tools/
    │ │ └── test_services/
    │ ├── flow/ # 流程测试
    │ │ ├── test_quick_check.py
    │ │ ├── test_deep_dive.py
    │ │ └── test_waterfall.py
    │ ├── integration/ # 集成测试
    │ └── fixtures/ # 测试数据
    │ ├── sample_configs/
    │ └── sample_outputs/
    │
    ├── configs/ # 环境配置
    │ ├── dev.yaml # 开发环境
    │ ├── test.yaml # 测试环境
    │ └── prod.yaml # 生产环境
    │
    ├── scripts/ # 工具脚本
    │ ├── build.py # 构建脚本
    │ ├── run_flow.py # 流程调试脚本
    │ └── pack.py # 打包脚本
    │
    ├── docs/ # 项目文档
    │ ├── user_guide.md # 用户手册
    │ ├── developer_guide.md # 开发指南
    │ └── api_reference.md # API参考
    │
    ├── pyproject.toml # 项目配置
    ├── README.md # 项目说明
    ├── CHANGELOG.md # 变更日志
    ├── .gitignore # Git忽略配置
    ├── .pre-commit-config.yaml # Pre-commit配置
    └── Makefile # 构建自动化
```

### 2.3 依赖关系规则

```mermaid
Interface Layer
│
▼
Orchestration Layer ──────────────────────┐
│ │
▼ ▼
Service Layer ◄──────────────────── Core Layer
│ ▲
▼ │
Tool Layer ─────────────────────────────┘
```

**依赖规则**:

1. Core Layer: 无外部依赖，仅标准库
2. Tool Layer: 依赖Core Layer，禁止依赖Service/Orchestration
3. Service Layer: 依赖Core Layer，通过Dispatcher访问Tool Layer
4. Orchestration Layer: 依赖Service/Tool/Core Layer
5. Interface Layer: 依赖Orchestration/Core Layer，禁止直接访问Tool Layer


---

## 3. 核心数据契约

### 3.1 基础契约类

```python
# src/sdwan_desktop/core/types/base.py

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

### 3.2 探测相关契约

```python
# src/sdwan_desktop/core/types/probe.py

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum

class ProbeProtocol(str, Enum):
    ICMP = "icmp"
    TCP = "tcp"
    UDP = "udp"
    DNS = "dns"
    HTTP = "http"
    HTTPS = "https"

class ProbeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    PARTIAL = "partial"

@dataclass(slots=True)
class ProbeTarget(BaseContract):
    """探测目标定义"""
    host: str
    port: Optional[int] = None
    protocol: ProbeProtocol = ProbeProtocol.ICMP
    dns_server: Optional[str] = None          # DNS探测时指定服务器
    count: int = 4                            # 探测次数
    timeout_seconds: int = 30
    extra_params: Dict[str, Any] = field(default_factory=dict)

@dataclass(slots=True)
class ProbeMetric:
    """探测指标"""
    rtt_min: Optional[float] = None           # 最小RTT(ms)
    rtt_avg: Optional[float] = None           # 平均RTT(ms)
    rtt_max: Optional[float] = None           # 最大RTT(ms)
    rtt_stddev: Optional[float] = None        # RTT标准差
    loss_rate: Optional[float] = None         # 丢包率(0-1)
    ttl: Optional[int] = None                 # TTL值
    resolved_ips: List[str] = field(default_factory=list)  # DNS解析结果
    response_code: Optional[int] = None       # HTTP状态码/DNS响应码

@dataclass(slots=True)
class ProbeResult(BaseContract):
    """单次探测结果"""
    target: ProbeTarget
    status: ProbeStatus = ProbeStatus.PENDING
    success: bool = False
    raw_output: Optional[str] = None          # 原始输出(仅内部流转)
    metrics: ProbeMetric = field(default_factory=ProbeMetric)
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    duration_ms: float = 0.0                  # 执行耗时
```

### 3.3 诊断相关契约
```python
# src/sdwan_desktop/core/types/diagnosis.py

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
from .base import BaseContract
from .probe import ProbeResult

class Severity(str, Enum):
    """严重程度"""
    INFO = "info"           # 信息
    WARNING = "warning"     # 警告
    ERROR = "error"         # 错误
    CRITICAL = "critical"   # 严重

class Confidence(str, Enum):
    """置信度"""
    HIGH = "high"           # >90%
    MEDIUM = "medium"       # 60-90%
    LOW = "low"             # 30-60%
    UNCERTAIN = "uncertain" # <30%

@dataclass(slots=True)
class DiagnosisEvidence(BaseContract):
    """诊断证据链"""
    step_name: str                          # 产生证据的步骤
    description: str                        # 证据描述
    probe_results: List[ProbeResult] = field(default_factory=list)
    config_snapshots: Dict[str, Any] = field(default_factory=dict)
    conclusion_hint: str = ""               # 指向的结论

@dataclass(slots=True)
class RootCause(BaseContract):
    """根因分析结果"""
    cause_id: str                           # 根因ID
    title: str                              # 根因标题
    description: str                        # 详细描述
    severity: Severity = Severity.WARNING
    confidence: float = 0.0                 # 置信度 0-1
    evidence_refs: List[str] = field(default_factory=list)  # 证据ID列表
    matched_rules: List[str] = field(default_factory=list)  # 匹配的规则

@dataclass(slots=True)
class Recommendation(BaseContract):
    """诊断建议"""
    action: str                             # 建议动作
    priority: int = 1                       # 优先级 1-5
    expected_outcome: str = ""              # 预期结果
    risk_level: Severity = Severity.INFO    # 操作风险等级
    commands: List[str] = field(default_factory=list)  # 可执行命令

@dataclass(slots=True)
class DiagnosisResult(BaseContract):
    """最终诊断结果"""
    # 基本信息
    diagnosis_type: str                     # quick_check / deep_dive / waterfall
    target_description: str                 # 诊断目标描述
    
    # 结论
    severity: Severity = Severity.INFO
    summary: str = ""                       # 一句话总结
    root_causes: List[RootCause] = field(default_factory=list)
    
    # 证据
    evidences: List[DiagnosisEvidence] = field(default_factory=list)
    
    # 建议
    recommendations: List[Recommendation] = field(default_factory=list)
    
    # 元信息
    overall_confidence: float = 0.0
    diagnosis_duration_ms: float = 0.0
    rule_version: str = "1.0.0"
```

### 3.4 上下文与状态契约

```python
# src/sdwan_desktop/core/types/context.py

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from enum import Enum
from .base import BaseContract

class FlowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass(slots=True)
class StepSnapshot(BaseContract):
    """步骤快照"""
    step_id: str
    step_name: str
    status: FlowStatus = FlowStatus.PENDING
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    retry_count: int = 0

@dataclass(slots=True)
class FlowContext(BaseContract):
    """流程上下文"""
    flow_id: str
    flow_name: str
    status: FlowStatus = FlowStatus.PENDING
    
    # 共享数据
    data: Dict[str, Any] = field(default_factory=dict)
    
    # 步骤记录
    steps: List[StepSnapshot] = field(default_factory=list)
    current_step_index: int = 0
    
    # 配置
    config: Dict[str, Any] = field(default_factory=dict)
    
    def add_step_snapshot(self, snapshot: StepSnapshot) -> None:
        self.steps.append(snapshot)
    
    def get_step_by_id(self, step_id: str) -> Optional[StepSnapshot]:
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None
```

---

## 4. 功能模块详细设计

### 4.1 功能模块总览

```mermaid
┌─────────────────────────────────────────────────────────────────┐
│                    SD-WAN桌面诊断专家                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              模块一: 基础网络工具集                       │    │
│  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ │    │
│  │  │ Ping │ │Trace │ │Tcping│ │ DNS  │ │ MTR  │ │ SSH  │ │    │
│  │  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ │    │
│  │  ┌──────┐                                               │    │
│  │  │Telnet│                                               │    │
│  │  └──────┘                                               │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              模块二: 一键体检 (QuickCheck)                │    │
│  │  • Windows配置采集    • 基础连通性测试    • 配置异常检测   │    │
│  │  • 网关可达性        • DNS解析测试       • 代理配置检查   │    │
│  │  • 路由表分析        • 防火墙规则检查    • 报告生成       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              模块三: 深度诊断 (DeepDive)                  │    │
│  │  • PC+CPE双端采集    • 配置一致性校验    • 网络拓扑构建   │    │
│  │  • Overlay状态分析   • 路由策略验证      • 隧道状态检测   │    │
│  │  • NAT类型识别       • DNS分流分析       • 根因定位       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              模块四: 业务监测 (Waterfall)                 │    │
│  │  • URL访问录制       • HAR文件解析       • 时序图生成     │    │
│  │  • 性能指标提取      • 瓶颈分析          • 优化建议       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 模块一: 基础网络工具集

**功能描述**: 
提供独立的网络诊断工具，可单独使用，也可被其他模块调用。

**工具清单**:

| 工具名称 | 功能 | 输入参数 | 输出内容 | 实现方式 |
| PingTool | ICMP连通性测试 | host, count, timeout, packet_size | RTT统计, 丢包率, TTL | pythonping / 系统ping |
| TraceRouteTool | 路由追踪 | host, max_hops, timeout, protocol | 每一跳IP, RTT, 归属地 | 系统tracert / scapy |
| TcpPortTool | TCP端口检测 | host, port, timeout | 端口状态, 响应时间 | socket.connect |
| DnsTool | DNS解析 | domain, dns_server, record_type | 解析结果, 响应时间, TTL | dnspython |
| MtrTool | 综合路由追踪 | host, count, interval | 逐跳丢包/延迟统计 | 组合ping+traceroute |
| SshAdapter | SSH远程执行 | host, port, username, password/key, command | 命令输出 | paramiko / asyncssh |
| TelnetAdapter | Telnet连接 | host, port, timeout | 连接状态, banner | telnetlib3 |

**工具注册示例**:

```python
# src/sdwan_desktop/tools/registry/decorator.py

from typing import Callable, Any
from functools import wraps

def tool_function(
    name: str,
    description: str = "",
    timeout: int = 30,
    retry_count: int = 0
) -> Callable:
    """工具函数装饰器 - 依据PATCH-003"""
    def decorator(func: Callable) -> Callable:
        func._spec_type = "tool"
        func._tool_name = name
        func._tool_description = description
        func._tool_timeout = timeout
        func._tool_retry = retry_count
        
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)
        
        return wrapper
    return decorator

# 使用示例
@tool_function(
    name="ping",
    description="ICMP连通性测试",
    timeout=30,
    retry_count=2
)
class PingTool:
    def execute(self, target: ProbeTarget, ctx: Context) -> ProbeResult:
        # 实现
        pass
```

### 4.3 模块二: 一键体检 (QuickCheck)

**触发方式**: 
GUI按钮 / CLI命令 agentctl quick-check

**检测项目清单**:

| 序号 | 检测项 | 检测内容 | 异常阈值 | 严重程度 |
| 1 | 网卡状态 | 是否启用、连接状态、速度 | 未连接/禁用 | CRITICAL |
| 2 | IP配置 | IP地址、子网掩码、是否DHCP | APIPA地址 | ERROR |
| 3 | 网关配置 | 默认网关地址、网关可达性 | 网关不通 | CRITICAL |
| 4 | DNS配置 | DNS服务器列表、解析测试 | 解析超时 | WARNING |
| 5 | 代理配置 | 系统代理、IE代理设置 | 代理不可达 | WARNING |
| 6 | 路由表 | 默认路由、持久路由 | 多条默认路由 | WARNING |
| 7 | 防火墙 | Windows防火墙状态、入站规则 | 阻止ICMP | INFO |
| 8 | 互联网连通性 | 公网IP可达性测试 | 丢包>10% | WARNING |
| 9 | DNS分流检测 | 国内外域名解析结果对比 | 结果不一致 | INFO |
| 10 | IPv6状态 | IPv6是否启用、连通性 | IPv6优先 | INFO |

**诊断规则示例**:
```python
# src/sdwan_desktop/services/analyzer/rule_engine.py

@pure_function
def evaluate_gateway_rule(
    gateway_ping: ProbeResult,
    gateway_config: Dict[str, Any]
) -> Optional[RootCause]:
    """评估网关故障规则"""
    
    # 规则1: 网关不可达
    if not gateway_ping.success:
        return RootCause(
            cause_id="GW-001",
            title="默认网关不可达",
            description=f"无法Ping通网关 {gateway_config.get('gateway')}",
            severity=Severity.CRITICAL,
            confidence=0.95,
            evidence_refs=[gateway_ping.id]
        )
    
    # 规则2: 网关延迟过高
    if gateway_ping.metrics.rtt_avg and gateway_ping.metrics.rtt_avg > 100:
        return RootCause(
            cause_id="GW-002",
            title="网关响应延迟过高",
            description=f"网关平均延迟 {gateway_ping.metrics.rtt_avg:.1f}ms",
            severity=Severity.WARNING,
            confidence=0.85,
            evidence_refs=[gateway_ping.id]
        )
    
    return None
```

### 4.4 模块三: 深度诊断 (DeepDive)
**触发方式**: 
GUI高级模式 / CLI命令 agentctl deep-dive --cpe 192.168.1.1

**执行流程图**:

```mermaid
┌─────────────────────────────────────────────────────────────────┐
│                      DeepDive 执行流程                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 1: 双端信息采集 (并行执行)                                  │
│  ┌─────────────────────┐    ┌─────────────────────────────────┐ │
│  │   PC端采集           │    │   CPE端采集                      │ │
│  │  • 网卡配置          │    │  • SSH连接建立                   │ │
│  │  • 路由表            │    │  • show version                  │ │
│  │  • ARP表             │    │  • show sdwan policy             │ │
│  │  • 活动连接          │    │  • show ip route                 │ │
│  │  • 代理设置          │    │  • show interface                │ │
│  │  • DNS缓存           │    │  • show ip nat translations      │ │
│  └─────────────────────┘    └─────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 2: 配置解析与校验                                           │
│  • 解析CPE配置，提取关键信息                                     │
│  • 对比PC端路由与CPE策略                                         │
│  • 识别配置不一致项                                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 3: 拓扑构建                                                 │
│  • 构建节点: PC, CPE, Underlay GW, Overlay Hub                  │
│  • 构建边: 物理链路, 逻辑隧道, 策略路由                          │
│  • 生成Mermaid格式拓扑图                                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 4: 针对性探测 (基于拓扑分析结果)                            │
│  • 探测Underlay路径质量                                          │
│  • 探测Overlay隧道状态                                           │
│  • 验证关键路由是否生效                                          │
│  • 测试DNS分流效果                                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 5: 根因分析                                                 │
│  • 执行诊断规则引擎                                              │
│  • 融合多源证据                                                  │
│  • 计算置信度                                                    │
│  • 生成诊断结论                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 6: 报告生成                                                 │
│  • 填充诊断结果                                                  │
│  • 渲染HTML模板                                                  │
│  • 保存报告文件                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**CPE配置解析器接口**:
```python
# src/sdwan_desktop/services/parser/config_parser.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class SdwanPolicy:
    """SD-WAN策略"""
    name: str
    source: str
    destination: str
    application: str
    sla_class: str
    preferred_path: str
    backup_path: Optional[str]

@dataclass
class RouteEntry:
    """路由条目"""
    destination: str
    gateway: str
    interface: str
    metric: int
    protocol: str  # static, bgp, ospf, connected

@dataclass
class InterfaceStatus:
    """接口状态"""
    name: str
    ip_address: str
    status: str  # up/down
    protocol: str
    mtu: int
    speed: str

@dataclass
class CpeConfiguration:
    """CPE配置解析结果"""
    vendor: str                     # cisco, huawei, fortinet, etc.
    model: str
    version: str
    hostname: str
    
    interfaces: List[InterfaceStatus]
    routes: List[RouteEntry]
    sdwan_policies: List[SdwanPolicy]
    nat_rules: List[Dict[str, Any]]
    vpn_tunnels: List[Dict[str, Any]]

class ConfigParser(ABC):
    """配置解析器抽象基类"""
    
    @abstractmethod
    def parse(self, raw_config: str) -> CpeConfiguration:
        """解析原始配置文本"""
        pass
    
    @abstractmethod
    def get_vendor(self) -> str:
        """返回支持的厂商"""
        pass
```

### 4.5 模块四: 业务监测 (Waterfall)
**触发方式**: 
GUI输入URL / CLI命令 agentctl waterfall --url https://example.com

**执行流程**:

```mermaid
┌─────────────────────────────────────────────────────────────────┐
│                    Waterfall 执行流程                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 1: 浏览器启动                                               │
│  • 启动Chromium无头模式                                          │
│  • 设置代理(如需要)                                              │
│  • 清理缓存和Cookie                                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 2: 页面访问录制                                             │
│  • 导航到目标URL                                                 │
│  • 等待页面加载完成                                              │
│  • 捕获HAR文件                                                   │
│  • 截取页面截图                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 3: HAR解析                                                  │
│  • 解析DNS查询时间                                               │
│  • 解析TCP连接时间                                               │
│  • 解析SSL握手时间                                               │
│  • 解析请求响应时间                                              │
│  • 计算各阶段耗时占比                                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 4: 性能分析                                                 │
│  • 识别最慢的资源                                                │
│  • 检测阻塞渲染的资源                                            │
│  • 分析网络耗时 vs 服务器耗时                                    │
│  • 生成优化建议                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 5: 报告生成                                                 │
│  • 生成Waterfall时序图                                           │
│  • 填充性能指标                                                  │
│  • 输出HTML报告                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**HAR解析结果契约**:

```python
# src/sdwan_desktop/core/types/waterfall.py

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from .base import BaseContract

@dataclass(slots=True)
class ResourceTiming(BaseContract):
    """单个资源加载时序"""
    url: str
    resource_type: str                     # document, script, stylesheet, image, xhr
    
    # 时序分解 (单位: ms)
    dns_time: float = 0.0
    connect_time: float = 0.0
    ssl_time: float = 0.0
    wait_time: float = 0.0                 # TTFB
    download_time: float = 0.0
    
    total_time: float = 0.0
    status_code: int = 0
    size_bytes: int = 0

@dataclass(slots=True)
class WaterfallResult(BaseContract):
    """Waterfall分析结果"""
    url: str
    screenshot_path: Optional[str] = None
    
    # 总体指标
    page_load_time: float = 0.0
    dom_content_loaded: float = 0.0
    total_requests: int = 0
    total_size_bytes: int = 0
    
    # 资源时序列表
    resources: List[ResourceTiming] = field(default_factory=list)
    
    # 性能瓶颈分析
    slowest_resources: List[ResourceTiming] = field(default_factory=list)
    blocking_resources: List[str] = field(default_factory=list)
    
    # 优化建议
    recommendations: List[str] = field(default_factory=list)
```

---

## 5. 工具层实现规范

### 5.1 工具注册与调度
```python
# src/sdwan_desktop/tools/registry/base.py

from typing import Dict, Type, Optional, Any
from dataclasses import dataclass, field
import asyncio

@dataclass
class ToolMetadata:
    """工具元数据"""
    name: str
    description: str
    version: str = "1.0.0"
    timeout_seconds: int = 30
    retry_count: int = 0
    required_permissions: List[str] = field(default_factory=list)
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None

class ToolRegistry:
    """工具注册中心"""
    
    _instance: Optional["ToolRegistry"] = None
    _tools: Dict[str, Type] = {}
    _metadata: Dict[str, ToolMetadata] = {}
    
    def __new__(cls) -> "ToolRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def register(
        self,
        tool_class: Type,
        metadata: ToolMetadata
    ) -> None:
        """注册工具"""
        self._tools[metadata.name] = tool_class
        self._metadata[metadata.name] = metadata
    
    def get_tool(self, name: str) -> Optional[Type]:
        """获取工具类"""
        return self._tools.get(name)
    
    def get_metadata(self, name: str) -> Optional[ToolMetadata]:
        """获取工具元数据"""
        return self._metadata.get(name)
    
    def list_tools(self) -> List[str]:
        """列出所有工具"""
        return list(self._tools.keys())


class ToolDispatcher:
    """工具调度器 - 唯一工具调用入口"""
    
    def __init__(self, registry: ToolRegistry):
        self.registry = registry
    
    async def dispatch(
        self,
        tool_name: str,
        request: ToolRequest,
        ctx: Context
    ) -> ToolResponse:
        """调度工具执行"""
        tool_class = self.registry.get_tool(tool_name)
        if not tool_class:
            raise ToolError(
                error_code="TOOL_NOT_FOUND",
                message=f"工具 {tool_name} 未注册",
                context={"tool_name": tool_name},
                trace_id=ctx.trace_id
            )
        
        metadata = self.registry.get_metadata(tool_name)
        
        # 参数校验
        self._validate_request(request, metadata)
        
        # 执行工具 (支持超时和重试)
        return await self._execute_with_retry(
            tool_class, request, ctx, metadata
        )
    
    async def _execute_with_retry(
        self,
        tool_class: Type,
        request: ToolRequest,
        ctx: Context,
        metadata: ToolMetadata
    ) -> ToolResponse:
        """带重试的执行"""
        last_error = None
        
        for attempt in range(metadata.retry_count + 1):
            try:
                tool_instance = tool_class()
                result = await asyncio.wait_for(
                    tool_instance.execute(request, ctx),
                    timeout=metadata.timeout_seconds
                )
                return result
            except asyncio.TimeoutError:
                last_error = ToolError(
                    error_code="TOOL_TIMEOUT",
                    message=f"工具 {metadata.name} 执行超时",
                    context={"attempt": attempt + 1},
                    trace_id=ctx.trace_id
                )
            except Exception as e:
                last_error = e
        
        raise last_error
```

### 5.2 Windows系统工具实现
```python
# src/sdwan_desktop/tools/implementations/system/windows.py

import subprocess
import ipaddress
from typing import Dict, List, Any
import wmi

@tool_function(
    name="windows_system",
    description="Windows系统信息采集",
    timeout=60
)
class WindowsSystemTool:
    """Windows系统信息采集工具"""
    
    def __init__(self):
        self.wmi_client = wmi.WMI()
    
    def execute(
        self,
        request: ToolRequest,
        ctx: Context
    ) -> ToolResponse:
        """执行系统信息采集"""
        
        result = {
            "network_adapters": self._get_network_adapters(),
            "routing_table": self._get_routing_table(),
            "dns_config": self._get_dns_config(),
            "proxy_config": self._get_proxy_config(),
            "firewall_status": self._get_firewall_status(),
            "active_connections": self._get_active_connections()
        }
        
        return ToolResponse(
            success=True,
            data=result,
            trace_id=ctx.trace_id
        )
    
    def _get_network_adapters(self) -> List[Dict[str, Any]]:
        """获取网卡配置"""
        adapters = []
        
        for nic in self.wmi_client.Win32_NetworkAdapterConfiguration(
            IPEnabled=True
        ):
            adapters.append({
                "description": nic.Description,
                "mac_address": nic.MACAddress,
                "ip_addresses": nic.IPAddress,
                "ip_subnets": nic.IPSubnet,
                "default_gateway": nic.DefaultIPGateway,
                "dhcp_enabled": nic.DHCPEnabled,
                "dns_servers": nic.DNSServerSearchOrder,
                "dns_suffix": nic.DNSDomainSuffixSearchOrder
            })
        
        return adapters
    
    def _get_routing_table(self) -> List[Dict[str, Any]]:
        """获取路由表"""
        output = subprocess.run(
            ["route", "print", "-4"],
            capture_output=True,
            text=True,
            encoding="utf-8"
        )
        
        routes = []
        # 解析route print输出
        # ... 解析逻辑 ...
        
        return routes
    
    def _get_dns_config(self) -> Dict[str, Any]:
        """获取DNS配置"""
        output = subprocess.run(
            ["nslookup", "-type=ns", "."],
            capture_output=True,
            text=True
        )
        
        return {
            "default_servers": self._parse_nslookup_servers(output.stdout)
        }
    
    def _get_proxy_config(self) -> Dict[str, Any]:
        """获取代理配置"""
        import winreg
        
        proxy_config = {}
        
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
            )
            
            proxy_config["proxy_enable"] = bool(
                winreg.QueryValueEx(key, "ProxyEnable")[0]
            )
            proxy_config["proxy_server"] = winreg.QueryValueEx(
                key, "ProxyServer"
            )[0]
            proxy_config["proxy_override"] = winreg.QueryValueEx(
                key, "ProxyOverride"
            )[0]
            
            winreg.CloseKey(key)
        except Exception:
            pass
        
        return proxy_config
    
    def _get_firewall_status(self) -> Dict[str, Any]:
        """获取防火墙状态"""
        output = subprocess.run(
            ["netsh", "advfirewall", "show", "allprofiles"],
            capture_output=True,
            text=True
        )
        
        # 解析netsh输出
        return {"raw_output": output.stdout}
    
    def _get_active_connections(self) -> List[Dict[str, Any]]:
        """获取活动连接"""
        output = subprocess.run(
            ["netstat", "-an"],
            capture_output=True,
            text=True
        )
        
        connections = []
        # 解析netstat输出
        # ... 解析逻辑 ...
        
        return connections
```

---

## 6. 流程编排设计

### 6.1 流程引擎基类
```python
# src/sdwan_desktop/flow/pipelines/base.py

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

@dataclass
class StepDefinition:
    """步骤定义"""
    id: str
    name: str
    description: str
    handler: str                    # 处理函数名
    depends_on: List[str] = field(default_factory=list)
    timeout_seconds: int = 60
    retry_policy: Optional[Dict[str, Any]] = None
    condition: Optional[str] = None  # 执行条件表达式

@dataclass
class FlowDefinition:
    """流程定义"""
    id: str
    name: str
    version: str
    description: str
    steps: List[StepDefinition]
    config: Dict[str, Any] = field(default_factory=dict)

class PipelineEngine(ABC):
    """流水线执行引擎"""
    
    def __init__(self, definition: FlowDefinition):
        self.definition = definition
        self.context: Optional[FlowContext] = None
        self.handlers: Dict[str, Callable] = {}
    
    def register_handler(self, name: str, handler: Callable) -> None:
        """注册步骤处理器"""
        self.handlers[name] = handler
    
    @abstractmethod
    async def execute(self, input_data: Dict[str, Any]) -> FlowContext:
        """执行流程"""
        pass
    
    @abstractmethod
    async def replay(
        self,
        trace_id: str,
        from_step: Optional[str] = None
    ) -> FlowContext:
        """回放流程"""
        pass
```

### 6.2 一键体检Flow定义
```python
# src/sdwan_desktop/flow/definitions/quick_check.py

QUICK_CHECK_FLOW = FlowDefinition(
    id="quick-check-v1",
    name="一键体检",
    version="1.0.0",
    description="Windows客户端基础配置检查与连通性分析",
    steps=[
        StepDefinition(
            id="step-1",
            name="系统信息采集",
            description="采集Windows网络配置",
            handler="windows_system.collect",
            timeout_seconds=30
        ),
        StepDefinition(
            id="step-2",
            name="网关连通性测试",
            description="测试默认网关可达性",
            handler="network.ping_gateway",
            depends_on=["step-1"],
            timeout_seconds=10,
            retry_policy={"max_attempts": 3, "backoff_seconds": 1}
        ),
        StepDefinition(
            id="step-3",
            name="DNS解析测试",
            description="测试DNS服务器解析能力",
            handler="network.dns_test",
            depends_on=["step-1"],
            timeout_seconds=15
        ),
        StepDefinition(
            id="step-4",
            name="互联网连通性测试",
            description="测试公网可达性",
            handler="network.internet_test",
            depends_on=["step-2"],
            timeout_seconds=20
        ),
        StepDefinition(
            id="step-5",
            name="配置异常检测",
            description="检测配置异常项",
            handler="analyzer.config_check",
            depends_on=["step-1", "step-2", "step-3"],
            timeout_seconds=5
        ),
        StepDefinition(
            id="step-6",
            name="诊断结论生成",
            description="综合所有检测结果生成诊断",
            handler="analyzer.generate_conclusion",
            depends_on=["step-5"],
            timeout_seconds=10
        ),
        StepDefinition(
            id="step-7",
            name="报告生成",
            description="生成HTML诊断报告",
            handler="reporter.generate_html",
            depends_on=["step-6"],
            timeout_seconds=15
        )
    ],
    config={
        "parallel_steps": ["step-2", "step-3"],
        "continue_on_error": True,
        "save_snapshots": True
    }
)
```

### 6.3 深度诊断Flow定义
```python
# src/sdwan_desktop/flow/definitions/deep_dive.py

DEEP_DIVE_FLOW = FlowDefinition(
    id="deep-dive-v1",
    name="深度诊断",
    version="1.0.0",
    description="PC+CPE联合诊断，网络拓扑构建与根因分析",
    steps=[
        StepDefinition(
            id="pc-collect",
            name="PC端信息采集",
            handler="windows_system.full_collect",
            timeout_seconds=60
        ),
        StepDefinition(
            id="cpe-connect",
            name="CPE连接建立",
            handler="ssh_adapter.connect",
            timeout_seconds=30,
            retry_policy={"max_attempts": 2, "backoff_seconds": 5}
        ),
        StepDefinition(
            id="cpe-collect",
            name="CPE配置采集",
            handler="ssh_adapter.collect_config",
            depends_on=["cpe-connect"],
            timeout_seconds=120
        ),
        StepDefinition(
            id="config-parse",
            name="配置解析",
            handler="parser.parse_cpe_config",
            depends_on=["cpe-collect"],
            timeout_seconds=30
        ),
        StepDefinition(
            id="topology-build",
            name="拓扑构建",
            handler="topology.build",
            depends_on=["pc-collect", "config-parse"],
            timeout_seconds=10
        ),
        StepDefinition(
            id="targeted-probe",
            name="针对性探测",
            handler="probe.targeted",
            depends_on=["topology-build"],
            timeout_seconds=120
        ),
        StepDefinition(
            id="root-cause",
            name="根因分析",
            handler="analyzer.root_cause",
            depends_on=["targeted-probe", "topology-build"],
            timeout_seconds=30
        ),
        StepDefinition(
            id="report-generate",
            name="报告生成",
            handler="reporter.deep_dive_html",
            depends_on=["root-cause"],
            timeout_seconds=20
        )
    ],
    config={
        "parallel_groups": [
            ["pc-collect", "cpe-connect"]
        ],
        "cpe_required": True,
        "max_diagnosis_depth": 5
    }
)
```

---

## 7. 报告生成系统

### 7.1 HTML报告模板结构

```html
<!-- src/sdwan_desktop/reporting/templates/base.html -->

<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SD-WAN诊断报告 - {{ diagnosis_type }}</title>
    <style>
        /* 报告样式 */
        :root {
            --color-critical: #d32f2f;
            --color-error: #f44336;
            --color-warning: #ff9800;
            --color-info: #2196f3;
            --color-success: #4caf50;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        
        .report-header {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .severity-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 16px;
            font-weight: bold;
            color: white;
        }
        
        .severity-critical { background: var(--color-critical); }
        .severity-error { background: var(--color-error); }
        .severity-warning { background: var(--color-warning); }
        .severity-info { background: var(--color-info); }
        
        .section {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .evidence-item {
            border-left: 3px solid #ddd;
            padding: 10px 15px;
            margin: 10px 0;
            background: #fafafa;
        }
        
        .topology-container {
            text-align: center;
            padding: 20px;
            background: #fafafa;
            border-radius: 4px;
        }
        
        .waterfall-chart {
            width: 100%;
            overflow-x: auto;
        }
        
        .recommendation {
            border-left: 3px solid var(--color-info);
            padding: 15px;
            margin: 15px 0;
            background: #e3f2fd;
        }
        
        .collapsible {
            cursor: pointer;
            user-select: none;
        }
        
        .collapsible-content {
            display: none;
            margin-top: 10px;
        }
        
        .collapsible.active + .collapsible-content {
            display: block;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        th, td {
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        
        th {
            background: #f5f5f5;
        }
    </style>
</head>
<body>
    <div class="report-header">
        <h1>SD-WAN诊断报告</h1>
        <p>
            <strong>报告ID:</strong> {{ report_id }}<br>
            <strong>Trace ID:</strong> {{ trace_id }}<br>
            <strong>生成时间:</strong> {{ timestamp }}<br>
            <strong>诊断类型:</strong> {{ diagnosis_type }}<br>
            <strong>规则版本:</strong> {{ rule_version }}
        </p>
    </div>
    
    <div class="section">
        <h2>执行摘要</h2>
        <div class="severity-badge severity-{{ severity }}">
            {{ severity_text }}
        </div>
        <p>{{ summary }}</p>
        <p><strong>综合置信度:</strong> {{ confidence }}%</p>
    </div>
    
    {% block content %}{% endblock %}
    
    <div class="section">
        <h2>诊断建议</h2>
        {% for rec in recommendations %}
        <div class="recommendation">
            <h3>[优先级 {{ rec.priority }}] {{ rec.action }}</h3>
            <p>{{ rec.expected_outcome }}</p>
            {% if rec.commands %}
            <pre><code>{{ rec.commands | join('\n') }}</code></pre>
            {% endif %}
        </div>
        {% endfor %}
    </div>
    
    <div class="section">
        <h2>证据附录</h2>
        {% for evidence in evidences %}
        <div class="evidence-item">
            <h3 class="collapsible">▶ {{ evidence.step_name }}</h3>
            <div class="collapsible-content">
                <p>{{ evidence.description }}</p>
                <pre><code>{{ evidence.details | tojson(indent=2) }}</code></pre>
            </div>
        </div>
        {% endfor %}
    </div>
    
    <script>
        // 折叠/展开功能
        document.querySelectorAll('.collapsible').forEach(el => {
            el.addEventListener('click', function() {
                this.classList.toggle('active');
                this.textContent = this.classList.contains('active') 
                    ? this.textContent.replace('▶', '▼')
                    : this.textContent.replace('▼', '▶');
            });
        });
    </script>
</body>
</html>
```

### 7.2 报告生成服务
```python
# src/sdwan_desktop/services/reporter/html_builder.py

from jinja2 import Environment, FileSystemLoader
from typing import Dict, Any, Optional
import os

class HtmlReportBuilder:
    """HTML报告生成器"""
    
    def __init__(self, template_dir: str):
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=True
        )
        self.env.filters['tojson'] = lambda x, **kw: json.dumps(x, **kw)
    
    def build_quick_check_report(
        self,
        result: DiagnosisResult,
        output_path: Optional[str] = None
    ) -> str:
        """生成一键体检报告"""
        template = self.env.get_template("quick_check.html")
        
        html_content = template.render(
            report_id=result.id,
            trace_id=result.trace_id,
            timestamp=result.timestamp,
            diagnosis_type="一键体检",
            rule_version=result.rule_version,
            severity=result.severity.value,
            severity_text=self._get_severity_text(result.severity),
            summary=result.summary,
            confidence=result.overall_confidence * 100,
            root_causes=result.root_causes,
            recommendations=result.recommendations,
            evidences=result.evidences,
            # 额外数据
            system_info=self._extract_system_info(result),
            connectivity_status=self._extract_connectivity(result)
        )
        
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
        
        return html_content
    
    def build_deep_dive_report(
        self,
        result: DiagnosisResult,
        topology_svg: Optional[str] = None,
        output_path: Optional[str] = None
    ) -> str:
        """生成深度诊断报告"""
        template = self.env.get_template("deep_dive.html")
        
        html_content = template.render(
            report_id=result.id,
            trace_id=result.trace_id,
            timestamp=result.timestamp,
            diagnosis_type="深度诊断",
            rule_version=result.rule_version,
            severity=result.severity.value,
            severity_text=self._get_severity_text(result.severity),
            summary=result.summary,
            confidence=result.overall_confidence * 100,
            root_causes=result.root_causes,
            recommendations=result.recommendations,
            evidences=result.evidences,
            topology_svg=topology_svg,
            # 配置对比
            config_comparison=self._build_config_comparison(result)
        )
        
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
        
        return html_content
    
    def build_waterfall_report(
        self,
        result: WaterfallResult,
        output_path: Optional[str] = None
    ) -> str:
        """生成Waterfall报告"""
        template = self.env.get_template("waterfall.html")
        
        html_content = template.render(
            report_id=result.id,
            trace_id=result.trace_id,
            timestamp=result.timestamp,
            url=result.url,
            page_load_time=result.page_load_time,
            total_requests=result.total_requests,
            total_size_bytes=result.total_size_bytes,
            resources=result.resources,
            slowest_resources=result.slowest_resources,
            recommendations=result.recommendations,
            screenshot_path=result.screenshot_path
        )
        
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
        
        return html_content
    
    def _get_severity_text(self, severity: Severity) -> str:
        """获取严重程度中文"""
        mapping = {
            Severity.INFO: "信息",
            Severity.WARNING: "警告",
            Severity.ERROR: "错误",
            Severity.CRITICAL: "严重"
        }
        return mapping.get(severity, "未知")
```

---

## 8. 客户端技术方案

### 8.1 GUI框架选型

| 方案 | 优点 | 缺点 | 推荐度 |
| --- | --- | --- | --- |
| PySide6 | 纯Python开发，与后端无缝集成，跨平台 | 打包体积较大(~50MB) | ⭐⭐⭐⭐⭐ |
| WinUI3 + Python | 原生Windows体验，性能好 | 需要C#/C++桥接，开发复杂 | ⭐⭐⭐ |
| Tauri + Python | 体积小，安全 | 前端开发工作量大 | ⭐⭐ |

**推荐方案**: PySide6

### 8.2 GUI架构设计

```python
# src/sdwan_desktop/interface/gui/main_window.py

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QProgressBar, QTabWidget,
    QTableWidget, QTableWidgetItem, QLabel, QLineEdit,
    QComboBox, QFileDialog, QMessageBox
)
from PySide6.QtCore import QThread, Signal, Slot, Qt
from PySide6.QtGui import QFont, QIcon

class DiagnosisWorker(QThread):
    """后台诊断工作线程"""
    
    # 信号定义
    progress_updated = Signal(int, str)          # 进度, 当前步骤
    step_completed = Signal(str, dict)           # 步骤名, 结果
    diagnosis_completed = Signal(object)         # DiagnosisResult
    diagnosis_failed = Signal(str)               # 错误信息
    
    def __init__(self, flow_type: str, params: dict):
        super().__init__()
        self.flow_type = flow_type
        self.params = params
    
    def run(self):
        """执行诊断流程"""
        try:
            # 初始化流程引擎
            if self.flow_type == "quick_check":
                flow = QuickCheckFlow()
            elif self.flow_type == "deep_dive":
                flow = DeepDiveFlow()
            elif self.flow_type == "waterfall":
                flow = WaterfallFlow()
            else:
                raise ValueError(f"未知流程类型: {self.flow_type}")
            
            # 设置进度回调
            flow.set_progress_callback(
                lambda p, s: self.progress_updated.emit(p, s)
            )
            
            # 执行诊断
            result = flow.execute(self.params)
            
            self.diagnosis_completed.emit(result)
            
        except Exception as e:
            self.diagnosis_failed.emit(str(e))


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SD-WAN桌面诊断专家")
        self.setMinimumSize(1000, 700)
        
        self.setup_ui()
        self.worker: Optional[DiagnosisWorker] = None
    
    def setup_ui(self):
        """初始化UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # 标签页
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # 工具标签页
        tools_tab = self.create_tools_tab()
        tabs.addTab(tools_tab, "网络工具")
        
        # 一键体检标签页
        quick_check_tab = self.create_quick_check_tab()
        tabs.addTab(quick_check_tab, "一键体检")
        
        # 深度诊断标签页
        deep_dive_tab = self.create_deep_dive_tab()
        tabs.addTab(deep_dive_tab, "深度诊断")
        
        # 业务监测标签页
        waterfall_tab = self.create_waterfall_tab()
        tabs.addTab(waterfall_tab, "业务监测")
        
        # 状态栏
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("就绪")
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
    
    def create_tools_tab(self) -> QWidget:
        """创建工具标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 工具选择
        tool_layout = QHBoxLayout()
        tool_layout.addWidget(QLabel("选择工具:"))
        
        self.tool_combo = QComboBox()
        self.tool_combo.addItems([
            "Ping", "Traceroute", "TCPing", "DNS查询",
            "MTR", "SSH连接", "Telnet连接"
        ])
        tool_layout.addWidget(self.tool_combo)
        
        tool_layout.addStretch()
        layout.addLayout(tool_layout)
        
        # 参数输入
        params_layout = QHBoxLayout()
        params_layout.addWidget(QLabel("目标:"))
        self.target_input = QLineEdit()
        self.target_input.setPlaceholderText("IP地址或域名")
        params_layout.addWidget(self.target_input)
        
        self.run_tool_btn = QPushButton("执行")
        self.run_tool_btn.clicked.connect(self.run_tool)
        params_layout.addWidget(self.run_tool_btn)
        
        layout.addLayout(params_layout)
        
        # 输出区域
        self.tool_output = QTextEdit()
        self.tool_output.setReadOnly(True)
        self.tool_output.setFont(QFont("Consolas", 10))
        layout.addWidget(self.tool_output)
        
        return widget
    
    def create_quick_check_tab(self) -> QWidget:
        """创建一键体检标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 说明
        info_label = QLabel(
            "一键体检将检查Windows网络配置、"
            "基础连通性和DNS解析状态"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # 开始按钮
        self.quick_check_btn = QPushButton("开始体检")
        self.quick_check_btn.clicked.connect(self.run_quick_check)
        self.quick_check_btn.setMinimumHeight(40)
        layout.addWidget(self.quick_check_btn)
        
        # 进度信息
        self.quick_check_progress = QLabel("等待开始...")
        layout.addWidget(self.quick_check_progress)
        
        # 结果表格
        self.quick_check_table = QTableWidget()
        self.quick_check_table.setColumnCount(3)
        self.quick_check_table.setHorizontalHeaderLabels([
            "检测项", "状态", "详情"
        ])
        self.quick_check_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.quick_check_table)
        
        # 保存报告按钮
        save_layout = QHBoxLayout()
        save_layout.addStretch()
        self.save_quick_report_btn = QPushButton("保存报告")
        self.save_quick_report_btn.setEnabled(False)
        self.save_quick_report_btn.clicked.connect(self.save_quick_report)
        save_layout.addWidget(self.save_quick_report_btn)
        layout.addLayout(save_layout)
        
        return widget
    
    def create_deep_dive_tab(self) -> QWidget:
        """创建深度诊断标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # CPE配置
        cpe_group = QWidget()
        cpe_layout = QVBoxLayout(cpe_group)
        cpe_layout.addWidget(QLabel("CPE设备配置"))
        
        cpe_form = QHBoxLayout()
        cpe_form.addWidget(QLabel("主机:"))
        self.cpe_host_input = QLineEdit()
        self.cpe_host_input.setPlaceholderText("192.168.1.1")
        cpe_form.addWidget(self.cpe_host_input)
        
        cpe_form.addWidget(QLabel("端口:"))
        self.cpe_port_input = QLineEdit("22")
        cpe_form.addWidget(self.cpe_port_input)
        
        cpe_layout.addLayout(cpe_form)
        
        cpe_form2 = QHBoxLayout()
        cpe_form2.addWidget(QLabel("用户名:"))
        self.cpe_user_input = QLineEdit("admin")
        cpe_form2.addWidget(self.cpe_user_input)
        
        cpe_form2.addWidget(QLabel("密码:"))
        self.cpe_pass_input = QLineEdit()
        self.cpe_pass_input.setEchoMode(QLineEdit.Password)
        cpe_form2.addWidget(self.cpe_pass_input)
        
        cpe_layout.addLayout(cpe_form2)
        
        layout.addWidget(cpe_group)
        
        # 开始按钮
        self.deep_dive_btn = QPushButton("开始深度诊断")
        self.deep_dive_btn.clicked.connect(self.run_deep_dive)
        self.deep_dive_btn.setMinimumHeight(40)
        layout.addWidget(self.deep_dive_btn)
        
        # 进度信息
        self.deep_dive_progress = QLabel("等待开始...")
        layout.addWidget(self.deep_dive_progress)
        
        # 输出区域
        self.deep_dive_output = QTextEdit()
        self.deep_dive_output.setReadOnly(True)
        layout.addWidget(self.deep_dive_output)
        
        # 保存报告按钮
        save_layout = QHBoxLayout()
        save_layout.addStretch()
        self.save_deep_report_btn = QPushButton("保存报告")
        self.save_deep_report_btn.setEnabled(False)
        self.save_deep_report_btn.clicked.connect(self.save_deep_report)
        save_layout.addWidget(self.save_deep_report_btn)
        layout.addLayout(save_layout)
        
        return widget
    
    def create_waterfall_tab(self) -> QWidget:
        """创建业务监测标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # URL输入
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("URL:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com")
        url_layout.addWidget(self.url_input)
        
        self.waterfall_btn = QPushButton("开始监测")
        self.waterfall_btn.clicked.connect(self.run_waterfall)
        url_layout.addWidget(self.waterfall_btn)
        
        layout.addLayout(url_layout)
        
        # 进度信息
        self.waterfall_progress = QLabel("等待开始...")
        layout.addWidget(self.waterfall_progress)
        
        # 输出区域
        self.waterfall_output = QTextEdit()
        self.waterfall_output.setReadOnly(True)
        layout.addWidget(self.waterfall_output)
        
        # 保存报告按钮
        save_layout = QHBoxLayout()
        save_layout.addStretch()
        self.save_waterfall_report_btn = QPushButton("保存报告")
        self.save_waterfall_report_btn.setEnabled(False)
        save_layout.addWidget(self.save_waterfall_report_btn)
        layout.addLayout(save_layout)
        
        return widget
    
    @Slot()
    def run_quick_check(self):
        """执行一键体检"""
        self.quick_check_btn.setEnabled(False)
        self.quick_check_progress.setText("正在采集系统信息...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        self.worker = DiagnosisWorker("quick_check", {})
        self.worker.progress_updated.connect(self.on_quick_check_progress)
        self.worker.diagnosis_completed.connect(self.on_quick_check_completed)
        self.worker.diagnosis_failed.connect(self.on_quick_check_failed)
        self.worker.start()
    
    @Slot(int, str)
    def on_quick_check_progress(self, value: int, step: str):
        """更新进度"""
        self.progress_bar.setValue(value)
        self.quick_check_progress.setText(f"[{value}%] {step}")
    
    @Slot(object)
    def on_quick_check_completed(self, result: DiagnosisResult):
        """诊断完成"""
        self.quick_check_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.quick_check_progress.setText("诊断完成")
        
        # 更新表格
        self.update_quick_check_table(result)
        
        # 保存结果
        self.last_quick_check_result = result
        self.save_quick_report_btn.setEnabled(True)
        
        QMessageBox.information(
            self, "完成",
            f"一键体检完成\n"
            f"严重程度: {result.severity.value}\n"
            f"置信度: {result.overall_confidence:.1%}"
        )
    
    @Slot(str)
    def on_quick_check_failed(self, error: str):
        """诊断失败"""
        self.quick_check_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.quick_check_progress.setText(f"失败: {error}")
        
        QMessageBox.critical(self, "错误", f"诊断失败: {error}")
```

### 8.3 打包配置
```python
# pyproject.toml

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "sdwan-desktop"
version = "0.1.0-alpha"
description = "SD-WAN桌面诊断专家"
readme = "README.md"
requires-python = ">=3.10"
authors = [
    {name = "SD-WAN Team"}
]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: System Administrators",
    "License :: OSI Approved :: MIT License",
    "Operating System :: Microsoft :: Windows",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]

dependencies = [
    "pydantic>=2.0.0",
    "pyside6>=6.5.0",
    "paramiko>=3.0.0",
    "asyncssh>=2.13.0",
    "dnspython>=2.4.0",
    "pythonping>=1.1.0",
    "playwright>=1.40.0",
    "jinja2>=3.1.0",
    "pyyaml>=6.0",
    "wmi>=1.5.0",
    "pywin32>=306",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    "ruff>=0.1.0",
    "mypy>=1.7.0",
    "pre-commit>=3.5.0",
]

[project.scripts]
agentctl = "sdwan_desktop.interface.cli.main:main"
sdwan-gui = "sdwan_desktop.interface.gui.main_window:main"

[tool.hatch.build.targets.wheel]
packages = ["src/sdwan_desktop"]

[tool.ruff]
line-length = 88
target-version = "py310"
select = ["E", "F", "I", "N", "W", "UP", "B", "C4"]

[tool.mypy]
python_version = "3.10"
strict = true
warn_return_any = true
warn_unused_configs = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-v --cov=src/sdwan_desktop --cov-report=html"
```

---

## 9. 安全与合规

### 9.1 凭据管理

```python
# src/sdwan_desktop/config/secure_storage.py

import json
import os
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
import base64

class SecureStorage:
    """安全存储 - 用于保存CPE凭据"""
    
    def __init__(self, app_data_dir: str):
        self.storage_path = os.path.join(app_data_dir, "secure_storage.enc")
        self.salt_path = os.path.join(app_data_dir, ".salt")
        self._fernet: Optional[Fernet] = None
    
    def initialize(self, master_password: str) -> None:
        """初始化加密器"""
        salt = self._get_or_create_salt()
        
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_password.encode()))
        self._fernet = Fernet(key)
    
    def save_credential(self, host: str, username: str, password: str) -> None:
        """保存凭据"""
        if not self._fernet:
            raise ValueError("Storage not initialized")
        
        data = self._load_data()
        data[host] = {
            "username": username,
            "password": self._fernet.encrypt(password.encode()).decode()
        }
        self._save_data(data)
    
    def get_credential(self, host: str) -> Optional[tuple]:
        """获取凭据"""
        if not self._fernet:
            raise ValueError("Storage not initialized")
        
        data = self._load_data()
        if host not in data:
            return None
        
        cred = data[host]
        password = self._fernet.decrypt(cred["password"].encode()).decode()
        return cred["username"], password
    
    def _get_or_create_salt(self) -> bytes:
        """获取或创建盐值"""
        if os.path.exists(self.salt_path):
            with open(self.salt_path, "rb") as f:
                return f.read()
        else:
            salt = os.urandom(16)
            with open(self.salt_path, "wb") as f:
                f.write(salt)
            return salt
    
    def _load_data(self) -> Dict[str, Any]:
        """加载数据"""
        if os.path.exists(self.storage_path):
            with open(self.storage_path, "r") as f:
                return json.load(f)
        return {}
    
    def _save_data(self, data: Dict[str, Any]) -> None:
        """保存数据"""
        with open(self.storage_path, "w") as f:
            json.dump(data, f)
```

### 9.2 日志脱敏

```python
# src/sdwan_desktop/observability/logger.py

import logging
import json
import re
from typing import Any, Dict, List

class SensitiveDataFilter(logging.Filter):
    """敏感数据过滤器"""
    
    SENSITIVE_KEYS = {
        "password", "passwd", "pwd", "secret", "token",
        "api_key", "private_key", "credential", "authorization"
    }
    
    SENSITIVE_PATTERNS = [
        (re.compile(r'password["\s:=]+([^\s"\']+)', re.I), r'password=***'),
        (re.compile(r'passwd["\s:=]+([^\s"\']+)', re.I), r'passwd=***'),
        (re.compile(r'Authorization["\s:=]+([^\s"\']+)', re.I), r'Authorization=***'),
        # IP地址部分脱敏 (保留前三段)
        (re.compile(r'(\d+\.\d+\.\d+)\.\d+'), r'\1.*'),
    ]
    
    def filter(self, record: logging.LogRecord) -> bool:
        """过滤敏感信息"""
        if isinstance(record.msg, str):
            record.msg = self._sanitize_string(record.msg)
        
        if record.args:
            record.args = tuple(
                self._sanitize_string(str(arg)) if isinstance(arg, str) else arg
                for arg in record.args
            )
        
        return True
    
    def _sanitize_string(self, text: str) -> str:
        """清理敏感字符串"""
        for pattern, replacement in self.SENSITIVE_PATTERNS:
            text = pattern.sub(replacement, text)
        return text


def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> None:
    """配置日志系统"""
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "format": "%(timestamp)s %(level)s %(name)s %(trace_id)s %(message)s"
            },
            "console": {
                "format": "[%(asctime)s] [%(levelname)s] [%(trace_id)s] %(message)s"
            }
        },
        "filters": {
            "sensitive": {
                "()": "sdwan_desktop.observability.logger.SensitiveDataFilter"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "console",
                "filters": ["sensitive"]
            }
        },
        "root": {
            "level": level,
            "handlers": ["console"]
        }
    }
    
    if log_file:
        config["handlers"]["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": log_file,
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "formatter": "json",
            "filters": ["sensitive"]
        }
        config["root"]["handlers"].append("file")
    
    logging.config.dictConfig(config)
```

---

## 10. 开发阶段与里程碑
### 10.1 版本规划

| 版本 | 阶段 | 功能范围 | 预计时间 |
| --- | --- | --- | --- |
| 0.1.0-alpha | 概念验证 | 基础工具集(Ping/Trace/DNS) | 核心架构+Trace ID | 2周 | 
| 0.2.0-alpha | 基础功能 | 一键体检完整实现 |  +数据契约+日志 | 3周 | 
| 0.3.0-alpha | 核心功能 | 深度诊断(单厂商支持) | +工具注册+流程引擎 | 4周 | 
| 0.4.0-alpha | 监测功能 | Waterfall实现 | +报告模板 | 2周 | 
| 1.0.0-rc.1 | 候选版本 | 完整功能+GUI | 契约测试+文档 | 3周 | 
| 1.0.0 | 正式版本 | 稳定版本 | 全部强制规范 | 2周 | 

### 10.2 里程碑检查清单

**Milestone 1 (v0.1.0-alpha)**

1. 项目骨架搭建
2. PingTool 实现
3. TraceRouteTool 实现
4. DnsTool 实现
5. 基础CLI入口
6. Trace ID贯穿验证

**Milestone 2 (v0.2.0-alpha)**

1. WindowsSystemTool 完整实现
2. 配置异常检测规则
3. 一键体检Flow定义
4. 基础HTML报告模板
5. 单元测试覆盖率 >60%

**Milestone 3 (v0.3.0-alpha)**

1. SSH适配器实现
2. CPE配置解析器(单厂商)
3. 拓扑构建服务
4. 根因分析引擎
5. 深度诊断Flow定义
6. 专业HTML报告模板

**Milestone 4 (v0.4.0-alpha)**

1. Playwright集成
2. HAR解析服务
3. Waterfall时序图
4. 性能优化建议

**Milestone 5 (v1.0.0-rc.1)**

1. PySide6 GUI完整实现
2. 异步任务处理
3. 安全存储实现
4. 完整文档
5. 契约测试通过
6. 覆盖率达标(PATCH-001)

**Milestone 6 (v1.0.0)**

1. 生产环境测试
2. 性能优化
3. 错误处理完善
4. 发布包构建

---

## 11. 附录

### 附录A: 错误码定义
| 错误码 | 类型 | 描述 |
| --- | --- | --- |
| VAL_001 | ValidationError | 输入参数格式错误 |
| VAL_002 | ValidationError | 必填参数缺失 |
| TOOL_001 | ToolError | 工具执行超时 |
| TOOL_002 | ToolError | 工具执行失败 |
| TOOL_003 | ToolError | 工具未注册 |
| TOOL_004 | ToolError | SSH连接失败 |
| TOOL_005 | ToolError | SSH认证失败 |
| FLOW_001 | FlowError | 流程步骤执行失败 |
| FLOW_002 | FlowError | 流程依赖不满足 |
| FLOW_003 | FlowError | 流程状态迁移非法 |
| TIME_001 | TimeoutError | 流程整体超时 |
| SYS_001 | SystemError | 系统资源不足 |
| SYS_002 | SystemError | 权限不足 |

### 附录B: 诊断规则ID定义
| 规则ID | 分类 | 描述 | 置信度 |
| --- | --- | --- | --- |
| GW-001 | 网关 | 默认网关不可达 | 0.95 |
| GW-002 | 网关 | 网关延迟过高 | 0.85 |
| DNS-001 | DNS | DNS服务器无响应 | 0.95 |
| DNS-002 | DNS | DNS解析结果异常 | 0.80 |
| DNS-003 | DNS | DNS分流配置异常 | 0.75 |
| ROUTE-001 | 路由 | 默认路由缺失 | 0.95 |
| ROUTE-002 | 路由 | 路由表冲突 | 0.85 |
| CPE-001 | CPE | CPE不可达 | 0.95 |
| CPE-002 | CPE | SD-WAN隧道Down | 0.95 |
| CPE-003 | CPE | 策略路由未生效 | 0.85 |
| CPE-004 | CPE | NAT规则不匹配 | 0.80 |
| NAT-001 | NAT | 多级NAT检测 | 0.70 |
| PERF-001 | 性能 | 链路丢包过高 | 0.90 |
| PERF-002 | 性能 | 链路延迟过高 | 0.85 |
| PERF-003 | 性能 | 应用响应慢 | 0.75 |

### 附录C: 术语表
| 术语 | 全称 | 说明 |
| --- | --- | --- |
| SD-WAN | Software-Defined Wide Area Network | 软件定义广域网 |
| CPE | Customer Premises Equipment | 客户前置设备 |
| Overlay | - | 叠加网络/逻辑隧道 |
| Underlay | - | 底层物理网络 |
| NAT | Network Address | Translation	网络地址转换 |
| HAR| HTTP Archive| HTTP归档格式|
| RTT| Round-Trip Time| 往返时间|
| TTFB| Time To First Byte| 首字节时间|
| MTR| My Traceroute| 综合路由追踪工具|
