"""
流程运行时引擎

支持基于 DAG 的步骤依赖解析、并行执行、超时和重试。
"""

import asyncio
import logging
import time
from typing import Dict, List, Set, Any, Optional
from collections import defaultdict

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.core.errors.flow import FlowError
from sdwan_desktop.flow.definitions.base import FlowDefinition, StepDefinition
from sdwan_desktop.runtime.executor import StepExecutor
from sdwan_desktop.core.types.flow_state import FlowStatus, StepSnapshot

logger = logging.getLogger(__name__)


class FlowRuntime:
    """流程运行时引擎"""

    def __init__(self):
        """初始化流程运行时"""
        self.executor = StepExecutor()
        self._step_handlers: Dict[str, Any] = {}

    def register_handler(self, step_id: str, handler: Any):
        """注册步骤处理器
        
        Args:
            step_id: 步骤ID
            handler: 处理器对象或函数
        """
        self._step_handlers[step_id] = handler

    async def execute_flow(
        self,
        flow_def: FlowDefinition,
        ctx: FlowContext,
        handlers: Dict[str, Any]
    ) -> Dict[str, StepSnapshot]:
        """执行流程定义

        Args:
            flow_def: 流程定义
            ctx: 流程上下文
            handlers: 步骤ID到处理器函数的映射 {step_id: async_func}

        Returns:
            步骤快照字典 {step_id: StepSnapshot}

        Raises:
            FlowError: 流程执行严重错误
        """
        start_time = time.time()
        snapshots: Dict[str, StepSnapshot] = {}
        
        # 构建依赖图
        dependencies = self._build_dependency_graph(flow_def.steps)
        # 获取并行组配置
        parallel_groups = flow_def.config.get("parallel_groups", [])
        continue_on_error = flow_def.config.get("continue_on_error", False)

        # 拓扑排序执行
        executed_steps: Set[str] = set()
        pending_steps = {step.id for step in flow_def.steps}
        
        # 简单的层级执行模型：每轮找出所有依赖已满足的步骤
        while pending_steps:
            # 找出当前可执行的步骤（依赖已全部满足）
            ready_steps = []
            for step_id in list(pending_steps):
                step_def = next((s for s in flow_def.steps if s.id == step_id), None)
                if not step_def:
                    continue
                
                deps = dependencies.get(step_id, [])
                if all(dep in executed_steps for dep in deps):
                    ready_steps.append(step_def)

            if not ready_steps:
                # 如果没有就绪步骤但仍有待执行步骤，说明有循环依赖或不可达步骤
                if pending_steps:
                    raise FlowError(
                        error_code="FLOW_DEADLOCK",
                        message=f"检测到循环依赖或无法执行的步骤: {pending_steps}",
                        trace_id=ctx.trace_id
                    )
                break

            # 检查并行组配置，将可以并行的步骤分组
            # 这里简化处理：如果 ready_steps 中的步骤在同一个 parallel_group 中，则并发执行
            # 否则，为了安全起见，默认串行执行不在同一组的，或者全部并发如果未指定严格顺序
            # 更复杂的逻辑需要解析 parallel_groups
            
            # 简化策略：将所有 ready_steps 分为若干批次
            # 如果配置了 parallel_groups，则只有同组且无其他依赖冲突的才真正并行
            # 此处实现一个基本的并发执行：所有 ready_steps 并发启动
            
            tasks = []
            step_map = {}
            
            for step_def in ready_steps:
                handler = handlers.get(step_def.id)
                if not handler:
                    logger.warning(f"未找到步骤 {step_def.id} 的处理器，跳过")
                    executed_steps.add(step_def.id)
                    pending_steps.discard(step_def.id)
                    continue

                task = self._execute_step_with_snapshot(
                    step_def, handler, ctx, snapshots
                )
                tasks.append(task)
                step_map[step_def.id] = step_def

            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for i, result in enumerate(results):
                    step_id = list(step_map.keys())[i]
                    step_def = step_map[step_id]
                    
                    if isinstance(result, Exception):
                        logger.error(
                            f"步骤 {step_id} 执行异常: {result}",
                            extra={"trace_id": ctx.trace_id},
                            exc_info=True
                        )
                        snapshot = StepSnapshot(
                            step_id=step_id,
                            name=step_def.name,
                            status=FlowStatus.FAILED,
                            error=str(result),
                            duration_ms=(time.time() - start_time) * 1000 # Approximate
                        )
                        snapshots[step_id] = snapshot
                        if not continue_on_error:
                            detail = str(result).strip()
                            message = f"步骤 {step_id} 执行失败且未配置忽略错误"
                            if detail:
                                message = f"{message}: {detail}"
                            raise FlowError(
                                error_code="FLOW_STEP_FAILED",
                                message=message,
                                trace_id=ctx.trace_id,
                            ) from result
                    else:
                        # Snapshot already updated in _execute_step_with_snapshot
                        pass
                    
                    executed_steps.add(step_id)
                    pending_steps.discard(step_id)

        total_duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"流程 {flow_def.id} 执行完成, 耗时: {total_duration_ms:.2f}ms",
            extra={"trace_id": ctx.trace_id}
        )

        expected_keys = flow_def.config.get("shared_context_keys")
        if expected_keys and logger.isEnabledFor(logging.DEBUG):
            missing = sorted(set(expected_keys) - set(ctx.metadata.keys()))
            if missing:
                logger.debug(
                    "流程 %s 结束后仍未写入的 shared_context_keys: %s",
                    flow_def.id,
                    missing,
                    extra={"trace_id": ctx.trace_id},
                )

        return snapshots

    async def _execute_step_with_snapshot(
        self,
        step_def: StepDefinition,
        handler: Any,
        ctx: FlowContext,
        snapshots: Dict[str, StepSnapshot]
    ):
        """执行单个步骤并记录快照"""
        start_time = time.time()
        try:
            logger.info(
                f"开始执行步骤: {step_def.name} ({step_def.id})",
                extra={"trace_id": ctx.trace_id}
            )
            
            result = await self.executor.execute(
                handler=handler,
                ctx=ctx,
                timeout_seconds=step_def.timeout_seconds,
                retry_policy=step_def.retry_policy
            )
            
            duration_ms = (time.time() - start_time) * 1000
            snapshot = StepSnapshot(
                step_id=step_def.id,
                name=step_def.name,
                status=FlowStatus.COMPLETED,
                start_time=start_time,
                end_time=time.time(),
                duration_ms=duration_ms,
                result=result
            )
            snapshots[step_def.id] = snapshot
            
            logger.info(
                "步骤完成: step_id=%s name=%s duration_ms=%.0f trace_id=%s",
                step_def.id,
                step_def.name,
                duration_ms,
                ctx.trace_id,
            )
            return result

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            snapshot = StepSnapshot(
                step_id=step_def.id,
                name=step_def.name,
                status=FlowStatus.FAILED,
                start_time=start_time,
                end_time=time.time(),
                duration_ms=duration_ms,
                error=str(e)
            )
            snapshots[step_def.id] = snapshot
            raise e

    def _build_dependency_graph(self, steps: List[StepDefinition]) -> Dict[str, List[str]]:
        """构建依赖图
        
        Returns:
            Dict[step_id, List[dependency_step_ids]]
        """
        graph = defaultdict(list)
        for step in steps:
            if step.depends_on:
                graph[step.id] = step.depends_on.copy()
            else:
                graph[step.id] = []
        return dict(graph)