# SD-WAN桌面诊断专家 - 功能设计详细方案

---

## 〇、三命令产品线定位（QuickCheck / BusinessDiagnose / DeepDive）

本节约定三条 CLI/GUI 流水线的**受众、证据边界、成功判据与升级路径**，与 HTML 报告扉页字段 `report_pack` 对齐；实现见 `sdwan_desktop.services.reporter.report_delivery_context`。

### 〇.1 对比总表

| 维度 | 一键体检 `sdwan-quick-check` / GUI「一键体检」 | 业务路径诊断 `sdwan-business-diagnose` / GUI「业务路径诊断」 | 深度诊断 `sdwan-deep-dive` / GUI「深度诊断」 |
|------|-----------------------------------------------|----------------------------------------------------------------|-----------------------------------------------|
| **受众** | 终端用户、一线自助 | 业务负责人、二线（针对**声明的一条业务**） | 运维/集成（CPE 与链路专检） |
| **主要输入** | 本机（可选流程参数） | `-b FQDN:端口`（可多组）；可选 `-S` DNS；失败或成功+CPE 时 `--cpe-host` 等 | CPE 管理地址与凭证；可选 `-b` 业务探测 |
| **输出物** | HTML（`quick_check.html`）；JSON 含 `report_pack` | 仅本机：`business_diagnosis.html`；联合 CPE：`deep_dive.html` + `commercial_delivery` | HTML（`deep_dive.html`） |
| **成功判据（产品语义）** | 流程跑完且生成报告；严重度由规则引擎汇总 | 声明目标 DNS/TCP 探测完成（可选 ICMP traceroute 作路径旁证，**不**单独决定「须联合」）；联合路径另含 CPE 采集与拓扑构建完成 | CPE 连接与采集（及探测步骤）按流程完成并出报告 |
| **刻意不包含** | CPE 配置解析、隧道 BFD、策略表逐项、对单条业务的 SLA 证明 | 全设备健康巡检、与声明业务无关的全量配置审计 | 不等价于「仅本机」体检；不替代业务方全链路压测 |
| **证据层级** | 以 **L1（本机探针与系统快照）** 为主 | **L1** + 联合时 **L2（CPE 侧采样：conntrack、ipset、隧道 peer ICMP 等）**；对端/运营商协同为 **L3** | **L2** 为主，叠加本机输入；**L3** 需对端配合时在报告中标注 |
| **升级路径** | 怀疑与某业务域名/端口相关 → `business-diagnose` | 需全设备配置/隧道/策略专检 → `deep-dive` | 仅需本机环境初判 → `quick-check` |

**表述原则**：对业务诊断采用「**以用户声明的探测目标为锚**」的证据链叙事，不承诺「绝不分析任何与业务无关的配置」——SD-WAN 转发面共享，但**默认排序与报告扉页**围绕声明目标。

### 〇.2 CLI 退出码约定（与实现对齐）

| 退出码 | 含义（约定） |
|--------|----------------|
| 0 | 成功完成并生成约定输出 |
| 2 | 参数/前置条件不满足（如业务失败且未提供 CPE 又未 `--allow-probe-only`） |
| 1 | 运行时错误、采集失败等其它失败 |

各命令在 `--help` 与 `report_pack.handoff_hint` 中提示升级路径；机器可读字段见 JSON 顶层 `report_pack`。

### 〇.3 与报告字段的对应

- `report_pack.product_line`：`quick_check` \| `business_diagnose` \| `deep_dive`。
- `report_pack.joint_mode`：业务联合诊断写 `deep_dive` 报告时为 `true`，其余为 `false`。
- `commercial_delivery`（仅联合业务模板）：业务阅读层归纳，与 `report_pack` 职责分离。

---

## 一、一键体检(QuickCheck)详细设计

### 1.1 信息采集清单

```python
# src/sdwan_desktop/services/collector/windows_collector.py

@dataclass
class SystemInfoSnapshot:
    """系统信息快照 - 一键体检采集的全部信息"""
    
    # 1. 网卡配置信息
    adapters: List[AdapterInfo]
    
    # 2. IP配置信息
    ip_config: IpConfigInfo
    
    # 3. 路由表信息
    routes: List[RouteInfo]
    
    # 4. DNS配置
    dns_config: DnsConfigInfo
    
    # 5. 代理配置
    proxy_config: ProxyConfigInfo
    
    # 6. 防火墙状态
    firewall_status: FirewallInfo
    
    # 7. ARP表
    arp_table: List[ArpEntry]
    
    # 8. 活动连接
    active_connections: List[ConnectionInfo]
```
### 1.2 探测目标与服务器选型

```python
# src/sdwan_desktop/config/probe_targets.py

@dataclass
class ProbeTargetSet:
    """探测目标集合"""
    
    # 国内DNS服务器 (用于国内解析测试)
    domestic_dns_servers: List[str] = field(default_factory=lambda: [
        "114.114.114.114",      # 114DNS
        "223.5.5.5",            # 阿里DNS
        "119.29.29.29",         # 腾讯DNS
    ])
    
    # 国际DNS服务器 (用于国际解析测试)
    international_dns_servers: List[str] = field(default_factory=lambda: [
        "8.8.8.8",              # Google DNS
        "1.1.1.1",              # Cloudflare DNS
        "208.67.222.222",       # OpenDNS
    ])
    
    # 连通性测试目标 (国内外混合)
    connectivity_targets: List[ProbeTarget] = field(default_factory=lambda: [
        # 国内目标
        ProbeTarget(host="www.baidu.com", protocol=ProbeProtocol.HTTP),
        ProbeTarget(host="www.qq.com", protocol=ProbeProtocol.HTTP),
        ProbeTarget(host="114.114.114.114", protocol=ProbeProtocol.ICMP),
        # 国际目标
        ProbeTarget(host="www.google.com", protocol=ProbeProtocol.HTTP),
        ProbeTarget(host="www.cloudflare.com", protocol=ProbeProtocol.HTTP),
        ProbeTarget(host="8.8.8.8", protocol=ProbeProtocol.ICMP),
    ])
    
    # DNS分流测试域名
    dns_split_domains: List[str] = field(default_factory=lambda: [
        "www.youtube.com",        # 应解析到国际互联网场景IP
        "www.tiktok.com",        # 应解析到国际直播场景IP
        "www.google.com",        # 应解析到国际IP
        "www.baidu.com",         # 应解析到国内IP
        "github.com",            # 国际
        "gitee.com",             # 国内
    ])
```

