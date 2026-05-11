# HTML报告ASN信息显示功能修复

**日期**: 2026-05-06  
**问题**: HTML报告的业务路径路由追踪模块未显示ASN相关信息  
**状态**: ✅ 已修复

## 📋 问题描述

在HTML报告的"业务路径路由追踪"章节中,详细路径分析表格只显示了跳数、IP地址和延迟信息,**缺少ASN(自治系统号)相关信息**,包括:
- AS号 (Autonomous System Number)
- 国家/地区代码
- 运营商名称

虽然底层数据结构 `TracerouteHopInfo` 已经包含了这些字段,但HTML模板没有渲染它们。

## 🔍 根本原因

1. **数据结构完整**: `TracerouteHopInfo` 类已定义ASN相关字段:
   ```python
   @dataclass
   class TracerouteHopInfo:
       as_number: Optional[str] = None  # AS号
       country: Optional[str] = None    # 国家/地区代码
       isp: Optional[str] = None        # 运营商名称
   ```

2. **模板缺失**: HTML模板中的路径追踪表格只有3列(跳数、IP地址、延迟),没有ASN信息列

## ✅ 修复方案

### 修改文件
- `src/sdwan_desktop/reporting/templates/quick_check.html`

### 具体改动

#### 1. 正常可达状态的路径表格
在 `<thead>` 中添加第4列:
```html
<th>ASN信息</th>
```

在 `<tbody>` 的每个跳点行中添加ASN信息显示:
```html
<td>
    {% if hop.as_number or hop.country or hop.isp %}
        {% if hop.as_number %}
        <div style="font-size: 0.9em;"><strong>AS:</strong> {{ hop.as_number }}</div>
        {% endif %}
        {% if hop.country %}
        <div style="font-size: 0.9em;"><strong>地区:</strong> {{ hop.country }}</div>
        {% endif %}
        {% if hop.isp %}
        <div style="font-size: 0.9em;"><strong>运营商:</strong> {{ hop.isp }}</div>
        {% endif %}
    {% else %}
        <span style="color: #999;">-</span>
    {% endif %}
</td>
```

#### 2. 路径受限状态的路径表格
同样添加ASN信息列,保持与正常状态一致的显示格式。

## 🎨 显示效果

修复后的路径追踪表格包含4列:

| 跳数 | IP地址 | 延迟 | ASN信息 |
|------|--------|------|---------|
| 1 | 192.168.1.1<br>(gateway.local) | 1.2 ms<br>1.1 ms<br>1.3 ms | - |
| 2 | 10.0.0.1<br>(cpe-gateway) | 2.5 ms<br>2.3 ms<br>2.4 ms | - |
| 3 | 202.106.0.20<br>(bj-bb-1.chinanet.cn) | 5.8 ms<br>5.6 ms<br>5.9 ms | **AS:** AS4134<br>**地区:** CN<br>**运营商:** ChinaNet Beijing |
| 4 | 202.97.33.1 | 12.3 ms<br>11.8 ms<br>12.1 ms | **AS:** AS4134<br>**地区:** CN<br>**运营商:** ChinaNet Backbone |
| 5 | 203.0.113.100<br>(target.example.com) | 25.4 ms<br>24.9 ms<br>25.2 ms | **AS:** AS15169<br>**地区:** US<br>**运营商:** Google LLC |

### 样式特点
- **字体大小**: ASN信息使用较小的字体(0.9em)以避免表格过宽
- **颜色**: 无ASN信息时显示灰色"-"
- **布局**: 每个ASN属性独占一行,清晰易读
- **条件显示**: 仅在有数据时显示对应字段

## 🧪 验证测试

创建了完整的验证脚本 `verify_asn_display.py`,测试内容包括:

1. ✅ **数据结构验证**: 确认 `TracerouteHopInfo` 包含ASN字段
2. ✅ **模板内容验证**: 确认HTML模板包含ASN信息列和相关变量引用
3. ✅ **示例数据创建**: 生成包含ASN信息的测试数据
4. ✅ **Jinja2语法验证**: 确认模板语法正确且过滤器已注册

运行结果:
```
✅ 所有验证通过!

📊 ASN信息显示功能已就绪:
   1. 数据结构包含ASN字段 (as_number, country, isp)
   2. HTML模板已添加ASN信息列
   3. Jinja2模板语法正确
```

## 💡 使用说明

### 查看ASN信息
1. 运行一键体检: `python -m sdwan_desktop.interface.cli.commands.quick_check quick_check`
2. 打开生成的HTML报告
3. 定位到"业务路径路由追踪"章节
4. 展开"详细路径分析"中的任意域名
5. 在路径表格的第4列查看ASN信息

### ASN数据来源
ASN信息依赖于以下组件:
- **geoip2库**: 用于离线IP地理位置查询(可选)
- **在线API**: geoip2未安装时的备选方案
- **内置规则**: 简单的IP段映射规则

如果看到警告 `geoip2库未安装，将使用在线API或内置规则`,这**不影响核心功能**,只是ASN信息可能不完整。

### 安装geoip2(可选)
如需完整的离线ASN查询功能:
```bash
pip install geoip2
# 下载 MaxMind GeoLite2-City.mmdb 数据库文件
```

## 📝 相关文件

- 数据结构定义: `src/sdwan_desktop/services/dns_split.py` (L316-L345)
- HTML模板: `src/sdwan_desktop/reporting/templates/quick_check.html`
- HTML构建器: `src/sdwan_desktop/services/reporter/html_builder.py`
- 验证脚本: `verify_asn_display.py`

## 🔗 相关规范

根据项目记忆规范:
> HTML报告中的业务路径路由追踪模块必须显示ASN相关信息,包括:
> 1. AS号(自治系统号) - 字段名: as_number
> 2. 国家/地区代码 - 字段名: country  
> 3. 运营商名称 - 字段名: isp

本次修复完全符合该规范要求。

## ✨ 总结

通过本次修复,HTML报告的路径追踪功能更加完善,用户可以:
- 🌍 了解网络路径经过的各个自治系统
- 🏢 识别运营商和网络边界
- 🔍 更准确地诊断路由问题
- 📊 获得更丰富的网络拓扑信息

这对于SD-WAN环境下的网络故障排查非常有价值。
