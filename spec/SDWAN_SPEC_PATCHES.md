# SDWAN_SPEC_PATCHES.md

**版本**: v1.0
**生效日期**: 2026-01-20
**适用范围**: 覆盖/补充/豁免 SDWAN_SPEC.md 中的条款
**冲突裁决**: 本文件优先于原规范

---

## PATCH-001: 降低测试覆盖率门槛

**原规范位置**: §3.6 质量门禁基线

| 函数类型 | 原要求 | 修正为 | 理由 |
|---------|--------|--------|------|
| pure function | ≥95% | ≥90% | AI生成的pure函数质量高，95%过度 |
| service function | ≥90% | ≥80% | 业务逻辑测试成本高，降低10% |
| tool function | ≥85% | ≥70% | 工具函数涉及外部依赖，mock成本高 |
| orchestrator | ≥90% | ≥70% | 编排逻辑测试代码量>生产代码 |

**新增规则**:
- 核心路径（happy path）必须100%覆盖
- 错误路径允许按优先级覆盖（高>中>低）
- 测试覆盖率不达标不阻断开发阶段，仅阻断生产发布

---

## PATCH-002: 放宽禁止dict规则

**原规范位置**: §6.0 强制约束

**原规则**: ❌ 禁止dict无结构传参

**修正规则**:
- ✅ **跨层接口**（Interface→Orchestration→Service→Tool）必须使用结构化对象（dataclass/pydantic）
- ✅ **Tool层内部**允许使用dict处理第三方数据（设备输出、API响应）
- ✅ 必须在**边界处**（Tool返回前）将dict转换为结构化对象
- ✅ **临时数据聚合**（性能敏感路径）允许使用dict，但需注释说明理由

**示例**:

    ```python
    # ✅ 允许：Tool内部解析第三方数据
    class PingTool:
        def _parse_output(self, raw: str) -> dict:
            """解析ping命令输出 - 格式不确定"""
            return {"rtt": 10.5, "loss": 0}

        def run(self, target: str) -> ToolResponse:
            raw = self._execute_ping(target)
            data = self._parse_output(raw)
            return ToolResponse(**data)

    # ❌ 禁止：跨层传递dict
    class BadService:
        def analyze(self, data: dict) -> dict:
            pass
    ```

---

## PATCH-003: 函数分类改为装饰器

**原规范位置**: §2.2.3 函数分类标准

**原规则**: 使用注释 `# type: pure` 标注函数类型

**修正规则**: 使用装饰器标注，CI可自动验证

**装饰器定义**:

    ```python
    from typing import Callable

    def pure_function(func: Callable) -> Callable:
        """标记纯函数 - CI验证：无IO、无副作用、确定性"""
        func._spec_type = "pure"
        return func

    def service_function(func: Callable) -> Callable:
        """标记服务函数 - CI验证：依赖注入、无直接IO"""
        func._spec_type = "service"
        return func

    def tool_function(func: Callable) -> Callable:
        """标记工具函数 - CI验证：使用ToolRequest/Response"""
        func._spec_type = "tool"
        return func

    def orchestrator_function(func: Callable) -> Callable:
        """标记编排函数 - CI验证：无业务逻辑、状态可回放"""
        func._spec_type = "orchestrator"
        return func
    ```

**使用示例**:

    ```python
    @pure_function
    def calculate_rtt_avg(rtts: list[float]) -> float:
        return sum(rtts) / len(rtts)

    @tool_function
    class PingTool:
        def run(self, request: ToolRequest) -> ToolResponse:
            pass
    ```

**迁移期**:
- 新代码必须使用装饰器
- 旧代码允许保留注释标签，3个月内迁移

---

## PATCH-004: 补充优先级裁决矩阵

**原规范位置**: §0.2 冲突与优先级

**原规则**: "安全优先、正确性次之、性能再次、迁移成本最后"

**补充规则** - 完整优先级矩阵:

| 优先级 | 场景 | 裁决规则 |
|--------|------|----------|
| **P0** | 生产安全 | 可能影响现网的操作 > 一切 |
| **P1** | 数据完整性 | 诊断结论必须可追溯 > 存储成本 |
| **P2** | 开发阶段效率 | Alpha/Beta阶段 > 契约严格性 |
| **P3** | 生产阶段契约 | 已发布API必须向后兼容 > 开发效率 |
| **P4** | 代码可读性 | 清晰代码 > 极致性能 |
| **P5** | 极致性能 | 性能关键路径可豁免其他规则 |

**冲突示例**:

| 冲突 | 裁决 |
|------|------|
| 安全 vs 性能 | 安全胜出 |
| 完整性 vs 存储 | 完整性胜出，但需分级 |
| 契约 vs 效率（开发中） | 效率胜出 |
| 契约 vs 效率（生产中） | 契约胜出 |

---

## PATCH-005: 简化spec目录要求

**原规范位置**: §1.4 目录结构标准

**原规则**: 要求70+个markdown文件

**修正规则**:

**必须存在的最小文件集**（9个）:

    spec/
    ├── 00_core/
    │   ├── data_contract.md
    │   ├── error_model.md
    │   └── state_context.md
    ├── 10_architecture/
    │   └── layering_model.md
    ├── 20_domain/
    │   ├── probe/
    │   └── reporting/
    └── 50_execution/
        └── pipeline_engine.md