### 1.3 异常判断规则详细设计

```python
# src/sdwan_desktop/services/analyzer/quick_check_rules.py

class QuickCheckRuleEngine:
    """一键体检规则引擎"""
    
    def __init__(self):
        self.rules: List[DiagnosisRule] = []
        self._register_rules()
    
    def _register_rules(self):
        """注册所有检测规则"""
        
        # === 网卡相关规则 ===
        self.rules.append(DiagnosisRule(
            rule_id="ADAPTER-001",
            name="网卡未连接",
            condition=lambda ctx: not ctx.primary_adapter.is_connected,
            severity=Severity.CRITICAL,
            confidence=0.95,
            message="主网卡未连接",
            suggestion="请检查网线连接或WiFi是否已连接"
        ))
        
        self.rules.append(DiagnosisRule(
            rule_id="ADAPTER-002",
            name="网卡速度异常",
            condition=lambda ctx: ctx.primary_adapter.speed_mbps < 100,
            severity=Severity.WARNING,
            confidence=0.90,
            message=f"网卡协商速率过低 ({ctx.primary_adapter.speed_mbps}Mbps)",
            suggestion="建议检查网线质量或更换千兆网卡"
        ))
        
        # === IP配置规则 ===
        self.rules.append(DiagnosisRule(
            rule_id="IP-001",
            name="APIPA地址",
            condition=lambda ctx: ctx.ip_config.ip_address.startswith("169.254"),
            severity=Severity.CRITICAL,
            confidence=0.95,
            message="获取到自动配置IP地址(169.254.x.x)，DHCP可能失败",
            suggestion="检查DHCP服务器状态或手动配置静态IP"
        ))
        
        self.rules.append(DiagnosisRule(
            rule_id="IP-002",
            name="IP地址冲突",
            condition=lambda ctx: self._check_ip_conflict(ctx.arp_table),
            severity=Severity.ERROR,
            confidence=0.85,
            message="检测到IP地址冲突",
            suggestion="检查网络中是否有重复IP地址"
        ))
        
        # === 网关规则 ===
        self.rules.append(DiagnosisRule(
            rule_id="GW-001",
            name="网关不可达",
            condition=lambda ctx: not ctx.gateway_ping.success,
            severity=Severity.CRITICAL,
            confidence=0.95,
            message=f"无法Ping通网关 {ctx.ip_config.default_gateway}",
            suggestion="检查网关设备状态、防火墙规则或ARP绑定"
        ))
        
        self.rules.append(DiagnosisRule(
            rule_id="GW-002",
            name="网关延迟过高",
            condition=lambda ctx: ctx.gateway_ping.metrics.rtt_avg > 100,
            severity=Severity.WARNING,
            confidence=0.85,
            message=f"网关平均延迟 {ctx.gateway_ping.metrics.rtt_avg:.1f}ms",
            suggestion="检查网络负载或更换网关设备"
        ))
        
        self.rules.append(DiagnosisRule(
            rule_id="GW-003",
            name="网关丢包",
            condition=lambda ctx: ctx.gateway_ping.metrics.loss_rate > 0.05,
            severity=Severity.WARNING,
            confidence=0.80,
            message=f"网关丢包率 {ctx.gateway_ping.metrics.loss_rate*100:.1f}%",
            suggestion="检查物理链路质量或是否存在环路"
        ))
        
        # === DNS规则 ===
        self.rules.append(DiagnosisRule(
            rule_id="DNS-001",
            name="DNS服务器无响应",
            condition=lambda ctx: not ctx.dns_test.any_success,
            severity=Severity.ERROR,
            confidence=0.90,
            message="所有DNS服务器均无响应",
            suggestion="检查DNS服务器配置或使用公共DNS如114.114.114.114"
        ))
        
        self.rules.append(DiagnosisRule(
            rule_id="DNS-002",
            name="DNS响应慢",
            condition=lambda ctx: ctx.dns_test.avg_response_time > 500,
            severity=Severity.WARNING,
            confidence=0.80,
            message=f"DNS平均响应时间 {ctx.dns_test.avg_response_time:.0f}ms",
            suggestion="建议更换响应更快的DNS服务器"
        ))
        
        # === 路由表规则 ===
        self.rules.append(DiagnosisRule(
            rule_id="ROUTE-001",
            name="多条默认路由",
            condition=lambda ctx: len(ctx.routes.default_routes) > 1,
            severity=Severity.WARNING,
            confidence=0.85,
            message=f"存在 {len(ctx.routes.default_routes)} 条默认路由",
            suggestion="检查是否同时连接多个网络，可能导致路由冲突"
        ))
        
        self.rules.append(DiagnosisRule(
            rule_id="ROUTE-002",
            name="默认路由metric过高",
            condition=lambda ctx: ctx.routes.default_route.metric > 100,
            severity=Severity.INFO,
            confidence=0.75,
            message=f"默认路由Metric值为 {ctx.routes.default_route.metric}",
            suggestion="可适当降低Metric值以提高优先级"
        ))
        
        # === 代理规则 ===
        self.rules.append(DiagnosisRule(
            rule_id="PROXY-001",
            name="系统代理已启用",
            condition=lambda ctx: ctx.proxy_config.enabled,
            severity=Severity.INFO,
            confidence=0.95,
            message=f"系统代理已启用: {ctx.proxy_config.server}",
            suggestion="如非必要，建议关闭代理以避免流量被错误转发"
        ))
        
        self.rules.append(DiagnosisRule(
            rule_id="PROXY-002",
            name="代理不可达",
            condition=lambda ctx: ctx.proxy_config.enabled and not ctx.proxy_ping.success,
            severity=Severity.WARNING,
            confidence=0.85,
            message=f"代理服务器 {ctx.proxy_config.server} 不可达",
            suggestion="检查代理服务器状态或临时关闭代理"
        ))
        
        # === 防火墙规则 ===
        self.rules.append(DiagnosisRule(
            rule_id="FW-001",
            name="防火墙阻止ICMP",
            condition=lambda ctx: ctx.firewall_status.icmp_blocked,
            severity=Severity.INFO,
            confidence=0.80,
            message="Windows防火墙可能阻止了ICMP回显请求",
            suggestion="如需使用Ping功能，请允许'文件和打印机共享(回显请求-ICMPv4-In)'规则"
        ))
        
        # === 互联网连通性规则 ===
        self.rules.append(DiagnosisRule(
            rule_id="INET-001",
            name="国内网络不通",
            condition=lambda ctx: not ctx.connectivity.domestic_success,
            severity=Severity.ERROR,
            confidence=0.90,
            message="无法访问国内网站",
            suggestion="检查网络连接、DNS设置或ISP服务状态"
        ))
        
        self.rules.append(DiagnosisRule(
            rule_id="INET-002",
            name="国际网络不通",
            condition=lambda ctx: not ctx.connectivity.international_success,
            severity=Severity.WARNING,
            confidence=0.85,
            message="无法访问国际网站",
            suggestion="检查是否需要配置代理或VPN"
        ))
        
        self.rules.append(DiagnosisRule(
            rule_id="INET-003",
            name="国际链路丢包严重",
            condition=lambda ctx: ctx.connectivity.international_loss_rate > 0.10,
            severity=Severity.WARNING,
            confidence=0.80,
            message=f"国际链路丢包率 {ctx.connectivity.international_loss_rate*100:.1f}%",
            suggestion="国际链路质量较差，建议联系ISP或使用专线"
        ))
        
        # === DNS分流规则 ===
        self.rules.append(DiagnosisRule(
            rule_id="SPLIT-001",
            name="DNS分流异常",
            condition=lambda ctx: self._check_dns_split_anomaly(ctx),
            severity=Severity.WARNING,
            confidence=0.70,
            message="DNS解析结果与预期不符，可能存在DNS劫持或配置问题",
            suggestion="检查DNS设置，建议使用DoH/DoT加密DNS"
        ))
        
        # === IPv6规则 ===
        self.rules.append(DiagnosisRule(
            rule_id="IPV6-001",
            name="IPv6优先导致延迟",
            condition=lambda ctx: ctx.ipv6.enabled and ctx.ipv6.is_preferred,
            severity=Severity.INFO,
            confidence=0.75,
            message="IPv6已启用且优先级高于IPv4",
            suggestion="如果不需要IPv6，可在网卡属性中禁用"
        ))
```

