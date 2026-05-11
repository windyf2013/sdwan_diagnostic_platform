# IP地理位置服务配置指南

**日期**: 2026-05-06  
**问题**: 系统启动时显示"geoip2库未安装，将使用在线API或内置规则"警告  
**影响**: 无功能性影响,但可能影响离线环境下的IP地理位置查询性能

## 警告说明

当您看到以下日志时:
```
WARNING - geoip2库未安装，将使用在线API或内置规则
```

这表示:
- ✅ **系统正常运行**: IP地理位置服务仍可工作
- ⚠️ **降级模式**: 使用在线API而非本地数据库
- 💡 **可选优化**: 可安装geoip2库提升性能和离线能力

## 工作原理

IP地理位置服务采用三层查询策略:

```
1. GeoIP2本地数据库 (最快,支持离线)
   ↓ 如果不可用
2. 在线API查询 (需要网络,有速率限制)
   ↓ 如果失败
3. 内置规则匹配 (兜底方案,精度较低)
```

## 解决方案

### 方案1: 安装GeoIP2支持(推荐用于生产环境)

#### 步骤1: 安装依赖
```bash
pip install sdwan-desktop[geoip]
```

或单独安装:
```bash
pip install geoip2>=4.6.0 maxminddb>=2.3.0
```

#### 步骤2: 下载GeoLite2数据库

从MaxMind官网下载免费数据库:
1. 访问: https://dev.maxmind.com/geoip/geolite2-free-geolocation-data
2. 注册账号并下载 `GeoLite2-City.mmdb`
3. 放置到以下任一位置:
   - `/usr/share/GeoIP/GeoLite2-City.mmdb` (Linux)
   - `~/.local/share/GeoIP/GeoLite2-City.mmdb` (用户目录)
   - `项目根目录/data/GeoLite2-City.mmdb` (项目内)

#### 步骤3: 验证安装
```python
from sdwan_desktop.services.ip_geo_service import IPGeoService

service = IPGeoService()
result = service.query_ip("8.8.8.8")
print(result)
# 应该显示 source: "geoip2"
```

### 方案2: 保持当前配置(适合开发/测试环境)

如果您不需要离线IP查询功能,可以忽略此警告:
- ✅ 在线API仍然可用
- ✅ 内置规则提供基础支持
- ✅ 减少安装包体积(~5MB)

### 方案3: 禁用警告(不推荐)

如果确认不需要此功能,可以调整日志级别:

```python
import logging
logging.getLogger('sdwan_desktop.services.ip_geo_service').setLevel(logging.ERROR)
```

## 性能对比

| 特性 | GeoIP2本地库 | 在线API | 内置规则 |
|------|-------------|---------|---------|
| 查询速度 | <1ms | 100-500ms | <1ms |
| 离线支持 | ✅ | ❌ | ✅ |
| 数据精度 | 高(城市级) | 中(省级) | 低(国家级) |
| 速率限制 | 无 | 有(60次/分) | 无 |
| 安装大小 | +50MB | 0 | 0 |

## 常见问题

### Q1: 不安装geoip2会影响功能吗?
**A**: 不会。系统会自动降级使用在线API,所有功能正常工作。

### Q2: 在线API有配额限制吗?
**A**: 是的。默认使用免费的IP-API服务,限制为每分钟60次查询。超过限制后会使用内置规则。

### Q3: 如何更新GeoIP2数据库?
**A**: MaxMind每月更新一次数据库。建议设置定时任务自动更新:
```bash
# 示例cron任务(每月1号更新)
0 0 1 * * wget -O /usr/share/GeoIP/GeoLite2-City.mmdb https://example.com/download
```

### Q4: 为什么默认不包含geoip2?
**A**: 
- 减小安装包体积
- 避免强制用户下载大型数据库文件
- 大多数用户只需要基础IP查询功能

## 最佳实践

### 开发环境
- ❌ 不需要安装geoip2
- ✅ 使用在线API足够

### 测试环境
- ⚠️ 可选安装
- ✅ 如需测试离线场景则安装

### 生产环境
- ✅ **强烈建议安装**
- ✅ 确保稳定的离线查询能力
- ✅ 避免API速率限制问题

## 相关配置

在配置文件中使用IP地理位置服务:

```yaml
# configs/prod.yaml
services:
  ip_geo:
    cache_enabled: true
    cache_ttl: 86400  # 缓存24小时
    fallback_to_builtin: true  # API失败时使用内置规则
```

## 故障排查

### 问题1: 安装后仍显示警告
**解决**: 检查数据库文件是否存在
```bash
ls -lh ~/.local/share/GeoIP/GeoLite2-City.mmdb
```

### 问题2: 在线API查询失败
**解决**: 检查网络连接和防火墙设置
```python
import requests
response = requests.get("http://ip-api.com/json/8.8.8.8")
print(response.status_code)  # 应该是200
```

### 问题3: 缓存文件损坏
**解决**: 删除缓存文件重新生成
```bash
rm -rf ~/.sdwan_desktop/ip_geo_cache/
```

## 参考资料

- [MaxMind GeoLite2文档](https://dev.maxmind.com/geoip/geolite2-free-geolocation-data)
- [geoip2 Python库](https://pypi.org/project/geoip2/)
- [IP-API免费服务](http://ip-api.com/)
