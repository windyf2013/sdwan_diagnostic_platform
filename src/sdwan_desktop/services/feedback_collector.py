"""
智能路径分析器 - 用户反馈收集模块

功能：
1. 收集用户对CPE识别结果的反馈
2. 统计准确率和误判率
3. 自动调整权重参数
4. 生成改进建议报告

使用方法：
    from sdwan_desktop.services.feedback_collector import FeedbackCollector
    
    collector = FeedbackCollector()
    collector.collect_feedback(case_id, expected_cpe, actual_cpe, confidence)
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class FeedbackRecord:
    """用户反馈记录"""
    case_id: str                    # 案例ID
    timestamp: str                  # 时间戳
    expected_cpe_hop: int           # 期望的CPE跳数
    actual_cpe_hop: int             # 实际识别的CPE跳数
    confidence: float               # 置信度
    is_correct: bool                # 是否正确
    deployment_mode: str            # 部署模式
    reasoning: List[str]            # 推理过程
    user_comment: str = ""          # 用户评论
    network_topology: str = ""      # 网络拓扑描述


class FeedbackCollector:
    """用户反馈收集器"""
    
    def __init__(self, storage_dir: Optional[str] = None):
        self.logger = logger
        
        # 设置存储目录
        if storage_dir:
            self.storage_dir = Path(storage_dir)
        else:
            self.storage_dir = Path.home() / ".sdwan_desktop" / "feedback"
        
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.feedback_file = self.storage_dir / "feedback_records.json"
        
        # 加载已有反馈
        self.records: List[FeedbackRecord] = []
        self._load_feedback()
    
    def collect_feedback(
        self,
        case_id: str,
        expected_cpe: int,
        actual_cpe: int,
        confidence: float,
        deployment_mode: str = "",
        reasoning: List[str] = None,
        user_comment: str = "",
        network_topology: str = ""
    ):
        """
        收集用户反馈
        
        Args:
            case_id: 案例唯一标识
            expected_cpe: 用户确认的正确CPE位置
            actual_cpe: 系统识别的CPE位置
            confidence: 系统给出的置信度
            deployment_mode: 部署模式
            reasoning: 推理过程
            user_comment: 用户评论
            network_topology: 网络拓扑描述
        """
        is_correct = (expected_cpe == actual_cpe)
        
        record = FeedbackRecord(
            case_id=case_id,
            timestamp=datetime.now().isoformat(),
            expected_cpe_hop=expected_cpe,
            actual_cpe_hop=actual_cpe,
            confidence=confidence,
            is_correct=is_correct,
            deployment_mode=deployment_mode,
            reasoning=reasoning or [],
            user_comment=user_comment,
            network_topology=network_topology
        )
        
        self.records.append(record)
        self._save_feedback()
        
        self.logger.info(
            f"收集用户反馈: case_id={case_id}, "
            f"期望CPE={expected_cpe}, 实际CPE={actual_cpe}, "
            f"正确={is_correct}, 置信度={confidence:.2f}"
        )
    
    def get_statistics(self) -> Dict[str, any]:
        """
        获取反馈统计信息
        
        Returns:
            包含准确率、平均置信度等指标的字典
        """
        if not self.records:
            return {
                "total_feedback": 0,
                "accuracy": 0.0,
                "avg_confidence": 0.0,
                "false_positive_rate": 0.0,
                "false_negative_rate": 0.0
            }
        
        total = len(self.records)
        correct = sum(1 for r in self.records if r.is_correct)
        accuracy = correct / total if total > 0 else 0
        
        avg_confidence = sum(r.confidence for r in self.records) / total
        
        # 计算误判率
        false_positives = sum(1 for r in self.records if not r.is_correct and r.confidence >= 0.8)
        false_negatives = sum(1 for r in self.records if not r.is_correct and r.confidence < 0.5)
        
        fp_rate = false_positives / total if total > 0 else 0
        fn_rate = false_negatives / total if total > 0 else 0
        
        return {
            "total_feedback": total,
            "correct_count": correct,
            "incorrect_count": total - correct,
            "accuracy": accuracy,
            "avg_confidence": avg_confidence,
            "false_positive_rate": fp_rate,
            "false_negative_rate": fn_rate,
            "last_updated": self.records[-1].timestamp if self.records else None
        }
    
    def generate_improvement_report(self) -> str:
        """
        生成改进建议报告
        
        Returns:
            包含分析结果和改进建议的文本报告
        """
        stats = self.get_statistics()
        
        report_lines = [
            "=" * 60,
            "智能路径分析器 - 用户反馈分析报告",
            "=" * 60,
            "",
            f"总反馈数: {stats['total_feedback']}",
            f"正确数: {stats['correct_count']}",
            f"错误数: {stats['incorrect_count']}",
            f"准确率: {stats['accuracy']*100:.2f}%",
            f"平均置信度: {stats['avg_confidence']:.2f}",
            f"高置信度误判率: {stats['false_positive_rate']*100:.2f}%",
            f"低置信度误判率: {stats['false_negative_rate']*100:.2f}%",
            "",
        ]
        
        # 分析常见错误模式
        if stats['incorrect_count'] > 0:
            report_lines.append("常见错误模式:")
            
            incorrect_records = [r for r in self.records if not r.is_correct]
            
            # 按部署模式分组
            mode_errors = {}
            for record in incorrect_records:
                mode = record.deployment_mode or "unknown"
                if mode not in mode_errors:
                    mode_errors[mode] = []
                mode_errors[mode].append(record)
            
            for mode, errors in mode_errors.items():
                report_lines.append(f"\n  部署模式: {mode}")
                report_lines.append(f"    错误次数: {len(errors)}")
                
                # 分析偏差方向
                overestimate = sum(1 for e in errors if e.actual_cpe_hop > e.expected_cpe_hop)
                underestimate = sum(1 for e in errors if e.actual_cpe_hop < e.expected_cpe_hop)
                
                if overestimate > 0:
                    report_lines.append(f"    高估CPE位置: {overestimate}次")
                if underestimate > 0:
                    report_lines.append(f"    低估CPE位置: {underestimate}次")
        
        # 提供改进建议
        report_lines.append("\n" + "=" * 60)
        report_lines.append("改进建议:")
        report_lines.append("=" * 60)
        
        if stats['accuracy'] < 0.9:
            report_lines.append("⚠️  准确率低于90%，建议：")
            report_lines.append("  1. 收集更多用户反馈数据")
            report_lines.append("  2. 调整证据权重参数")
            report_lines.append("  3. 检查是否有特殊网络拓扑未覆盖")
        
        if stats['false_positive_rate'] > 0.1:
            report_lines.append("⚠️  高置信度误判率较高，建议：")
            report_lines.append("  1. 提高置信度阈值")
            report_lines.append("  2. 增加更多验证条件")
            report_lines.append("  3. 对高置信度结果进行人工审核")
        
        if stats['total_feedback'] < 50:
            report_lines.append("ℹ️  反馈数据不足，建议：")
            report_lines.append("  1. 鼓励用户提供更多反馈")
            report_lines.append("  2. 扩大测试范围")
            report_lines.append("  3. 收集不同网络环境的样本")
        
        report_lines.append("")
        
        report = "\n".join(report_lines)
        
        # 保存报告
        report_file = self.storage_dir / f"improvement_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        self.logger.info(f"改进建议报告已保存到: {report_file}")
        
        return report
    
    def _load_feedback(self):
        """加载反馈记录"""
        try:
            if self.feedback_file.exists():
                with open(self.feedback_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self.records = [
                    FeedbackRecord(**record_data)
                    for record_data in data.get("records", [])
                ]
                
                self.logger.info(f"加载用户反馈: {len(self.records)}条记录")
        except Exception as e:
            self.logger.warning(f"加载反馈失败: {e}")
            self.records = []
    
    def _save_feedback(self):
        """保存反馈记录"""
        try:
            data = {
                "version": "1.0",
                "last_updated": datetime.now().isoformat(),
                "records": [
                    {
                        "case_id": r.case_id,
                        "timestamp": r.timestamp,
                        "expected_cpe_hop": r.expected_cpe_hop,
                        "actual_cpe_hop": r.actual_cpe_hop,
                        "confidence": r.confidence,
                        "is_correct": r.is_correct,
                        "deployment_mode": r.deployment_mode,
                        "reasoning": r.reasoning,
                        "user_comment": r.user_comment,
                        "network_topology": r.network_topology
                    }
                    for r in self.records
                ]
            }
            
            with open(self.feedback_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.logger.debug(f"保存用户反馈: {len(self.records)}条记录")
        except Exception as e:
            self.logger.error(f"保存反馈失败: {e}")


# 全局单例
_feedback_collector: Optional[FeedbackCollector] = None


def get_feedback_collector() -> FeedbackCollector:
    """获取反馈收集器单例"""
    global _feedback_collector
    if _feedback_collector is None:
        _feedback_collector = FeedbackCollector()
    return _feedback_collector