### 1.4 规则上下文定义

```python
# src/sdwan_desktop/services/analyzer/rule_context.py

@dataclass
class QuickCheckContext:
    """一键体检规则评估上下文 - 聚合所有检测结果"""
    
    # 系统采集信息
    primary_adapter: AdapterInfo
    ip_config: IpConfigInfo
    routes: RouteTableInfo
    dns_config: DnsConfigInfo
    proxy_config: ProxyConfigInfo
    firewall_status: FirewallInfo
    arp_table: List[ArpEntry]
    ipv6: Ipv6Info
    
    # 探测结果
    gateway_ping: ProbeResult
    dns_test: DnsTestResult
    proxy_ping: Optional[ProbeResult]
    connectivity: ConnectivityTestResult
    
    # 计算属性
    @property
    def has_internet(self) -> bool:
        return self.connectivity.domestic_success
```

### 1.5 配置化设计

```yaml
# configs/quick_check.yaml

quick_check:
  # 采集配置
  collection:
    adapters: true
    routes: true
    dns: true
    proxy: true
    firewall: true
    arp: true
    ipv6: true
    active_connections: false  # 性能考虑，默认关闭
    
  # 探测目标
  targets:
    dns_servers:
      domestic:
        - 114.114.114.114
        - 223.5.5.5
      international:
        - 8.8.8.8
        - 1.1.1.1
    
    connectivity:
      domestic:
        - host: www.baidu.com
          type: http
        - host: www.qq.com
          type: http
        - host: 114.114.114.114
          type: icmp
      international:
        - host: www.google.com
          type: http
        - host: 8.8.8.8
          type: icmp
    
    dns_split_domains:
      - www.google.com
      - www.baidu.com
      - github.com
      
  # 阈值配置
  thresholds:
    gateway_rtt_warning_ms: 100
    gateway_rtt_critical_ms: 500
    gateway_loss_warning_pct: 5
    gateway_loss_critical_pct: 20
    dns_timeout_ms: 2000
    dns_slow_ms: 500
    international_loss_warning_pct: 10
    international_loss_critical_pct: 30
    
  # 规则开关
  rules_enabled:
    ADAPTER-001: true
    ADAPTER-002: true
    IP-001: true
    IP-002: true
    GW-001: true
    GW-002: true
    GW-003: true
    DNS-001: true
    DNS-002: true
    ROUTE-001: true
    PROXY-001: true
    FW-001: true
    INET-001: true
    INET-002: true
    INET-003: true
    SPLIT-001: true
```

---

## 二、深度诊断(DeepDive)配置解析设计

### 2.1 多厂商配置解析架构

