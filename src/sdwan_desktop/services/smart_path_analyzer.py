"""
智能路径分析器 - 基于多维度特征动态识别CPE和分流点

核心功能：
1. IP地址段特征分析
2. RTT延迟突变检测
3. AS号变更识别（✅ Phase 2实现）
4. Hostname关键词匹配
5. 综合决策引擎
6. 部署模式分类
7. IP地理位置分析（✅ Phase 2实现）

设计原则：
- 多维度证据综合判断，避免单一特征误判
- 提供置信度评分和可解释性
- 支持降级策略确保始终有结果
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from .dns_split import TracerouteHopInfo
from .ip_geo_service import get_ip_geo_service

logger = logging.getLogger(__name__)


@dataclass
class PathAnalysisResult:
    """路径分析结果"""
    
    cpe_hop: int = 2
    """CPE设备所在跳数"""
    
    wan_exit_hop: int = 3
    """WAN出口跳数"""
    
    split_point_hop: int = 3
    """分流点跳数（通常=CPE+1）"""
    
    deployment_mode: str = "unknown"
    """部署模式: pc_side/gateway/upstream/unknown"""
    
    confidence: float = 0.3
    """判断置信度 (0.0-1.0)"""
    
    path_fingerprint: str = ""
    """智能路径指纹"""
    
    # ✅ 可解释性字段
    evidence: Dict[str, Any] = field(default_factory=dict)
    """原始证据数据"""
    
    reasoning: List[str] = field(default_factory=list)
    """推理过程说明"""
    
    alternative_candidates: List[Dict] = field(default_factory=list)
    """备选候选项"""


class SmartPathAnalyzer:
    """智能路径分析器"""
    
    def __init__(self):
        self.logger = logger
        
        # 证据权重配置
        self.evidence_weights = {
            "hostname_match": 4,      # Hostname匹配最可靠
            "as_number_change": 3,    # AS号变更很可靠
            "ip_range_transition": 3, # IP段变化较可靠
            "rtt_jump": 2,            # RTT突变中等可靠
            "default_fallback": 1     # 默认值最低可信度
        }
    
    def analyze(self, full_path: List[TracerouteHopInfo]) -> PathAnalysisResult:
        """
        综合分析路径，识别关键节点
        
        Args:
            full_path: 完整的Traceroute路径
            
        Returns:
            PathAnalysisResult包含CPE位置、分流点和部署模式
        """
        import time
        start_time = time.time()
        
        if not full_path:
            self.logger.warning("路径为空，使用降级策略")
            return self._fallback_analysis()
        
        try:
            # ✅ Phase 2: 首先填充IP地理位置和AS号信息
            geo_start = time.time()
            self._enrich_hops_with_geo_info(full_path)
            geo_time = (time.time() - geo_start) * 1000
            
            self.logger.debug(f"地理位置查询耗时: {geo_time:.1f}ms")
            
            # 1. 提取多维度特征
            feature_start = time.time()
            ip_features = self._identify_by_ip_range(full_path)
            rtt_feature = self._identify_by_rtt_jump(full_path)
            as_feature = self._identify_by_as_change(full_path)  # ✅ Phase 2启用
            hostname_features = self._identify_by_hostname(full_path)
            feature_time = (time.time() - feature_start) * 1000
            
            self.logger.debug(f"特征提取耗时: {feature_time:.1f}ms")
            
            # 2. 综合决策
            result = self._determine_cpe_and_split_point(
                full_path, ip_features, rtt_feature, as_feature, hostname_features
            )
            
            # 3. 生成智能路径指纹
            result.path_fingerprint = self._generate_smart_fingerprint(
                full_path, result.split_point_hop
            )
            
            total_time = (time.time() - start_time) * 1000
            
            # ✅ 生产环境日志：记录关键指标
            self.logger.info(
                f"✅ 智能路径分析完成 | "
                f"CPE={result.cpe_hop}跳 | "
                f"分流点={result.split_point_hop}跳 | "
                f"模式={result.deployment_mode} | "
                f"置信度={result.confidence:.2f} | "
                f"耗时={total_time:.1f}ms | "
                f"证据数={len(result.reasoning)}"
            )
            
            # ✅ 详细调试日志（仅DEBUG级别）
            if result.reasoning:
                self.logger.debug(
                    f"推理过程: {'; '.join(result.reasoning)}"
                )
            
            # ✅ 性能警告：如果耗时过长
            if total_time > 100:
                self.logger.warning(
                    f"⚠️ 智能路径分析耗时过长: {total_time:.1f}ms，建议优化"
                )
            
            # ✅ 低置信度警告
            if result.confidence < 0.5:
                self.logger.warning(
                    f"⚠️ 智能路径分析置信度较低: {result.confidence:.2f}，"
                    f"建议人工确认或使用更多证据"
                )
            
            return result
        
        except Exception as e:
            total_time = (time.time() - start_time) * 1000
            self.logger.error(
                f"❌ 智能路径分析失败: {e}，使用降级策略 | "
                f"耗时={total_time:.1f}ms",
                exc_info=True
            )
            return self._fallback_analysis(full_path)
    
    def _identify_by_ip_range(
        self, 
        hops: List[TracerouteHopInfo]
    ) -> Dict[str, List[int]]:
        """
        基于IP地址段识别网络层级
        
        Returns:
            {
                "private_lan": [1, 2],      # 私网LAN段
                "cpe_wan": [3],             # CPE WAN口
                "isp_core": [4, 5],         # ISP核心网
                "internet": [6, 7, ...]     # 互联网段
            }
        """
        candidates = {
            "private_lan": [],
            "cpe_wan": [],
            "isp_core": [],
            "internet": []
        }
        
        for hop in hops:
            if not hop.ip_addresses:
                continue
            
            ip = hop.ip_addresses[0]
            
            # 判断IP类型
            if self._is_private_lan(ip):
                candidates["private_lan"].append(hop.hop_number)
                hop.latency_class = "lan"
            elif self._is_isp_network(ip):
                candidates["isp_core"].append(hop.hop_number)
                hop.latency_class = "wan"
            elif self._is_public_internet(ip):
                candidates["internet"].append(hop.hop_number)
                hop.latency_class = "internet"
        
        return candidates
    
    def _identify_by_rtt_jump(
        self, 
        hops: List[TracerouteHopInfo]
    ) -> Optional[int]:
        """
        基于RTT延迟突变识别WAN出口
        
        Returns:
            WAN出口跳数，未检测到返回None
        """
        for i in range(1, len(hops)):
            prev_hop = hops[i-1]
            curr_hop = hops[i]
            
            if not prev_hop.rtts or not curr_hop.rtts:
                continue
            
            # 计算平均RTT
            prev_avg = sum(prev_hop.rtts) / len(prev_hop.rtts)
            curr_avg = sum(curr_hop.rtts) / len(curr_hop.rtts)
            
            # RTT突增超过阈值（如从5ms跳到20ms+），可能是WAN出口
            if curr_avg > prev_avg * 3 and curr_avg > 15:
                self.logger.debug(
                    f"检测到RTT突变: 第{prev_hop.hop_number}跳({prev_avg:.1f}ms) → "
                    f"第{curr_hop.hop_number}跳({curr_avg:.1f}ms)"
                )
                return curr_hop.hop_number
        
        return None
    
    def _identify_by_hostname(
        self, 
        hops: List[TracerouteHopInfo]
    ) -> Dict[str, List[int]]:
        """
        基于主机名关键词识别设备类型
        
        Returns:
            {
                "cpe_device": [3],          # CPE设备
                "isp_router": [4, 5],       # ISP路由器
                "cloud_provider": []        # 云服务商
            }
        """
        patterns = {
            "cpe_device": ["cpe", "router", "gateway", "edge"],
            "isp_router": ["isp", "core", "backbone", "ix", "net"],
            "cloud_provider": ["aws", "azure", "aliyun", "tencent"]
        }
        
        result = {key: [] for key in patterns.keys()}
        
        for hop in hops:
            if not hop.hostnames:
                continue
            
            hostname = hop.hostnames[0].lower()
            
            for device_type, keywords in patterns.items():
                if any(keyword in hostname for keyword in keywords):
                    result[device_type].append(hop.hop_number)
                    self.logger.debug(
                        f"Hostname匹配: 第{hop.hop_number}跳({hostname}) → {device_type}"
                    )
        
        return result
    
    def _determine_cpe_and_split_point(
        self,
        full_path: List[TracerouteHopInfo],
        ip_features: Dict[str, List[int]],
        rtt_feature: Optional[int],
        as_feature: Optional[int],
        hostname_features: Dict[str, List[int]]
    ) -> PathAnalysisResult:
        """综合所有特征，确定CPE位置和分流点"""
        
        scores: Dict[int, float] = {}
        reasoning = []
        
        # 策略1: 基于IP段变化（私网→ISP核心的过渡点）
        private_lan_hops = ip_features.get("private_lan", [])
        isp_core_hops = ip_features.get("isp_core", [])
        
        if private_lan_hops and isp_core_hops:
            last_private = max(private_lan_hops)
            first_isp = min(isp_core_hops)
            
            # CPE通常在最后一个私网跳或第一个ISP跳
            scores[last_private] = scores.get(last_private, 0) + self.evidence_weights["ip_range_transition"]
            scores[first_isp] = scores.get(first_isp, 0) + self.evidence_weights["ip_range_transition"] - 1
            
            reasoning.append(
                f"IP段变化: 私网最后跳={last_private}, ISP第一跳={first_isp}"
            )
        
        # 策略2: 基于RTT突变
        if rtt_feature:
            scores[rtt_feature] = scores.get(rtt_feature, 0) + self.evidence_weights["rtt_jump"]
            reasoning.append(f"RTT突变: 第{rtt_feature}跳延迟显著增长")
        
        # 策略3: 基于AS变更（Phase 2实现）
        if as_feature:
            scores[as_feature] = scores.get(as_feature, 0) + self.evidence_weights["as_number_change"]
            reasoning.append(f"AS号变更: 第{as_feature}跳跨越网络边界")
        
        # 策略4: 基于Hostname
        cpe_hops = hostname_features.get("cpe_device", [])
        for hop_num in cpe_hops:
            scores[hop_num] = scores.get(hop_num, 0) + self.evidence_weights["hostname_match"]
            reasoning.append(f"Hostname匹配: 第{hop_num}跳识别为CPE设备")
        
        # 选择得分最高的跳作为CPE
        if scores:
            cpe_hop = max(scores, key=scores.get)
            total_score = scores[cpe_hop]
            confidence = min(total_score / 10.0, 1.0)
        else:
            # 降级策略：默认第2跳
            cpe_hop = 2
            confidence = 0.3
            reasoning.append("无有效证据，使用默认值（第2跳）")
        
        # 确定分流点（通常在CPE之后1跳）
        split_point_hop = cpe_hop + 1
        wan_exit_hop = cpe_hop + 1
        
        # 判断部署模式
        private_lan_count = len(ip_features.get("private_lan", []))
        deployment_mode = self._classify_deployment_mode(cpe_hop, private_lan_count)
        
        # 构建备选候选项
        alternative_candidates = [
            {"hop": hop, "score": score, "reason": f"得分={score}"}
            for hop, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)[1:3]
        ]
        
        return PathAnalysisResult(
            cpe_hop=cpe_hop,
            wan_exit_hop=wan_exit_hop,
            split_point_hop=split_point_hop,
            deployment_mode=deployment_mode,
            confidence=confidence,
            evidence={
                "ip_features": ip_features,
                "rtt_feature": rtt_feature,
                "as_feature": as_feature,
                "hostname_features": hostname_features,
                "scores": scores
            },
            reasoning=reasoning,
            alternative_candidates=alternative_candidates
        )
    
    def _classify_deployment_mode(
        self, 
        cpe_hop: int, 
        private_lan_count: int
    ) -> str:
        """
        分类部署模式
        
        Returns:
            "pc_side"   - PC侧分流（CPE在第1跳，软件客户端直接分流）
            "gateway"   - 网关分流（CPE在第2-3跳，传统SD-WAN网关）
            "upstream"  - 上层设备分流（CPE在第4跳及以上，运营商级部署）
            "unknown"   - 无法判断
        """
        if cpe_hop == 1:
            return "pc_side"
        elif cpe_hop <= 3:
            return "gateway"
        elif cpe_hop >= 4:
            return "upstream"
        else:
            return "unknown"
    
    def _generate_smart_fingerprint(
        self, 
        full_path: List[TracerouteHopInfo],
        split_point_hop: int
    ) -> str:
        """生成带有业务语义的路径指纹"""
        
        # 从分流点开始取前6跳
        post_split_hops = [
            hop for hop in full_path 
            if hop.hop_number >= split_point_hop
        ][:6]
        
        fingerprint_parts = []
        for hop in post_split_hops:
            if hop.ip_addresses:
                ip_str = hop.ip_addresses[0]
            elif hop.is_timeout:
                ip_str = "T"
            else:
                ip_str = "?"
            
            # 添加跳数和IP
            part = f"{hop.hop_number}:{ip_str}"
            
            # 如果有AS号，也加入指纹（Phase 2）
            if hop.as_number:
                part += f"(AS{hop.as_number})"
            
            fingerprint_parts.append(part)
        
        return "->".join(fingerprint_parts) if fingerprint_parts else "无有效跳点"
    
    def _enrich_hops_with_geo_info(self, hops: List[TracerouteHopInfo]):
        """
        ✅ Phase 2: 为每个跳点填充IP地理位置和AS号信息
        
        使用IPGeoService查询每个跳点的：
        - AS号
        - 国家/地区
        - 运营商
        - 城市
        
        Args:
            hops: Traceroute跳点列表
        """
        geo_service = get_ip_geo_service()
        
        for hop in hops:
            if not hop.ip_addresses:
                continue
            
            ip = hop.ip_addresses[0]
            
            # 跳过超时或无效IP
            if ip in ["*", "T", "?"]:
                continue
            
            # 查询IP地理信息
            geo_info = geo_service.query_ip(ip)
            
            if geo_info:
                # 填充到hop对象
                hop.as_number = geo_info.get("as_number")
                hop.country = geo_info.get("country")
                hop.isp = geo_info.get("isp")
                
                self.logger.debug(
                    f"第{hop.hop_number}跳 {ip}: "
                    f"AS{hop.as_number or 'N/A'}, "
                    f"{hop.country or 'N/A'}, "
                    f"{hop.isp or 'N/A'}"
                )
    
    def _identify_by_as_change(self, hops: List[TracerouteHopInfo]) -> Optional[int]:
        """
        ✅ Phase 2: 基于AS号变更识别网络边界
        
        AS号变更通常表示跨越了不同的自治系统，这是识别CPE/WAN出口的强证据。
        
        Returns:
            AS变更发生的跳数，未检测到返回None
        """
        prev_as = None
        
        for hop in hops:
            if not hop.as_number:
                continue
            
            current_as = hop.as_number
            
            # 检测AS号变更
            if prev_as and current_as != prev_as:
                self.logger.info(
                    f"检测到AS号变更: AS{prev_as} → AS{current_as} (第{hop.hop_number}跳)"
                )
                return hop.hop_number
            
            prev_as = current_as
        
        return None
    
    def _fallback_analysis(
        self, 
        full_path: Optional[List[TracerouteHopInfo]] = None
    ) -> PathAnalysisResult:
        """
        降级分析：简单的启发式规则
        
        当智能分析失败或置信度过低时使用
        """
        if not full_path:
            return PathAnalysisResult(
                cpe_hop=2,
                split_point_hop=3,
                deployment_mode="unknown",
                confidence=0.2,
                path_fingerprint="default:cpe@2",
                reasoning=["降级策略：无路径数据，使用默认值"]
            )
        
        # 查找第一个公网IP
        for hop in full_path:
            if hop.ip_addresses and self._is_public_ip(hop.ip_addresses[0]):
                # 第一个公网IP的前一跳很可能是CPE
                cpe_hop = max(1, hop.hop_number - 1)
                return PathAnalysisResult(
                    cpe_hop=cpe_hop,
                    split_point_hop=cpe_hop + 1,
                    deployment_mode="unknown",
                    confidence=0.4,
                    path_fingerprint=f"fallback:cpe@{cpe_hop}",
                    reasoning=[f"降级策略：第一个公网IP在第{hop.hop_number}跳，推测CPE在第{cpe_hop}跳"]
                )
        
        # 最后的兜底
        return PathAnalysisResult(
            cpe_hop=2,
            split_point_hop=3,
            deployment_mode="unknown",
            confidence=0.2,
            path_fingerprint="default:cpe@2",
            reasoning=["降级策略：未找到公网IP，使用默认值"]
        )
    
    # ==================== IP地址判断工具方法 ====================
    
    @staticmethod
    def _is_private_lan(ip: str) -> bool:
        """判断是否为私网LAN地址"""
        if not ip or ip in ["*", "T", "?"]:
            return False
        
        try:
            import ipaddress
            addr = ipaddress.ip_address(ip)
            
            # RFC 1918私网地址
            return (
                addr.is_private and 
                not addr.is_loopback and
                not addr.is_link_local
            )
        except ValueError:
            return False
    
    @staticmethod
    def _is_isp_network(ip: str) -> bool:
        """
        判断是否为ISP网络地址
        
        简化版：检查是否为中国常见运营商IP段
        TODO: Phase 2集成IP地理位置数据库后优化
        """
        if not ip or ip in ["*", "T", "?"]:
            return False
        
        # 简化判断：非私网且非回环的IPv4地址可能是ISP网络
        try:
            import ipaddress
            addr = ipaddress.ip_address(ip)
            
            if isinstance(addr, ipaddress.IPv4Address):
                # 排除明显的私网和特殊地址
                return not (
                    addr.is_private or 
                    addr.is_loopback or 
                    addr.is_link_local or
                    addr.is_multicast
                )
        except ValueError:
            pass
        
        return False
    
    @staticmethod
    def _is_public_internet(ip: str) -> bool:
        """判断是否为公网互联网地址"""
        if not ip or ip in ["*", "T", "?"]:
            return False
        
        try:
            import ipaddress
            addr = ipaddress.ip_address(ip)
            
            # 公网地址：非私网、非回环、非链路本地
            return not (
                addr.is_private or 
                addr.is_loopback or 
                addr.is_link_local or
                addr.is_multicast or
                addr.is_reserved
            )
        except ValueError:
            return False
    
    @staticmethod
    def _is_public_ip(ip: str) -> bool:
        """判断是否为公网IP（简化版）"""
        return SmartPathAnalyzer._is_public_internet(ip)
