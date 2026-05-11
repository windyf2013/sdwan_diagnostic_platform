# ═══════════════════════════════════════════════════════════════════
# 指令 ID: SPRINT-3-COMPLETE
# 指令名称: Sprint 3 完整开发流程
# 依赖: Sprint 2 已完成 (所有工具可用)
# ═══════════════════════════════════════════════════════════════════

**【阅读文件】**
1. detail_function_design.md - §1 一键体检详细设计 (全部)
2. sdwan_analyzer_project.md - §4.3 模块二, §6.2 Flow定义, §7 报告系统
3. developing_tasks.md - Sprint 3 任务清单
4. AI_SPEC_GUIDE.md - 核心约束、Flow模板
5. SDWAN_SPEC_PATCHES.md - PATCH-001(覆盖率), PATCH-003(装饰器)

**【执行顺序】**
 - 按以下阶段依次完成，每个阶段完成后进行自检验收。

## 阶段 3.1: 配置采集器实现 (Week 3)

**【输出文件】**
1. src/sdwan_desktop/services/collector/windows_collector.py
   - WindowsCollector 类
   - SystemInfoSnapshot 数据类 (聚合所有采集信息)
   - async collect(ctx: FlowContext) -> SystemInfoSnapshot

2. src/sdwan_desktop/services/collector/__init__.py
   - 导出 WindowsCollector, SystemInfoSnapshot

**【功能要求】**
- 通过 ToolDispatcher 调用 WindowsSystemTool (已在Sprint 2实现)
- 将工具返回的dict转换为结构化的 SystemInfoSnapshot
- 采集内容包括:
  * 网卡适配器信息 (AdapterInfo列表)
  * IP配置 (IpConfigInfo)
  * 路由表 (RouteInfo列表)
  * DNS配置 (DnsConfigInfo)
  * 代理配置 (ProxyConfigInfo)
  * 防火墙状态 (FirewallInfo)
  * ARP表 (ArpEntry列表)
  * IPv6信息 (可选)
- 采集失败时记录错误但不中断整体流程 (返回部分数据)

**【自检清单】**
- 正确调用 WindowsSystemTool 并解析返回数据
- 返回完整的 SystemInfoSnapshot 对象
- 采集失败时记录日志并继续
- 所有数据类使用 @dataclass(slots=True)

---

## 阶段 3.2: 探测目标配置与连通性测试服务 (Week 3)

**【输出文件】**
1. configs/quick_check.yaml
   - 一键体检配置 (参考 detail_function_design.md §1.5)
   - 包含: 采集开关、探测目标、阈值配置、规则开关

2. src/sdwan_desktop/services/connectivity.py
   - ConnectivityTester 类
   - ConnectivityTestResult 数据类
   - 方法:
     * async test_gateway(gateway_ip, ctx) -> ProbeResult
     * async test_domestic_dns(ctx) -> List[ProbeResult]
     * async test_international_dns(ctx) -> List[ProbeResult]
     * async test_domestic_targets(ctx) -> List[ProbeResult]
     * async test_international_targets(ctx) -> List[ProbeResult]
     * async test_all(ctx) -> ConnectivityTestResult

3. src/sdwan_desktop/services/dns_split.py
   - DnsSplitTester 类
   - DnsSplitTestResult 数据类
   - 方法:
     * async test_domain(domain, ctx) -> dict
     * async test_all_domains(domains, ctx) -> DnsSplitTestResult

**【功能要求】**
- 使用 asyncio.gather 并发执行多个探测
- 使用 asyncio.Semaphore 限制最大并发数 (参考配置)
- 国内/国际目标分别统计成功率
- DNS分流测试: 对比国内外DNS服务器对同一域名的解析结果

**【配置结构参考】**
```yaml
quick_check:
  collection:
    adapters: true
    routes: true
    dns: true
    proxy: true
    firewall: true
    arp: true
    ipv6: true
  
  targets:
    dns_servers:
      domestic: ["114.114.114.114", "223.5.5.5"]
      international: ["8.8.8.8", "1.1.1.1"]
    
    connectivity:
      domestic:
        - host: www.baidu.com
          type: http
        - host: 114.114.114.114
          type: icmp
      international:
        - host: www.google.com
          type: http
        - host: 8.8.8.8
          type: icmp
    
    dns_split_domains:
      - www.google.com
      - www.baidu.com
      - github.com
  
  thresholds:
    gateway_rtt_warning_ms: 100
    gateway_loss_warning_pct: 5
    dns_timeout_ms: 2000
    dns_slow_ms: 500
    international_loss_warning_pct: 10
```