```python
# src/sdwan_desktop/services/parser/vendor/__init__.py

from abc import ABC, abstractmethod
from typing import Dict, Type, Optional

class VendorConfigParser(ABC):
    """厂商配置解析器抽象基类"""
    
    @abstractmethod
    def get_vendor_name(self) -> str:
        """返回厂商名称"""
        pass
    
    @abstractmethod
    def detect_vendor(self, raw_output: str) -> bool:
        """检测是否为该厂商设备"""
        pass
    
    @abstractmethod
    def parse_version(self, raw_output: str) -> str:
        """解析软件版本"""
        pass
    
    @abstractmethod
    def parse_interfaces(self, raw_output: str) -> List[InterfaceInfo]:
        """解析接口信息"""
        pass
    
    @abstractmethod
    def parse_routes(self, raw_output: str) -> List[RouteEntry]:
        """解析路由表"""
        pass
    
    @abstractmethod
    def parse_sdwan_policies(self, raw_output: str) -> List[SdwanPolicy]:
        """解析SD-WAN策略"""
        pass
    
    @abstractmethod
    def parse_vpn_tunnels(self, raw_output: str) -> List[VpnTunnelInfo]:
        """解析VPN隧道状态"""
        pass
    
    @abstractmethod
    def parse_nat_rules(self, raw_output: str) -> List[NatRuleInfo]:
        """解析NAT规则"""
        pass


class ConfigParserRegistry:
    """配置解析器注册中心"""
    
    _parsers: Dict[str, VendorConfigParser] = {}
    
    @classmethod
    def register(cls, parser: VendorConfigParser) -> None:
        cls._parsers[parser.get_vendor_name()] = parser
    
    @classmethod
    def detect_and_parse(cls, raw_outputs: Dict[str, str]) -> CpeConfiguration:
        """自动检测厂商并解析"""
        for parser in cls._parsers.values():
            for cmd, output in raw_outputs.items():
                if parser.detect_vendor(output):
                    return parser.parse_all(raw_outputs)
        
        raise ValueError("无法识别设备厂商")
```

### 2.2.1 Raisecom MSG5200A/B 设备类型指纹（产品规则）

实现位置：`src/sdwan_desktop/services/parser/vendor/raisecom_msg5200.py` 中 `is_raisecom_msg5200b_version_output`、`is_raisecom_msg5200a_version_output`；5200B 专用解析器见同目录 `raisecom_msg5200b.py`。

**禁止**

- **不得**使用 `Software Version` 字段作为 MSG5200A / MSG5200B 类型指纹。5200B 的 `show version` / `show version all` 输出中**通常不包含** `Software Version`；该字段亦不作为可靠代际依据。版本字符串解析同样不得依赖 `Software Version` 作为回退来源。

**MSG5200B（`raisecom_msg5200b`，满足下列任一即判为 B；与 A 互斥）**

| 优先级 | 条件 |
|--------|------|
| 1 | `RCIOS version` 主版本为 `4.33.xxx` |
| 2 | `Product series` 行值**稳定包含子串** `433`（如 `P410_433_2511`） |
| 3 | `PV` 行为固定代际硬件版本 `B.00` |
| 4 | `Product Version` 行取值为固定 **`B.00`**（整字段匹配，**不**依据该行是否含 `433` 子串） |
| 5 | `Product series` 行为 `RCIOS_4.33`（若存在） |

**MSG5200A（`raisecom_msg5200`，显式指纹；排除 B 后由解析器 `detect_vendor` 兜底）**

| 优先级 | 条件 |
|--------|------|
| 1 | `RCIOS version` 主版本为 `4.23.xxx` |
| 2 | `Product Version` 行值含 `423`（历史形态如 `P410_423_xxxx`，与 B 的 `Product series` 中 `433` 区分） |
| 3 | `PV` 行为固定 **`A.00`** |
| 4 | `Product Version` 行取值为固定 **`A.00`** |
| 5 | `Product series` 行为 `RCIOS_4.23`（若存在） |

**说明**：5200A 的 `Product series` 在不同固件上**不一定出现或不稳定**，故**不**将「仅 `Product series` 行含 `423`」作为显式 A 指纹，避免误判。

**注册顺序**：全局 `ConfigParserRegistry` 中须**先注册** `raisecom_msg5200b`，再注册 `raisecom_msg5200`，保证 B 优先于 A 匹配。

### 2.2.2 业务主机探测服务（DNS A + TCP + 可选 Traceroute）

- **实现**：[`src/sdwan_desktop/services/probe/business_host_probe.py`](src/sdwan_desktop/services/probe/business_host_probe.py)（`BizDomainPortSpec`、`parse_biz_target_tokens`、`run_business_domain_port_probes`）；工具经 `ToolDispatcher` 调用已注册的 `dns` / `tcping` / `traceroute`。
- **行契约**：每行 `business_probes[]` 含 `domain`、`port`、`dns`、`tcp`；可选 `trace`（与解析 IPv4 对齐的列表，每项含 `host`、`port`（业务 TCP 端口，便于与 `tcp` 行对照）、`status`、`data`（成功时含 `summary`：`target_reached`、`total_hops`、`last_hop_ip` 等，及 `hops` 全量）、`error`。**聚合错误 `aggregate_error` 仅含 DNS/TCP 关键失败**；traceroute 失败或「未到达目标」写入 `trace` 行并打日志，**不**触发「须 CPE 联合」门控（ICMP 与 TCP 服务路径可能不一致）。
- **编排（仅探测）**：[`src/sdwan_desktop/services/diagnosis/business_diagnosis.py`](src/sdwan_desktop/services/diagnosis/business_diagnosis.py) 中 `orchestrate_business_domain_port_diagnosis`；可选 `compare_system_dns`：当传入 `--biz-dns-server` 时对同一域名追加**系统 DNS**与**显式 DNS**的 A 记录对照，结果写入每行 `dns_comparison.split_v4`。可选 `enable_traceroute`（CLI `--no-traceroute` 为关闭）。返回 `BusinessDiagnosisOutcome`（`status`、`business_probes`、`aggregate_error`），**不**内含根因列表，避免与 `RootCauseEngine` 重复归纳。
- **证据契约**：[`src/sdwan_desktop/core/types/business_rca.py`](src/sdwan_desktop/core/types/business_rca.py) 定义 `ObservationContext`、`ProbeBundle`、`Hypothesis`、`BusinessRCAFinding`；融合引擎 [`business_rca_engine.py`](src/sdwan_desktop/services/diagnosis/business_rca_engine.py)（`BusinessRCAEngine`、`HypothesisGenerator`）消费 PC 观测摘要 + `ProbeBundle`，输出带边界提示的 `RootCause`（如 **BIZ-CONF-001**、**BIZ-DNS-SPLIT-001**）。
- **路径层规则**：[`business_path_analyzer.py`](src/sdwan_desktop/services/diagnosis/business_path_analyzer.py)（`BusinessPathAnalyzer`）仍负责由 `business_probes` 行生成 **BIZ-DNS-001/002**、**BIZ-TCP-001** 等；`RootCauseEngine` 对 `business_probes` **仅经** `BusinessRCAEngine.analyze`，避免与旧版重复拼接。

