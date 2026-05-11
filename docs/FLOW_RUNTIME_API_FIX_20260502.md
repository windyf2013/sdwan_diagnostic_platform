# FlowRuntime API调用错误修复记录

## 🐛 问题描述

### 问题1：FlowRuntime构造函数参数错误

运行一键体检流程时出现以下错误：

```
TypeError: FlowRuntime.__init__() got an unexpected keyword argument 'flow_def'
```

错误发生在 `src/sdwan_desktop/interface/cli/commands/quick_check.py` 第466行。

### 问题2：HtmlReportBuilder方法名错误（本次修复）

修复问题1后，报告生成步骤出现新错误：

```
AttributeError: 'HtmlReportBuilder' object has no attribute 'build_html'
```

错误发生在 `src/sdwan_desktop/interface/cli/commands/quick_check.py` 第435行。

---

## 🔍 根本原因分析

### 问题1：FlowRuntime API调用方式错误

**错误的API调用方式**：
```python
# ❌ 错误：FlowRuntime构造函数不接受flow_def参数
runtime = FlowRuntime(flow_def=QUICK_CHECK_FLOW)

final_ctx = loop.run_until_complete(
    runtime.execute(ctx=ctx, handlers=step_handlers)  # ❌ 方法名也错误
)
```

**正确的API设计**：

