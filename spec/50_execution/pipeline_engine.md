# 流程执行引擎规范

## 概述
本规范定义SD-WAN诊断平台的流程执行引擎，包括流水线、DAG、状态机等执行模型，以及任务调度、状态管理、错误处理和回放机制。

## 执行模型

### 执行模型分类
| 执行模型 | 描述 | 适用场景 |
|----------|------|----------|
| **流水线模型** | 线性步骤序列，前一步输出作为后一步输入 | 简单诊断流程 |
| **DAG模型** | 有向无环图，支持并行执行和条件分支 | 复杂诊断流程 |
| **状态机模型** | 基于状态转移的有限状态机 | 交互式诊断流程 |
| **工作流模型** | 组合多种执行模型 | 混合诊断流程 |

### 执行引擎架构
```python
@dataclass
class ExecutionEngine:
    """执行引擎基类"""
    # 引擎配置
    engine_id: str                      # 引擎ID
    engine_type: str                    # 引擎类型
    engine_version: str                 # 引擎版本
    
    # 执行状态
    status: str                         # 引擎状态
    current_step: Optional[str] = None  # 当前步骤
    progress: float = 0.0               # 执行进度（0-1）
    
    # 统计信息
    total_steps: int = 0                # 总步骤数
    completed_steps: int = 0            # 已完成步骤数
    failed_steps: int = 0               # 失败步骤数
    
    # 性能指标
    start_time: Optional[datetime] = None  # 开始时间
    end_time: Optional[datetime] = None    # 结束时间
    execution_time_ms: Optional[float] = None  # 执行时间
    
    # 资源管理
    resource_usage: Dict[str, Any] = field(default_factory=dict)  # 资源使用情况
    concurrency_limit: int = 5          # 并发限制
    
    # 错误处理
    error_policy: str = "stop_on_error"  # 错误处理策略
    max_retries: int = 3                # 最大重试次数
    retry_delay_ms: int = 1000          # 重试延迟
    
    # 可观测性
    trace_id: str                       # 追踪ID
    log_level: str = "INFO"             # 日志级别
    enable_metrics: bool = True         # 是否启用指标
```

## 流水线模型

### 流水线定义
```python
@dataclass
class PipelineDefinition:
    """流水线定义"""
    # 标识信息
    pipeline_id: str                    # 流水线ID
    pipeline_name: str                  # 流水线名称
    pipeline_version: str               # 流水线版本
    
    # 步骤定义
    steps: List["PipelineStep"]         # 步骤列表
    step_order: List[str]               # 步骤执行顺序
    
    # 配置
    config: Dict[str, Any] = field(default_factory=dict)  # 配置参数
    context_schema: Dict[str, Any] = field(default_factory=dict)  # 上下文schema
    
    # 执行策略
    execution_strategy: str = "sequential"  # 执行策略
    error_handling_strategy: str = "stop_on_error"  # 错误处理策略
    timeout_ms: Optional[int] = None    # 超时时间
    
    # 验证规则
    validation_rules: List[Dict[str, Any]] = field(default_factory=list)  # 验证规则
    preconditions: List[Dict[str, Any]] = field(default_factory=list)     # 前置条件
    postconditions: List[Dict[str, Any]] = field(default_factory=list)    # 后置条件
```

### 流水线步骤
```python
@dataclass
class PipelineStep:
    """流水线步骤"""
    # 标识信息
    step_id: str                        # 步骤ID
    step_name: str                      # 步骤名称
    step_type: str                      # 步骤类型
    
    # 执行信息
    handler: str                        # 处理函数
    input_schema: Dict[str, Any]        # 输入schema
    output_schema: Dict[str, Any]       # 输出schema
    
    # 配置
    config: Dict[str, Any] = field(default_factory=dict)  # 步骤配置
    dependencies: List[str] = field(default_factory=list)  # 依赖步骤
    
    # 执行策略
    timeout_ms: int = 30000             # 超时时间（毫秒）
    retry_policy: Dict[str, Any] = field(default_factory=dict)  # 重试策略
    error_handler: Optional[str] = None  # 错误处理函数
    
    # 资源管理
    resource_requirements: Dict[str, Any] = field(default_factory=dict)  # 资源需求
    concurrency_limit: Optional[int] = None  # 并发限制
    
    # 验证
    validation_rules: List[Dict[str, Any]] = field(default_factory=list)  # 验证规则
    preconditions: List[Dict[str, Any]] = field(default_factory=list)     # 前置条件
    postconditions: List[Dict[str, Any]] = field(default_factory=list)    # 后置条件
    
    # 可观测性
    enable_logging: bool = True         # 是否启用日志
    enable_metrics: bool = True         # 是否启用指标
    enable_tracing: bool = True         # 是否启用追踪
```

