# SD-WAN桌面诊断专家

一个面向Windows客户端的SD-WAN业务分析诊断平台，提供一键体检、深度诊断和业务监测功能。

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.10+-green)
![License](https://img.shields.io/badge/license-MIT-orange)

## 📸 界面预览

| 网络工具 | 一键体检 | 深度诊断 |
| :---: | :---: | :---: |
| ![Network Tools](docs/screenshots/tools_tab.png) | ![Quick Check](docs/screenshots/quick_check.png) | ![Deep Dive](docs/screenshots/deep_dive.png) |

| 业务监测 (Waterfall) | 报告预览 |
| :---: | :---: |
| ![Waterfall](docs/screenshots/waterfall.png) | ![Report](docs/screenshots/report.png) |

## ✨ 功能特性

### 基础工具集
- **Ping/Traceroute/TCPing**: 基础连通性与路由追踪。
- **DNS查询/MTR**: 域名解析与链路质量监测。
- **SSH/Telnet**: 远程设备连接支持。

### 一键体检 (QuickCheck)
- **自动巡检**: 5分钟内完成系统配置、网关、DNS及互联网连通性检查。
- **智能诊断**: 基于规则引擎自动识别根因并给出修复建议。
- **HTML报告**: 生成包含证据链和置信度的专业诊断报告。

### 深度诊断 (DeepDive)
- **联合分析**: 结合本地PC状态与CPE设备配置进行综合研判。
- **拓扑可视化**: 自动构建并展示 Overlay 隧道与底层链路拓扑。
- **厂商支持**: 原生支持 Cisco SD-WAN 及 Raisecom MSG5200。

### 业务监测 (Waterfall)
- **真实模拟**: 基于 Playwright 模拟浏览器行为，捕获全量资源请求。
- **性能瓶颈定位**: 自动标记渲染阻塞资源、慢速 DNS 及 TLS 握手延迟。

## 🚀 快速安装

### 方式一：安装包（推荐）
1. 下载最新的 `sdwan-diagnostic-setup.exe`。
2. 运行安装程序，按照提示完成安装。
3. 在开始菜单启动“SD-WAN桌面诊断专家”。

### 方式二：便携版
1. 下载 `sdwan-diagnostic-portable.zip`。
2. 解压到任意目录。
3. 双击 `sdwan-diagnostic-gui.exe` 即可运行。

### 方式三：开发者安装
```bash
git clone <repository_url>
cd sdwan_diagnostic_platform
pip install -e ".[dev]"
```

## 📖 使用文档

- **[用户手册 (User Guide)](docs/user_guide.md)**: 详细的安装指南、功能说明及常见问题解答。
- **[开发指南 (Developer Guide)](docs/developer_guide.md)**: 架构说明、扩展开发教程及发布流程。
- **[API 参考 (API Reference)](docs/api_reference.md)**: 核心数据契约与接口定义。

## 🛠️ 技术架构

项目采用分层架构设计，符合 SDWAN_SPEC 规范：

1. **Interface Layer** - CLI/GUI/API 入口
2. **Orchestration Layer** - 流程编排引擎 (Flow Engine)
3. **Service Layer** - 业务逻辑层 (Collector, Analyzer, Reporter)
4. **Tool Layer** - 工具抽象层 (Registry & Adapters)
5. **Core Layer** - 核心数据契约 (Data Contracts)

## 🤝 贡献指南

我们欢迎任何形式的贡献！
1. Fork 本项目
2. 创建您的功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交您的更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 开启一个 Pull Request

## 📄 许可证

本项目基于 MIT 许可证开源 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 📞 联系与支持

如有问题或建议，请通过以下方式联系：
- 提交 Issue
- 发送邮件至 support@sdwan-expert.com