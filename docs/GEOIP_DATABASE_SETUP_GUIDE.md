# GeoIP数据库配置指南

**日期**: 2026-05-06  
**问题**: 已安装geoip2库,但系统仍提示"未找到GeoIP数据库文件"  
**状态**: 📖 配置指南

## 📋 问题说明

虽然您已经执行了 `pip install geoip2`,但系统仍然显示警告:
```
WARNING - ⚠️ 未找到GeoIP数据库文件，将使用在线API
```

**原因**: `geoip2` 只是一个Python库,它需要配合MaxMind的数据库文件(`GeoLite2-City.mmdb`)才能工作。这个数据库文件需要单独下载。

## ✅ 解决方案

### 方案1: 手动下载(推荐)

#### 步骤1: 注册MaxMind账号
访问: https://www.maxmind.com/en/geolite2/signup
- 免费注册账号
- 验证邮箱

#### 步骤2: 下载数据库文件
访问: https://dev.maxmind.com/geoip/geolite2-free-geolocation-data
- 选择 **GeoLite2-City**
- 下载格式: **MMDB (Binary)**
- 文件名类似: `GeoLite2-City_YYYYMMDD.tar.gz`

#### 步骤3: 解压并放置
解压后找到 `GeoLite2-City.mmdb` 文件,放置到以下任一位置:

**Windows系统推荐路径**:
```
D:\deepseek\sdwan_diagnostic_platform\data\GeoLite2-City.mmdb
```

**其他可选路径**:
```
D:\deepseek\sdwan_diagnostic_platform\GeoLite2-City.mmdb
C:\Users\YourUsername\AppData\Local\GeoIP\GeoLite2-City.mmdb
```

#### 步骤4: 验证配置
运行配置助手脚本:
```bash
cd D:\deepseek\sdwan_diagnostic_platform
python setup_geoip.py
```

如果看到以下输出,说明配置成功:
```
✅ 数据库验证成功!
   文件: D:\deepseek\sdwan_diagnostic_platform\data\GeoLite2-City.mmdb
   大小: 65.23 MB
   测试查询 8.8.8.8: United States, Mountain View
```

### 方案2: 使用配置助手自动创建目录

运行配置助手:
```bash
python setup_geoip.py
```

脚本会:
1. 检查geoip2库是否安装
2. 显示建议的数据库存放位置
3. 询问是否创建data目录
4. 提供详细的下载和配置指导

### 方案3: 设置环境变量(高级)

如果您想将数据库放在自定义位置:

**Windows PowerShell**:
```powershell
# 临时设置(当前会话有效)
$env:GEOIP_DB_PATH="D:\your\path\GeoLite2-City.mmdb"

# 永久设置(用户级别)
[Environment]::SetEnvironmentVariable('GEOIP_DB_PATH', 'D:\your\path\GeoLite2-City.mmdb', 'User')
```

**Windows CMD**:
```cmd
setx GEOIP_DB_PATH "D:\your\path\GeoLite2-City.mmdb"
```

## 🔍 验证配置

### 方法1: 运行配置助手
```bash
python setup_geoip.py
```

### 方法2: 查看应用日志
重启SD-WAN诊断平台后,查看日志输出:

**成功**:
```
INFO: ✅ 加载GeoIP数据库: D:\deepseek\sdwan_diagnostic_platform\data\GeoLite2-City.mmdb
```

**失败**:
```
WARNING: ⚠️ 未找到GeoIP数据库文件，将使用在线API
```

### 方法3: 测试ASN信息显示
运行一键体检,在HTML报告中查看路径追踪表格的ASN信息列是否有数据。

## 💡 常见问题

### Q1: 为什么需要单独下载数据库文件?
A: MaxMind的GeoLite2数据库是独立的数据产品,与geoip2 Python库分开分发。这是为了:
- 保持Python库轻量
- 允许用户选择不同的数据库版本
- 支持离线使用

### Q2: 数据库文件有多大?
A: GeoLite2-City.mmdb 大约 60-70 MB。

### Q3: 数据库需要更新吗?
A: 是的,MaxMind建议每30天更新一次数据库以保持准确性。您可以:
- 定期手动下载新版本
- 使用MaxMind提供的更新工具(需要付费订阅)

### Q4: 没有数据库文件会影响功能吗?
A: 
- ✅ **核心功能不受影响**: HTML报告生成、路径追踪、配置快照等正常工作
- ⚠️ **ASN信息可能不完整**: 会使用在线API或内置规则,可能缺少部分AS号和运营商信息
- 💡 **建议**: 生产环境强烈建议配置离线数据库

### Q5: 可以使用其他数据库吗?
A: 当前版本仅支持MaxMind GeoLite2格式。未来版本可能支持:
- IPInfo数据库
- DB-IP数据库
- 自定义数据源

## 📊 数据库搜索路径优先级

系统按以下顺序查找数据库文件:

1. `data/GeoLite2-City.mmdb` (项目相对路径)
2. `GeoLite2-City.mmdb` (项目根目录)
3. `%USERPROFILE%\AppData\Local\GeoIP\GeoLite2-City.mmdb` (Windows)
4. `/usr/share/GeoIP/GeoLite2-City.mmdb` (Linux)
5. `~/.local/share/GeoIP/GeoLite2-City.mmdb` (Linux)
6. `/usr/local/share/GeoIP/GeoLite2-City.mmdb` (macOS)
7. `~/Library/GeoIP/GeoLite2-City.mmdb` (macOS)
8. `$GEOIP_DB_PATH` (环境变量指定)

找到第一个存在的文件即停止搜索。

## 🎯 快速配置步骤总结

```bash
# 1. 确保geoip2已安装
pip install geoip2

# 2. 创建data目录
mkdir data

# 3. 下载 GeoLite2-City.mmdb 并复制到 data/ 目录

# 4. 运行验证
python setup_geoip.py

# 5. 重启应用,检查日志
```

## 📚 相关资源

- MaxMind官网: https://www.maxmind.com
- GeoLite2下载: https://dev.maxmind.com/geoip/geolite2-free-geolocation-data
- geoip2文档: https://geoip2.readthedocs.io
- 配置助手脚本: `setup_geoip.py`

## 🔗 相关文档

- ASN信息显示修复: `docs/ROUTE_PATH_ASN_DISPLAY_FIX_20260506.md`
- IP地理位置服务: `src/sdwan_desktop/services/ip_geo_service.py`

---

**最后更新**: 2026-05-06  
**维护人员**: Lingma (灵码)
