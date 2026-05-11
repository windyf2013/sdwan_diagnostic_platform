# Sprint 4 完整开发指令

## 基本信息

-   **Sprint 名称**: 深度诊断 (DeepDive)
-   **周期**: 第5-6周 (80h)
-   **目标**: 实现 PC + CPE 联合诊断，包括 SSH/TELNET
    采集、配置解析、拓扑构建和根因分析
-   **前置依赖**: Sprint 2 SshAdapter, TelnetAdapter, Sprint 3 WindowsCollector

------------------------------------------------------------------------

## 指令信息

-   **指令 ID**: SPRINT-4-COMPLETE
-   **指令名称**: Sprint 4 完整开发流程
-   **依赖**: Sprint 2 和 Sprint 3 已完成

> 请按阶段顺序执行，每完成一个阶段需暂停并输出进度报告，等待确认后继续。

------------------------------------------------------------------------

## 常用参考文档

-   `developing_tasks.md §5`
-   `detail_function_design.md §2`
-   `detail_function_design.md §2.5`
-   `sdwan_analyzer_project.md §4.4`

------------------------------------------------------------------------

# 阶段 4.1：CPE 配置解析器架构（Week 5）

## 输出文件

1.  `src/sdwan_desktop/services/parser/vendor/__init__.py`
    -   VendorConfigParser 抽象基类
    -   ConfigParserRegistry 注册中心类
2.  `src/sdwan_desktop/core/types/cpe_config.py`
    -   CpeConfiguration 数据类
    -   InterfaceInfo, RouteEntry, SdwanPolicy, VpnTunnelInfo,
        NatRuleInfo
3.  `src/sdwan_desktop/services/parser/__init__.py`
    -   导出解析器 API

## 自检清单

-   [ ] VendorConfigParser 定义完整抽象方法
-   [ ] ConfigParserRegistry 支持自动检测厂商
-   [ ] CpeConfiguration 包含派生属性

------------------------------------------------------------------------

# 阶段 4.2：Cisco SD-WAN 解析器实现（Week 5）

## 输出文件

1.  `vendor/cisco_sdwan.py`
    -   CiscoSdwanParser 类
    -   实现解析方法（version / interfaces / routes / policies / vpn /
        nat）
2.  `configs/commands/cisco_sdwan.yaml`
    -   命令模板
3.  `tests/unit/services/parser/test_cisco_sdwan.py`

## 自检清单

-   [ ] detect_vendor() 正确识别设备
-   [ ] 正则解析准确
-   [ ] 失败有日志
-   [ ] 单测通过

------------------------------------------------------------------------

# 阶段 4.3：CPE 采集服务（Week 5）

## 输出文件

1.  `collector/cpe_collector.py`

    -   CpeCollector 类
    -   SSH/TELNET 采集 + 解析

2.  `collector/__init__.py`

3.  `test_cpe_collector.py`

## 自检清单

-   [ ] 自动识别厂商
-   [ ] 命令失败降级
-   [ ] 局部失败不影响整体
-   [ ] 敏感信息不入日志

------------------------------------------------------------------------

# 阶段 4.4：拓扑构建服务（Week 5）

## 输出文件

1.  `topology_builder.py`
    -   TopologyBuilder 类
    -   build() 方法
    -   \_detect_nat_traversal()
2.  `topology.py`
    -   NetworkTopology
    -   Node / Edge / 枚举
3.  `test_topology_builder.py`

## 自检清单

-   [ ] 节点构建完整（PC / CPE / GW / Hub）
-   [ ] 链路正确
-   [ ] NAT 识别准确
-   [ ] 可序列化

------------------------------------------------------------------------

# 阶段 4.5：根因分析引擎（Week 6）

## 输出文件

1.  `root_cause.py`
    -   RootCauseEngine
    -   analyze()

    覆盖故障：
    -   CPE-001: 不可达
    -   CPE-002: 隧道 Down
    -   CPE-003: 策略路由未生效
    -   CPE-004: NAT 不匹配
    -   OVERLAY-001: BFD Down
2.  `overlay_analyzer.py`
3.  `nat_detector.py`
4.  `test_root_cause.py`

## 自检清单

-   [ ] 使用 @service_function
-   [ ] 关联证据 ID
-   [ ] 覆盖 ≥5 种故障
-   [ ] 测试覆盖完整

------------------------------------------------------------------------

# 阶段 4.6：DeepDive Flow 与报告（Week 6）

## 输出文件

1.  `deep_dive.py`

    -   DEEP_DIVE_FLOW
    -   DeepDiveFlow 类

    流程： PC采集 → CPE连接 → CPE采集 → 配置解析 → 拓扑构建 → 根因分析 →
    报告生成

2.  `deep_dive.html`

    -   报告模板（含拓扑图）

3.  `topology.html`

    -   拓扑组件

4.  `html_builder.py`

    -   build_deep_dive_report()

5.  `deep_dive CLI`

    -   参数：--cpe --port --user --password

6.  `test_deep_dive.py`

## 自检清单

-   [ ] Flow 完整
-   [ ] 拓扑图正确
-   [ ] 报告包含配置对比
-   [ ] CLI 可执行
-   [ ] 测试覆盖 ≥70%
