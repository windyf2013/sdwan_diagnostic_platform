from PySide6.QtCore import QThread, Signal, QObject
import asyncio
import time

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.runtime.engine import FlowRuntime


class DiagnosisWorker(QThread):
    """诊断执行工作线程"""
    
    # 信号定义
    progress_updated = Signal(int, str)  # (百分比, 状态文本)
    step_completed = Signal(str, dict)   # (步骤ID, 结果数据)
    finished = Signal(object)            # 最终诊断结果
    error_occurred = Signal(str)         # 错误信息

    def __init__(self, flow_definition, context: FlowContext, handlers: dict):
        super().__init__()
        self.flow_definition = flow_definition
        self.context = context
        self.handlers = handlers
        self._is_cancelled = False
        self._runtime = FlowRuntime()

    def run(self):
        """在后台线程中执行异步流程"""
        try:
            # 创建一个新的事件循环用于当前线程
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            loop.run_until_complete(self._execute_flow())
            
        except Exception as e:
            if not self._is_cancelled:
                self.error_occurred.emit(str(e))
        finally:
            self.finished.emit(self.context.get("final_result"))

    async def _execute_flow(self):
        total_steps = len(self.flow_definition.steps)
        
        for i, step in enumerate(self.flow_definition.steps):
            if self._is_cancelled:
                break
            
            # 更新进度
            progress = int((i / total_steps) * 100)
            self.progress_updated.emit(progress, f"正在执行: {step.name}")
            
            # 执行步骤
            handler = self.handlers.get(step.id)
            if handler:
                try:
                    result = await handler(self.context)
                    self.step_completed.emit(step.id, result)
                except Exception as e:
                    self.error_occurred.emit(f"步骤 {step.name} 失败: {str(e)}")
                    if not step.continue_on_error:
                        break

        self.progress_updated.emit(100, "诊断完成")

    def cancel(self):
        """取消诊断执行"""
        self._is_cancelled = True
        self.progress_updated.emit(0, "已取消")