### 2.2.3 独立 CLI：`sdwan-business-diagnose` / `agentctl business-diagnose`

- **入口**：[`src/sdwan_desktop/interface/cli/commands/business_diagnose.py`](src/sdwan_desktop/interface/cli/commands/business_diagnose.py)；控制台脚本 `sdwan-business-diagnose`（见 `pyproject.toml` `[project.scripts]`）。
- **探测失败后的强制路径**：当 **DNS 或 TCP** 任一未达「可视为通达」时（`business_probe_requires_joint_diagnosis`；**不含**仅 traceroute 异常），须继续 **CPE 采集 + 拓扑 + 拓扑后 CPE 命令 + `RootCauseEngine`**（与 deep-dive 证据链一致，实现见 [`business_diagnose_followup.py`](src/sdwan_desktop/services/diagnosis/business_diagnose_followup.py)）。须提供 `--cpe-host` / `-c` 与 `--username` / `-u`（及密码/密钥等，与 deep-dive 相同），否则 CLI **以退出码 2** 终止并提示命令行示例；**仅**接受本机探针层结论文档时显式加 `--allow-probe-only`。
- **参数（规范长名 / 短名）**：`--biz-target`（`-b`）、`--biz-dns-server`（`-S`）、`--no-traceroute`、`--output`（`-o`）、`--format`（`-F`）、`--collect-pc` / `--no-collect-pc`、`--cpe-host`（`-c`）、`--port` / `-p`（CPE 端口）、`--username` / `-u`、`--password`、`--key-file` / `-k`、`--protocol` / `-P`、`--credentials-file` / `-f`、`--view-credentials-file` / `-V`、`--allow-probe-only`、`--verbose`（`-v`）。
- **输出**：
  - **默认 HTML 文件名**（未指定 `-o` 时，写入 `./reports/`）：仅本机为 `business_probe_<YYYYMMDD_HHMMSS>.html`；联合且本机探测未通过为 `business_joint_postfailure_<…>.html`；联合且本机探测已通过（仍带 CPE 做核查）为 `business_joint_verify_<…>.html`。
  - 探测**全部成功**且**未**连接 CPE：HTML/JSON 为轻量业务报告（`hypotheses`、`root_causes` 经 `BusinessRCAEngine`）。
  - 探测失败且已完成联合分析，或探测成功但用户仍提供 CPE 并跑联合：HTML 复用 **deep_dive** 模板（含拓扑），但浏览器标题 / 扉页主标题 / `report_pack.product_title` 等与「深度诊断」区分（见 `business_diagnose._write_joint_deep_dive_style_report`、`deep_dive.html`）；JSON 含 `joint_diagnosis: true`、`topology`、`targeted_probe`（若存在）。
  - **Overlay / 隧道条带与根因过滤门控**：与 `compute_joint_overlay_datapath_gate`（`raisecom_msg5200b_session.py`，规则见 `docs/rules/product_features/raisecom_msg5200b_network_analysis.md` §5.2）对齐。`step-overlay-policy-flow` 是否执行、`underlay_declared_business_focus`、`_filter_business_joint_causes_for_datapath_accuracy` 是否保留 **CPE-002** / **OVERLAY-*** 等隧道库存类根因、以及 `topology_dict` 中 `business_joint_suppress_overlay_topology_presentation`、`declared_business_datapath_banner`、`declared_business_datapath_verdict` 等，均以 gate 的 `show_overlay_tunnel_strip` / `overlay_evidence_positive` 为准，**不得**仅用「nf_conntrack 是否有非空行」二分替代 5200B 会话规则。JSON 联合模式可额外输出 `joint_overlay_rule_case`（gate 的规则分支标识）。
  - **HTML 呈现**：联合报告页首「结论」区保持综述级判断（见同一规则文档中 HTML 呈现约定）；根因卡片须写清依据，5200B 会话/隧道启发式说明落在根因与证据链，不在结论区堆叠解释。
- **拓扑问题标记（`_annotate_problem_nodes`）**：**不得**在「声明业务路径已判定 ok」时以粗暴方式清空全部问题标记。须按根因类型补全判断：
  - 当 `targeted_probe.data.business_probes` 经 `_infer_business_failure_stage` 为 **ok** 时：**抑制** Underlay 上因 **CPE-003/CPE-004**（PC 主地址与策略/NAT 的启发式比对）及以 ``BIZ-DNS``、``BIZ-TCP`` 为前缀的根因所产生的 PC↔CPE 业务路径红段，避免与「探测已通」矛盾。
  - **仍保留** **CPE-001**（管理不可达）、**RAISECOM-LINK-PROT-001** 等基础设施/设备侧观测类根因在拓扑上的标记。
  - **CPE-002** 与以 ``OVERLAY-`` 为前缀的根因继续沿用 `joint_datapath_evidence_from_targeted_probe` + `path_beyond_tunnel_likely` 的既有抑制逻辑，不因「仅 business ok」整表抹掉隧道侧结论。
  - 每次标注前清除 `edges` / `layout_underlay_items` 上旧的 `problem` 字段，再按本轮 `causes` 重算，避免残留边与规则不一致。

### 2.2.4 深度诊断（`sdwan-deep-dive`）中的可选编排

- **目的**：拓扑构建之后，可选在 PC 侧执行业务探测，与 CPE 上 `plan_post_topology_probe_commands` 互补。
- **CLI**（与 §2.2.3 相同探测语义）：`--biz-target … (-b)`、`--biz-dns-server … (-S)`、`--no-traceroute`；CPE 连接等其余参数见 `sdwan-deep-dive --help`（规范名如 `--cpe-host`、`--username` 等）。
- **数据落点**：`topology.targeted_probe.data.business_probes`（与 `raw_outputs` 同信封）；业务相关根因由 `RootCauseEngine` 调用 `BusinessRCAEngine` 与 PC 快照/CPE 可达性融合生成；`analyze(..., trace_id=..., pc_snapshot=...)` 须传入以便证据引用。整体 `targeted_probe` 仍满足 `{status, data, error}` 契约。

### 2.2 厂商解析器实现示例