**【自检清单】**
- 配置正确加载 (使用ConfigLoader)
- 并发探测正常工作
- 探测结果包含完整的 ProbeResult 对象
- 超时和错误正确处理

---

## 阶段 3.3: 规则引擎框架与网关/DNS/系统规则实现 (Week 3-4)

**【输出文件】**
1. src/sdwan_desktop/services/analyzer/rule_engine.py
  - DiagnosisRule 数据类
  - RuleEngine 类
  - 方法: register_rule(), evaluate(ctx) -> List[RootCause]

2. src/sdwan_desktop/services/analyzer/rule_context.py
  - QuickCheckContext 数据类
  - 聚合 SystemInfoSnapshot + ConnectivityTestResult + DnsSplitTestResult

3. src/sdwan_desktop/services/analyzer/rules/init.py
  - 导出所有规则模块

4. src/sdwan_desktop/services/analyzer/rules/gateway.py
  - 规则: GW-001 (网关不可达), GW-002 (网关延迟高), GW-003 (网关丢包)
  - 使用 @pure_function 装饰器

5. src/sdwan_desktop/services/analyzer/rules/dns.py
  - 规则: DNS-001 (DNS无响应), DNS-002 (DNS响应慢)

6. src/sdwan_desktop/services/analyzer/rules/system.py
  - 规则: ADAPTER-001 (网卡未连接), ADAPTER-002 (网卡速度异常)
  - IP-001 (APIPA地址), IP-002 (IP冲突)
  - ROUTE-001 (多条默认路由)
  - PROXY-001 (代理启用), PROXY-002 (代理不可达)
  - FW-001 (防火墙阻止ICMP)

7. src/sdwan_desktop/services/analyzer/rules/connectivity.py
  - 规则: INET-001 (国内不通), INET-002 (国际不通), INET-003 (国际丢包)
  - SPLIT-001 (DNS分流异常)

**【规则编写模板】**
```python
from sdwan_desktop.tools.registry.decorator import pure_function
from sdwan_desktop.core.types.diagnosis import RootCause, Severity

@pure_function
def evaluate_gateway_reachable(ctx: QuickCheckContext) -> Optional[RootCause]:
    """GW-001: 默认网关不可达"""
    if not ctx.gateway_ping.success:
        return RootCause(
            cause_id="GW-001",
            title="默认网关不可达",
            description=f"无法Ping通网关 {ctx.ip_config.default_gateway}",
            severity=Severity.CRITICAL,
            confidence=0.95,
            evidence_refs=[ctx.gateway_ping.id],
            matched_rules=["GW-001"]
        )
    return None
```

**【自检清单】**
- 每条规则独立可测试
- 规则条件函数使用 @pure_function 装饰
- 规则返回 RootCause 对象，包含置信度
- RuleEngine 正确聚合所有规则结果
- 规则评估失败不抛异常，返回 None
- 至少实现 17 条规则 (参考 developing_tasks.md §4.3)

---

## 阶段 3.4: PipelineEngine 与 QuickCheck Flow定义 (Week 4)

**【输出文件】**

1. src/sdwan_desktop/runtime/engine.py (完善)
  - FlowRuntime 类
  - 支持步骤依赖解析 (DAG)
  - 支持并行步骤执行
  - 支持步骤重试和超时

2. src/sdwan_desktop/runtime/executor.py (完善)
  - StepExecutor 类
  - 支持超时控制和重试策略

3. src/sdwan_desktop/flow/definitions/quick_check.py
  - QUICK_CHECK_FLOW 常量 (FlowDefinition)
  - QuickCheckFlow 类
  - **步骤定义**:
    - step-1: 系统信息采集
    - step-2: 网关连通性测试 (可与step-3并行)
    - step-3: DNS解析测试 (可与step-2并行)
    - step-4: 互联网连通性测试 (依赖step-2)
    - step-5: DNS分流测试
    - step-6: 配置异常检测 (规则引擎)
    - step-7: 诊断结论生成
    - step-8: 报告生成

**【步骤依赖关系】**
```text
step-1 (采集)
   ├── step-2 (网关测试) ──┐
   └── step-3 (DNS测试) ───┼── step-4 (连通性测试)
                          │
                          └── step-5 (DNS分流)
                                 │
                                 ▼
                            step-6 (规则分析)
                                 │
                                 ▼
                            step-7 (结论生成)
                                 │
                                 ▼
                            step-8 (报告生成)
```

**【自检清单】**
 - FlowDefinition 包含完整步骤定义
 - 支持并行步骤 (step-2 和 step-3)
 - 每个步骤记录 StepSnapshot
 - 支持按 trace_id 追踪执行过程
 - 步骤失败时根据配置决定是否继续

