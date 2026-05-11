# sprint7_plan.md

# Sprint 7 完整开发流程计划

## 基础信息
- **指令 ID**: SPRINT-7-COMPLETE
- **指令名称**: Sprint 7 完整开发流程
- **依赖要求**: Sprint 2、Sprint 3、Sprint 4、Sprint 5、Sprint 6 已完成

## 执行说明
- 请按以下顺序分步执行 Sprint 7 开发。每完成一个阶段后暂停，输出进度报告，等待确认后再继续下一阶段。

## 常用参考文档
- 开发任务详情: developing_tasks.md §8
- 性能指标要求: developing_tasks.md §8.3
- 质量门禁: SDWAN_SPEC.md §3.6, SDWAN_SPEC_PATCHES.md PATCH-001

---

# 阶段 7.1: 端到端测试用例编写
## 输出文件
1. `tests/e2e/test_quick_check_e2e.py`
- 一键体检完整流程测试
- 覆盖: 采集 → 探测 → 规则分析 → 报告生成
- 验证: DiagnosisResult 结构完整性、trace_id 贯穿
- Mock 所有外部工具调用

2. `tests/e2e/test_deep_dive_e2e.py`
- 深度诊断完整流程测试
- 覆盖: PC采集 → CPE连接 → 配置解析 → 拓扑构建 → 根因分析 → 报告生成
- Mock SSH 连接和命令执行
- 验证: 拓扑结构正确、根因逻辑合理

3. `tests/e2e/test_waterfall_e2e.py`
- 业务监测完整流程测试
- 覆盖: HAR采集 → 解析 → 性能分析 → 报告生成
- Mock Playwright 调用
- 验证: WaterfallResult 时序数据正确

4. `tests/e2e/test_cli_e2e.py`
- CLI端到端测试
- 测试命令: agentctl quick-check, agentctl deep-dive, agentctl waterfall
- 验证: 退出码、输出格式、报告文件生成
- 使用 click.testing.CliRunner

5. `tests/e2e/conftest.py`
- 共享 fixtures: mock_registry, sample_flow_context, temp_dir

## 自检清单
- [ ] 每个 Flow 至少 1 个完整 happy path 测试
- [ ] Mock 策略合理，不依赖真实网络
- [ ] 测试验证 trace_id 在输出中贯穿
- [ ] 报告生成后验证文件存在且内容有效
- [ ] CLI 测试覆盖正常和错误情况

---

# 阶段 7.2: 性能基准测试
## 输出文件
1. `tests/benchmark/test_performance_benchmark.py`
- 一键体检耗时基准 <30s
- 深度诊断耗时基准 <2min
- Waterfall耗时基准 <45s
- GUI启动时间基准 <3s
- 使用 pytest-benchmark 或 time 统计

2. `tests/benchmark/test_memory_benchmark.py`
- 空闲内存占用 <200MB
- 诊断执行时内存峰值
- 报告生成时内存占用
- 使用 memory_profiler 或 psutil

3. `tests/benchmark/conftest.py`
- 性能测试 fixtures

4. `configs/benchmark.yaml` (可选)
- 性能阈值配置

## 自检清单
- [ ] 一键体检执行时间 <30s
- [ ] 深度诊断执行时间 <2min
- [ ] Waterfall执行时间 <45s
- [ ] GUI启动时间 <3s
- [ ] 内存占用 <200MB (空闲)
- [ ] 性能测试可在CI环境运行

---

# 阶段 7.3: 异常场景测试与健壮性
## 输出文件
1. `tests/e2e/test_error_scenarios.py`
- 工具超时场景: PingTool超时、SSH连接超时
- 工具失败场景: DNS解析失败、TCP端口关闭
- 部分失败场景: 部分探测成功部分失败
- 配置缺失场景: 网关不可达、DNS服务器无响应
- 流程中断场景: 步骤失败后恢复

2. `tests/e2e/test_edge_cases.py`
- 空路由表
- 无默认网关
- 单网卡/多网卡
- IPv6 启用/禁用
- 代理启用/禁用
- 无效URL输入
- 极大HAR文件 1000+请求

3. `tests/e2e/test_concurrency.py`
- 多个 Flow 并发执行
- ToolRegistry 并发注册
- GUI 诊断期间重复点击

## 自检清单
- [ ] 每个异常场景有对应测试
- [ ] 错误信息包含有效的 error_code
- [ ] Flow 在步骤失败时可正确降级
- [ ] 并发场景无竞态条件
- [ ] 资源正确释放 无泄漏

---

# 阶段 7.4: GUI响应优化
## 输出文件
1. `src/sdwan_desktop/interface/gui/workers/diagnosis_worker.py` (优化)
- 优化信号发射频率 避免过多更新阻塞UI
- 添加取消支持 QThread.requestInterruption
- 添加暂停/恢复支持

2. `src/sdwan_desktop/interface/gui/main_window.py` (优化)
- 添加取消按钮 诊断执行中
- 优化进度条更新 节流
- 添加窗口关闭确认 如有正在执行的诊断

3. `src/sdwan_desktop/interface/gui/widgets/report_viewer.py` (优化)
- 大报告加载优化 异步加载
- 报告滚动性能优化
- 拓扑图/时序图渲染性能优化