```python
# src/sdwan_desktop/services/parser/vendor/cisco_sdwan.py

import re
from typing import List, Dict

class CiscoSdwanParser(VendorConfigParser):
    """Cisco SD-WAN (Viptela) 配置解析器"""
    
    def get_vendor_name(self) -> str:
        return "cisco_sdwan"
    
    def detect_vendor(self, raw_output: str) -> bool:
        """通过show version输出检测"""
        indicators = [
            "Viptela", "vEdge", "cEdge", 
            "Cisco SD-WAN", "VEDGE"
        ]
        return any(ind.lower() in raw_output.lower() for ind in indicators)
    
    def parse_version(self, raw_output: str) -> str:
        """解析版本: 20.9.3"""
        pattern = r"Version\s+(\d+\.\d+\.\d+)"
        match = re.search(pattern, raw_output)
        return match.group(1) if match else "unknown"
    
    def parse_interfaces(self, raw_output: str) -> List[InterfaceInfo]:
        """解析show interface输出"""
        interfaces = []
        
        # 正则匹配接口块
        pattern = r"Interface\s+(\S+)[\s\S]+?(?=Interface|\Z)"
        
        for match in re.finditer(pattern, raw_output, re.MULTILINE):
            block = match.group(0)
            
            name = re.search(r"Interface\s+(\S+)", block).group(1)
            
            # 解析状态
            status_match = re.search(r"status:\s*(\S+)", block)
            status = status_match.group(1) if status_match else "unknown"
            
            # 解析IP
            ip_match = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", block)
            ip_address = ip_match.group(1) if ip_match else None
            
            # 解析MTU
            mtu_match = re.search(r"mtu\s+(\d+)", block)
            mtu = int(mtu_match.group(1)) if mtu_match else 1500
            
            interfaces.append(InterfaceInfo(
                name=name,
                ip_address=ip_address,
                status=status,
                mtu=mtu,
                raw_block=block
            ))
        
        return interfaces
    
    def parse_routes(self, raw_output: str) -> List[RouteEntry]:
        """解析show ip route输出"""
        routes = []
        
        # Cisco SD-WAN路由表格式
        # C    10.0.0.0/24 is directly connected, ge0/0
        # S*   0.0.0.0/0 [1/0] via 192.168.1.1, ge0/1
        
        lines = raw_output.strip().split('\n')
        
        for line in lines:
            # 跳过表头
            if not line.strip() or line.startswith('Codes:'):
                continue
            
            # 解析路由条目
            parts = line.strip().split()
            if len(parts) < 2:
                continue
            
            protocol_code = parts[0]
            destination = parts[1]
            
            # 解析下一跳和接口
            via_match = re.search(r"via\s+(\S+)", line)
            intf_match = re.search(r",\s*(\S+)$", line)
            
            routes.append(RouteEntry(
                destination=destination,
                gateway=via_match.group(1) if via_match else None,
                interface=intf_match.group(1) if intf_match else None,
                protocol=self._decode_protocol(protocol_code),
                raw_line=line
            ))
        
        return routes
    
    def parse_sdwan_policies(self, raw_output: str) -> List[SdwanPolicy]:
        """解析show sdwan policy输出"""
        policies = []
        
        # 解析策略名称和规则
        policy_pattern = r"Policy\s+(\S+)[\s\S]+?(?=Policy|\Z)"
        
        for match in re.finditer(policy_pattern, raw_output):
            block = match.group(0)
            
            name = re.search(r"Policy\s+(\S+)", block).group(1)
            
            # 解析匹配条件
            source_match = re.search(r"source-ip\s+(\S+)", block)
            dest_match = re.search(r"destination-ip\s+(\S+)", block)
            app_match = re.search(r"app-list\s+(\S+)", block)
            
            # 解析动作
            sla_match = re.search(r"sla-class\s+(\S+)", block)
            path_match = re.search(r"preferred-path\s+(\S+)", block)
            
            policies.append(SdwanPolicy(
                name=name,
                source=source_match.group(1) if source_match else "any",
                destination=dest_match.group(1) if dest_match else "any",
                application=app_match.group(1) if app_match else "any",
                sla_class=sla_match.group(1) if sla_match else None,
                preferred_path=path_match.group(1) if path_match else None,
                raw_block=block
            ))
        
        return policies
    
    def parse_vpn_tunnels(self, raw_output: str) -> List[VpnTunnelInfo]:
        """解析show sdwan bfd sessions / show ipsec ike sa"""
        tunnels = []
        
        # BFD会话解析 (Overlay状态)
        session_pattern = r"(\d+\.\d+\.\d+\.\d+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)"
        
        for line in raw_output.strip().split('\n'):
            match = re.search(session_pattern, line)
            if match:
                tunnels.append(VpnTunnelInfo(
                    remote_ip=match.group(1),
                    local_color=match.group(3),
                    remote_color=match.group(4),
                    state=match.group(5),
                    type="ipsec"
                ))
        
        return tunnels
    
    def parse_nat_rules(self, raw_output: str) -> List[NatRuleInfo]:
        """解析show ip nat translations"""
        nat_rules = []
        
        # NAT转换表格式
        # tcp 192.168.1.100:54321 203.0.113.10:54321 8.8.8.8:53 8.8.8.8:53
        
        for line in raw_output.strip().split('\n'):
            if not line.strip() or line.startswith('Pro'):
                continue
            
            parts = line.strip().split()
            if len(parts) >= 4:
                nat_rules.append(NatRuleInfo(
                    protocol=parts[0],
                    inside_addr=parts[1],
                    outside_addr=parts[2],
                    raw_line=line
                ))
        
        return nat_rules
    
    def parse_all(self, raw_outputs: Dict[str, str]) -> CpeConfiguration:
        """解析所有命令输出"""
        return CpeConfiguration(
            vendor=self.get_vendor_name(),
            model=self._detect_model(raw_outputs.get("show version", "")),
            version=self.parse_version(raw_outputs.get("show version", "")),
            hostname=self._detect_hostname(raw_outputs.get("show version", "")),
            interfaces=self.parse_interfaces(raw_outputs.get("show interface", "")),
            routes=self.parse_routes(raw_outputs.get("show ip route", "")),
            sdwan_policies=self.parse_sdwan_policies(raw_outputs.get("show sdwan policy", "")),
            vpn_tunnels=self.parse_vpn_tunnels(raw_outputs.get("show sdwan bfd sessions", "")),
            nat_rules=self.parse_nat_rules(raw_outputs.get("show ip nat translations", "")),
            raw_outputs=raw_outputs
        )
    
    def _decode_protocol(self, code: str) -> str:
        """解码路由协议代码"""
        mapping = {
            "C": "connected",
            "S": "static",
            "B": "bgp",
            "O": "ospf",
            "S*": "static_default",
            "B*": "bgp_default"
        }
        return mapping.get(code, "unknown")
    
    def _detect_model(self, version_output: str) -> str:
        """检测设备型号"""
        patterns = [
            r"vEdge-(\S+)",
            r"cEdge-(\S+)",
            r"VEDGE-(\S+)",
            r"Model\s+:\s+(\S+)"
        ]
        for pattern in patterns:
            match = re.search(pattern, version_output, re.I)
            if match:
                return match.group(1)
        return "unknown"
    
    def _detect_hostname(self, version_output: str) -> str:
        """检测主机名"""
        match = re.search(r"hostname\s+(\S+)", version_output, re.I)
        return match.group(1) if match else "unknown"
```

