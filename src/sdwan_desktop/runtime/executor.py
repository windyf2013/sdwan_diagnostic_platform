"""
步骤执行器

负责单个步骤的执行，支持超时控制和重试策略。
"""

import asyncio
import logging
from typing import Any, Dict, Optional, Callable, Awaitable

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.core.errors.flow import FlowError
from sdwan_desktop.flow.definitions.base import RetryPolicy

logger = logging.getLogger(__name__)


class StepExecutor:
    """步骤执行器"""

    def __init__(self):
        """初始化步骤执行器"""
        pass

    async def execute(
        self,
        handler: Callable[..., Awaitable[Any]],
        ctx: FlowContext,
        timeout_seconds: int = 30,
        retry_policy: Optional[RetryPolicy] = None,
        **kwargs
    ) -> Any:
        """执行步骤处理函数

        Args:
            handler: 异步处理函数
            ctx: 流程上下文
            timeout_seconds: 超时时间（秒）
            retry_policy: 重试策略
            **kwargs: 传递给 handler 的其他参数

        Returns:
            处理结果

        Raises:
            FlowError: 当执行失败或超时时
        """
        last_exception = None
        max_attempts = retry_policy.max_attempts if retry_policy else 1
        backoff_seconds = retry_policy.backoff_seconds if retry_policy else 0

        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(
                    f"执行步骤: {handler.__name__} (尝试 {attempt}/{max_attempts})",
                    extra={"trace_id": ctx.trace_id}
                )
                
                # 执行带超时的任务
                result = await asyncio.wait_for(
                    handler(ctx=ctx, **kwargs),
                    timeout=timeout_seconds
                )
                
                logger.info(
                    f"步骤执行成功: {handler.__name__}",
                    extra={"trace_id": ctx.trace_id}
                )
                return result

            except asyncio.TimeoutError:
                last_exception = FlowError(
                    error_code="FLOW_TIMEOUT",
                    message=f"步骤 {handler.__name__} 执行超时 ({timeout_seconds}s)",
                    context={"attempt": attempt, "timeout_seconds": timeout_seconds},
                    trace_id=ctx.trace_id
                )
                logger.warning(
                    f"步骤超时: {handler.__name__} (尝试 {attempt}/{max_attempts})",
                    extra={"trace_id": ctx.trace_id}
                )

            except Exception as e:
                last_exception = FlowError(
                    error_code="FLOW_EXECUTION_ERROR",
                    message=f"步骤 {handler.__name__} 执行失败: {str(e)}",
                    context={"attempt": attempt, "error_type": type(e).__name__},
                    trace_id=ctx.trace_id
                )
                logger.error(
                    f"步骤执行失败: {handler.__name__} (尝试 {attempt}/{max_attempts}): {e}",
                    extra={"trace_id": ctx.trace_id},
                    exc_info=True
                )

            # 如果还有重试机会，等待后继续
            if attempt < max_attempts:
                if backoff_seconds > 0:
                    wait_time = backoff_seconds * attempt  # 简单线性退避
                    logger.info(
                        f"等待 {wait_time}s 后重试...",
                        extra={"trace_id": ctx.trace_id}
                    )
                    await asyncio.sleep(wait_time)

        # 所有尝试均失败
        raise last_exception