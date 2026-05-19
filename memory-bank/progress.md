# SD-WAN诊断平台 - 开发进度记录

**文档版本**: v1.41.0  
**更新日期**: 2026-05-13  
**当前迭代**: Sprint 8 - 发布准备 (阶段 8.3 完成 ✅)  
**关联文档**: developing_tasks.md, SDWAN_SPEC.md, SDWAN_SPEC_PATCHES.md, sprint8_plan.md

---

## 当前状态

### ✅ 已完成
- [x] Sprint 1: 基础框架搭建 (全部10个任务完成)
- [x] Sprint 2: 网络工具集 (全部任务完成，测试通过率 100%)
- [x] Sprint 3: 一键体检 (全部阶段完成)
- [x] **Sprint 4: 深度诊断 (全部阶段已完成)**

- [x] **Sprint 5 阶段 5.1 ~ 5.6: Waterfall 性能分析全流程** ✅

- [x] **Sprint 6 阶段 6.1 ~ 6.8: GUI 界面与主题系统** ✅

- [x] **Sprint 7 阶段 7.1: 端到端测试用例编写** ✅
  - [x] 修复循环导入问题 (`vendor/__init__.py`)
  - [x] 修复异常基类冲突 (`BaseError`)
  - [x] 统一数据契约字段名称 (`SystemInfoSnapshot`, `WaterfallResult` 等)
  - [x] 完善 `FlowContext` 上下文管理方法
  - [x] **E2E 测试通过率：18/18 (100%)**

- [x] **Sprint 7 阶段 7.2: 性能基准测试** ✅
  - [x] 完成 `tests/benchmark/test_performance_benchmark.py`：验证各流程执行耗时基准。
  - [x] 完成 `tests/benchmark/test_memory_benchmark.py`：验证空闲及负载下的内存占用。
  - [x] 修复基准测试中的数据契约字段名称错误。
  - [x] **基准测试通过率：7/7 (100%)**

- [x] **Sprint 7 阶段 7.3: 异常场景测试与健壮性** ✅
  - [x] 完成 `tests/e2e/test_error_scenarios.py`：覆盖超时、失败及部分成功场景。
  - [x] 完成 `tests/e2e/test_edge_cases.py`：覆盖空路由、无网关及极端 HAR 场景。
  - [x] 完成 `tests/e2e/test_concurrency.py`：验证并发流程执行及 GUI 重复点击防护。
  - [x] **E2E 测试总通过率：21/21 (100%)**

- [x] **Sprint 7 阶段 7.4: GUI响应优化** ✅
  - [x] 创建 `workers/diagnosis_worker.py`：实现后台异步诊断执行、取消支持及进度信号发射。
  - [x] 优化 `main_window.py`：增加取消按钮、进度条节流逻辑及窗口关闭时的任务确认。
  - [x] 优化 `widgets/report_viewer.py`：实现报告文件的异步后台加载，提升大体积 HTML 渲染性能。
  - [x] **GUI 启动时间验证：<3s**

- [x] **Sprint 7 阶段 7.5: 报告生成性能优化** ✅
  - [x] 优化 `html_builder.py`：增加 Jinja2 字节码缓存，提升模板编译速度；实现大文件流式写入。
  - [x] 优化 `reporting/templates/base.html`：使用 CSS 变量统一颜色定义，减少重复代码。
  - [x] 完成 `tests/benchmark/test_report_benchmark.py`：验证报告生成耗时（<5s）及文件大小（<5MB）。
  - [x] **基准测试通过率：2/2 (100%)**

- [x] **Sprint 7 阶段 7.6: Bug修复与代码质量提升** (待开始)

- [x] **Sprint 7 阶段 7.7: 最终集成验证** ✅
  - [x] 运行全量测试并验证覆盖率达标。
  - [x] 执行 mypy 和 ruff 静态检查。
  - [x] 编写跨模块集成测试 `tests/integration/test_full_integration.py`。
  - [x] 生成测试报告摘要 `docs/test_report.md`。

- [x] **Sprint 8 阶段 8.1: PyInstaller打包配置与构建** ✅
  - [x] 创建 `scripts/build.py`：配置 PyInstaller 单文件模式，包含隐藏导入和数据文件。
  - [x] 创建 `scripts/pack.py`：实现便携版 zip 包生成逻辑。
  - [x] 更新 `pyproject.toml`：补全所有 CLI 命令入口点。
  - [x] 创建 `assets/icon.ico`：应用程序图标占位符。

- [x] **Sprint 8 阶段 8.2: 安装包验证与签名** ✅
  - [x] 创建 `scripts/verify_build.py`：验证可执行文件存在性、大小及模块完整性。
  - [x] 仿真打包测试通过：GUI 产物约 17.68MB，CLI 模块导入成功。
  - [x] 修复了 `pack.py` 的路径计算逻辑和 `verify_build.py` 的模块引用问题。

