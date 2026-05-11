# Sprint 6 完整开发流程计划
## 基础信息
- **指令 ID**: SPRINT-6-COMPLETE
- **指令名称**: Sprint 6 完整开发流程
- **依赖要求**: Sprint 2、Sprint 3、Sprint 4、Sprint 5 已完成

## 执行说明
请按以下顺序分步执行 Sprint 6 开发。每完成一个阶段后暂停，输出进度报告，等待确认后再继续下一阶段。

## 常用参考文档
- 开发任务详情: developing_tasks.md §7
- GUI架构设计: sdwan_analyzer_project.md §8.2
- 界面布局: developing_tasks.md §7.3

---

# 阶段 6.1: 主窗口框架与导航结构
## 输出文件
1. `src/sdwan_desktop/interface/gui/main_window.py`
   - MainWindow 类 (继承 QMainWindow)
   - `setup_ui()` 方法:
     - 创建 QTabWidget 作为中心组件
     - 预留 4 个标签页: 网络工具、一键体检、深度诊断、业务监测
     - 底部状态栏: 状态信息 + QProgressBar
   - 窗口属性: 标题 "SD-WAN桌面诊断专家", 最小尺寸 1000x700

2. `src/sdwan_desktop/interface/gui/__init__.py`
   - 导出 MainWindow 和启动函数 `main()`

3. `src/sdwan_desktop/interface/gui/resources.py` (可选)
   - 应用图标、样式资源

4. `tests/unit/gui/test_main_window.py`
   - 窗口创建和标签页切换测试

## 自检清单
- [ ] MainWindow 可正常实例化
- [ ] 4个标签页已创建 (可用空白QWidget占位)
- [ ] 状态栏显示 "就绪"
- [ ] 进度条初始隐藏

---

# 阶段 6.2: 网络工具标签页
## 输出文件
1. `src/sdwan_desktop/interface/gui/tabs/tools_tab.py`
   - ToolsTab 类 (继承 QWidget)
   - 组件:
     - QComboBox: 选择工具 (Ping, Traceroute, DNS, TCPing, MTR)
     - QLineEdit: 目标输入
     - 参数输入区 (动态切换，如count, port)
     - QPushButton: "执行"
     - QTextEdit: 只读输出区域 (等宽字体)
   - 逻辑:
     - 点击"执行" → 创建 ToolWorker 后台线程 → 调用 ToolDispatcher
     - 结果格式化显示在 QTextEdit
   - 支持通过工具注册表动态填充 QComboBox

2. `src/sdwan_desktop/interface/gui/workers/diagnosis_worker.py` (新增)
   - ToolWorker 类 (继承 QThread)
   - 信号: `tool_result_ready(Signal)`, `tool_error(Signal)`

3. `tests/unit/gui/tabs/test_tools_tab.py`

## 自检清单
- [ ] 工具列表从 ToolRegistry 动态获取
- [ ] 选择工具后参数区域自动切换
- [ ] 执行结果显示在输出区域
- [ ] 长任务不阻塞UI (使用后台线程)
- [ ] 错误信息友好显示

---

# 阶段 6.3: 一键体检标签页
## 输出文件
1. `src/sdwan_desktop/interface/gui/tabs/quick_check_tab.py`
   - QuickCheckTab 类 (继承 QWidget)
   - 组件:
     - 说明标签
     - QPushButton: "开始体检"
     - QLabel: 进度文本
     - QTableWidget: 检测结果表格 (列: 检测项, 状态, 详情)
     - QPushButton: "保存报告" (初始禁用)
   - 逻辑:
     - 点击"开始体检" → 创建 QuickCheckWorker → 执行 QuickCheckFlow
     - 进度更新: `worker.progress_signal` 更新 QLabel 和 QProgressBar
     - 完成: 填充表格, 启用"保存报告"

2. `src/sdwan_desktop/interface/gui/workers/diagnosis_worker.py` (扩展)
   - QuickCheckWorker 类 (继承 QThread)
   - 信号: `progress_updated(int, str)`, `diagnosis_completed(DiagnosisResult)`, `diagnosis_failed(str)`

3. `tests/unit/gui/tabs/test_quick_check_tab.py`

