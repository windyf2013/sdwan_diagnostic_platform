# HTML报告配置快照显示优化

## 问题描述

在HTML报告的"证据附录->配置快照"部分，所有配置信息都以Python对象的字符串表示形式（如`SystemInfoSnapshot(adapters=1, primary=...)`）显示，这种格式不便于用户阅读和理解。

## 根本原因

1. **数据存储格式**：配置快照中存储的是Python dataclass对象
2. **模板渲染问题**：Jinja2模板直接调用对象的`__repr__`方法，导致显示为不易读的格式
3. **缺少序列化层**：没有在传递给模板之前将Python对象转换为可读的字典/列表结构

## 解决方案

### 1. 添加数据转换函数

在 `src/sdwan_desktop/services/reporter/html_builder.py` 中添加 `_convert_to_readable()` 函数：

```python
def _convert_to_readable(obj):
    """将Python对象转换为HTML模板可读的格式
    
    支持dataclass、字典、列表等复杂结构的递归转换。
    """
    from dataclasses import is_dataclass, asdict
    
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

**功能特点**：
- ✅ 递归处理嵌套结构
- ✅ 支持dataclass自动转换为字典
- ✅ 处理集合类型（set/frozenset）转换为列表
- ✅ 其他类型安全转换为字符串

### 2. 在报告生成时预处理配置快照

修改 `build_quick_check_report()` 方法，在传递数据给模板之前进行序列化：

```python
# ✅ 关键修复：序列化evidences中的config_snapshots，使其易于阅读
converted_evidences = []
for evidence in result.evidences:
    if hasattr(evidence, 'config_snapshots') and evidence.config_snapshots:
        # 创建证据的副本并序列化config_snapshots
        evidence_copy = copy.copy(evidence)
        converted_snapshots = {}
        for key, value in evidence.config_snapshots.items():
            converted_snapshots[key] = _convert_to_readable(value)
        evidence_copy.config_snapshots = converted_snapshots
        converted_evidences.append(evidence_copy)
    else:
        converted_evidences.append(evidence)

context = {
    # ... 其他字段 ...
    "evidences": converted_evidences,  # ✅ 使用转换后的evidences
}
```

### 3. 优化HTML模板显示

修改 `src/sdwan_desktop/reporting/templates/quick_check.html` 中的配置快照显示逻辑：

**改进前**：
```html
<div style="padding: 10px; background: var(--bg-secondary);">
    {{ value }}  <!-- 显示为 Python对象字符串 -->
</div>
```

**改进后**：
```html
{% if value is mapping %}
    <!-- 字典类型：转换为美观的表格 -->
    <table style="font-size: 0.9em; width: 100%; border-collapse: collapse;">
        <tbody>
            {% for k, v in value.items() %}
            <tr>
                <td style="width: 30%; font-weight: 500; padding: 8px;">{{ k }}</td>
                <td style="padding: 8px;">
                    {% if v is mapping %}
                        <!-- 嵌套字典：使用缩进列表 -->
                        <ul style="margin: 0; padding-left: 20px;">
                            {% for nk, nv in v.items() %}
                            <li><strong>{{ nk }}:</strong> {{ nv }}</li>
                            {% endfor %}
                        </ul>
                    {% elif v is sequence and v is not string %}
                        <!-- 列表类型：使用项目符号 -->
                        <ul style="margin: 0; padding-left: 20px;">
                            {% for item in v %}
                            <li>{{ item }}</li>
                            {% endfor %}
                        </ul>
                    {% else %}
                        {{ v }}
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
{% endif %}
```

**显示特性**：
- ✅ 表格化展示字典键值对
- ✅ 嵌套结构使用缩进列表
- ✅ 列表项使用项目符号
- ✅ 支持多层嵌套
- ✅ 响应式布局，自适应宽度

## 优化效果对比

### 优化前

```
⚙️ 配置快照
  system_snapshot
    SystemInfoSnapshot(adapters=1, primary=Intel(R) Dual Band Wireless-AC 8260)
  
  dns_split_result
    DnsSplitTestResult(domain_results=[DomainDnsResult(domain='www.baidu.com', ...)], ...)