- [x] **Sprint 8 阶段 8.3: 用户手册编写** ✅
  - [x] 编写 `docs/user_guide.md`：涵盖安装指南、功能说明及常见问题解答。
  - [x] 更新根目录 `README.md`：增加快速开始指南、功能亮点展示及文档索引链接。

- [x] **Raisecom MSG5200B CPE 新型号接入** ✅ (2026-05-12)
  - [x] 新增 `raisecom_msg5200b` 解析器与 `RaisecomMsg5200BParser`，依据 `templates/whole_config_5200b.txt` 与现网 XGE/RCIOS 4.3x 指纹与 5200A 互斥识别。
  - [x] `ConfigParserRegistry` 优先注册 5200B；`CpeCollector` 对 `raisecom_msg5200` / `raisecom_msg5200b` 共用采集命令模板。
  - [x] 单元测试：`tests/unit/services/parser/test_raisecom_msg5200b.py`（含 ``Product Version`` **423/433**、Software Version 不误判、兜底场景）。
- [x] **CPE Telnet deep-dive 断线修复** ✅ (2026-05-12)
  - [x] `cpe_collector`：`open_connection(term=vt100, cols/rows)` + EOF 立即失败；避免 telnetlib3 默认 `unknown` 终端与 SecureCRT 行为差异导致设备踢线，以及 EOF 后空转超时误判。
  - [x] 单元测试：`test_read_until_any_eof_raises`（`tests/unit/services/collector/test_cpe_collector.py`）。
  - [x] **5200B `su` 诊断 shell 提示符**：识别 busybox 单独一行 `#`（与 `bash-N.N#` 并列），`diagnose:` 命令读回显时同步支持；`TestCpeCollectorDiagnosticShellPrompt`；现网 deep-dive 验证 `diagnose:ip rule show` 等成功。
- [x] **CPE 凭证 YAML + CLI** ✅ (2026-05-12)
  - [x] `configs/cpe_credentials.example.yaml` 与默认 `configs/cpe_credentials.yaml`（已 `.gitignore`）；`cpe_credentials_loader` + `deep_dive --credentials-file`；`CpeCollectorConfig.testnode_password`。
  - [x] **通用视图口令**：`configs/cpe_view_credentials.example.yaml` / `cpe_view_credentials.yaml`（已 `.gitignore`）；`cpe_view_credentials_loader`；`CpeCollectorConfig.preset_view_passwords` + `_password_for_view`；CLI `--view-credentials-file`；GUI `deep_dive_tab` 合并与提示。
  - [x] **5200A/B 代际指纹**：`raisecom_msg5200.py` 中仅依据 ``Product Version`` 行值含 **423** 判 A、含 **433** 判 B（与 RCIOS/PV 规则并存；**不使用** ``Software Version``）。
- [x] **深度报告拓扑显示修复（PC节点/链路接口语义）** ✅ (2026-05-12)
  - [x] `deep_dive.py`：新增 `SystemInfoSnapshot -> topology input` 归一化，确保 PC `hostname/primary_ip/interfaces` 可入拓扑构建。
  - [x] `topology_builder.py`：`_find_tunnel_local_interface` 优先解析 `running-config` 中 `vxlan bind tunnel` 对应的本地 `ip address`，并在链路元数据中写入 `source_interface_name`。
  - [x] `reporting/templates/deep_dive.html`：节点展示上/下行路径与接口信息；链路一览新增“接口说明”列，减少“本地侧/对端跨网段”误解。
  - [x] 回归测试：`tests/unit/services/topology/test_topology_builder.py` + `tests/flow/test_deep_dive.py`（22 passed）。

- [x] **三命令产品线商用对齐（报告扉页 + CLI/GUI）** ✅ (2026-05-13)
  - [x] `spec/detail_function_design.md` 章节「〇」：`quick-check` / `business-diagnose` / `deep-dive` 对比表、成功判据、不包含项、证据层级 L1/L2/L3、退出码约定。
  - [x] `docs/user_guide.md`：标签页说明、业务路径诊断与深度诊断分节；`README.md` 链至 spec 章节。
  - [x] `report_delivery_context.py`：`ReportDeliveryPack`、`build_*_pack`；JSON/HTML 共用 `report_pack` 字典。
  - [x] `html_builder.py`：`build_quick_check_report` / `build_deep_dive_report` / `build_business_diagnosis_report` 注入 `report_pack`；联合诊断可由 `topology.report_pack` 覆盖（业务产品线）。
  - [x] `partials/report_product_header.html`；`quick_check.html`、`deep_dive.html`、`business_diagnosis.html` 引入扉页与导航。
  - [x] `quick_check.py`：`--format json` 写 `diagnosis` + `report_pack`；`epilog`；`FlowContext.output_format`。
  - [x] `business_diagnose.py`：JSON 顶层 `report_pack`；联合 HTML 注入 `topology.report_pack`（`product_line=business_diagnose`，`joint_mode=true`）；`epilog`。
  - [x] `deep_dive.py`：`epilog`；`deep_dive.html` 顺序：扉页 → 交付摘要（若有）→ 诊断摘要。
  - [x] GUI：`business_diagnose_tab.py` + `main_window` 注册「业务路径诊断」；`quick_check_tab` / `deep_dive_tab` 范围说明。
  - [x] 单测：`tests/unit/services/reporter/test_report_delivery_context.py`；`test_business_diagnose_cli` 断言 JSON 含 `report_pack`。

