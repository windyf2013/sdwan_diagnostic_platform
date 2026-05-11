# Sprint 5 完整开发流程计划
## 基础信息
- **指令 ID**: SPRINT-5-COMPLETE
- **指令名称**: Sprint 5 完整开发流程
- **依赖要求**: Sprint 2 和 Sprint 3 已完成

## 执行说明
请按以下顺序分步执行 Sprint 5 开发。每完成一个阶段后暂停，输出进度报告，等待确认后再继续下一阶段。

## 常用参考文档
- 开发任务详情: developing_tasks.md §6
- Waterfall设计: sdwan_analyzer_project.md §4.5
- HAR解析模型: sdwan_analyzer_project.md §4.5 (ResourceTiming, WaterfallResult)

---

# 阶段 5.1: Playwright集成与HAR采集工具
## 输出文件
1. `src/sdwan_desktop/tools/implementations/web/har_capture.py`
   - HarCaptureTool 类
   - 装饰器: `@tool_function(name="har_capture", timeout=120)`
   - 方法: `async execute(request: ToolRequest, ctx: FlowContext) -> ToolResponse`
   - 功能:
     - 启动Chromium无头模式 (通过 Playwright)
     - 导航到目标URL
     - 录制HAR文件 (通过 browser.new_context 的 record_har 选项)
     - 可配置选项: headless(默认true), timeout, wait_until(load/domcontentloaded/networkidle)
     - 返回: har_file_path, screenshot_path (可选)

2. `src/sdwan_desktop/tools/adapters/playwright_adapter.py`
   - PlaywrightAdapter 类
   - 封装 Playwright 启动、上下文创建、页面导航
   - 支持代理设置

3. `tests/unit/tools/web/test_har_capture.py`
   - Mock Playwright调用测试

## 自检清单
- [ ] HarCaptureTool 通过 ToolDispatcher 调用
- [ ] 录制完成后正确生成HAR文件
- [ ] 支持超时和错误处理
- [ ] 页面加载超时时仍返回已录制数据
- [ ] Playwright 进程正确回收

---

# 阶段 5.2: HAR解析服务
## 输出文件
1. `src/sdwan_desktop/services/parser/har_parser.py`
   - HarParser 类
   - 方法: `parse(har_file_path: str) -> WaterfallResult`
   - 解析HAR JSON结构:
     - 提取所有 entries
     - 为每个 entry 构造 ResourceTiming (dns_time, connect_time, ssl_time, wait_time, download_time)
     - 计算总体指标: page_load_time, dom_content_loaded, total_requests, total_size_bytes

2. `src/sdwan_desktop/core/types/waterfall.py`
   - ResourceTiming 数据类 (继承 BaseContract)
   - WaterfallResult 数据类 (继承 BaseContract)
   - 字段参考 sdwan_analyzer_project.md §4.5

3. `tests/unit/services/parser/test_har_parser.py`
   - 使用样本HAR文件测试

## 自检清单
- [ ] 正确解析所有资源条目
- [ ] 正确计算DNS/TCP/SSL/等待/下载各阶段耗时
- [ ] 正确处理缺失字段 (如无SSL)
- [ ] WaterfallResult 包含完整统计信息

---

# 阶段 5.3: 性能分析与瓶颈规则
## 输出文件
1. `src/sdwan_desktop/services/analyzer/perf_analyzer.py`
   - PerfAnalyzer 类
   - 方法: `analyze(waterfall: WaterfallResult) -> AnalysisReport`
   - 识别: 最慢5个资源、阻塞渲染资源 (render_blocking)
   - 生成优化建议列表

2. `src/sdwan_desktop/services/analyzer/rules/performance.py`
   - 性能诊断规则 (使用 `@pure_function`):
     - PERF-001: 页面加载时间过长 (>3s)
     - PERF-002: DNS解析慢 (>200ms)
     - PERF-003: TCP握手慢 (>300ms)
     - PERF-004: SSL握手慢 (>500ms)
     - PERF-005: TTFB过长 (>600ms)
     - PERF-006: 资源下载慢 (>2s)
     - PERF-007: 阻塞渲染资源

3. `tests/unit/services/analyzer/test_perf_rules.py`

## 自检清单
- [ ] 每条规则独立可测试
- [ ] 分析与建议关联到具体资源URL
- [ ] 规则阈值可配置 (从 configs/thresholds.yaml 读取)

---

# 阶段 5.4: Waterfall Flow定义
## 输出文件
1. `src/sdwan_desktop/flow/definitions/waterfall.py`
   - WATERFALL_FLOW 常量
   - WaterfallFlow 类
   - 步骤定义:
     - step-1: HAR采集 (har_capture tool)
     - step-2: HAR解析 (har_parser service)
     - step-3: 性能分析 (perf_analyzer service)
     - step-4: 诊断建议生成 (performance rules)
     - step-5: 报告生成

2. `tests/flow/test_waterfall.py` (基础流程测试)

## 自检清单
- [ ] Flow定义包含完整步骤
- [ ] 步骤依赖关系正确
- [ ] 采集失败时流程可降级 (返回部分结果)

---

# 阶段 5.5: Waterfall HTML报告与CLI命令
## 输出文件
1. `src/sdwan_desktop/reporting/templates/waterfall.html`
   - Waterfall报告模板
   - 包含: 性能摘要、Waterfall时序图 (Chart.js)、最慢资源表格、优化建议

2. `src/sdwan_desktop/reporting/templates/components/waterfall_chart.html`
   - 时序图组件 (使用 Chart.js 或 自定义 Canvas)

3. `src/sdwan_desktop/services/reporter/html_builder.py` (扩展)
   - `build_waterfall_report(result: WaterfallResult) -> str`

4. `src/sdwan_desktop/interface/cli/commands/waterfall.py`
   - `waterfall_command()` 函数
   - 参数: --url (必填), --output, --headless, --wait-until

5. `tests/flow/test_waterfall_full.py`
   - Mock Playwright 的集成测试

## 自检清单
- [ ] CLI命令 `agentctl waterfall --url https://example.com` 可执行
- [ ] HTML报告正确展示资源加载时序图
- [ ] 最慢资源高亮显示
- [ ] 报告包含可操作的优化建议
- [ ] 支持 `--format json` 输出机器格式
- [ ] 所有测试通过，覆盖率达标

---

# Sprint 5 完成标志
- ✅ HarCaptureTool 已注册并可用
- ✅ HAR正确解析为 WaterfallResult
- ✅ 至少7条性能规则实现
- ✅ Waterfall Flow完整执行
- ✅ HTML报告包含交互式时序图
- ✅ CLI命令可用
- ✅ 代码通过 lint/type 检查
- ✅ 无违反核心约束