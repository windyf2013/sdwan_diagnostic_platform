# Sprint 8 完整开发流程计划

## 基础信息
- **指令 ID**: SPRINT-8-COMPLETE
- **指令名称**: Sprint 8 完整开发流程
- **依赖**: Sprint 2、3、4、5、6、7 已完成

## 执行说明
请按以下顺序分步执行 Sprint 8 开发。每完成一个阶段后暂停，输出进度报告，等待我确认后再继续下一阶段。

## 常用参考文档
- 开发任务详情: developing_tasks.md §9
- 打包配置: sdwan_analyzer_project.md §8.3
- 发布检查清单: developing_tasks.md §9.3
- 安全与合规: SDWAN_SPEC.md §2.9、sdwan_analyzer_project.md §9

---

# 阶段 8.1: PyInstaller打包配置与构建
## 输出文件
1. `scripts/build.py`（或 `build.spec`）
- PyInstaller 打包配置
- 单文件模式（onefile）
- 包含隐藏导入: paramiko、playwright、jinja2、pyside6、wmi
- 数据文件: templates/、configs/
- 图标: assets/icon.ico
- 清理临时文件

2. `scripts/pack.py`
- 便携版打包脚本（生成zip包）
- MSI制作脚本（可选，使用 WiX Toolset 或类似）
- 版本信息注入

3. `pyproject.toml`（更新）
- [project.scripts] 添加:
  - agentctl = "sdwan_desktop.interface.cli.main:main"
  - sdwan-gui = "sdwan_desktop.interface.gui.main_window:main"

4. `.github/workflows/release.yml`（可选）
- CI/CD 自动构建流水线

## 构建产物
- sdwan-diagnostic-setup.exe（安装包）
- sdwan-diagnostic-portable.zip（便携版）
- sdwan-diagnostic-cli.exe（独立的CLI工具）

## 自检清单
- [ ] PyInstaller 打包成功，无遗漏依赖
- [ ] 生成的可执行文件可正常运行
- [ ] CLI 和 GUI 入口均可启动
- [ ] 资源文件（模板、配置）正确嵌入
- [ ] 便携版解压即可运行
- [ ] 文件大小在合理范围 (<200MB)
- [ ] 在干净的 Windows 10/11 上测试通过

---

# 阶段 8.2: 安装包验证与签名
## 输出文件
1. `scripts/verify_build.py`
- 验证打包产物完整性
- 检查版本信息
- 测试基础命令（--version、--help）

2. `scripts/sign_release.ps1`（或 `.bat`）
- 代码签名脚本（需要证书）

## 自检清单
- [ ] 安装包在 Win10/11 上正常安装
- [ ] 安装后 agentctl 和 sdwan-gui 可在命令行调用
- [ ] 卸载干净，无残留（检查 AppData、注册表）
- [ ] 数字签名有效（如有证书）
- [ ] 杀毒软件不误报（提交样本检查）

---

# 阶段 8.3: 用户手册编写
## 输出文件
1. `docs/user_guide.md`
- 安装指南（系统要求、安装步骤）
- 快速开始（首次使用）
- 功能说明:
  - 网络工具集（各工具用法）
  - 一键体检（操作步骤、报告解读）
  - 深度诊断（CPE连接、拓扑图说明）
  - 业务监测（URL监测、时序图解读）
- 常见问题（FAQ）
- 术语表

2. `docs/user_guide.pdf`（可选，由 markdown 生成）

3. `README.md`（更新）
- 项目概述
- 快速安装
- 基本使用
- 截图（GUI各标签页）
- 文档链接

## 自检清单
- [ ] 覆盖所有功能模块
- [ ] 安装步骤准确可执行
- [ ] 截图与当前版本一致
- [ ] 术语准确一致
- [ ] FAQ 覆盖已知常见问题

---

# 阶段 8.4: 开发文档与API参考
## 输出文件
1. `docs/developer_guide.md`
- 项目架构概览
- 开发环境搭建
- 分层设计说明
- 如何添加新工具
- 如何添加新厂商解析器
- 如何添加诊断规则
- 测试指南
- 发布流程