---

## 阶段 3.5: 基础HTML报告模板与生成服务 (Week 4)

**【输出文件】**

1. src/sdwan_desktop/reporting/templates/base.html
 - 基础样式定义
 - 严重程度颜色变量
 - 折叠组件JavaScript

2. src/sdwan_desktop/reporting/templates/quick_check.html
 - 继承 base.html
 - 包含章节: 元信息、执行摘要、检测结果表格、根因分析、诊断建议、证据附录

3. src/sdwan_desktop/services/reporter/html_builder.py
 - HtmlReportBuilder 类
 - build_quick_check_report(result: DiagnosisResult, output_path=None) -> str
 - 辅助方法: _get_severity_text, _extract_system_info, _extract_connectivity

4. src/sdwan_desktop/reporting/assets/ (目录)
 - css/style.css (可选)
 - js/main.js (可选)

**【报告结构要求】(符合 SDWAN_SPEC §4.3)**
1. 元信息: 报告ID, Trace ID, 生成时间, 诊断类型, 规则版本
2. 执行摘要: 严重程度徽章、一句话总结、综合置信度
3. 检测结果表格: 检测项、状态、详情 (按严重程度排序)
4. 根因分析: 每个根因包含标题、描述、置信度、证据引用
5. 诊断建议: 优先级排序的可执行步骤
6. 证据附录: 可折叠的详细证据

**【自检清单】**
 - HTML报告包含完整的元信息
 - 检测结果按严重程度排序
 - 每条诊断结论可追溯到证据ID
 - 支持响应式布局
 - 无内联调试信息泄露

---

## 阶段 3.6: CLI命令实现与流程集成测试 (Week 4)

**【输出文件】**

1. src/sdwan_desktop/interface/cli/commands/quick_check.py
- quick_check_command() 函数
- 参数:
  1. --output, -o: 报告输出路径
  2. --format, -f: json|html (默认html)
  3. --verbose, -v: 详细输出
  4. --no-parallel: 禁用并行执行
- 执行流程: 初始化配置 → 创建FlowContext → 执行QuickCheckFlow → 生成报告

2. src/sdwan_desktop/interface/cli/formatters.py (补充)
- format_diagnosis_summary(result: DiagnosisResult) -> str
- format_root_causes(causes: List[RootCause]) -> str
- format_recommendations(recs: List[Recommendation]) -> str
- colorize(text, severity) -> str

3. tests/flow/test_quick_check.py
- 端到端流程测试
- Mock所有外部依赖 (工具调用)
- 验证规则正确触发
- 验证报告生成

4. tests/unit/services/test_collector.py
5. tests/unit/services/test_connectivity.py
6. tests/unit/services/test_rule_engine.py
7. tests/unit/services/test_rules.py

**【测试覆盖率要求】(PATCH-001)**
- service function ≥80%
- pure function (规则) ≥90%
- orchestrator (Flow) ≥70%
- 核心路径 (happy path) 100%覆盖

**【验收命令】**
```bash
# 执行一键体检
agentctl quick-check --output report.html

# JSON格式输出
agentctl quick-check --format json --output result.json

# 运行测试
pytest tests/flow/test_quick_check.py -v
pytest tests/unit/services/ -v --cov=src/sdwan_desktop/services

# 类型检查
mypy src/sdwan_desktop/services/ src/sdwan_desktop/flow/

# Lint检查
ruff check src/sdwan_desktop/
```

**【自检清单】**
- CLI命令可完整执行
- 生成的HTML报告可正常打开显示
- 所有测试通过，覆盖率达标
- mypy 类型检查无错误
- ruff lint 检查无错误
- 日志包含 trace_id
- 无 print 语句

---

## Sprint 3 完成标志

**当以下所有条件满足时，Sprint 3 完成**：
-  配置采集器正确采集Windows信息
-  连通性测试服务正确探测国内外目标
-  DNS分流测试正常工作
-  至少17条诊断规则实现并通过测试
-  QuickCheck Flow完整执行 (采集→探测→分析→报告)
-  HTML报告包含完整的元信息、结论、证据、建议
-  CLI命令 agentctl quick-check 可执行
-  流程测试覆盖率 ≥80%
-  代码通过 lint/type 检查
-  无违反核心约束

---

## 附加说明

**【规则优先级】**
**按 detail_function_design.md §1.3 实现以下规则**:
- ADAPTER-001, ADAPTER-002
- IP-001, IP-002
- GW-001, GW-002, GW-003
- DNS-001, DNS-002
- ROUTE-001
- PROXY-001, PROXY-002
- FW-001
- INET-001, INET-002, INET-003
- SPLIT-001

