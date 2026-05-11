# Waterfall CLI 命令修复报告

## 问题描述

运行 `agentctl waterfall https://www.baidu.com` 时报错：

```
TypeError: HarCaptureTool.execute() got an unexpected keyword argument 'url'
```

## 根本原因分析

CLI 的 [waterfall.py](file://d:\git_repository\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\interface\cli\commands\waterfall.py) 命令在第 47 行直接调用了：

```python
har_result = har_tool.execute(url=url, headless=headless, timeout=timeout)
```

但 [HarCaptureTool.execute()](file://d:\git_repository\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\tools\implementations\web\har_capture.py#L80-L123) 方法的正确签名是：

```python
async def execute(self, request: ToolRequest, ctx: FlowContext) -> ToolResponse:
```

**问题根源**：
1. CLI 命令没有遵循工具系统的统一调用规范
2. 应该创建 [ToolRequest](file://d:\git_repository\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\core\types\tool.py#L13-L67) 和 [FlowContext](file://d:\git_repository\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\core\types\context.py#L0-L0)，然后异步执行
3. 缺少错误处理逻辑，当 HAR 采集失败时会导致 `AttributeError`

## 修复方案

### 修改文件：`src/sdwan_desktop/interface/cli/commands/waterfall.py`

#### 修复 1: 添加必要的导入

```python
import asyncio
from sdwan_desktop.core.types.tool import ToolRequest
from sdwan_desktop.core.types.context import FlowContext
```

#### 修复 2: 正确使用 ToolRequest 和 FlowContext

```python
# 在事件循环中运行异步代码
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

try:
    # 1. HAR 采集
    har_tool = HarCaptureTool()
    
    # 构造 ToolRequest 和 FlowContext
    request = ToolRequest(
        tool_name="har_capture",
        parameters={
            "url": url,
            "headless": headless,
            "timeout": timeout * 1000,  # 转换为毫秒
            "wait_until": "networkidle"
        }
    )
    ctx = FlowContext(flow_id="cli-waterfall", flow_name="cli-waterfall-diagnosis")
    
    # 异步执行 HAR 采集
    har_result = loop.run_until_complete(har_tool.execute(request, ctx))
    
finally:
    loop.close()
```

#### 修复 3: 完善的错误处理

```python
# 检查执行结果
if not har_result or not har_result.success:
    error_msg = har_result.error_message if har_result else "未知错误"
    print(f"❌ HAR 采集失败: {error_msg}")
    return

har_path = har_result.data.get("har_file_path") if har_result.data else None

if not har_path or not os.path.exists(har_path):
    print(f"❌ HAR 文件不存在: {har_path}")
    return
```

## 验证测试

创建了测试脚本 [tests/flow/test_waterfall_cli.py](file://d:\git_repository\deepseek\sdwan_diagnostic_platform\tests\flow\test_waterfall_cli.py)，验证以下内容：

1. ✅ **ToolRequest 创建** - 参数传递正确
2. ✅ **FlowContext 创建** - 上下文初始化正确
3. ✅ **HarCaptureTool 调用（Mock）** - 异步执行正确
4. ✅ **错误处理** - 失败响应处理正确
5. ✅ **None 响应处理** - 空值检查正确

测试结果：
```
🎉 所有测试通过！Waterfall CLI 命令已修复。
```

## 注意事项

### Playwright 浏览器安装

实际运行 waterfall 命令需要安装 Playwright 浏览器：

```bash
playwright install chromium
```

或者在虚拟环境中：

```bash
.venv\Scripts\playwright install chromium
```

### 与 GUI 的一致性

修复后的 CLI 实现与 GUI 的 [WaterfallWorker](file://d:\git_repository\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\interface\gui\tabs\waterfall_tab.py#L11-L122) 保持一致：

- 都使用 [ToolRequest](file://d:\git_repository\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\core\types\tool.py#L13-L67) 和 [FlowContext](file://d:\git_repository\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\core\types\context.py#L0-L0)
- 都通过异步方式调用 [HarCaptureTool](file://d:\git_repository\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\tools\implementations\web\har_capture.py#L48-L124)
- 都有完善的错误处理逻辑

## 相关文件

- 修复的文件：`src/sdwan_desktop/interface/cli/commands/waterfall.py`
- 测试文件：`tests/flow/test_waterfall_cli.py`
- 参考实现：
  - `src/sdwan_desktop/tools/implementations/web/har_capture.py` - HAR 采集工具
  - `src/sdwan_desktop/interface/gui/tabs/waterfall_tab.py` - GUI 的 waterfall 实现

## 后续建议

1. **添加集成测试** - 在 CI/CD 中添加实际的 HAR 采集测试（需要安装 Playwright）
2. **超时优化** - 考虑根据页面复杂度动态调整超时时间
3. **进度反馈** - 为长时间运行的 HAR 采集添加进度提示
4. **缓存机制** - 对相同 URL 的 HAR 文件进行缓存，避免重复采集
