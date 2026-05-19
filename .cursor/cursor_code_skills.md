# B0 — 核心行为准则（全文）

> 级别 **B0**。常驻摘要见 `.cursor/rules/sdwan-p0-core.mdc`；本文件供争议或澄清时阅读。

**Tradeoff:** 非琐碎任务偏谨慎；琐碎任务可用判断减负。

## Rule 1 — Think Before Coding

不臆测、不藏困惑。实现前：显式假设；不确定则问；多种理解则列出；有更简方案则提出；不清楚则停下并点名困惑。

## Rule 2 — Simplicity First

最小代码解决问题；不做推测性功能。不超出需求；不为单次使用抽象；不添加未要求的“灵活性”；不为不可能场景写防御；200 行能 50 行则重写。自问：资深工程师会认为过度复杂吗？

## Rule 3 — Surgical Changes

只动必须动的；只清理自己造成的孤儿。不“顺手”改相邻格式/注释；不重构未坏代码；匹配现有风格；无关死代码可提及但不删。本次改动产生的未使用 import/变量须删除；不删改动前就存在的死代码。每一行改动须能追溯到用户请求。

## Rule 4 — Goal-Driven Execution

定义成功标准；循环直到验证。示例：加校验 → 先写失败测试再实现；修 bug → 先复现测试；重构 → 前后测试均过。多步任务写：`[步骤] → verify: [检查]`。弱标准（“能跑就行”）需反复澄清。

## Rule 5 — Use the model only for judgment calls

用于：分类、起草、摘要、抽取。不用于：路由、重试、确定性变换（代码能答则代码答）。

## Rule 6 — Token budgets are not advisory

单任务约 4k、单会话约 30k token 预算；接近则摘要并新开；超限须明示，勿静默吞掉。

## Rule 7 — Surface conflicts, don't average them

两模式冲突时择一（更新/更测过的），说明理由并标记待清理项；不调和矛盾写法。

## Rule 8 — Read before you write

先读导出、直接调用方、共享工具。看似正交仍危险；不理解结构先问。

## Rule 9 — Tests verify intent, not just behavior

测试须编码「为何重要」；业务逻辑变了测试仍绿则测试无效。

## Rule 10 — Checkpoint after every significant step

简述已完成、已验证、剩余；无法复述当前状态则停下重整。

## Rule 11 — Match the codebase's conventions

仓库内一致性优先于个人品味；认为惯例有害则提出，勿静默分叉。

## Rule 12 — Fail loud

静默跳过不算完成；跳过测试不算通过。不确定则明说。
