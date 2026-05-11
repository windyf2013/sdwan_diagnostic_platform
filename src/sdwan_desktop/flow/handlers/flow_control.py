"""
Flow控制处理器 - 流程级别的逻辑控制

包括：
1. 连通性检查（决定是否执行后续测试）
2. 条件分支
3. 错误恢复策略
"""
import logging
from sdwan_desktop.core.types.context import FlowContext

logger = logging.getLogger(__name__)


async def check_connectivity(ctx: FlowContext):
    """检查连通性测试结果，失败则标记流程应终止
    
    Args:
        ctx: 流程上下文
        
    Returns:
        dict: 连通性检查结果
    """
    logger.info("开始检查连通性测试结果", extra={"trace_id": ctx.trace_id})
    
    # 获取网关测试结果（ProbeResult类型，有success属性）
    gateway_result = ctx.get("gateway_ping_result")
    gateway_ok = gateway_result is not None and hasattr(gateway_result, 'success') and gateway_result.success
    
    # 获取互联网连通性测试结果（ConnectivityTestResult类型，无success属性）
    internet_result = ctx.get("internet_connectivity_result")
    # ConnectivityTestResult通过成功率判断是否连通
    internet_ok = False
    if internet_result is not None:
        # 只要国内或国际任一成功率>0即视为连通
        domestic_ok = getattr(internet_result, 'domestic_success_rate', 0) > 0
        international_ok = getattr(internet_result, 'international_success_rate', 0) > 0
        internet_ok = domestic_ok or international_ok
    
    # 记录结果
    logger.info(
        f"连通性检查结果: 网关={'✅' if gateway_ok else '❌'}, "
        f"互联网={'✅' if internet_ok else '❌'}",
        extra={"trace_id": ctx.trace_id}
    )
    
    # 如果任一失败，标记后续步骤应跳过
    if not gateway_ok or not internet_ok:
        ctx.set("connectivity_failed", True)
        logger.warning(
            f"连通性测试失败（网关={gateway_ok}, 互联网={internet_ok}），"
            f"将跳过DNS分流和CPE链路追踪测试",
            extra={"trace_id": ctx.trace_id}
        )
    else:
        ctx.set("connectivity_failed", False)
        logger.info("连通性测试通过，继续执行高级测试", extra={"trace_id": ctx.trace_id})
    
    return {
        "gateway_ok": gateway_ok,
        "internet_ok": internet_ok,
        "should_continue": gateway_ok and internet_ok
    }