2. `docs/api_reference.md`
- 核心数据契约
- Tool Registry API
- Flow Engine API
- Reporter API
- CLI扩展接口

3. `docs/design_decisions.md`（可选）
- 架构决策记录（ADR）

## 自检清单
- [ ] 所有公开API有文档说明
- [ ] 示例代码可运行
- [ ] 架构图清晰
- [ ] 扩展开发文档符合实际代码

---

# 阶段 8.5: CHANGELOG与发布说明
## 输出文件
1. `CHANGELOG.md`
- 版本 1.0.0 记录
- 功能列表（按模块）
- 已知问题
- 致谢

2. `docs/release_notes/v1.0.0.md`
- 详细发布说明
- 新功能
- 改进
- 修复
- 升级提醒（如有破坏性变更）

3. `docs/screenshots/`（目录）
- 收集所有功能截图

## 自检清单
- [ ] CHANGELOG 遵循 Keep a Changelog 格式
- [ ] 包含所有 Sprint 2-7 完成的功能
- [ ] 版本号与 pyproject.toml 一致
- [ ] 已知问题列表真实有效

---

# 阶段 8.6: 最终验收测试与发布
## 验收测试清单
### 1. 功能验收
- [ ] agentctl --version 正确输出版本
- [ ] agentctl tool list 列出所有工具
- [ ] agentctl quick-check 可完整执行并生成报告
- [ ] agentctl deep-dive --cpe <IP> 可连接设备并诊断
- [ ] agentctl waterfall --url <URL> 可生成时序报告
- [ ] sdwan-gui 启动正常，所有标签页可用

### 2. 报告验收
- [ ] 一键体检HTML报告包含完整的6个章节
- [ ] 深度诊断报告包含拓扑图和配置对比
- [ ] Waterfall报告包含交互式时序图

### 3. 质量验收
- [ ] 测试覆盖率达标
- [ ] 代码质量检查通过
- [ ] 无已知 P0/P1 Bug

### 4. 打包验收
- [ ] 安装包正常安装/卸载
- [ ] 便携版解压即可运行
- [ ] 所有入口程序可启动

## 输出文件
1. `docs/acceptance_report.md`
- 验收测试结果
- 环境信息（OS、Python版本）
- 测试用例通过/失败统计
- 签字确认

## 自检清单
- [ ] 以上所有验收项通过
- [ ] 验收报告完成并签署
- [ ] 安装包已上传到发布位置

---

# 阶段 8.7: 发布与交付
## 任务说明
完成最终发布，包括:
1. 在 GitHub/GitLab 创建 Release
   - 关联 tag v1.0.0
   - 上传安装包和便携版
   - 粘贴 CHANGELOG 内容

2. 更新项目主页（如有）
   - 下载链接
   - 安装说明
   - 功能截图

3. 发布公告（内部/外部）
   - 邮件通知团队
   - 更新内部知识库

## 输出文件
1. `scripts/publish.py`（可选）
- 发布自动化脚本

## 自检清单
- [ ] Git tag v1.0.0 已创建
- [ ] Release 包含所有产物
- [ ] 下载链接可访问且校验和正确
- [ ] 文档链接指向正确版本
- [ ] 团队成员已通知

---

# Sprint 8 完成标志
- ✅ 安装包成功构建并测试
- ✅ 便携版/CLI独立版可用
- ✅ 用户手册完整准确
- ✅ 开发文档齐全
- ✅ CHANGELOG 已更新
- ✅ 最终验收通过
- ✅ 产品已发布到目标位置
- ✅ 项目正式进入维护阶段

---

# 附加说明
## 发布版本号
- 版本: 1.0.0
- 发布日期: 待定

## 产物清单
- sdwan-diagnostic-1.0.0-setup.exe
- sdwan-diagnostic-1.0.0-portable.zip
- 用户手册（PDF/Markdown）
- 校验和文件（sha256）

## 回滚方案
- 保留上一个稳定版本（0.4.0-alpha）
- 发布页面保留历史版本
- 数据库/配置文件向后兼容