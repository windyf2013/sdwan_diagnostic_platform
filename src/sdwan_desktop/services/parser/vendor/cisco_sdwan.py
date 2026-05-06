"""
Cisco SD-WAN (Viptela) 配置解析器

实现 Cisco SD-WAN 设备的配置解析，支持 vEdge/cEdge/Viptela 系列设备。
遵循 SDWAN_SPEC.md §2.4 工具系统规范
遵循 detail_function_design.md §2.2 厂商解析器实现示例
"""

import logging
import re
from typing import Dict, List, Optional

from sdwan_desktop.core.types.cpe_config import (
    CpeConfiguration,
    InterfaceInfo,
    NatRuleInfo,
    RouteEntry,
    SdwanPolicy,
    VpnTunnelInfo,
)
from sdwan_desktop.services.parser.vendor import VendorConfigParser

logger = logging.getLogger(__name__)


class CiscoSdwanParser(VendorConfigParser):
    """Cisco SD-WAN (Viptela) 配置解析器
    
    支持解析以下 Cisco SD-WAN 设备：
    - vEdge 系列
    - cEdge 系列
    - Viptela VEDGE 系列
    
    通过正则表达式解析 show version / show interface / show ip route 等命令输出。
    """
    
    def get_vendor_name(self) -> str:
        """返回厂商名称标识"""
        return "cisco_sdwan"
    
    def detect_vendor(self, raw_output: str) -> bool:
        """检测是否为 Cisco SD-WAN 设备
        
        通过检测版本输出中的特征字符串来识别设备。
        
        Args:
            raw_output: 设备命令输出（通常是 show version）
            
        Returns:
            True 如果检测到是 Cisco SD-WAN 设备
        """
        if not raw_output:
            return False
        
        indicators = [
            "viptela",
            "vedge",
            "cedge",
            "cisco sd-wan",
            "ios xe sdwan",
        ]
        
        output_lower = raw_output.lower()
        return any(ind in output_lower for ind in indicators)
    
    def parse_version(self, raw_output: str) -> str:
        """解析软件版本
        
        支持的格式：
        - Version 20.9.3
        - viptela-20.9.3
        - 20.9.3
        
        Args:
            raw_output: show version 命令输出
            
        Returns:
            版本号字符串，如 "20.9.3"，失败返回 "unknown"
        """
        if not raw_output:
            return "unknown"
        
        # 尝试多种版本匹配模式
        patterns = [
            r"[Vv]ersion\s+(\d+\.\d+\.\d+)",
            r"viptela-(\d+\.\d+\.\d+)",
            r"vedge-(\d+\.\d+\.\d+)",
            r"(\d+\.\d+\.\d+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, raw_output, re.IGNORECASE)
            if match:
                return match.group(1)
        
        logger.warning("无法解析 Cisco SD-WAN 版本信息")
        return "unknown"
    
    def _detect_model(self, raw_output: str) -> str:
        """检测设备型号
        
        Args:
            raw_output: show version 命令输出
            
        Returns:
            设备型号字符串，如 "vEdge-2000"，失败返回 "unknown"
        """
        if not raw_output:
            return "unknown"
        
        patterns = [
            r"[Vv][Ee][Dd][Gg][Ee]-([A-Za-z0-9_-]+)",
            r"[Cc][Ee][Dd][Gg][Ee]-([A-Za-z0-9_-]+)",
            r"[Mm]odel\s*:\s*([A-Za-z0-9_-]+)",
            r"[Pp]latform\s*:\s*([A-Za-z0-9_-]+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, raw_output, re.IGNORECASE)
            if match:
                # 提取完整型号（包括前缀）
                full_match = match.group(0)
                # 标准化格式：保留 VEDGE/cedge 前缀
                if "vedge" in full_match.lower():
                    prefix = "VEDGE"
                elif "cedge" in full_match.lower():
                    prefix = "cEdge"
                else:
                    prefix = ""
                
                model_suffix = match.group(1)
                return f"{prefix}-{model_suffix}" if prefix else model_suffix
        
        return "unknown"
    
    def _detect_hostname(self, raw_output: str) -> str:
        """检测主机名
        
        Args:
            raw_output: show version 或 show running-config 命令输出
            
        Returns:
            主机名字符串，失败返回 "unknown"
        """
        if not raw_output:
            return "unknown"
        
        # 从 hostname 配置行提取
        match = re.search(r"hostname\s+(\S+)", raw_output, re.IGNORECASE)
        if match:
            return match.group(1)
        
        # 从 prompt 提取（备选方案）
        match = re.search(r"([a-zA-Z0-9_-]+)#", raw_output)
        if match:
            return match.group(1)
        
        return "unknown"
    
    def parse_interfaces(self, raw_output: str) -> List[InterfaceInfo]:
        """解析接口信息
        
        解析 show interface 命令输出，提取接口名称、IP地址、状态、MTU等信息。
        
        Args:
            raw_output: show interface 命令输出
            
        Returns:
            InterfaceInfo 对象列表
        """
        interfaces = []
        
        if not raw_output:
            logger.warning("接口信息输出为空")
            return interfaces
        
        # 按行分割，查找以 "Interface" 开头的行作为新接口的开始
        lines = raw_output.split('\n')
        current_block_lines = []
        current_interface_name = None
        
        for line in lines:
            # 检测新的接口块开始
            interface_match = re.match(r'^\s*Interface\s+(\S+)', line)
            
            if interface_match:
                # 如果已有正在处理的接口块，先解析它
                if current_interface_name and current_block_lines:
                    block = '\n'.join(current_block_lines)
                    iface = self._parse_single_interface_block(current_interface_name, block)
                    if iface:
                        interfaces.append(iface)
                
                # 开始新的接口块
                current_interface_name = interface_match.group(1)
                current_block_lines = [line]
            elif current_interface_name:
                # 继续收集当前接口块的行
                current_block_lines.append(line)
        
        # 处理最后一个接口块
        if current_interface_name and current_block_lines:
            block = '\n'.join(current_block_lines)
            iface = self._parse_single_interface_block(current_interface_name, block)
            if iface:
                interfaces.append(iface)
        
        logger.info(f"成功解析 {len(interfaces)} 个接口")
        return interfaces
    
    def _parse_single_interface_block(self, name: str, block: str) -> Optional[InterfaceInfo]:
        """解析单个接口块
        
        Args:
            name: 接口名称
            block: 接口块的完整文本
            
        Returns:
            InterfaceInfo 对象，解析失败返回 None
        """
        try:
            # 提取状态
            status_match = re.search(r"(?:status|line protocol):\s*(.+)", block, re.IGNORECASE)
            status = "unknown"
            if status_match:
                status_raw = status_match.group(1).strip().lower()
                # 标准化状态值
                if "up" in status_raw and "down" not in status_raw:
                    status = "up"
                elif "administratively down" in status_raw or "admin down" in status_raw:
                    status = "down"
                elif "down" in status_raw:
                    status = "down"
            
            # 提取 IP 地址
            ip_match = re.search(r"(?:inet|IP address):\s*(\d+\.\d+\.\d+\.\d+)", block)
            ip_address = ip_match.group(1) if ip_match else None
            
            # 提取 MAC 地址
            mac_match = re.search(r"(?:Hardware address|MAC):\s*([0-9a-fA-F.:]{12,17})", block)
            mac_address = mac_match.group(1) if mac_match else None
            
            # 提取 MTU
            mtu_match = re.search(r"MTU\s+(\d+)", block, re.IGNORECASE)
            mtu = int(mtu_match.group(1)) if mtu_match else 1500
            
            # 提取描述
            desc_match = re.search(r"Description:\s*(.+)", block)
            description = desc_match.group(1).strip() if desc_match else None
            
            # 提取速度
            speed_match = re.search(r"(\d+)\s*(?:Mbps|Gb/s)", block)
            speed_mbps = None
            if speed_match:
                speed_val = int(speed_match.group(1))
                if "Gb" in speed_match.group(0):
                    speed_mbps = speed_val * 1000
                else:
                    speed_mbps = speed_val
            
            return InterfaceInfo(
                name=name,
                ip_address=ip_address,
                status=status,
                mtu=mtu,
                mac_address=mac_address,
                description=description,
                speed_mbps=speed_mbps,
                raw_block=block.strip(),
            )
            
        except Exception as e:
            logger.warning(f"解析接口块失败 [{name}]: {e}", exc_info=True)
            return None
    
    def parse_routes(self, raw_output: str) -> List[RouteEntry]:
        """解析路由表
        
        解析 show ip route 命令输出，提取目标网络、下一跳、出接口、协议等信息。
        
        Cisco SD-WAN 路由表格式示例：
        C    10.0.0.0/24 is directly connected, ge0/0
        S*   0.0.0.0/0 [1/0] via 192.168.1.1, ge0/1
        B    172.16.0.0/16 [200/0] via 10.1.1.1
        
        Args:
            raw_output: show ip route 命令输出
            
        Returns:
            RouteEntry 对象列表
        """
        routes = []
        
        if not raw_output:
            logger.warning("路由表输出为空")
            return routes
        
        lines = raw_output.strip().split('\n')
        
        for line in lines:
            # 跳过空行和表头
            if not line.strip() or line.startswith('Codes:') or line.startswith('Gateway'):
                continue
            
            try:
                parts = line.strip().split()
                if len(parts) < 2:
                    continue
                
                # 提取协议代码和目标网络
                protocol_code = parts[0]
                destination = parts[1]
                
                # 解码路由协议
                protocol = self._decode_protocol(protocol_code)
                
                # 提取下一跳网关
                via_match = re.search(r"via\s+(\d+\.\d+\.\d+\.\d+)", line)
                gateway = via_match.group(1) if via_match else None
                
                # 提取出接口
                intf_match = re.search(r",\s*(\S+)$", line)
                interface = intf_match.group(1) if intf_match else None
                
                # 提取度量值（如果有）
                metric_match = re.search(r"\[(\d+)/(\d+)\]", line)
                metric = int(metric_match.group(1)) if metric_match else 0
                
                routes.append(RouteEntry(
                    destination=destination,
                    gateway=gateway,
                    interface=interface,
                    metric=metric,
                    protocol=protocol,
                    raw_line=line.strip(),
                ))
                
            except Exception as e:
                logger.warning(f"解析路由条目失败: {line[:50]}... Error: {e}")
                continue
        
        logger.info(f"成功解析 {len(routes)} 条路由")
        return routes
    
    def _decode_protocol(self, code: str) -> str:
        """解码路由协议代码
        
        Args:
            code: 路由协议代码（如 C, S, B, O 等）
            
        Returns:
            协议名称字符串
        """
        mapping = {
            "C": "connected",
            "L": "local",
            "S": "static",
            "S*": "static_default",
            "B": "bgp",
            "B*": "bgp_default",
            "O": "ospf",
            "O*": "ospf_default",
            "R": "rip",
            "D": "eigrp",
            "EX": "eigrp_external",
            "i": "isis",
            "SU": "supernet",
            "OIA": "ospf_inter_area",
            "N1": "ospf_nssa_external_1",
            "N2": "ospf_nssa_external_2",
            "E1": "ospf_external_1",
            "E2": "ospf_external_2",
        }
        return mapping.get(code, f"unknown_{code}")
    
    def parse_sdwan_policies(self, raw_output: str) -> List[SdwanPolicy]:
        """解析SD-WAN策略
        
        解析 show sdwan policy 或 show policy ipv4 命令输出。
        
        Args:
            raw_output: SD-WAN 策略命令输出
            
        Returns:
            SdwanPolicy 对象列表
        """
        policies = []
        
        if not raw_output:
            logger.warning("SD-WAN 策略输出为空")
            return policies
        
        # 解析策略块：Policy <name> ... 到下一个 Policy 或结尾
        policy_pattern = r"Policy\s+(\S+)[\s\S]+?(?=Policy\s+\S+|\Z)"
        
        for match in re.finditer(policy_pattern, raw_output, re.MULTILINE | re.IGNORECASE):
            block = match.group(0)
            
            try:
                # 提取策略名称
                name_match = re.search(r"Policy\s+(\S+)", block, re.IGNORECASE)
                if not name_match:
                    continue
                name = name_match.group(1)
                
                # 提取源地址
                source_match = re.search(r"source(?:-ip)?\s+(\S+)", block, re.IGNORECASE)
                source = source_match.group(1) if source_match else "any"
                
                # 提取目的地址
                dest_match = re.search(r"destination(?:-ip)?\s+(\S+)", block, re.IGNORECASE)
                destination = dest_match.group(1) if dest_match else "any"
                
                # 提取应用列表
                app_match = re.search(r"app-list\s+(\S+)", block, re.IGNORECASE)
                application = app_match.group(1) if app_match else "any"
                
                # 提取 SLA 等级
                sla_match = re.search(r"sla-class\s+(\S+)", block, re.IGNORECASE)
                sla_class = sla_match.group(1) if sla_match else None
                
                # 提取首选路径
                path_match = re.search(r"preferred-path\s+(\S+)", block, re.IGNORECASE)
                preferred_path = path_match.group(1) if path_match else None
                
                # 提取备份路径
                backup_match = re.search(r"backup-path\s+(\S+)", block, re.IGNORECASE)
                backup_path = backup_match.group(1) if backup_match else None
                
                policies.append(SdwanPolicy(
                    name=name,
                    source=source,
                    destination=destination,
                    application=application,
                    sla_class=sla_class,
                    preferred_path=preferred_path,
                    backup_path=backup_path,
                    raw_block=block.strip(),
                ))
                
            except Exception as e:
                logger.warning(f"解析 SD-WAN 策略块失败: {e}", exc_info=True)
                continue
        
        logger.info(f"成功解析 {len(policies)} 条 SD-WAN 策略")
        return policies
    
    def parse_vpn_tunnels(self, raw_output: str) -> List[VpnTunnelInfo]:
        """解析VPN隧道状态
        
        解析 show sdwan bfd sessions 或 show ipsec ike sa 命令输出。
        
        BFD 会话格式示例：
        192.168.1.1  12345  blue  red  up
        10.0.0.1     67890  gold  silver  down
        
        Args:
            raw_output: VPN/BFD 会话命令输出
            
        Returns:
            VpnTunnelInfo 对象列表
        """
        tunnels = []
        
        if not raw_output:
            logger.warning("VPN 隧道输出为空")
            return tunnels
        
        # BFD 会话解析模式
        session_pattern = r"(\d+\.\d+\.\d+\.\d+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)"
        
        for line in raw_output.strip().split('\n'):
            # 跳过表头和空行
            if not line.strip() or line.startswith('REMOTE') or line.startswith('ADDR'):
                continue
            
            try:
                match = re.search(session_pattern, line)
                if not match:
                    continue
                
                remote_ip = match.group(1)
                # local_port = match.group(2)  # 可选字段
                local_color = match.group(3)
                remote_color = match.group(4)
                state = match.group(5).lower()
                
                # 标准化状态值
                if state in ["up", "active"]:
                    state = "up"
                elif state in ["down", "inactive", "init"]:
                    state = "down"
                
                tunnels.append(VpnTunnelInfo(
                    remote_ip=remote_ip,
                    local_color=local_color,
                    remote_color=remote_color,
                    state=state,
                    type="ipsec",
                ))
                
            except Exception as e:
                logger.warning(f"解析 VPN 隧道行失败: {line[:50]}... Error: {e}")
                continue
        
        logger.info(f"成功解析 {len(tunnels)} 条 VPN 隧道")
        return tunnels
    
    def parse_nat_rules(self, raw_output: str) -> List[NatRuleInfo]:
        """解析NAT规则
        
        解析 show ip nat translations 命令输出。
        
        NAT 转换表格式示例：
        Pro  Inside global      Inside local       Outside local      Outside global
        tcp  192.168.1.100:54321 203.0.113.10:54321 8.8.8.8:53         8.8.8.8:53
        
        Args:
            raw_output: NAT 转换表命令输出
            
        Returns:
            NatRuleInfo 对象列表
        """
        nat_rules = []
        
        if not raw_output:
            logger.warning("NAT 规则输出为空")
            return nat_rules
        
        for line in raw_output.strip().split('\n'):
            # 跳过表头和空行
            if not line.strip() or line.startswith('Pro') or line.startswith('---'):
                continue
            
            try:
                parts = line.strip().split()
                if len(parts) < 4:
                    continue
                
                protocol = parts[0].lower()
                inside_addr = parts[1]
                outside_addr = parts[2]
                
                # 判断 NAT 类型（简化：有固定映射为 static，否则为 dynamic）
                nat_type = "dynamic"
                if len(parts) >= 5 and parts[3] == parts[1]:
                    nat_type = "static"
                
                nat_rules.append(NatRuleInfo(
                    protocol=protocol,
                    inside_addr=inside_addr,
                    outside_addr=outside_addr,
                    nat_type=nat_type,
                    raw_line=line.strip(),
                ))
                
            except Exception as e:
                logger.warning(f"解析 NAT 规则行失败: {line[:50]}... Error: {e}")
                continue
        
        logger.info(f"成功解析 {len(nat_rules)} 条 NAT 规则")
        return nat_rules
    
    def parse_all(self, raw_outputs: Dict[str, str]) -> CpeConfiguration:
        """解析所有命令输出，构建完整的CPE配置对象
        
        Args:
            raw_outputs: 命令名称到输出的映射字典
                例如: {"show version": "...", "show interface": "..."}
                
        Returns:
            完整的 CpeConfiguration 对象
        """
        # 获取各命令输出
        version_output = raw_outputs.get("show version", "")
        interface_output = raw_outputs.get("show interface", "")
        route_output = raw_outputs.get("show ip route", "")
        policy_output = raw_outputs.get("show sdwan policy", "")
        tunnel_output = raw_outputs.get("show sdwan bfd sessions", "")
        nat_output = raw_outputs.get("show ip nat translations", "")
        
        # 解析各部分配置
        vendor = self.get_vendor_name()
        model = self._detect_model(version_output)
        version = self.parse_version(version_output)
        hostname = self._detect_hostname(raw_outputs.get("show running-config", version_output))
        
        interfaces = self.parse_interfaces(interface_output) if interface_output else []
        routes = self.parse_routes(route_output) if route_output else []
        sdwan_policies = self.parse_sdwan_policies(policy_output) if policy_output else []
        vpn_tunnels = self.parse_vpn_tunnels(tunnel_output) if tunnel_output else []
        nat_rules = self.parse_nat_rules(nat_output) if nat_output else []
        
        config = CpeConfiguration(
            vendor=vendor,
            model=model,
            version=version,
            hostname=hostname,
            interfaces=interfaces,
            routes=routes,
            sdwan_policies=sdwan_policies,
            vpn_tunnels=vpn_tunnels,
            nat_rules=nat_rules,
            raw_outputs=raw_outputs,
        )
        
        logger.info(
            f"Cisco SD-WAN 配置解析完成: "
            f"vendor={vendor}, model={model}, version={version}, "
            f"interfaces={len(interfaces)}, routes={len(routes)}, "
            f"policies={len(sdwan_policies)}, tunnels={len(vpn_tunnels)}, "
            f"nat_rules={len(nat_rules)}"
        )
        
        return config