**【阈值配置】**
- 所有阈值从 configs/quick_check.yaml 读取，不硬编码。

**【错误处理】**
- 单个探测失败不中断整体流程
- 规则评估失败不影响其他规则
- 报告生成失败应返回错误信息

**【性能要求】**
- 一键体检总耗时 <30s (developing_tasks.md §8.3)

---

## 代码模板参考

### QuickCheckFlow 结构

```python
"""一键体检流程定义"""

from sdwan_desktop.flow.definitions.base import FlowDefinition, StepDefinition, RetryPolicy
from sdwan_desktop.core.types.flow_state import FlowStatus

QUICK_CHECK_FLOW = FlowDefinition(
    id="quick-check-v1",
    name="一键体检",
    version="1.0.0",
    description="Windows客户端基础配置检查与连通性分析",
    steps=[
        StepDefinition(
            id="step-collect",
            name="系统信息采集",
            description="采集Windows网络配置",
            handler="collector.collect",
            timeout_seconds=30,
            retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=1)
        ),
        StepDefinition(
            id="step-gateway",
            name="网关连通性测试",
            description="测试默认网关可达性",
            handler="connectivity.test_gateway",
            depends_on=["step-collect"],
            timeout_seconds=10
        ),
        StepDefinition(
            id="step-dns",
            name="DNS解析测试",
            description="测试DNS服务器解析能力",
            handler="connectivity.test_dns",
            depends_on=["step-collect"],
            timeout_seconds=15
        ),
        StepDefinition(
            id="step-internet",
            name="互联网连通性测试",
            description="测试公网可达性",
            handler="connectivity.test_internet",
            depends_on=["step-gateway", "step-dns"],
            timeout_seconds=20
        ),
        StepDefinition(
            id="step-dns-split",
            name="DNS分流测试",
            description="测试国内外DNS解析差异",
            handler="dns_split.test",
            depends_on=["step-dns"],
            timeout_seconds=15
        ),
        StepDefinition(
            id="step-analyze",
            name="配置异常检测",
            description="执行诊断规则",
            handler="analyzer.analyze",
            depends_on=["step-internet", "step-dns-split"],
            timeout_seconds=10
        ),
        StepDefinition(
            id="step-conclusion",
            name="诊断结论生成",
            description="综合所有检测结果生成诊断",
            handler="analyzer.generate_conclusion",
            depends_on=["step-analyze"],
            timeout_seconds=5
        ),
        StepDefinition(
            id="step-report",
            name="报告生成",
            description="生成HTML诊断报告",
            handler="reporter.generate_html",
            depends_on=["step-conclusion"],
            timeout_seconds=15
        )
    ],
    config={
        "parallel_groups": [["step-gateway", "step-dns"]],
        "continue_on_error": True,
        "save_snapshots": True
    }
)
```

### 控制台输出格式示例
```text
🔍 SD-WAN 一键体检 v1.0.0
Trace ID: abc-123-def-456

📊 采集系统信息... ✓ (1.2s)
   - 网卡: Realtek PCIe GbE Family Controller
   - IP: 192.168.1.100/24
   - 网关: 192.168.1.1

🌐 测试网关连通性... ✓ (2.1s)
   - 网关 192.168.1.1: 可达, RTT=2.3ms

🔬 测试DNS解析... ✓ (1.5s)
   - 国内DNS 114.114.114.114: 响应正常
   - 国际DNS 8.8.8.8: 响应正常

🌍 测试互联网连通性... ✓ (3.2s)
   - 国内目标: 4/4 成功
   - 国际目标: 3/4 成功 (www.google.com 超时)

🔎 测试DNS分流... ✓ (1.8s)
   - www.google.com: 国内解析 203.208.x.x, 国际解析 142.250.x.x

📈 分析诊断结果... ✓ (0.3s)

═══════════════════════════════════════════════════════════════════
📋 诊断结果摘要
═══════════════════════════════════════════════════════════════════
严重程度: ⚠️ 警告
综合置信度: 85%

🔴 发现 2 个问题:

1. [INET-002] 国际网络不通 (置信度: 85%)
   无法访问 www.google.com，可能原因: 国际链路问题或需要代理

2. [SPLIT-001] DNS分流异常 (置信度: 70%)
   www.google.com 国内外解析结果不一致，可能存在DNS劫持

💡 诊断建议:
   1. [优先级 1] 检查是否需要配置代理访问国际网站
   2. [优先级 2] 考虑使用DoH/DoT加密DNS防止劫持

📄 报告已保存: ./reports/quick_check_20260122_143022.html
```