**可选目录**（按需创建）:
- `30_rfc/` - RFC详细设计
- `55_observability/` - 可观测性
- `60_examples/` - 示例
- `70_validation/` - 验证

**规则**:
- 缺失可选目录不阻断开发
- 生产发布前必须补全与功能相关的文档
- AI开发时仅需读取最小文件集

---

## PATCH-006: 补充依赖注入规范

**原规范位置**: §2.2.7 禁止模式

**补充规则**:

**必须遵守**:
- ✅ 类依赖必须通过构造函数注入
- ✅ 函数依赖必须通过参数传递
- ✅ 测试必须提供mock/fake实现

**禁止**:
- ❌ 在类内部实例化外部依赖
- ❌ 使用全局单例获取依赖
- ❌ 硬编码配置值

**示例**:

    ```python
    # ✅ 正确：依赖注入
    class PingTool:
        def __init__(self, dispatcher: ToolDispatcher, config: Config):
            self.dispatcher = dispatcher
            self.config = config

    # ❌ 错误：硬编码依赖
    class BadPingTool:
        def __init__(self):
            self.dispatcher = ToolDispatcher()
            self.timeout = 5
    ```

---

## PATCH-007: 补充异步与并发规范

**原规范位置**: 缺失章节

**补充规范**:

**并发策略**:
- 探针执行：使用 asyncio + semaphore 限制并发数
- 设备连接：使用连接池，默认最大10个并发连接
- Flow执行：每个trace_id独立执行，不互相阻塞

**超时策略**:
- 单次探测：默认30秒超时，可配置
- 整体Flow：默认5分钟超时，可配置
- 超时后必须支持取消

**示例**:

    ```python
    import asyncio

    class ProbeExecutor:
        def __init__(self, max_concurrent: int = 5):
            self.semaphore = asyncio.Semaphore(max_concurrent)

        async def execute_many(self, targets: list[str]) -> list[dict]:
            async def limited_execute(target):
                async with self.semaphore:
                    return await self.execute_one(target)

            return await asyncio.gather(*[
                limited_execute(t) for t in targets
            ])
    ```

---

## PATCH-008: 补充资源生命周期规范

**原规范位置**: 缺失章节

**补充规则**:

**必须实现**:
- 资源类必须实现上下文管理器
- 网络连接必须有自动释放机制
- 长连接必须有健康检查和自动重连

**示例**:

    ```python
    class CPEConnection:
        def __init__(self, host: str):
            self.host = host
            self._client = None

        def __enter__(self):
            self._client = self._connect()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if self._client:
                self._client.close()

        async def execute(self, cmd: str) -> str:
            if not self._is_healthy():
                await self._reconnect()
            return await self._client.exec(cmd)
    ```

---

## PATCH-009: 补充开发阶段豁免条款

**原规范位置**: 缺失章节

**补充规则**:

**Alpha阶段（0.x.x）**:
- 豁免：契约测试、向后兼容、完整文档
- 强制：核心架构、数据契约、trace贯穿

**Beta阶段（1.0.0-rc.x）**:
- 豁免：性能基线、SLO定义
- 强制：契约测试、API稳定性

**生产阶段（>=1.0.0）**:
- 全部规范强制生效

**版本标记**:

    ```toml
    version = "0.1.0-alpha"
    version = "1.0.0-rc.1"
    version = "1.0.0"
    ```

---

## PATCH-010: 补充性能豁免机制

**原规范位置**: 缺失章节

**补充规则**:

当规范约束导致性能问题时，允许豁免：

**豁免条件**:
1. 存在性能测试证据
2. 豁免代码有清晰注释说明理由
3. Code Review批准

**示例**:

    ```python
    # PERF-EXEMPT: 高频调用路径（10k+ QPS）
    # 理由：Tool Dispatcher调度开销占40% CPU
    # 审批：架构组批准，2026-03-01前优化
    class FastPathPing:
        def run(self, target: str):
            return self._ping_impl(target)
    ```

**有效期**: 最长3个月，必须提供优化计划

---

## 附录A：补丁与原规范映射表

| 补丁ID | 原规范章节 | 操作类型 | 优先级 |
|--------|-----------|----------|--------|
| PATCH-001 | §3.6 | 覆盖 | 高 |
| PATCH-002 | §6.0 | 放宽 | 高 |
| PATCH-003 | §2.2.3 | 替换 | 中 |
| PATCH-004 | §0.2 | 补充 | 高 |
| PATCH-005 | §1.4 | 放宽 | 中 |
| PATCH-006 | §2.2.7 | 补充 | 高 |
| PATCH-007 | 缺失 | 补充 | 中 |
| PATCH-008 | 缺失 | 补充 | 中 |
| PATCH-009 | 缺失 | 补充 | 高 |
| PATCH-010 | 缺失 | 补充 | 低 |

## 附录B：AI使用指引

**当AI读取规范时，按以下优先级**：
1. 先读本补丁文件（PATCH-001 ~ PATCH-010）
2. 补丁未覆盖的内容，读完整规范对应章节
3. 冲突时以本补丁为准

## 新对话启动模板:

**请遵守以下规范开发SD-WAN诊断平台**：
1. 补丁文件: [粘贴 SDWAN_SPEC_PATCHES.md]
2. 完整规范作为补充参考
3. 开始实现 [功能名称]