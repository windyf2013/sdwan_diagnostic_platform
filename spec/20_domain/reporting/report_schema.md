# 报告输出Schema规范

## 概述
本规范定义SD-WAN诊断平台的报告输出格式，包括诊断报告、性能报告、配置报告和根因分析报告的统一数据模型。

## 报告类型

### 报告分类
| 报告类型 | 描述 | 输出格式 |
|----------|------|----------|
| **诊断报告** | 网络问题诊断结果 | HTML, JSON, PDF |
| **性能报告** | 网络性能分析结果 | HTML, JSON, CSV |
| **配置报告** | 设备配置分析结果 | HTML, JSON, YAML |
| **根因分析报告** | 问题根因分析结果 | HTML, JSON |
| **趋势报告** | 历史趋势分析结果 | HTML, JSON, PNG |

### 报告级别
| 报告级别 | 描述 | 目标受众 |
|----------|------|----------|
| **摘要报告** | 高层摘要，1-2页 | 管理层 |
| **详细报告** | 完整分析，包含证据 | 技术专家 |
| **技术报告** | 原始数据和技术细节 | 开发/运维 |
| **审计报告** | 合规性和审计记录 | 审计人员 |

## 基础报告模型

### 报告元数据
```python
@dataclass
class ReportMetadata:
    """报告元数据"""
    # 标识信息
    report_id: str                      # 报告唯一ID
    report_type: str                    # 报告类型
    report_version: str                 # 报告schema版本
    
    # 时间信息
    created_at: datetime                # 创建时间
    start_time: Optional[datetime] = None  # 分析开始时间
    end_time: Optional[datetime] = None    # 分析结束时间
    
    # 来源信息
    source_system: str                  # 生成系统
    source_version: str                 # 系统版本
    trace_id: str                       # 追踪ID
    
    # 目标信息
    target_host: Optional[str] = None   # 目标主机
    target_ip: Optional[str] = None     # 目标IP
    target_domain: Optional[str] = None # 目标域名
    
    # 配置信息
    config_version: str                 # 配置版本
    rule_version: str                   # 规则版本
    probe_version: str                  # 探针版本
    
    # 统计信息
    analysis_duration_ms: Optional[float] = None  # 分析耗时
    data_points: Optional[int] = None   # 数据点数
    probes_executed: Optional[int] = None  # 执行的探针数
```

### 报告摘要
```python
@dataclass
class ReportSummary:
    """报告摘要"""
    # 总体状态
    overall_status: str                 # 总体状态
    overall_severity: str               # 总体严重程度
    overall_confidence: float           # 总体置信度（0-1）
    
    # 关键指标
    key_metrics: Dict[str, Any] = field(default_factory=dict)  # 关键指标
    
    # 问题摘要
    total_issues: int = 0               # 总问题数
    critical_issues: int = 0            # 严重问题数
    warning_issues: int = 0             # 警告问题数
    info_issues: int = 0                # 信息问题数
    
    # 建议摘要
    total_recommendations: int = 0      # 总建议数
    high_priority_recs: int = 0         # 高优先级建议数
    medium_priority_recs: int = 0       # 中优先级建议数
    low_priority_recs: int = 0          # 低优先级建议数
    
    # 执行摘要
    execution_summary: str = ""         # 执行摘要文本
    conclusion: str = ""                # 结论文本
```

### 报告内容
```python
@dataclass
class ReportContent:
    """报告内容"""
    # 章节列表
    sections: List[Dict[str, Any]] = field(default_factory=list)  # 报告章节
    
    # 图表数据
    charts: List[Dict[str, Any]] = field(default_factory=list)    # 图表数据
    
    # 表格数据
    tables: List[Dict[str, Any]] = field(default_factory=list)    # 表格数据
    
    # 附件
    attachments: List[Dict[str, Any]] = field(default_factory=list)  # 附件信息
    
    # 原始数据引用
    data_references: List[Dict[str, Any]] = field(default_factory=list)  # 数据引用
```

## 诊断报告Schema

### 诊断问题
```python
@dataclass
class DiagnosticIssue:
    """诊断问题"""
    # 标识信息
    issue_id: str                      # 问题ID
    issue_type: str                    # 问题类型
    
    # 问题描述
    title: str                         # 问题标题
    description: str                   # 问题描述
    impact: str                        # 影响描述
    
    # 严重程度
    severity: str                      # 严重程度
    confidence: float                  # 置信度（0-1）
    priority: int                      # 优先级（1-5）
    
    # 位置信息
    location: Optional[str] = None     # 问题位置
    component: Optional[str] = None    # 组件名称
    interface: Optional[str] = None    # 接口名称
    
    # 时间信息
    first_seen: Optional[datetime] = None  # 首次发现时间
    last_seen: Optional[datetime] = None   # 最后发现时间
    duration_ms: Optional[float] = None    # 持续时间
    
    # 证据
    evidence: List[Dict[str, Any]] = field(default_factory=list)  # 证据列表
    
    # 相关指标
    metrics: Dict[str, Any] = field(default_factory=dict)  # 相关指标
    
    # 状态
    status: str = "active"             # 问题状态
    acknowledged: bool = False         # 是否已确认
    resolved: bool = False             # 是否已解决
```