### 2.3 命令模板配置

```yaml
# configs/commands/cisco_sdwan.yaml

vendor: cisco_sdwan

# 采集命令模板
commands:
  # 基础信息
  - name: show version
    timeout: 30
    required: true
    parser: parse_version
    
  - name: show interface
    timeout: 60
    required: true
    parser: parse_interfaces
    
  # 路由信息
  - name: show ip route
    timeout: 30
    required: true
    parser: parse_routes
    
  - name: show ip route vrf 1
    timeout: 30
    required: false
    condition: "has_vrf"
    parser: parse_routes
    
  # SD-WAN信息
  - name: show sdwan policy
    timeout: 30
    required: true
    parser: parse_sdwan_policies
    
  - name: show sdwan bfd sessions
    timeout: 30
    required: true
    parser: parse_vpn_tunnels
    
  - name: show sdwan control connections
    timeout: 30
    required: true
    
  - name: show sdwan omp peers
    timeout: 30
    required: true
    
  - name: show sdwan tunnel statistics
    timeout: 30
    required: false
    
  # NAT信息
  - name: show ip nat translations
    timeout: 30
    required: false
    condition: "has_nat"
    parser: parse_nat_rules
    
  # 其他
  - name: show running-config
    timeout: 120
    required: false
    sensitive: true  # 包含敏感信息，不入报告
    
  - name: show logging
    timeout: 30
    required: false
    max_lines: 100   # 只取最后100行

# 命令执行顺序
execution_order:
  - parallel:
      - show version
      - show interface
  - sequential:
      - show ip route
      - show sdwan policy
      - show sdwan bfd sessions
      - show sdwan control connections
      - show sdwan omp peers
  - conditional:
      - show ip nat translations
      - show sdwan tunnel statistics

# 输出解析配置
parsing:
  # 接口过滤
  interface_filters:
    exclude_patterns:
      - "^Loopback"
      - "^Null"
      - "^Virtual"
    
  # 路由过滤
  route_filters:
    include_protocols:
      - connected
      - static
      - bgp
      - ospf
    exclude_networks:
      - "224.0.0.0/8"   # 组播
      - "127.0.0.0/8"   # 本地回环
```

### 2.4 配置解析结果模型

```python
# src/sdwan_desktop/core/types/cpe_config.py

@dataclass
class CpeConfiguration:
    """CPE配置解析结果 - 标准化模型"""
    
    # 设备信息
    vendor: str
    model: str
    version: str
    hostname: str
    
    # 接口列表
    interfaces: List[InterfaceInfo] = field(default_factory=list)
    
    # 路由表
    routes: List[RouteEntry] = field(default_factory=list)
    
    # SD-WAN策略
    sdwan_policies: List[SdwanPolicy] = field(default_factory=list)
    
    # VPN隧道
    vpn_tunnels: List[VpnTunnelInfo] = field(default_factory=list)
    
    # NAT规则
    nat_rules: List[NatRuleInfo] = field(default_factory=list)
    
    # 原始输出 (仅用于调试)
    raw_outputs: Dict[str, str] = field(default_factory=dict)
    
    # === 派生属性 ===
    
    @property
    def wan_interfaces(self) -> List[InterfaceInfo]:
        """获取WAN口列表"""
        wan_patterns = ["ge0/", "eth0", "wan", "GigabitEthernet0/"]
        return [
            iface for iface in self.interfaces
            if any(p in iface.name.lower() for p in wan_patterns)
        ]
    
    @property
    def lan_interfaces(self) -> List[InterfaceInfo]:
        """获取LAN口列表"""
        lan_patterns = ["ge0/1", "eth1", "lan", "Vlan"]
        return [
            iface for iface in self.interfaces
            if any(p in iface.name.lower() for p in lan_patterns)
        ]
    
    @property
    def default_route(self) -> Optional[RouteEntry]:
        """获取默认路由"""
        for route in self.routes:
            if route.destination in ["0.0.0.0/0", "default"]:
                return route
        return None
    
    @property
    def tunnel_status_summary(self) -> Dict[str, int]:
        """隧道状态汇总"""
        summary = {"up": 0, "down": 0, "unknown": 0}
        for tunnel in self.vpn_tunnels:
            state = tunnel.state.lower()
            if state in summary:
                summary[state] += 1
            else:
                summary["unknown"] += 1
        return summary
    
    def get_interface_by_ip(self, ip: str) -> Optional[InterfaceInfo]:
        """根据IP查找接口"""
        for iface in self.interfaces:
            if iface.ip_address == ip:
                return iface
        return None
    
    def get_routes_to(self, destination: str) -> List[RouteEntry]:
        """获取到目标的路由"""
        # 实现最长前缀匹配
        pass
```

### 2.5 拓扑构建服务