- [x] **联合 / 深度诊断：商用交付摘要（HTML 阅读层）** ✅ (2026-05-13)
  - [x] `src/sdwan_desktop/services/reporter/joint_commercial_delivery.py`：`CommercialDeliveryPayload`、`build_commercial_delivery_payload`（主叙述、核查表、隧道 peer ICMP 摘要、nf_conntrack 采样说明、PC 与 conntrack 源对齐提示、ipset/CDN 消歧、建议动作）。
  - [x] `business_diagnose.py`：联合诊断写 HTML 前将 `commercial_delivery` 注入 `topology_dict`。
  - [x] `deep_dive.py`：`step_report_gen` 同步注入；`pc_snapshot_included`；lazy import `_annotate_problem_nodes` 避免与 `business_diagnose` 循环依赖。
  - [x] `src/sdwan_desktop/reporting/templates/deep_dive.html`：快速导航锚点「交付摘要」、`#delivery` 区块（表格与列表呈现上述字段）。
  - [x] 单测：`tests/unit/services/reporter/test_joint_commercial_delivery.py`。

---

## 已记录需求（备忘，暂不开发）

| 编号 | 需求摘要 | 说明 |
|------|-----------|------|
| REQ-CRED-001 | 应用内「凭据管理」 | 在 GUI 或 CLI 子命令中维护 CPE 设备列表、**新增/删除设备**、编辑口令并**安全写回** `cpe_credentials.yaml` / `cpe_view_credentials.yaml`（文件锁、备份、权限、敏感信息不落日志等）。**当前**：仅支持手工编辑 YAML + 运行时按 IP/视图键读取合并；**无**内置 CRUD。用户确认暂不开发，后续迭代再评估。 |

---

## 技术决策记录

### PyInstaller 模块搜索路径最终方案
1. **显式路径声明**: 在 `scripts/build.py` 中使用 `--paths=src` 参数，确保 PyInstaller 在分析阶段就能正确识别项目模块结构。
2. **运行时路径注入**: 在 `main_window.py` 中增加了针对 `sys.frozen` 的多路径尝试逻辑，覆盖了 `_MEIxxxxxx` 临时目录和项目根目录等多种可能情况。
3. **入口点调整**: 坚持使用 `main_window.py` 作为直接入口，避开了 `__init__.py` 在打包环境下的相对导入陷阱。

### PyInstaller 打包权限警告处理
1. **主动清理旧产物**: 在 `scripts/build.py` 中增加了对 `dist/sdwan-diagnostic-gui.exe` 的预清理逻辑，尝试在 PyInstaller 写入前移除被占用的文件。
2. **延时重试机制**: 针对 Windows 环境下常见的 `PermissionError`，在删除失败后增加了 1 秒的缓冲期，给予操作系统释放文件句柄的时间。

### PyInstaller 入口点优化
1. **规避相对导入错误**: 将打包入口点从 `__init__.py` 调整为 `main_window.py`，彻底解决了在冻结环境下因缺少父包上下文导致的 `ImportError: attempted relative import with no known parent package`。
2. **路径兼容性增强**: 在 `main_window.py` 和 `__init__.py` 中均增加了针对 `sys.frozen` 状态的判断与路径注入逻辑，确保无论是直接运行源码还是运行打包后的 exe，都能正确定位到 `src` 目录。
3. **依赖显式声明**: 在 `scripts/build.py` 中增加 `--hidden-import=sdwan_desktop`，防止深层嵌套模块在静态分析时被遗漏。

### 打包环境路径与依赖修复
1. **虚拟环境一致性**: 确认所有打包操作必须在项目根目录的 `.venv` 环境中执行，以解决 `Pillow` 等依赖在不同 Python 解释器间不共享的问题。
2. **资源显式声明**: 在 `scripts/build.py` 中通过 `--add-data=src;src` 显式声明源码目录，防止动态导入模块在打包后丢失。

