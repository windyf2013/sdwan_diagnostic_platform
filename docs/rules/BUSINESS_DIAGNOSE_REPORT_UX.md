# business-diagnose 联合报告：呈现 UX 规范

> **定位**：**项目规则库**（跨厂商）。约束 `business_joint_verify` / `business_topology_joint` 等 **deep_dive 骨架** 联合 HTML 的**可见信息密度**。  
> **原则**：**证据完整，显示简洁**——尤其**结论区**（页首、交付摘要、路径实证首屏）。

---

## 1. 分区职责总表

| 报告区域 | 简洁（默认可见） | 完整（须保留、可折叠） |
|----------|------------------|------------------------|
| **页首结论**（`report_joint_probe_outcome`） | 现象一句；主故障/「探测通过」；**【精确定位】/【启发式】** 前缀的一句路径结论；已排除（弱化，如「未见 Overlay 旁证」） | 逐跳 traceroute 表、完整 conntrack 样例、url-group 全文 → **证据链** 或 `<details>` |
| **商业交付摘要**（`joint_commercial_delivery` T0–T3） | 每档 **一行** 结论 + **一句** 说明 | 消歧列表、多段原始输出 → 证据链对应锚点 |
| **路径实证**（`datapath_banner` / `topology_joint_presentation`） | **≤2 句** + 层级标签（Underlay / Overlay）；`egress_shape` 分叉一句 | 长列表、重复隧道库存话术 → 证据链 |
| **拓扑主图** | Underlay 一句 +（门控为真时）Overlay 一句 | 链路一览全表、节点表、路径焦点长文 → 折叠或下部表格 |
| **根因卡片** | 标题 + 严重级别 + **一段** 摘要 | 证据引用块、命令原文、多段对照表 |
| **证据链** | 小节标题 + 2–3 行摘要（可选） | **完整**保留与本业务相关的 conntrack、mangle、ip rule、探测输出 |

---

## 2. 页首结论（强制）

### 2.1 应包含

- 用户可读的**现象**（如「本机访问 youtube.com 超时」或「本机探测已通过」）；
- **主故障**或明确「无故障 / 无需联合根因」；
- 与门控一致的**短路径结论**（走 Underlay / 可能或确定走 Overlay）；
- 置信度或 joint_needed 状态**一行**。

### 2.2 禁止出现在页首

- 完整 `show url-group` 列表（除非仅 1 条与声明域相关且为结论必要）；
- 重复「隧道库存」「全表 ipset」；
- 多段启发式推导过程（移至证据链）；
- 与当前结论矛盾的用语（如 conntrack「未见」与连接器标题「已采样」不一致——属缺陷，须修代码）。

### 2.3 verify 通过时的叙述

- 使用「本机探测已通过，不在 CPE/Hub 上标红」类表述；
- **禁止**「故障段示意」等暗示仍有 CPE 故障的措辞（除非 postfailure 或探测失败）。

---

## 3. 拓扑与链路表

| `show_business_flow_overlay` | 主图 Overlay 条带 | 链路一览 tunnel/hub 行 | Underlay 叙述 |
|:----------------------------:|:-----------------:|:----------------------:|:-------------:|
| false | 不展示 | 不展示 | **展示** |
| true | 展示 | 展示 | **展示**（在下或并列） |

链路表中 tunnel 行文案须与门控一致：verify 通过且未展示 Overlay 时，不得出现「Overlay 隧道（故障段）」类表述。

---

## 4. 交付摘要 T0–T3

| 档位 | 页首/表格式展示 | 完整证据 |
|------|-----------------|----------|
| T0 | 环境/采集是否就绪，一行 | 命令失败 stderr |
| T1 | conntrack **行数与结论一致**（禁止「1 行」叙述 vs 证据链 17 行矛盾） | 完整 grep 输出 |
| T2 | 策略/会话匹配结论一句 | 策略表节选 |
| T3 | 「是/否/本机探测」+ 一句原因 | SYN-only 等判定须基于 **TCP** 行解析 |

---

## 5. 精确定位 / 启发式标签

| 标签 | 使用场景 |
|------|----------|
| `【精确定位】` | 5200B D1/D2 或等价非 5200B 强证据（见产品门控文档） |
| `【启发式】` | 5200B D3、url-group 优先级补充、跳表旁证等 |
| （无标签） | 纯 Underlay、探测通过、无 Overlay 叠加 |

标签出现在**路径实证首句**或页首路径结论，**不**重复堆砌在每一表格单元格。

---

## 6. 与代码模块映射

| 模块 | 职责 |
|------|------|
| `topology_joint_presentation.py` | 生成 `datapath_banner`、路径焦点、链路表 flags；遵守 §3 |
| `joint_commercial_delivery.py` | T0–T3 文案与计数；遵守 §4 |
| `deep_dive_joint_ux.html` / `topology_detail_tables.html` | 页首与折叠结构；禁止 §2.2 |
| `business_diagnose.py` | 传入 `business_probe_all_ok`、`show_business_flow_overlay` 等呈现字段 |

**禁止**：在模板 Jinja 中嵌入 5200B 专有判定；仅使用上游已计算的布尔与 tier 字段。

---

## 7. 相关文档

- 三条流定位：[`THREE_FLOWS_PRODUCT_POSITIONING.md`](THREE_FLOWS_PRODUCT_POSITIONING.md)
- 5200B 门控真值表：[`product_features/raisecom_msg5200b_business_joint_gate.md`](product_features/raisecom_msg5200b_business_joint_gate.md)
- 5200B 网络背景：[`product_features/raisecom_msg5200b_network_analysis.md`](product_features/raisecom_msg5200b_network_analysis.md) §5.3