查看 [`FlowRuntime`](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\runtime\engine.py#L19-L236) 类的实现：

```python
class FlowRuntime:
    """流程运行时引擎"""

    def __init__(self):
        """初始化流程运行时（不接受任何参数）"""
        self.executor = StepExecutor()
        self._step_handlers: Dict[str, Any] = {}

    async def execute_flow(
        self,
        flow_def: FlowDefinition,  # ✅ flow_def在这里传入
        ctx: FlowContext,
        handlers: Dict[str, Any]
    ) -> Dict[str, StepSnapshot]:
        """执行流程定义"""
        # ... 实现逻辑
```

**关键点**：
1. [FlowRuntime](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\runtime\engine.py#L19-L236) 的构造函数不接受任何参数
2. `flow_def` 应该在 [execute_flow](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\runtime\engine.py#L38-L154) 方法中传入
3. 方法名是 `execute_flow`，不是 `execute`

---

### 问题2：HtmlReportBuilder方法名错误

**错误的代码**：
```python
# ❌ 错误：使用了不存在的方法名
html_content = report_builder.build_html(result)
```

**正确的方法签名**：

查看 [`HtmlReportBuilder`](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\services\reporter\html_builder.py#L22-L576) 类的方法：

```python
class HtmlReportBuilder:
    def build_quick_check_report(
        self,
        result: DiagnosisResult,
        output_path: Optional[Path] = None
    ) -> str:
        """构建一键体检 HTML 报告
        
        Args:
            result: 诊断结果
            output_path: 输出文件路径（可选，如提供则写入文件）
        
        Returns:
            HTML 内容字符串
        """
        # ... 实现逻辑
```

**关键点**：
1. 方法名是 [build_quick_check_report](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\services\reporter\html_builder.py#L61-L117)，不是 `build_html`
2. 该方法接受两个参数：`result` 和 `output_path`
3. 如果提供了 `output_path`，方法会自动写入文件并返回HTML内容

---

## ✅ 修复方案

### 修复1：FlowRuntime API调用

**修复后的代码**：
```python
# ✅ 正确：FlowRuntime不接受参数
runtime = FlowRuntime()

# ✅ 正确：使用execute_flow方法，传入flow_def、ctx和handlers
final_ctx = loop.run_until_complete(
    runtime.execute_flow(
        flow_def=QUICK_CHECK_FLOW,
        ctx=ctx,
        handlers=step_handlers
    )
)
```

**修复要点**：
1. **移除构造函数参数**：`FlowRuntime()` 不接受任何参数
2. **使用正确的方法名**：`execute_flow` 而不是 `execute`
3. **在方法调用时传入flow_def**：将 `QUICK_CHECK_FLOW` 作为第一个参数传入

---

### 修复2：HtmlReportBuilder方法调用

**修复后的代码**：
```python
# ✅ 正确：使用正确的方法名，并传入output_path参数
html_content = report_builder.build_quick_check_report(result, output_path)
duration = (datetime.now() - start).total_seconds()
print(f"✓ ({duration:.1f}s)")
print(f"   报告已保存至: {output_path.absolute()}")
```

**修复要点**：
1. **使用正确的方法名**：[build_quick_check_report](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\services\reporter\html_builder.py#L61-L117) 而不是 `build_html`
2. **传入output_path参数**：让方法自动处理文件写入
3. **简化代码**：不需要手动调用 `write_text`，方法内部已处理

---

## 📋 相关修改文件

- ✅ `src/sdwan_desktop/interface/cli/commands/quick_check.py` 
  - 第466-475行：修复FlowRuntime调用
  - 第433-436行：修复HtmlReportBuilder调用

---

## 🧪 验证方法

运行一键体检命令验证修复：

```bash
python -m sdwan_desktop.interface.cli.main quick-check --verbose
```

### 预期输出

应该看到类似以下内容：
```
============================================================
开始执行一键体检流程
============================================================

[INFO] 步骤 step-collect 开始执行...
[INFO] 步骤 step-collect 执行完成
[INFO] 步骤 step-gateway 开始执行...
...
生成诊断报告... ✓ (0.5s)
   报告已保存至: D:\ai-missions\deepseek\sdwan_diagnostic_platform\reports\quick_check_20260502_211031.html

============================================================
体检完成！
============================================================
```

---

## 💡 经验教训

### 1. API设计模式理解

**常见的两种API设计模式**：

**模式A：构造函数注入**（本项目未采用）
```python
# 某些框架的设计
runtime = FlowRuntime(flow_def=QUICK_CHECK_FLOW)
result = await runtime.execute(ctx=ctx, handlers=handlers)
```

**模式B：方法参数传递**（本项目采用）
```python
# 本项目的设计
runtime = FlowRuntime()
result = await runtime.execute_flow(
    flow_def=QUICK_CHECK_FLOW,
    ctx=ctx,
    handlers=handlers
)
```

**关键区别**：
- 模式A适合单例或固定配置的场景
- 模式B更灵活，同一个runtime可以执行不同的flow

### 2. 阅读源码的重要性

在使用API前，务必：
- ✅ 查看类的构造函数签名
- ✅ 查看方法的参数列表
- ✅ 阅读docstring了解用法
- ✅ 参考其他地方的调用示例

### 3. 类型提示的价值

如果有正确的类型提示，IDE会提前发现错误：

```python
# 如果有完整的类型提示
class FlowRuntime:
    def __init__(self) -> None:  # 明确显示无参数
        ...
    
    async def execute_flow(
        self,
        flow_def: FlowDefinition,  # 明确的参数类型
        ctx: FlowContext,
        handlers: Dict[str, Any]
    ) -> Dict[str, StepSnapshot]:
        ...
```

IDE会在编写代码时就提示错误，而不是等到运行时。

### 4. 方法命名规范

遵循清晰的方法命名规范可以避免混淆：
- ✅ `build_quick_check_report` - 明确表示构建一键体检报告
- ✅ `build_deep_dive_report` - 明确表示构建深度诊断报告
- ❌ `build_html` - 过于通用，不清楚构建什么类型的报告

---

## 🔗 相关文档

- 📘 [Flow引擎规范](spec/50_execution/pipeline_engine.md)
- 📘 [SD-WAN核心规范](spec/SDWAN_SPEC.md) - Flow引擎章节
- 📘 [CLI与GUI实现一致性规范](memory: CLI与GUI实现一致性规范)
- 📘 [HTML报告生成流程复用规范](memory: HTML报告生成流程复用规范)

---

**修复日期**: 2026-05-02  
**修复版本**: v1.0.4  
**状态**: ✅ 已修复并验证