## 自检清单
- [ ] GUI启动时间 <3s
- [ ] 界面响应流畅，长任务不阻塞UI
- [ ] 支持取消正在执行的诊断
- [ ] 关闭窗口时有未完成任务提示
- [ ] 大报告加载不卡顿

---

# 阶段 7.5: 报告生成性能优化
## 输出文件
1. `src/sdwan_desktop/services/reporter/html_builder.py` (优化)
- 缓存 Jinja2 模板编译结果
- 大报告流式写入文件 避免内存膨胀
- 报告资源内联优化 CSS/JS
- 拓扑图生成优化 Mermaid 渲染移至前端

2. `src/sdwan_desktop/reporting/templates/` (优化)
- 减少CSS重复定义
- 使用CSS变量统一颜色
- JavaScript 延迟加载非关键图表
- 优化 Chart.js 配置 避免过多动画

3. `tests/benchmark/test_report_benchmark.py`
- 报告生成时间基准
- 报告文件大小基准

## 自检清单
- [ ] 报告生成时间 <5s 含拓扑图
- [ ] 报告文件大小 <5MB 含截图
- [ ] 报告在浏览器中打开流畅
- [ ] HTML/CSS/JS 通过 W3C 验证

---

# 阶段 7.6: Bug修复与代码质量提升
## 任务说明
本阶段不限定具体文件，需根据前面阶段测试中发现的问题进行修复。优先修复以下类别:

1. 阻断性Bug (按优先级排序):
- CLI命令执行崩溃
- GUI启动崩溃
- Flow执行中断
- 报告生成失败

2. 功能性Bug:
- 工具返回数据格式不匹配
- 规则判断逻辑错误
- 配置解析异常

3. 体验性Bug:
- 错误信息不清晰
- 日志缺失 trace_id
- 进度提示不准确

## 修复记录模板
每个修复记录包含:
- Bug ID (S7-001 开始编号)
- 发现阶段/测试用例
- 根因描述
- 修复方案
- 影响文件
- 验证方式

## 示例
Bug ID: S7-001
发现: tests/e2e/test_quick_check_e2e.py
根因: QuickCheckFlow 在网关测试超时时未继续执行后续步骤
修复: 修改 continue_on_error 配置逻辑，添加超时处理
文件: src/sdwan_desktop/flow/definitions/quick_check.py
验证: test_quick_check_e2e → test_gateway_timeout_continues

## 自检清单
- [ ] 所有 P0/P1 Bug 已修复
- [ ] 修复后回归测试通过
- [ ] CHANGELOG 记录修复内容
- [ ] Bug修复有对应测试覆盖

---

# 阶段 7.7: 最终集成验证
## 验证命令
```bash
# 1. 运行全部测试
pytest tests/ -v --cov=src/sdwan_desktop --cov-report=html

# 2. 类型检查
mypy src/sdwan_desktop/ --strict

# 3. Lint检查
ruff check src/sdwan_desktop/ tests/

# 4. 安全检查 (如已配置)
bandit -r src/sdwan_desktop/

# 5. 性能测试
pytest tests/benchmark/ -v

# 6. CLI功能验证
agentctl --version
agentctl quick-check --format json
agentctl tool list

# 7. GUI启动测试
python -c "from sdwan_desktop.interface.gui.main_window import MainWindow; print('OK')"
```

## 输出文件
1. tests/integration/test_full_integration.py
- 跨模块集成测试
  验证：工具注册 → 采集 → 诊断 → 报告 完整链路
2. docs/test_report.md (测试报告摘要)
  测试统计：总数、通过 / 失败 / 跳过
  覆盖率统计：按模块
  性能基准：关键指标
  已知问题列表

## 自检清单
- 所有测试通过
- 覆盖率达标 (PATCH-001):
  - pure function ≥90%
  - service function ≥80%
  - tool function ≥70%
  - orchestrator ≥70%
- mypy 类型检查无错误
- ruff lint 检查无错误
- 无已知 P0/P1 Bug
- 性能指标满足要求

---

# Sprint 7 完成标志
- ✅ 端到端测试全部通过 一键体检、深度诊断、业务监测
- ✅ 性能指标满足目标值
- ✅ 异常场景覆盖充分
- ✅ GUI 响应流畅
- ✅ 报告生成性能达标
- ✅ 所有已知 Bug 修复
- ✅ 代码质量和测试覆盖率达标
- ✅ 集成验证通过
- ✅ CHANGELOG 更新

---

# 附加说明

## 性能目标
| 指标 | 目标值 |
| | |
| 一键体检耗时 | <30s |
| 深度诊断耗时 | <2min |
| Waterfall 耗时 | <45s |
| GUI 启动时间 | <3s |
| 内存占用 (空闲) | <200MB |
| 报告生成时间 | <5s |
| 报告文件大小 | <5MB |

## 覆盖率目标
| 函数类型 | 目标 |
| | |
| pure function | ≥90% |
| service function | ≥80% |
| tool function | ≥70% |
| orchestrator | ≥70% |

## Bug 优先级
- P0: 阻断性 崩溃、无法完成核心功能
- P1: 严重 功能可用但结果错误
- P2: 一般 体验问题、边缘情况