### 诊断建议
```python
@dataclass
class DiagnosticRecommendation:
    """诊断建议"""
    # 标识信息
    recommendation_id: str             # 建议ID
    issue_id: str                      # 关联的问题ID
    
    # 建议内容
    title: str                         # 建议标题
    description: str                   # 建议描述
    expected_outcome: str              # 预期结果
    
    # 优先级
    priority: int                      # 优先级（1-5）
    effort_level: str                  # 实施难度
    risk_level: str                    # 风险等级
    
    # 实施信息
    implementation_steps: List[str] = field(default_factory=list)  # 实施步骤
    commands: List[str] = field(default_factory=list)              # 命令示例
    configuration_changes: List[Dict[str, Any]] = field(default_factory=list)  # 配置变更
    
    # 验证信息
    verification_steps: List[str] = field(default_factory=list)    # 验证步骤
    success_criteria: List[str] = field(default_factory=list)      # 成功标准
    
    # 依赖信息
    dependencies: List[str] = field(default_factory=list)          # 依赖项
    prerequisites: List[str] = field(default_factory=list)         # 前提条件
    
    # 状态
    status: str = "pending"           # 建议状态
    implemented: bool = False         # 是否已实施
    verified: bool = False            # 是否已验证
```

### 诊断证据
```python
@dataclass
class DiagnosticEvidence:
    """诊断证据"""
    # 标识信息
    evidence_id: str                   # 证据ID
    issue_id: str                      # 关联的问题ID
    
    # 证据内容
    evidence_type: str                 # 证据类型
    description: str                   # 证据描述
    content: Any                       # 证据内容
    
    # 来源信息
    source: str                        # 证据来源
    source_type: str                   # 来源类型
    collected_at: datetime             # 收集时间
    
    # 可信度
    reliability: float                 # 可信度（0-1）
    relevance: float                   # 相关性（0-1）
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据
    
    # 引用
    references: List[Dict[str, Any]] = field(default_factory=list)  # 引用信息
```

### 完整诊断报告
```python
@dataclass
class DiagnosticReport:
    """完整诊断报告"""
    # 元数据
    metadata: ReportMetadata           # 报告元数据
    summary: ReportSummary             # 报告摘要
    
    # 诊断内容
    issues: List[DiagnosticIssue] = field(default_factory=list)      # 问题列表
    recommendations: List[DiagnosticRecommendation] = field(default_factory=list)  # 建议列表
    evidence: List[DiagnosticEvidence] = field(default_factory=list)  # 证据列表
    
    # 分析结果
    root_causes: List[Dict[str, Any]] = field(default_factory=list)  # 根因分析
    impact_analysis: Dict[str, Any] = field(default_factory=dict)    # 影响分析
    trend_analysis: Dict[str, Any] = field(default_factory=dict)     # 趋势分析
    
    # 内容
    content: ReportContent             # 报告内容
    
    # 状态
    status: str = "completed"          # 报告状态
    reviewed: bool = False             # 是否已评审
    approved: bool = False             # 是否已批准
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "metadata": dataclasses.asdict(self.metadata),
            "summary": dataclasses.asdict(self.summary),
            "issues": [dataclasses.asdict(issue) for issue in self.issues],
            "recommendations": [dataclasses.asdict(rec) for rec in self.recommendations],
            "evidence": [dataclasses.asdict(ev) for ev in self.evidence],
            "root_causes": self.root_causes,
            "impact_analysis": self.impact_analysis,
            "trend_analysis": self.trend_analysis,
            "content": dataclasses.asdict(self.content),
            "status": self.status,
            "reviewed": self.reviewed,
            "approved": self.approved
        }
```

## 性能报告Schema

### 性能指标
```python
@dataclass
class PerformanceMetric:
    """性能指标"""
    # 标识信息
    metric_id: str                     # 指标ID
    metric_name: str                   # 指标名称
    metric_type: str                   # 指标类型
    
    # 数值
    value: float                       # 当前值
    unit: str                          # 单位
    scale: Optional[str] = None        # 缩放比例
    
    # 阈值
    min_value: Optional[float] = None  # 最小值
    max_value: Optional[float] = None  # 最大值
    warning_threshold: Optional[float] = None  # 警告阈值
    critical_threshold: Optional[float] = None  # 严重阈值
    
    # 统计信息
    avg_value: Optional[float] = None  # 平均值
    p95_value: Optional[float] = None  # P95值
    p99_value: Optional[float] = None  # P99值
    std_dev: Optional[float] = None    # 标准差
    
    # 趋势
    trend: Optional[str] = None        # 趋势方向
    trend_value: Optional[float] = None  # 趋势值
    
    # 状态
    status: str                        # 状态
    severity: str                      # 严重程度
```

