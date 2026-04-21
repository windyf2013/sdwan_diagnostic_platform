# SD-WAN桌面诊断专家

一个面向Windows客户端的SD-WAN业务分析诊断平台，提供一键体检、深度诊断和业务监测功能。

## 功能特性

### 基础工具集
- Ping/Traceroute/TCPing/DNS查询/MTR/SSH/Telnet
- 实时探测结果与结构化输出

### 一键体检 (QuickCheck)
- Windows网络配置检查
- 基础连通性分析
- 配置异常检测
- HTML诊断报告生成

### 深度诊断 (DeepDive)
- PC+CPE联合分析
- 网络拓扑构建
- 根因定位
- 专业HTML报告

### 业务监测 (Waterfall)
- 单次URL访问Waterfall分析
- HAR可视化报告
- 性能瓶颈识别

## 技术架构

项目采用分层架构设计，符合SDWAN_SPEC规范：

1. **Interface Layer** - CLI/GUI/API入口
2. **Orchestration Layer** - 流程编排引擎
3. **Service Layer** - 业务逻辑层
4. **Tool Layer** - 工具抽象层
5. **Core Layer** - 核心数据契约
6. **Infra Layer** - 基础设施层

## 快速开始

### 安装依赖

```bash
# 使用uv（推荐）
uv venv
uv pip install -e .

# 或使用pip
pip install -e .
```

### 运行CLI

```bash
# 查看帮助
agentctl --help

# 一键体检
agentctl quick-check

# 深度诊断
agentctl deep-dive --cpe 192.168.1.1

# 业务监测
agentctl waterfall --url https://example.com
```

### 运行GUI

```bash
sdwan-gui
```

## 开发指南

### 项目结构

```
sdwan_diagnostic_platform/
├── spec/              # 规范层（最小集）
├── src/sdwan_desktop/ # 源代码
├── tests/             # 测试
├── configs/           # 环境配置
└── templates/         # 报告模板
```

### 代码规范

项目遵循以下规范：
- SDWAN_SPEC.md + SDWAN_SPEC_PATCHES.md
- 使用dataclass/pydantic定义数据结构
- 返回统一格式 `{status, data, error}`
- 使用logging，禁止print
- 函数包含类型注解和docstring
- trace_id全链路贯穿

### 开发工具

```bash
# 安装pre-commit钩子
pre-commit install

# 运行测试
pytest

# 代码格式化
ruff format src/

# 类型检查
mypy src/
```

## 许可证

MIT License

## 贡献指南

1. Fork项目
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建Pull Request