### 流水线执行器
```python
@dataclass
class PipelineExecutor:
    """流水线执行器"""
    # 执行器配置
    executor_id: str                    # 执行器ID
    executor_type: str = "pipeline"     # 执行器类型
    
    # 执行状态
    pipeline: Optional[PipelineDefinition] = None  # 当前流水线
    context: Dict[str, Any] = field(default_factory=dict)  # 执行上下文
    step_results: Dict[str, Any] = field(default_factory=dict)  # 步骤结果
    
    # 执行控制
    current_step_index: int = 0         # 当前步骤索引
    execution_mode: str = "normal"      # 执行模式
    pause_on_error: bool = True         # 错误时暂停
    
    # 性能指标
    metrics: Dict[str, Any] = field(default_factory=dict)  # 性能指标
    statistics: Dict[str, Any] = field(default_factory=dict)  # 统计信息
    
    # 错误处理
    error_history: List[Dict[str, Any]] = field(default_factory=list)  # 错误历史
    recovery_points: List[Dict[str, Any]] = field(default_factory=list)  # 恢复点
    
    async def execute(self) -> Dict[str, Any]:
        """执行流水线"""
        # 验证流水线
        self._validate_pipeline()
        
        # 初始化执行上下文
        self._initialize_context()
        
        # 按顺序执行步骤
        for step_id in self.pipeline.step_order:
            step = self._get_step(step_id)
            
            # 检查前置条件
            if not self._check_preconditions(step):
                raise PipelineError(f"Preconditions not met for step {step_id}")
            
            # 执行步骤
            step_result = await self._execute_step(step)
            
            # 检查后置条件
            if not self._check_postconditions(step, step_result):
                raise PipelineError(f"Postconditions not met for step {step_id}")
            
            # 保存结果
            self.step_results[step_id] = step_result
            
            # 更新上下文
            self._update_context(step, step_result)
            
            # 更新进度
            self._update_progress()
        
        # 构建最终结果
        return self._build_final_result()
    
    async def _execute_step(self, step: PipelineStep) -> Dict[str, Any]:
        """执行单个步骤"""
        start_time = datetime.now()
        
        try:
            # 准备输入数据
            input_data = self._prepare_input(step)
            
            # 执行处理函数
            result = await self._call_handler(step, input_data)
            
            # 验证输出
            self._validate_output(step, result)
            
            # 记录执行信息
            execution_info = {
                "step_id": step.step_id,
                "step_name": step.step_name,
                "start_time": start_time,
                "end_time": datetime.now(),
                "success": True,
                "result": result
            }
            
            return execution_info
            
        except Exception as e:
            # 错误处理
            error_info = {
                "step_id": step.step_id,
                "step_name": step.step_name,
                "start_time": start_time,
                "end_time": datetime.now(),
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
            
            # 根据错误策略处理
            if self.pipeline.error_handling_strategy == "stop_on_error":
                raise
            elif self.pipeline.error_handling_strategy == "continue_on_error":
                return error_info
            else:
                # 调用自定义错误处理
                if step.error_handler:
                    return await self._call_error_handler(step, e)
                else:
                    raise
```

## DAG模型

### DAG定义
```python
@dataclass
class DAGDefinition:
    """DAG定义"""
    # 标识信息
    dag_id: str                         # DAG ID
    dag_name: str                       # DAG名称
    dag_version: str                    # DAG版本
    
    # 节点定义
    nodes: List["DAGNode"]              # 节点列表
    edges: List["DAGEdge"]              # 边列表
    
    # 拓扑信息
    adjacency_list: Dict[str, List[str]] = field(default_factory=dict)  # 邻接表
    reverse_adjacency_list: Dict[str, List[str]] = field(default_factory=dict)  # 反向邻接表
    
    # 配置
    config: Dict[str, Any] = field(default_factory=dict)  # 配置参数
    context_schema: Dict[str, Any] = field(default_factory=dict)  # 上下文schema
    
    # 执行策略
    execution_strategy: str = "parallel"  # 执行策略
    max_concurrency: int = 10           # 最大并发数
    timeout_ms: Optional[int] = None    # 超时时间
    
    # 验证规则
    validation_rules: List[Dict[str, Any]] = field(default_factory=list)  # 验证规则
    cycle_detection: bool = True        # 是否检测环
```

### DAG节点
```python
@dataclass
class DAGNode:
    """DAG节点"""
    # 标识信息
    node_id: str                        # 节点ID
    node_name: str                      # 节点名称
    node_type: str                      # 节点类型
    
    # 执行信息
    handler: str                        # 处理函数
    input_schema: Dict[str, Any]        # 输入schema
    output_schema: Dict[str, Any]       # 输出schema
    
    # 依赖关系
    dependencies: List[str] = field(default_factory=list)  # 依赖节点
    dependents: List[str] = field(default_factory=list)    # 被依赖节点
    
    # 配置
    config: Dict[str, Any] = field(default_factory=dict)  # 节点配置
    resource_requirements: Dict[str, Any] = field(default_factory=dict)  # 资源需求
    
    # 执行策略
    timeout_ms: int = 30000             # 超时时间（毫秒）
    retry_policy: Dict[str, Any] = field(default_factory=dict)  # 重试策略
    error_handler: Optional[str] = None  # 错误处理函数
    
    # 验证
    validation_rules: List[Dict[str, Any]] = field(default_factory=list)  # 验证规则
    preconditions: List[Dict[str, Any]] = field(default_factory=list)     # 前置条件
    postconditions: List[Dict[str, Any]] = field(default_factory=list)    # 后置条件
```