### 性能测试结果
```python
@dataclass
class PerformanceTestResult:
    """性能测试结果"""
    # 标识信息
    test_id: str                       # 测试ID
    test_name: str                     # 测试名称
    test_type: str                     # 测试类型
    
    # 配置
    target: str                        # 测试目标
    protocol: str                      # 测试协议
    duration_ms: float                 # 测试持续时间
    
    # 结果
    success: bool                      # 是否成功
    error_message: Optional[str] = None  # 错误消息
    
    # 指标
    metrics: List[PerformanceMetric] = field(default_factory=list)  # 性能指标
    
    # 时间序列数据
    time_series: Optional[Dict[str, List[Any]]] = None  # 时间序列数据
    
    # 统计信息
    statistics: Dict[str, Any] = field(default_factory=dict)  # 统计信息
    
    # 比较基准
    baseline: Optional[Dict[str, Any]] = None  # 基准数据
    comparison: Optional[Dict[str, Any]] = None  # 比较结果
```

### 完整性能报告
```python
@dataclass
class PerformanceReport:
    """完整性能报告"""
    # 元数据
    metadata: ReportMetadata           # 报告元数据
    summary: ReportSummary             # 报告摘要
    
    # 性能测试
    test_results: List[PerformanceTestResult] = field(default_factory=list)  # 测试结果
    
    # 性能分析
    performance_analysis: Dict[str, Any] = field(default_factory=dict)  # 性能分析
    bottleneck_analysis: Dict[str, Any] = field(default_factory=dict)   # 瓶颈分析
    capacity_analysis: Dict[str, Any] = field(default_factory=dict)     # 容量分析
    
    # 建议
    optimization_recommendations: List[Dict[str, Any]] = field(default_factory=list)  # 优化建议
    
    # 内容
    content: ReportContent             # 报告内容
    
    # 状态
    status: str = "completed"          # 报告状态
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "metadata": dataclasses.asdict(self.metadata),
            "summary": dataclasses.asdict(self.summary),
            "test_results": [dataclasses.asdict(result) for result in self.test_results],
            "performance_analysis": self.performance_analysis,
            "bottleneck_analysis": self.bottleneck_analysis,
            "capacity_analysis": self.capacity_analysis,
            "optimization_recommendations": self.optimization_recommendations,
            "content": dataclasses.asdict(self.content),
            "status": self.status
        }
```

## 配置报告Schema

### 配置项
```python
@dataclass
class ConfigurationItem:
    """配置项"""
    # 标识信息
    item_id: str                       # 配置项ID
    item_type: str                     # 配置项类型
    
    # 配置信息
    name: str                          # 配置项名称
    value: Any                         # 配置值
    default_value: Optional[Any] = None  # 默认值
    
    # 位置信息
    path: Optional[str] = None         # 配置路径
    file: Optional[str] = None         # 配置文件
    line_number: Optional[int] = None  # 行号
    
    # 状态
    status: str                        # 状态
    validation_status: str             # 验证状态
    compliance_status: str             # 合规状态
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据
    
    # 依赖
    dependencies: List[str] = field(default_factory=list)   # 依赖项
    conflicts: List[str] = field(default_factory=list)      # 冲突项
```

### 配置差异
```python
@dataclass
class ConfigurationDiff:
    """配置差异"""
    # 标识信息
    diff_id: str                       # 差异ID
    item_id: str                       # 配置项ID
    
    # 差异信息
    diff_type: str                     # 差异类型
    path: str                          # 配置路径
    
    # 原始值
    old_value: Optional[Any] = None    # 原始值
    old_source: Optional[str] = None   # 原始来源
    
    # 新值
    new_value: Optional[Any] = None    # 新值
    new_source: Optional[str] = None   # 新来源
    
    # 差异详情
    diff_details: Optional[str] = None  # 差异详情
    
    # 影响
    impact: Optional[str] = None       # 影响描述
    severity: str = "info"             # 严重程度
    
    # 状态
    status: str = "detected"           # 状态
    reviewed: bool = False             # 是否已评审
    approved: bool = False             # 是否已批准
```

### 完整配置报告
```python
@dataclass
class ConfigurationReport:
    """完整配置报告"""
    # 元数据
    metadata: ReportMetadata           # 报告元数据
    summary: ReportSummary             # 报告摘要
    
    # 配置信息
    configuration: List[ConfigurationItem] = field(default_factory=list)  # 配置项
    configuration_diffs: List[ConfigurationDiff] = field(default_factory=list)  # 配置差异
    
    # 分析结果
    compliance_analysis: Dict[str, Any] = field(default_factory=dict)  # 合规分析
    security_analysis: Dict[str, Any] = field(default_factory=dict)    # 安全分析
    best_practices_analysis: Dict[str, Any] = field(default_factory=dict)  # 最佳实践分析
    
    # 建议
    configuration_recommendations: List[Dict[str, Any