**模块路径**：`src/sdwan_desktop/services/topology/topology_builder.py`（`TopologyBuilder`）；报告富化：`src/sdwan_desktop/interface/cli/commands/deep_dive.py`（`_enrich_topology_report_dict`）；拓扑类型：`src/sdwan_desktop/services/topology/topology.py`。

**职责**：从 PC 扁平采集数据（`hostname` / `primary_ip` / `arp_table` 等）与 `CpeConfiguration` 构造 `NetworkTopology`。`TopologyBuilder.build(pc_data, cpe_result, cpe_mgmt_ip=…)` 中 **`cpe_mgmt_ip`** 为本次会话所用 CPE 管理地址（通常为 CLI `-c/--cpe`），用于在无二层附着证据时绘制 **会话可达（logical）** 的 PC→CPE 边。

#### Underlay / Overlay

| 平面 | 示意 | `LinkType` |
|------|------|-------------|
| Underlay | PC → CPE → 默认路由下一跳 | `PHYSICAL` 或 `LOGICAL` |
| Overlay | CPE 隧道入口（vxlan 等）→ Hub | `TUNNEL`（首条 `state != down` 隧道） |

#### PC → CPE（无 ICMP）

1. **`PHYSICAL`**：其一即可 —— CPE `arp_entries` 含本 PC IPv4 且映射到已知接口；或 PC `arp_table` 中默认网关 IPv4 的 MAC 与 CPE 某接口 MAC 一致。禁止仅凭「网关 IP 落在 CPE 某接口地址上」作为主要依据。
2. **`LOGICAL`**：不满足上条，但 **`cpe_result.success`** 且提供 **`cpe_mgmt_ip`** 时，`target_interface = cpe_mgmt_ip`；表示信息采集路径可达，**不表示**已通过 ARP/MAC 证明二层同 LAN。

#### CPE → 默认路由下一跳

按顺序判定（满足即止）并写入 `metadata.adjacency_evidence`：

1. **`cpe_arp_gateway`**：ARP 在所选默认路由的出口接口上对下一跳网关 IP 有可解析条目；→ `PHYSICAL`。
2. **`explicit_subnet_route`**：在同一出口上存在非默认 IPv4 前缀（长度 ≥ `/24`）同时覆盖本机 WAN 接口 IP 与下一跳；→ `PHYSICAL`。
3. **`slash24_heuristic`**：两地址同源 `/24`（弱推断）；→ `PHYSICAL`。
4. **`route_only`**：上述皆否；→ `LOGICAL`。

#### NAT 标注

沿用 `nat_rules`，当边 `source_interface` 命中 `inside_addr` 时设置 `Edge.is_nat` 等字段。

#### HTML 简报

Underlay / Overlay **分两横向行**（自左向右）。`topology.layout_underlay_items` 交织 **节点** 与 **hop**（箭头 + 简报，关联 `report_subnet_note`）；节点卡片内 **左栏上行 / 右栏下行** 接口清单。若无 Overlay：`topology.layout_overlay_placeholder` 占位说明。


---

## 三、配置管理设计

### 3.1 配置加载机制

```python
# src/sdwan_desktop/config/loader.py

class ConfigLoader:
    """配置加载器 - 支持多层级配置覆盖"""
    
    def __init__(self):
        self.config_cache: Dict[str, Any] = {}
    
    def load(
        self,
        config_name: str,
        env: str = "prod"
    ) -> Dict[str, Any]:
        """加载配置 (支持环境覆盖)"""
        
        # 1. 加载基础配置
        base_config = self._load_yaml(f"configs/{config_name}.yaml")
        
        # 2. 加载环境覆盖配置
        env_config_path = f"configs/{env}/{config_name}.yaml"
        if os.path.exists(env_config_path):
            env_config = self._load_yaml(env_config_path)
            base_config = self._deep_merge(base_config, env_config)
        
        # 3. 加载用户配置 (最高优先级)
        user_config_path = self._get_user_config_path(config_name)
        if os.path.exists(user_config_path):
            user_config = self._load_yaml(user_config_path)
            base_config = self._deep_merge(base_config, user_config)
        
        return base_config
    
    def _load_yaml(self, path: str) -> Dict[str, Any]:
        """加载YAML文件"""
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def _deep_merge(
        self,
        base: Dict[str, Any],
        override: Dict[str, Any]
    ) -> Dict[str, Any]:
        """深度合并配置"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
```

### 3.2 规则阈值配置

```yaml
# configs/thresholds.yaml

thresholds:
  # 网关相关
  gateway:
    rtt:
      warning_ms: 100
      critical_ms: 500
    loss:
      warning_pct: 5
      critical_pct: 20
    jitter:
      warning_ms: 30
      critical_ms: 100
  
  # DNS相关
  dns:
    timeout_ms: 2000
    slow_response_ms: 500
    failure_threshold_pct: 50  # 超过50%失败即判定异常
  
  # 连通性相关
  connectivity:
    domestic:
      success_threshold_pct: 80
      loss_warning_pct: 10
      loss_critical_pct: 30
      rtt_warning_ms: 100
      rtt_critical_ms: 300
    international:
      success_threshold_pct: 60
      loss_warning_pct: 15
      loss_critical_pct: 40
      rtt_warning_ms: 200
      rtt_critical_ms: 500
  
  # SD-WAN相关
  sdwan:
    tunnel_up_threshold_pct: 50  # 至少50%隧道UP
    bfd_loss_warning_pct: 5
    bfd_loss_critical_pct: 15
    policy_mismatch: critical   # 策略不匹配视为严重
    
  # 性能相关
  performance:
    http_slow_ms: 3000
    tcp_handshake_slow_ms: 500
    ssl_handshake_slow_ms: 1000
```

---

## 总结
**一键体检的详细设计包括**：

1. 明确的采集信息清单(SystemInfoSnapshot)
2. 固定的探测目标集合(国内外DNS、连通性目标)
3. 完整的异常判断规则(RuleEngine + 25+规则)
4. 可配置的阈值参数

**深度诊断的配置解析设计包括**：

1. 多厂商解析器架构(插件化)
2. 厂商特定的命令模板
3. 统一的配置解析结果模型
4. 拓扑构建服务(自动识别NAT层级、Overlay隧道)