### DAG边
```python
@dataclass
class DAGEdge:
    """DAG边"""
    # 标识信息
    edge_id: str                        # 边ID
    source_node: str                    # 源节点
    target_node: str                    # 目标节点
    
    # 传输信息
    data_mapping: Dict[str, str] = field(default_factory=dict)  # 数据映射
    condition: Optional[str] = None     # 条件表达式
    
    # 配置
    config: Dict[str, Any] = field(default_factory=dict)  # 边配置
    
    # 验证
    validation_rules: List[Dict[str, Any]] = field(default_factory=list)  # 验证规则
```

### DAG执行器
```python
@dataclass
class DAGExecutor:
    """DAG执行器"""
    # 执行器配置
    executor_id: str                    # 执行器ID
    executor_type: str = "dag"          # 执行器类型
    
    # 执行状态
    dag: Optional[DAGDefinition] = None  # 当前DAG
    context: Dict[str, Any] = field(default_factory=dict)  # 执行上下文
    node_results: Dict[str, Any] = field(default_factory=dict)  # 节点结果
    
    # 执行控制
    execution_mode: str = "normal"      # 执行模式
    max_concurrency: int = 10           # 最大并发数
    
    # 性能指标
    metrics: Dict[str, Any] = field(default_factory=dict)  # 性能指标
    statistics: Dict[str, Any] = field(default_factory=dict)  # 统计信息
    
    # 错误处理
    error_history: List[Dict[str, Any]] = field(default_factory=list)  # 错误历史
    
    async def execute(self) -> Dict[str, Any]:
        """执行DAG"""
        # 验证DAG
        self._validate_dag()
        
        # 初始化执行上下文
        self._initialize_context()
        
        # 拓扑排序
        execution_order = self._topological_sort()
        
        # 按拓扑顺序执行节点
        for node_id in execution_order:
            node = self._get_node(node_id)
            
            # 检查前置条件
            if not self._check_preconditions(node):
                raise DAGError(f"Preconditions not met for node {node_id}")
            
            # 准备输入数据
            input_data = self._prepare_input(node)
            
            # 执行节点（支持并发）
            node_result = await self._execute_node(node, input_data)
            
            # 检查后置条件
            if not self._check_postconditions(node, node_result):
                raise DAGError(f"Postconditions not met for node {node_id}")
            
            # 保存结果
            self.node_results[node_id] = node_result
            
            # 更新上下文
            self._update_context(node, node_result)
        
        # 构建最终结果
        return self._build_final_result()
    
    def _topological_sort(self) -> List[str]:
        """拓扑排序"""
        # Kahn算法实现
        in_degree = {node.node_id: 0 for node in self.dag.nodes}
        
        # 计算入度
        for edge in self.dag.edges:
            in_degree[edge.target_node] += 1
        
        # 初始化队列
        queue = deque([node_id for node_id, degree in in_degree.items() if degree == 0])
        result = []
        
        # 拓扑排序
        while queue:
            node_id = queue.popleft()
            result.append(node_id)
            
            # 更新相邻节点的入度
            for neighbor in self.dag.adjacency_list.get(node_id, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # 检查是否有环
        if len(result) != len(self.dag.nodes):
            raise DAGError("Cycle detected in DAG")
        
        return result
```

## 状态机模型

### 状态机定义
```python
@dataclass
class StateMachineDefinition:
    """状态机定义"""
    # 标识信息
    sm_id: str                          # 状态机ID
    sm_name: str                        # 状态机名称
    sm_version: str                     # 状态机版本
    
    # 状态定义
    states: List["State"]               # 状态列表
    transitions: List["Transition"]     # 转移列表
    
    # 初始状态
    initial_state: str                  # 初始状态
    final_states: List[str]             # 终止状态列表
    
    # 配置
    config: Dict[str, Any] = field(default_factory=dict)  # 配置参数
    context_schema: Dict[str, Any] = field(default_factory=dict)  # 上下文schema
    
    # 执行策略
    execution_strategy: str = "event_driven"  # 执行策略
    timeout_ms: Optional[int] = None    # 超时时间
    
    # 验证规则
    validation_rules: List[Dict[str, Any]] = field(default_factory=list)  # 验证规则
```

### 状态
```python
@dataclass
class State:
    """状态"""
    # 标识信息
    state_id: str                       # 状态ID
    state_name: str                     # 状态名称
    state_type: str                     # 状态类型
    
    # 执行信息
    entry_action: Optional[str] = None  # 进入动作
    exit