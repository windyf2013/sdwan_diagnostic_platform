# 产品简介 (Product Brief)

**项目**: SD-WAN 桌面诊断专家  
**版本**: v0.2.0-alpha (Sprint 3 进行中)  
**目标平台**: Windows 10/11 x64

## 核心价值

一款面向运维人员的本地桌面工具，通过自动采集 Windows 网络配置并执行多维度连通性探测，快速定位 SD-WAN 环境中常见的网络故障（网关不可达、DNS 分流异常、国际链路丢包、代理配置错误等），输出结构化诊断报告。

## 诊断场景

- **一键体检**: 采集本机网卡/路由/DNS/代理/防火墙，检测网关、国内外连通性，输出 HTML 报告。
- **深度诊断** (规划中): 远程登录 CPE(客户前置设备)，解析厂商配置，构建网络拓扑，进行根因分析。
- **业务监测** (规划中): 用无头浏览器访问业务 URL，生成 HAR 瀑布图与性能瓶颈建议。

## 主要功能模块

| 模块 | 状态 | 说明 |
|------|------|------|
| 基础网络工具集 | ✅ 已交付 | Ping, Traceroute, TCPing, DNS, MTR, SSH, Telnet |
| 一键体检 (QuickCheck) | 📋 开发中 | 采集→探测→规则分析→报告 |
| 深度诊断 (DeepDive) | 规划 | PC+CPE 联合诊断 |
| 业务监测 (Waterfall) | 规划 | URL 性能分析 |

## 交付形式

- **CLI**: `agentctl quick-check` / `agentctl deep-dive` / `agentctl waterfall`
- **GUI** (规划): PySide6 桌面界面
- **报告**: HTML 文件（含结论、证据、建议、置信度）