## 自检清单
- [ ] 点击按钮正确触发后台诊断
- [ ] 进度条反映实际执行状态
- [ ] 结果表格按严重程度排序
- [ ] "保存报告"按钮正常工作
- [ ] UI在诊断过程中不冻结

---

# 阶段 6.4: 深度诊断标签页
## 输出文件
1. `src/sdwan_desktop/interface/gui/tabs/deep_dive_tab.py`
   - DeepDiveTab 类 (继承 QWidget)
   - 组件:
     - CPE配置区域: QLineEdit (host, port, username, password)
     - QPushButton: "开始深度诊断"
     - QLabel: 进度文本
     - QTextEdit: 结果输出 (拓扑描述、根因列表)
     - QPushButton: "保存报告" (初始禁用)
   - 逻辑: 类似 QuickCheckTab, 调用 DeepDiveFlow

2. `src/sdwan_desktop/interface/gui/workers/diagnosis_worker.py` (扩展)
   - DeepDiveWorker 类

3. `tests/unit/gui/tabs/test_deep_dive_tab.py`

## 自检清单
- [ ] CPE连接参数正确传递
- [ ] 密码字段回显隐藏
- [ ] 诊断结果显示根因和拓扑摘要
- [ ] 出错时显示具体错误信息

---

# 阶段 6.5: 业务监测标签页
## 输出文件
1. `src/sdwan_desktop/interface/gui/tabs/waterfall_tab.py`
   - WaterfallTab 类
   - 组件:
     - QLineEdit: URL输入
     - QPushButton: "开始监测"
     - QLabel: 进度文本
     - QTextEdit: 结果摘要
     - QPushButton: "保存报告" (初始禁用)
   - 逻辑: 调用 WaterfallFlow

2. `src/sdwan_desktop/interface/gui/workers/diagnosis_worker.py` (扩展)
   - WaterfallWorker 类

3. `tests/unit/gui/tabs/test_waterfall_tab.py`

## 自检清单
- [ ] URL输入校验
- [ ] 监测完成后显示页面加载时间等关键指标
- [ ] 支持保存HTML报告

---

# 阶段 6.6: 报告预览组件与模板完善
## 输出文件
1. `src/sdwan_desktop/interface/gui/widgets/report_viewer.py`
   - ReportViewer 类 (继承 QWidget)
   - 内嵌 QWebEngineView 或 QTextBrowser
   - 加载并显示HTML报告
   - 支持导出和打印

2. 完善报告模板 (优化视觉和交互)
   - `templates/base.html`: 统一导航栏
   - `templates/quick_check.html`: 添加图表 (可选)
   - `templates/deep_dive.html`: 集成拓扑图渲染
   - `templates/waterfall.html`: 优化时序图交互

3. `tests/unit/gui/widgets/test_report_viewer.py`

## 自检清单
- [ ] 报告可在界面内正常预览
- [ ] 拓扑图和时序图正确渲染
- [ ] 支持报告导出保存
- [ ] 模板样式统一协调

---

# 阶段 6.7: 集成与GUI验收测试
## 输出文件
1. `tests/integration/test_gui_flow.py`
   - 模拟完整用户操作流程
   - 覆盖所有标签页的基本功能

2. 更新 `pyproject.toml`
   - 添加 console_scripts 入口: `sdwan-gui`

## 验收命令
```bash
# 启动GUI
python -m sdwan_desktop.interface.gui.main_window

# 或通过入口
sdwan-gui

# 运行GUI测试
pytest tests/unit/gui/ tests/integration/test_gui_flow.py -v
```

## 自检清单
- [ ] GUI 可正常启动 (无 crash)
- [ ] 所有工具可从界面独立调用
- [ ] 一键体检 / 深度诊断 / 业务监测可完整执行
- [ ] 报告可在界面内预览
- [ ] 报告可保存到本地文件
- [ ] 界面响应流畅，长任务不阻塞 UI
- [ ] 所有测试通过

---

# Sprint 6 完成标志
- ✅ 主窗口和 4 个功能标签页完整实现
- ✅ 后台工作线程机制正常工作
- ✅ 工具标签页动态加载已注册工具
- ✅ 所有诊断流程可在 GUI 中触发
- ✅ 报告预览和保存功能正常
- ✅ HTML 模板完善且风格统一
- ✅ GUI 测试通过
- ✅ 入口命令 sdwan-gui 可正常启动应用