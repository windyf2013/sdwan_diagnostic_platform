# GeoIP数据库配置指南 (Windows)

**问题**: 已安装`geoip2`库,但系统提示"未找到GeoIP数据库文件"

**原因**: `geoip2`库需要配合MaxMind的数据库文件(`GeoLite2-City.mmdb`)才能工作

---

## 🎯 快速解决方案

### 方案1: 手动下载(推荐 - 离线使用)

#### 步骤1: 注册MaxMind账号
1. 访问: https://www.maxmind.com/en/geolite2/signup
2. 填写注册信息(免费)
3. 验证邮箱

#### 步骤2: 生成License Key
1. 登录MaxMind账号
2. 进入 "My License Key" 页面
3. 点击 "Generate new license key"
4. 复制生成的License Key

#### 步骤3: 下载数据库文件
1. 访问: https://dev.maxmind.com/geoip/geolite2-free-geolocation-data
2. 找到 "GeoLite2 City" 
3. 选择下载格式: **MMDB (binary)**
4. 点击下载链接(会要求输入License Key)
5. 下载 `GeoLite2-City_MMDB.tar.gz` 文件

#### 步骤4: 解压并放置文件
```powershell
# 在项目根目录创建data文件夹
cd d:\deepseek\sdwan_diagnostic_platform
mkdir data

# 解压下载的tar.gz文件
# 可以使用7-Zip或WinRAR解压
# 将 GeoLite2-City.mmdb 文件复制到 data 目录
```

最终文件路径应该是:
```
d:\deepseek\sdwan_diagnostic_platform\data\GeoLite2-City.mmdb
```

#### 步骤5: 验证安装
```powershell
python download_geoip_db.py --verify
```

预期输出:
```
✅ geoip2库已安装
✅ 找到数据库文件: d:\deepseek\sdwan_diagnostic_platform\data\GeoLite2-City.mmdb
   文件大小: XX.XX MB
✅ 数据库文件格式正确,可以正常使用

🎉 GeoIP环境配置完成!
```

---

### 方案2: 使用在线API(无需下载 - 需要网络)

如果不想下载数据库文件,系统会自动降级使用在线API。

**优点**:
- ✅ 无需下载和配置
- ✅ 数据实时更新

**缺点**:
- ❌ 需要网络连接
- ❌ 查询速度较慢(每次需网络请求)
- ❌ 有查询频率限制

**使用方法**:
直接运行诊断工具,系统会自动使用在线API。

---

### 方案3: 使用内置规则(离线模式 - 精度较低)

系统内置了简单的IP段映射规则,适用于常见IP地址。

**优点**:
- ✅ 完全离线
- ✅ 速度快

**缺点**:
- ❌ 精度较低
- ❌ 仅支持常见IP段(如中国主要运营商)

**适用场景**:
- 开发测试环境
- 对ASN信息精度要求不高的场景

---

## 📊 三种方案对比

| 特性 | 本地数据库 | 在线API | 内置规则 |
|------|-----------|---------|---------|
| 离线可用 | ✅ | ❌ | ✅ |
| 查询速度 | ⚡ 快 | 🐢 慢 | ⚡ 快 |
| 数据精度 | 🎯 高 | 🎯 高 | 📍 低 |
| 配置复杂度 | 🔧 中等 | ✅ 简单 | ✅ 简单 |
| 数据更新 | 📅 需手动更新 | 🔄 自动 | ❌ 固定 |
| 推荐场景 | 生产环境 | 临时使用 | 开发测试 |

---

## 💡 推荐配置

### 生产环境
使用**方案1(本地数据库)**,理由:
- 离线可用,稳定性高
- 查询速度快
- 数据精度高
- 无网络依赖

### 开发/测试环境
使用**方案3(内置规则)**即可,理由:
- 配置简单
- 满足基本测试需求
- ASN信息显示功能仍可验证

### 临时使用
使用**方案2(在线API)**,理由:
- 无需配置
- 数据最新

---

## 🔍 常见问题

### Q1: 数据库文件应该放在哪里?
A: 以下任一位置均可:
```
d:\deepseek\sdwan_diagnostic_platform\data\GeoLite2-City.mmdb
d:\deepseek\sdwan_diagnostic_platform\GeoLite2-City.mmdb
C:\Users\你的用户名\AppData\Local\GeoIP\GeoLite2-City.mmdb
```

### Q2: 数据库文件多大?
A: 约60-80 MB(压缩后约20 MB)

### Q3: 多久需要更新一次数据库?
A: MaxMind每月更新一次数据库,建议每季度更新一次

### Q4: 可以不安装geoip2库吗?
A: 可以,系统会自动使用在线API或内置规则,但会显示警告信息

### Q5: 如何验证数据库是否正常工作?
A: 运行 `python download_geoip_db.py --verify`

---

## 📝 技术细节

### 数据库查找顺序
系统按以下顺序查找数据库文件:
1. `./data/GeoLite2-City.mmdb` (项目data目录)
2. `./GeoLite2-City.mmdb` (项目根目录)
3. `%USERPROFILE%/AppData/Local/GeoIP/GeoLite2-City.mmdb` (Windows用户目录)
4. `/usr/share/GeoIP/GeoLite2-City.mmdb` (Linux系统目录)
5. `~/.local/share/GeoIP/GeoLite2-City.mmdb` (Linux用户目录)

找到第一个存在的文件即停止搜索。

### 降级策略
```
本地数据库 → 在线API → 内置规则
   ↓           ↓          ↓
 最优       中等       基础
```

---

## 🚀 下一步

配置完成后,运行一键体检即可在HTML报告中看到完整的ASN信息:

```powershell
python -m sdwan_desktop.interface.cli.commands.quick_check quick_check
```

查看报告中的"业务路径路由追踪"章节,每个跳点都会显示:
- **AS号**: 如 AS4134
- **地区**: 如 CN, US
- **运营商**: 如 ChinaNet, Google LLC

---

**最后更新**: 2026-05-06
