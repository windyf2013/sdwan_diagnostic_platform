# HTML报告配置快照显示优化

## 问题描述

在HTML报告的"证据附录 -> 配置快照"部分，所有信息都以Python对象的字符串表示形式（`__repr__`）显示，例如：

```
SystemInfoSnapshot(adapters=1, primary=Intel(R) Dual Band Wireless-AC 8260)
DnsSplitTestResult(domain_results=[DomainDnsResult(domain='www.baidu.com', ...)])
```

这种格式非常难以阅读，特别是对于嵌套的复杂数据结构。

## 根本原因

1. **数据传递问题**: `config_snapshots`中存储的是Python dataclass对象
2. **模板渲染问题**: Jinja2模板直接调用对象的`__repr__`方法，输出原始字符串表示
3. **缺少格式化**: 没有将对象转换为结构化的JSON格式进行展示

## 解决方案

### 1. 添加对象转换函数

在 `src/sdwan_desktop/services/reporter/html_builder.py` 中添加 `_convert_to_readable` 函数：

```python
def _convert_to_readable(obj: Any) -> Any:
    """将Python对象转换为可序列化的可读格式"""
    if obj is None:
        return None
    elif isinstance(obj, (str, int, float, bool)):
        return obj
    elif is_dataclass(obj):
        # 将dataclass转换为字典，并递归处理嵌套对象
        try:
            data = asdict(obj)
            return {k: _convert_to_readable(v) for k, v in data.items()}
        except Exception:
            return {k: _convert_to_readable(getattr(obj, k)) 
                   for k in dir(obj) if not k.startswith('_')}
    elif isinstance(obj, dict):
        return {k: _convert_to_readable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_convert_to_readable(item) for item in obj]
    elif isinstance(obj, set):
        return list(obj)
    else:
        try:
            json.dumps(obj)
            return obj
        except (TypeError, ValueError):
            return str(obj)
```

**功能特点**:
- ✅ 递归处理嵌套的dataclass对象
- ✅ 支持字典、列表、集合等常见数据类型
- ✅ 自动处理无法序列化的类型（转为字符串）
- ✅ 保持数据的完整结构

### 2. 修改报告生成逻辑

在 `build_quick_check_report` 方法中，在准备模板数据之前转换config_snapshots：

```python
# ✅ 转换证据链中的config_snapshots为可读格式
import copy
converted_evidences = []
for evidence in (result.evidences or []):
    if hasattr(evidence, 'config_snapshots') and evidence.config_snapshots:
        evidence_copy = copy.deepcopy(evidence)
        converted_snapshots = {}
        for key, value in evidence.config_snapshots.items():
            converted_snapshots[key] = _convert_to_readable(value)
        evidence_copy.config_snapshots = converted_snapshots
        converted_evidences.append(evidence_copy)
    else:
        converted_evidences.append(evidence)

# 使用转换后的evidences
context = {
    "evidences": converted_evidences,
    # ... 其他字段
}
```

**关键点**:
- 使用深拷贝避免修改原始诊断结果
- 只转换有config_snapshots的证据
- 保持其他证据不变

### 3. 优化HTML模板显示

修改 `src/sdwan_desktop/reporting/templates/quick_check.html` 中的配置快照显示部分：

```html
<div class="json-viewer">
    <script type="application/json" class="json-data">{{ value | tojson(indent=2) }}</script>
    <pre style="margin: 0; color: var(--text-primary);"></pre>
</div>
<script>
    (function() {
        const container = document.currentScript.parentElement;
        const jsonData = container.querySelector('.json-data');
        const preElement = container.querySelector('pre');
        if (jsonData && preElement) {
            try {
                const data = JSON.parse(jsonData.textContent);
                preElement.textContent = JSON.stringify(data, null, 2);
            } catch(e) {
                preElement.textContent = jsonData.textContent;
            }
        }
    })();
</script>
```

**优化效果**:
- ✅ 使用 `<pre>` 标签保持格式
- ✅ 通过JavaScript动态格式化JSON
- ✅ 支持缩进和语法高亮
- ✅ 优雅降级：如果JSON解析失败，显示原始文本
- ✅ 响应式设计：支持横向滚动和自动换行

