"""
RAISECOM MSG5200B 配置解析器

针对 Raisecom 5200B CPE：与 5200A 可能同为 MSG5200 系列型号，指纹以
``RCIOS version`` **4.33.xxx**、``Product series`` 行**稳定含子串 433**、``PV`` / ``Product Version`` 固定 **B.00** 等为主
（见 ``templates/whole_config_5200b.txt`` 与 ``spec/detail_function_design.md`` §2.2.1；**禁止**使用 ``Software Version``），
复用 MSG5200A 解析逻辑，仅 ``detect_vendor`` / ``get_vendor_name`` 区分。

**诊断视图**：5200B 在 enable 下进入 Linux 诊断 shell 的命令为 ``su``；5200A 为 ``diagnose``。
采集器仍统一使用 ``diagnose:`` 前缀逻辑命令，由 ``CpeCollector._enter_diagnose_view`` 按 ``raisecom_msg5200b`` / ``raisecom_msg5200`` 路由到 ``su`` 或 ``diagnose``。

**与 ``templates/whole_config_5200b.txt`` 对齐的数据契约（采集/补探由流程完成，用户不手填）**：

1. **Underlay 出口**：业务侧通常为 ``ge1``；主模板含 ``show interface ge1``。
2. **Overlay 接口**：vxlan / ipsec / l2tp / tunnel 等接口名由 ``raisecom_interface_discovery`` 根据
   ``running-config``、``show ip route``、``show link detect``、策略表输出推断后，在 enable 视图追加 ``show interface <ifname>``。
3. **NAT 现表**：诊断视图 ``cat /proc/rcios/net/netfilter/nf_conntrack | grep "<ip>"``（仅业务目的 IP；**禁止默认全量 conntrack**）。
4. **业务域名解析 IP 规则**：诊断视图 ``ipset --list``，由 ``plan_post_topology_probe_commands`` 作为补探下发。
5. **单目的 ``ip route get``**：设备暂不支持；由主路由 + ``ip rule`` + table 99/100 组合推断（预留）。
6. **隧道对端探针**：仅对 ``vpn_tunnels[].remote_ip`` 执行 ``ping -c 2``；**不对业务目的 IP 探针**。
7. **ACL/专用丢包统计**：当前不采集。
8. **PC 侧**：由既有 Windows 采集流程提供。

遵循 SDWAN_SPEC.md 工具与数据契约相关章节。
"""

from sdwan_desktop.services.parser.vendor.raisecom_msg5200 import (
    RaisecomMsg5200Parser,
    is_raisecom_msg5200b_version_output,
)


class RaisecomMsg5200BParser(RaisecomMsg5200Parser):
    """RAISECOM MSG5200B 系列（5200B CPE）配置解析器。"""

    def get_vendor_name(self) -> str:
        """返回厂商/型号标识，用于注册表与采集命令模板路由。"""
        return "raisecom_msg5200b"

    def detect_vendor(self, raw_output: str) -> bool:
        """检测是否为 MSG5200B（见 §2.2.1：RCIOS 4.33、series 含 433、PV/Product Version 为 B.00 等；与 5200A 互斥）。"""
        if not raw_output:
            return False
        lowered = raw_output.lower()
        base = any(x in lowered for x in ("raisecom", "msg5200", "rcios"))
        if not base:
            return False
        return is_raisecom_msg5200b_version_output(raw_output)