### Sprint 8 阶段 8.2 总结
1. **自动化验证**: 建立了基础的构建产物检查流程，确保打包后的文件符合预期（如体积限制）。
2. **依赖处理**: 解决了 `Pillow` 缺失导致的图标转换失败问题，以及 `pyside6` 在部分环境下的隐藏导入警告。
3. **路径健壮性**: 统一了脚本中相对于项目根目录的路径获取方式，增强了在不同运行环境下的兼容性。

---

## 验收结果

### 代码质量检查
- [x] 所有新增文件通过 `get_problems` 语法检查
- [x] 类型注解完整，符合 mypy 严格模式要求
- [x] 遵循 PEP 8 命名规范
- [x] 单元测试覆盖率达到预期标准

### 测试覆盖率
- [x] **Sprint 7 阶段 7.3 新增 8 个异常与边界测试用例，全部通过** ✅

---

## 下一步计划

### Sprint 8 阶段 8.4: 正式发布准备
1. 最终确认所有文档链接有效性。
2. 准备 GitHub Release 草稿及变更日志 (Changelog)。
3. 进行最后一次全量回归测试。

---

## 版本信息
- **项目版本**: 0.8.2-alpha
- **Python版本**: 3.13.2
- **规范版本**: SDWAN_SPEC.md v1.0
- **当前状态**: Sprint 8 阶段 8.3 ✅ 完成；三命令商用对齐与联合交付摘要已落地（2026-05-13）；准备进入阶段 8.4

---

## 变更记录
| 日期 | 变更内容 | 负责人 |
|------|---------|--------|
| 2026-05-13 | 三命令商用对齐：`report_delivery_context`、三 HTML 扉页、quick JSON、business JSON `report_pack`、GUI 业务路径诊断页；spec/user_guide/README | AI |
| 2026-05-13 | 联合/深度诊断 HTML：商用交付摘要（`joint_commercial_delivery` + `deep_dive.html` `#delivery`）；CLI 注入 `topology.commercial_delivery`；单测 `test_joint_commercial_delivery.py`；更新 memory-bank | AI |
| 2026-05-12 | deep-dive 报告：修复 PC 节点空值；拓扑节点补充上下行 IP/接口；CPE→Hub 本地侧优先 vxlan 绑定IP；更新 memory-bank | AI |
| 2026-05-12 | CPE Telnet：`cpe_collector` 使用 vt100+NAWS 尺寸、EOF 即失败；新增 `test_read_until_any_eof_raises`；更新 memory-bank | AI |
| 2026-05-12 | 更新 memory-bank：记录 CPE 双文件凭据与匹配流程；登记 REQ-CRED-001（应用内凭据管理/增删设备，暂不开发） | AI |
| 2026-04-28 | 修复 `windows.py` 中网卡信息采集回退逻辑，实现 `ipconfig` 解析器 | AI |
| 2026-04-28 | 验证一键体检流程在 WMI 失败时能正确采集系统信息并生成报告 | AI |
| 2026-04-28 | 修复 CLI 一键体检流程中的接口契约错误、工具注册缺失及 TCP/DNS 探测异常 | AI |
| 2026-04-28 | 验证 `sdwan-quick-check` 命令行功能运行正常并生成报告 | AI |
| 2026-04-28 | 完成用户手册 `docs/user_guide.md` 编写 | AI |
| 2026-04-28 | 更新项目主页 `README.md`，增加功能亮点与文档索引 | AI |
| 2026-04-28 | 优化打包脚本以处理 Windows 下的文件权限警告 | AI |
| 2026-04-28 | 解决 PyInstaller 打包后 `ModuleNotFoundError` 问题 | AI |
| 2026-04-28 | 修复 PyInstaller 打包后的相对导入崩溃问题 | AI |
| 2026-04-28 | 修复 PyInstaller 打包时的相对导入错误及图标格式问题 | AI |
| 2026-04-28 | 更新Sprint 8阶段8.2完成状态，版本升级至 0.8.2-alpha | AI |
| 2026-04-28 | 更新Sprint 8阶段8.1完成状态，版本升级至 0.8.1-alpha | AI |
| 2026-04-27 | 更新Sprint 7阶段7.7完成状态，版本升级至 0.7.7-alpha | AI |
| 2026-04-27 | 更新Sprint 7阶段7.5完成状态，版本升级至 0.7.5-alpha | AI |
| 2026-04-27 | 更新Sprint 7阶段7.4完成状态，版本升级至 0.7.4-alpha | AI |
| 2026-04-27 | 更新Sprint 7阶段7.3完成状态，版本升级至 0.7.3-alpha | AI |
| 2026-04-27 | 更新Sprint 7阶段7.2完成状态，版本升级至 0.7.2-alpha | AI |
| 2026-04-27 | 更新Sprint 7阶段7.1完成状态，版本升级至 0.7.1-alpha | AI |
| 2026-04-27 | 更新Sprint 6阶段6.8完成状态，版本升级至 0.6.8-alpha | AI |