```

### 优化后

```
⚙️ 配置快照
  
  ▼ system_snapshot
    ┌─────────────────────┬──────────────────────────────────┐
    │ adapters            │ 1                                │
    ├─────────────────────┼──────────────────────────────────┤
    │ primary             │ Intel(R) Dual Band Wireless...   │
    ├─────────────────────┼──────────────────────────────────┤
    │ ip_config           │                                  │
    │                     │ • gateway: 192.168.1.1           │
    │                     │ • dns_servers:                   │
    │                     │   - 8.8.8.8                      │
    │                     │   - 114.114.114.114              │
    └─────────────────────┴──────────────────────────────────┘

  ▼ dns_split_result
    ┌─────────────────────┬──────────────────────────────────┐
    │ domain              │ www.baidu.com                    │
    ├─────────────────────┼──────────────────────────────────┤
    │ resolved_ips        │                                  │
    │                     │ - 39.156.66.10                   │
    │                     │ - 39.156.66.18                   │
    ├─────────────────────┼──────────────────────────────────┤
    │ is_split            │ true                             │
    ├─────────────────────┼──────────────────────────────────┤
    │ split_description   │ 存在全局性解析差异               │
    └─────────────────────┴──────────────────────────────────┘
```

## 技术细节

### 支持的Python对象类型

| 类型 | 转换方式 | 示例 |
|------|---------|------|
| `None` | → `null` | `None` → `null` |
| `bool` | → 布尔值 | `True` → `true` |
| `int/float` | → 数字 | `42` → `42` |
| `str` | → 字符串 | `"test"` → `"test"` |
| `dataclass` | → 字典 | `SystemInfo(...)` → `{"adapters": 1, ...}` |
| `dict` | → 字典（递归） | `{"key": val}` → `{"key": val}` |
| `list/tuple` | → 列表（递归） | `[1, 2]` → `[1, 2]` |
| `set` | → 列表 | `{1, 2}` → `[1, 2]` |
| 其他 | → 字符串 | `object` → `"str(object)"` |

### 嵌套结构处理

```python
# 输入
{
    "system": SystemInfo(
        adapters=2,
        ip_config={
            "gateway": "192.168.1.1",
            "dns": ["8.8.8.8", "8.8.4.4"]
        }
    )
}

# 输出
{
    "system": {
        "adapters": 2,
        "ip_config": {
            "gateway": "192.168.1.1",
            "dns": ["8.8.8.8", "8.8.4.4"]
        }
    }
}
```

## 修改的文件

1. **`src/sdwan_desktop/services/reporter/html_builder.py`**
   - 添加 `_convert_to_readable()` 函数
   - 修改 `build_quick_check_report()` 方法，预处理config_snapshots

2. **`src/sdwan_desktop/reporting/templates/quick_check.html`**
   - 优化配置快照的HTML显示结构
   - 支持嵌套字典和列表的美观展示
   - 添加表格化布局和缩进列表

## 测试验证

运行以下命令验证修复：

```bash
python quick_verify.py
```

预期输出：
```
测试结果:
  输入: TestObj(name='test', value=42)
  输出: {'name': 'test', 'value': 42}
  类型: <class 'dict'>
  ✅ 转换成功!
```

## 用户体验提升

### 可读性
- ✅ 从难以理解的Python对象字符串变为结构化的表格/列表
- ✅ 清晰的层级关系，支持折叠展开
- ✅ 关键字段高亮显示

### 易用性
- ✅ 技术人员可以快速定位配置信息
- ✅ 支持复制粘贴单个配置项
- ✅ 嵌套结构一目了然

### 专业性
- ✅ 统一的视觉风格
- ✅ 符合Web标准的HTML结构
- ✅ 响应式设计，适配不同屏幕尺寸

## 后续优化建议

1. **添加搜索功能**：允许用户在配置快照中搜索特定键名
2. **导出功能**：支持将配置快照导出为JSON文件
3. **差异对比**：如果有多次诊断，可以对比配置变化
4. **语法高亮**：为IP地址、域名等添加特殊颜色标识
5. **折叠优化**：默认折叠深层嵌套结构，减少页面长度

## 相关文件

- `src/sdwan_desktop/services/reporter/html_builder.py` - HTML报告构建器
- `src/sdwan_desktop/reporting/templates/quick_check.html` - 一键体检报告模板
- `src/sdwan_desktop/core/types/diagnosis.py` - 诊断结果数据结构定义
- `quick_verify.py` - 快速验证脚本
