## 持久化记忆规则 (Memory Bank)

本项目根目录下的 `memory-bank/` 文件夹用于存储 AI 的上下文记忆。
AI 在完成**每一轮显著的功能开发或 Bug 修复后**，必须自动执行以下操作：

1.  **读取** `memory-bank/progress.md` 了解历史进度。
2.  **更新** `memory-bank/progress.md`，记录**已完成**的工作和**下一步**计划。
3.  **更新** `memory-bank/activeContext.md`，记录当前最新的技术决策、API 变更或待解决问题。
4.  **必须使用** `write_to_file` 工具执行写入操作。

Memory Bank 文件结构：
- `productBrief.md`: 项目愿景、核心功能、目标用户。
- `techContext.md`: 所用技术栈、数据库表结构、关键配置。
- `systemPatterns.md`: 代码架构模式、关键组件关系。
- `activeContext.md`: **当前冲刺**的目标、最近变更的摘要。
- `progress.md`: **已完成**的功能清单、**当前状态**、**已知问题**。

## 记忆更新触发条件

- 当用户输入 `/update-memory` 时，强制执行 Memory Bank 更新流程。
- 当用户说 "提交代码前" 或 "今天先到这" 时，**建议**先执行 Memory Bank 更新。