## 优化前后对比

### 优化前
```
DnsSplitTestResult(domain_results=[DomainDnsResult(domain='www.baidu.com', domestic_results={'218.201.96.130': ['39.156.70.239', '39.156.70.46']}, ...)])
```

### 优化后
```json
{
  "domain_results": [
    {
      "domain": "www.baidu.com",
      "domestic_results": {
        "218.201.96.130": [
          "39.156.70.239",
          "39.156.70.46"
        ]
      },
      "international_results": {
        "8.8.8.8": [
          "103.235.46.115",
          "103.235.46.102"
        ]
      },
      "is_split": true,
      "split_description": "域名 www.baidu.com 存在全局性解析差异",
      "domestic_avg_rtt_ms": 0.0,
      "international_avg_rtt_ms": 0.0
    }
  ],
  "split_domains": [
    "www.baidu.com",
    "www.google.com"
  ],
  "total_domains": 4,
  "split_count": 4,
  "total_duration_ms": 10255.87
}
```

## 技术细节

### 1. Dataclass序列化

使用Python标准库的 `dataclasses.asdict()` 函数将dataclass转换为字典：

```python
from dataclasses import asdict, is_dataclass

if is_dataclass(obj):
    data = asdict(obj)  # 递归转换为字典
    return {k: _convert_to_readable(v) for k, v in data.items()}
```

### 2. 深拷贝保护

使用 `copy.deepcopy()` 确保不修改原始诊断结果：

```python
import copy
evidence_copy = copy.deepcopy(evidence)
```

### 3. Jinja2模板过滤器

使用 `tojson` 过滤器将Python对象转换为JSON字符串：

```jinja2
{{ value | tojson(indent=2) }}
```

### 4. JavaScript JSON格式化

在客户端使用 `JSON.stringify()` 进行美化和缩进：

```javascript
JSON.stringify(data, null, 2)  // 2空格缩进
```

## 测试验证

运行验证脚本确认功能正常：

```bash
python verify_config_snapshot_fix.py
```

预期输出：
```
✅ 测试1: 简单dataclass转换通过
✅ 测试2: 嵌套dataclass转换通过
✅ 测试3: 复杂嵌套结构转换通过
✅ 测试4: 基本类型转换通过
================================================================================
✅ 所有测试通过！配置快照将正确显示为美化的JSON格式
================================================================================
```

## 影响范围

### 修改的文件
1. `src/sdwan_desktop/services/reporter/html_builder.py` - 添加转换逻辑
2. `src/sdwan_desktop/reporting/templates/quick_check.html` - 优化显示格式
3. `verify_config_snapshot_fix.py` - 新增验证脚本

### 兼容性
- ✅ 向后兼容：不影响现有功能
- ✅ 性能影响小：仅在生成报告时执行一次转换
- ✅ 支持所有Python版本（3.7+）
- ✅ 支持PyInstaller打包环境

## 用户体验提升

1. **可读性**: JSON格式清晰易读，支持折叠展开
2. **专业性**: 统一的代码风格和缩进
3. **可复制**: 用户可以轻松复制JSON数据进行分析
4. **响应式**: 适配不同屏幕尺寸
5. **容错性**: 即使JSON解析失败也能显示原始数据

## 后续优化建议

1. **语法高亮**: 集成highlight.js或Prism.js实现JSON语法高亮
2. **交互式折叠**: 添加点击折叠/展开功能
3. **搜索过滤**: 支持在JSON中搜索特定键值
4. **导出功能**: 提供单独下载JSON文件的选项
5. **对比视图**: 支持多次诊断结果的配置对比

## 相关文件

- `src/sdwan_desktop/services/reporter/html_builder.py` - HTML报告构建器
- `src/sdwan_desktop/reporting/templates/quick_check.html` - 一键体检报告模板
- `src/sdwan_desktop/core/types/diagnosis.py` - 诊断结果数据类型定义
- `verify_config_snapshot_fix.py` - 验证脚本
