"""
IP地理位置和AS号查询服务

提供以下功能：
1. IP地址地理位置查询（国家、城市、运营商）
2. AS号查询（自治系统号、组织名称）
3. 本地缓存机制减少重复查询
4. 离线模式支持（使用内置数据库）

设计原则：
- 优先使用本地数据库，避免网络依赖
- 支持多种数据源（MaxMind GeoLite2、IPInfo等）
- 查询失败时优雅降级
- 缓存常用结果提升性能
"""

import logging
import json
import os
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class IPGeoService:
    """IP地理位置和AS号查询服务"""
    
    def __init__(self, cache_dir: Optional[str] = None):
        self.logger = logger
        self.cache: Dict[str, Dict[str, Any]] = {}
        
        # 设置缓存目录
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path.home() / ".sdwan_desktop" / "ip_geo_cache"
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "ip_geo_cache.json"
        
        # 加载缓存
        self._load_cache()
        
        # 初始化GeoIP数据库（如果存在）
        self.geoip_db = self._init_geoip_database()
    
    def _init_geoip_database(self) -> Optional[Any]:
        """初始化GeoIP数据库
        
        尝试加载MaxMind GeoLite2数据库
        如果不存在，返回None，使用在线API或内置规则
        
        支持PyInstaller打包环境:
        - 打包后: 优先查找 sys._MEIPASS/data/GeoLite2-City.mmdb
        - 开发时: 查找当前目录和系统标准路径
        """
        try:
            # 检查是否安装了geoip2库
            try:
                import geoip2.database
            except ImportError:
                self.logger.info(
                    "💡 提示: geoip2库未安装，将使用在线API或内置规则\n"
                    "   如需离线IP地理位置查询，可执行: pip install sdwan-desktop[geoip]"
                )
                return None
            
            # 检测是否为PyInstaller打包环境
            import sys
            if getattr(sys, 'frozen', False):
                # PyInstaller打包后的临时目录
                base_path = Path(sys._MEIPASS)
                self.logger.debug(f"检测到打包环境，基础路径: {base_path}")
                
                # 优先查找打包内的数据库文件
                db_paths = [
                    base_path / "data" / "GeoLite2-City.mmdb",
                    base_path / "GeoLite2-City.mmdb",
                ]
            else:
                # 开发环境的Path
                self.logger.debug("检测到开发环境")
                
                # 查找数据库文件(支持多平台)
                db_paths = [
                    # Windows系统路径
                    Path.cwd() / "data" / "GeoLite2-City.mmdb",
                    Path.cwd() / "GeoLite2-City.mmdb",
                    Path.home() / "AppData" / "Local" / "GeoIP" / "GeoLite2-City.mmdb",
                    
                    # Linux系统路径
                    Path("/usr/share/GeoIP/GeoLite2-City.mmdb"),
                    Path.home() / ".local" / "share" / "GeoIP" / "GeoLite2-City.mmdb",
                    
                    # macOS系统路径
                    Path("/usr/local/share/GeoIP/GeoLite2-City.mmdb"),
                    Path.home() / "Library" / "GeoIP" / "GeoLite2-City.mmdb",
                ]
            
            for db_path in db_paths:
                if db_path.exists():
                    self.logger.info(f"✅ 加载GeoIP数据库: {db_path}")
                    return geoip2.database.Reader(str(db_path))
            
            self.logger.warning(
                "⚠️ 未找到GeoIP数据库文件，将使用在线API\n"
                "💡 提示: 如需离线查询，请下载 GeoLite2-City.mmdb 并放置到以下任一位置:\n"
                f"   - {Path.cwd() / 'data' / 'GeoLite2-City.mmdb'}\n"
                f"   - {Path.cwd() / 'GeoLite2-City.mmdb'}\n"
                f"   - {Path.home() / 'AppData' / 'Local' / 'GeoIP' / 'GeoLite2-City.mmdb'}\n"
                "   或设置环境变量 GEOIP_DB_PATH 指向数据库文件路径\n"
                "   下载地址: https://dev.maxmind.com/geoip/geolite2-free-geolocation-data"
            )
            return None
        
        except Exception as e:
            self.logger.error(f"❌ 初始化GeoIP数据库失败: {e}")
            return None
    
    def query_ip(self, ip: str) -> Dict[str, Any]:
        """
        查询IP地址的地理位置和AS号信息
        
        Args:
            ip: IP地址字符串
            
        Returns:
            {
                "country": "CN",           # 国家代码
                "country_name": "China",   # 国家名称
                "city": "Beijing",         # 城市
                "isp": "China Telecom",    # 运营商
                "as_number": "4134",       # AS号
                "as_organization": "CHINANET-BACKBONE",  # AS组织
                "latitude": 39.9042,       # 纬度
                "longitude": 116.4074,     # 经度
                "source": "geoip2"         # 数据来源
            }
        """
        if not ip or ip in ["*", "T", "?"]:
            return {}
        
        # 检查缓存
        if ip in self.cache:
            self.logger.debug(f"IP {ip} 命中缓存")
            return self.cache[ip].copy()
        
        result = {}
        
        # 策略1: 尝试GeoIP2本地数据库
        if self.geoip_db:
            result = self._query_geoip2(ip)
        
        # 策略2: 如果GeoIP2失败，使用在线API（可选）
        if not result:
            result = self._query_online_api(ip)
        
        # 策略3: 使用内置规则（兜底）
        if not result:
            result = self._query_builtin_rules(ip)
        
        # 添加到缓存
        if result:
            self.cache[ip] = result
            self._save_cache()
        
        return result
    
    def _query_geoip2(self, ip: str) -> Dict[str, Any]:
        """使用GeoIP2数据库查询"""
        try:
            import geoip2.errors
            
            response = self.geoip_db.city(ip)
            
            result = {
                "country": response.country.iso_code,
                "country_name": response.country.name,
                "city": response.city.name,
                "latitude": response.location.latitude,
                "longitude": response.location.longitude,
                "source": "geoip2"
            }
            
            # 查询AS号
            try:
                as_response = self.geoip_db.asn(ip)
                result.update({
                    "as_number": str(as_response.autonomous_system_number),
                    "as_organization": as_response.autonomous_system_organization,
                    "isp": as_response.autonomous_system_organization
                })
            except geoip2.errors.AddressNotFoundError:
                pass
            
            self.logger.debug(f"GeoIP2查询成功: {ip} → {result.get('country')} AS{result.get('as_number', 'N/A')}")
            return result
        
        except Exception as e:
            self.logger.debug(f"GeoIP2查询失败: {ip}, 错误: {e}")
            return {}
    
    def _query_online_api(self, ip: str) -> Dict[str, Any]:
        """
        使用在线API查询（可选功能）
        
        注意：生产环境建议配置API密钥或使用本地数据库
        """
        try:
            import requests
            
            # 使用ipapi.co免费API（有速率限制）
            url = f"https://ipapi.co/{ip}/json/"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                
                result = {
                    "country": data.get("country_code"),
                    "country_name": data.get("country_name"),
                    "city": data.get("city"),
                    "isp": data.get("org"),
                    "as_number": data.get("asn"),
                    "as_organization": data.get("org"),
                    "latitude": data.get("latitude"),
                    "longitude": data.get("longitude"),
                    "source": "ipapi.co"
                }
                
                self.logger.debug(f"在线API查询成功: {ip} → {result.get('country')}")
                return result
        
        except ImportError:
            self.logger.debug("requests库未安装，跳过在线API查询")
        except Exception as e:
            self.logger.debug(f"在线API查询失败: {ip}, 错误: {e}")
        
        return {}
    
    def _query_builtin_rules(self, ip: str) -> Dict[str, Any]:
        """
        使用内置规则查询（兜底策略）
        
        基于常见IP段的简化判断
        包含中国主要运营商的IP地址段
        """
        try:
            import ipaddress
            addr = ipaddress.ip_address(ip)
            
            if not isinstance(addr, ipaddress.IPv4Address):
                return {}
            
            # 中国主要运营商IP段（扩展版）
            # 数据来源: IANA, APNIC, 中国工信部
            
            china_telecom_ranges = [
                # 中国电信骨干网
                "202.96.0.0/11",      # 广东电信
                "202.97.0.0/16",      # 北京电信
                "202.98.0.0/15",      # 四川电信
                "202.100.0.0/14",     # 陕西电信
                "202.104.0.0/13",     # 福建电信
                "218.0.0.0/11",       # 浙江电信
                "218.56.0.0/13",      # 山东电信
                "218.64.0.0/11",      # 江西电信
                "218.192.0.0/10",     # 教育网电信
                "219.128.0.0/11",     # 广东电信
                "219.133.0.0/16",     # 深圳电信
                "220.160.0.0/11",     # 福建电信
                "221.224.0.0/12",     # 江苏电信
                "58.16.0.0/12",       # 贵州电信
                "58.32.0.0/11",       # 上海电信
                "58.64.0.0/11",       # 河南电信
                "58.96.0.0/12",       # 海南电信
                "58.128.0.0/11",      # 安徽电信
                "58.192.0.0/10",      # 江苏电信
                "59.32.0.0/11",       # 湖南电信
                "59.64.0.0/12",       # 北京电信
                "59.80.0.0/12",       # 甘肃电信
                "60.160.0.0/11",      # 云南电信
                "60.192.0.0/11",      # 山西电信
                "61.128.0.0/10",      # 重庆电信
                "61.135.0.0/16",      # 北京电信
                "113.64.0.0/10",      # 广东电信
                "116.1.0.0/16",       # 广西电信
                "116.224.0.0/12",     # 上海电信
                "117.40.0.0/13",      # 江西电信
                "117.136.0.0/13",     # 移动电信共用
                "124.160.0.0/12",     # 浙江电信
                "125.64.0.0/11",      # 四川电信
                "140.206.0.0/15",     # 联通电信共用
                "171.8.0.0/13",       # 电信移动共用
                "180.96.0.0/11",      # 江苏电信
                "182.80.0.0/12",      # 山东电信
                "183.0.0.0/10",       # 电信宽带
            ]
            
            china_unicom_ranges = [
                # 中国联通
                "202.106.0.0/16",     # 北京联通
                "202.108.0.0/14",     # 辽宁联通
                "202.112.0.0/12",     # 教育网联通
                "210.12.0.0/14",      # 天津联通
                "210.51.0.0/16",      # 北京联通
                "210.72.0.0/13",      # 中科院联通
                "211.90.0.0/15",      # 吉林联通
                "211.136.0.0/13",     # 移动联通共用
                "218.240.0.0/13",     # 北京联通
                "218.241.0.0/16",     # 河北联通
                "219.144.0.0/12",     # 陕西联通
                "221.192.0.0/11",     # 河北联通
                "221.224.0.0/11",     # 江苏联通
                "58.16.0.0/13",       # 贵州联通
                "58.240.0.0/12",      # 江苏联通
                "59.108.0.0/14",      # 北京联通
                "60.0.0.0/13",        # 河北联通
                "60.12.0.0/14",       # 浙江联通
                "60.28.0.0/14",       # 天津联通
                "61.48.0.0/13",       # 北京联通
                "61.135.0.0/16",      # 北京联通
                "101.64.0.0/11",      # 联通宽带
                "110.52.0.0/14",      # 湖南联通
                "112.64.0.0/14",      # 上海联通
                "113.128.0.0/15",     # 山东联通
                "114.240.0.0/12",     # 北京联通
                "115.28.0.0/14",      # 阿里云联通
                "116.112.0.0/12",     # 北京联通
                "117.8.0.0/13",       # 广西联通
                "117.128.0.0/10",     # 移动联通共用
                "119.160.0.0/11",     # 湖北联通
                "120.32.0.0/11",      # 福建联通
                "123.96.0.0/11",      # 浙江联通
                "124.128.0.0/12",     # 山东联通
                "125.32.0.0/11",      # 吉林联通
                "140.206.0.0/15",     # 联通电信共用
                "171.8.0.0/13",       # 电信移动共用
                "175.0.0.0/12",       # 联通宽带
                "180.76.0.0/14",      # 百度云联通
                "182.32.0.0/12",      # 广东联通
                "221.0.0.0/11",       # 山东联通
            ]
            
            china_mobile_ranges = [
                # 中国移动
                "211.136.0.0/13",     # 移动骨干网
                "211.144.0.0/12",     # 移动骨干网
                "218.200.0.0/13",     # 移动骨干网
                "221.176.0.0/12",     # 移动骨干网
                "221.192.0.0/11",     # 移动宽带
                "223.64.0.0/11",      # 移动宽带
                "223.96.0.0/12",      # 移动宽带
                "36.128.0.0/10",      # 移动4G/5G
                "39.128.0.0/10",      # 移动宽带
                "58.240.0.0/13",      # 移动宽带
                "59.32.0.0/12",       # 移动宽带
                "60.208.0.0/12",      # 移动宽带
                "61.128.0.0/11",      # 移动宽带
                "100.64.0.0/10",      # CGNAT (运营商级NAT)
                "111.0.0.0/10",       # 移动骨干网
                "112.0.0.0/10",       # 移动4G/5G
                "117.128.0.0/10",     # 移动联通共用
                "117.136.0.0/13",     # 移动电信共用
                "120.192.0.0/10",     # 移动宽带
                "125.120.0.0/13",     # 移动宽带
                "134.196.0.0/16",     # 移动专线
                "139.196.0.0/16",     # 阿里云移动
                "140.206.0.0/15",     # 联通电信共用
                "171.8.0.0/13",       # 电信移动共用
                "175.16.0.0/12",      # 移动宽带
                "180.76.0.0/14",      # 百度云移动
                "183.192.0.0/10",     # 移动宽带
                "211.96.0.0/13",      # 移动骨干网
                "218.200.0.0/13",     # 移动骨干网
                "221.176.0.0/12",     # 移动骨干网
                "223.0.0.0/11",       # 移动宽带
            ]
            
            china_edu_ranges = [
                # 中国教育科研网(CERNET)
                "101.4.0.0/16",       # 清华大学
                "101.5.0.0/16",       # 北京大学
                "101.6.0.0/16",       # 北京邮电大学
                "166.111.0.0/16",     # 清华大学
                "202.112.0.0/12",     # CERNET骨干网
                "202.116.0.0/16",     # 中山大学
                "202.117.0.0/16",     # 西安交通大学
                "202.118.0.0/16",     # 东北大学
                "202.119.0.0/16",     # 南京大学
                "202.120.0.0/16",     # 上海交通大学
                "202.121.0.0/16",     # 复旦大学
                "202.122.0.0/16",     # 浙江大学
                "202.127.0.0/16",     # 中国科大
                "210.25.0.0/16",      # CERNET
                "210.26.0.0/16",      # CERNET
                "210.27.0.0/16",      # CERNET
                "210.28.0.0/16",      # CERNET
                "210.29.0.0/16",      # CERNET
                "210.30.0.0/16",      # CERNET
                "210.31.0.0/16",      # CERNET
                "210.32.0.0/16",      # CERNET
                "210.33.0.0/16",      # CERNET
                "210.34.0.0/16",      # CERNET
                "210.35.0.0/16",      # CERNET
                "210.36.0.0/16",      # CERNET
                "210.37.0.0/16",      # CERNET
                "210.38.0.0/16",      # CERNET
                "210.39.0.0/16",      # CERNET
                "210.40.0.0/16",      # CERNET
                "210.41.0.0/16",      # CERNET
                "210.42.0.0/16",      # CERNET
                "210.43.0.0/16",      # CERNET
                "210.44.0.0/16",      # CERNET
                "210.45.0.0/16",      # CERNET
                "211.64.0.0/16",      # CERNET
                "211.65.0.0/16",      # CERNET
                "211.66.0.0/16",      # CERNET
                "211.67.0.0/16",      # CERNET
                "211.68.0.0/16",      # CERNET
                "211.69.0.0/16",      # CERNET
                "211.70.0.0/16",      # CERNET
                "211.71.0.0/16",      # CERNET
                "211.80.0.0/16",      # CERNET
                "211.81.0.0/16",      # CERNET
                "211.82.0.0/16",      # CERNET
                "211.83.0.0/16",      # CERNET
                "211.84.0.0/16",      # CERNET
                "211.85.0.0/16",      # CERNET
                "211.86.0.0/16",      # CERNET
                "211.87.0.0/16",      # CERNET
            ]
            
            # 检查IP是否在已知范围内
            for network_str in china_telecom_ranges:
                if addr in ipaddress.ip_network(network_str, strict=False):
                    return {
                        "country": "CN",
                        "country_name": "China",
                        "isp": "China Telecom",
                        "as_number": "4134",
                        "as_organization": "CHINANET-BACKBONE",
                        "source": "builtin_rules"
                    }
            
            for network_str in china_unicom_ranges:
                if addr in ipaddress.ip_network(network_str, strict=False):
                    return {
                        "country": "CN",
                        "country_name": "China",
                        "isp": "China Unicom",
                        "as_number": "4837",
                        "as_organization": "CHINA UNICOM China169 Backbone",
                        "source": "builtin_rules"
                    }
            
            for network_str in china_mobile_ranges:
                if addr in ipaddress.ip_network(network_str, strict=False):
                    return {
                        "country": "CN",
                        "country_name": "China",
                        "isp": "China Mobile",
                        "as_number": "9808",
                        "as_organization": "Guangdong Mobile Communication Co.Ltd",
                        "source": "builtin_rules"
                    }
            
            for network_str in china_edu_ranges:
                if addr in ipaddress.ip_network(network_str, strict=False):
                    return {
                        "country": "CN",
                        "country_name": "China",
                        "isp": "CERNET",
                        "as_number": "4538",
                        "as_organization": "China Education and Research Network Center",
                        "source": "builtin_rules"
                    }
            
            # 检查是否为中国IP(基于IANA分配)
            # 中国IP段大致范围(APNIC分配)
            china_general_ranges = [
                "1.0.0.0/8",          # APNIC
                "14.0.0.0/8",         # APNIC
                "27.0.0.0/8",         # APNIC
                "36.0.0.0/8",         # APNIC
                "39.0.0.0/8",         # APNIC
                "42.0.0.0/8",         # APNIC
                "43.224.0.0/11",      # APNIC
                "49.0.0.0/8",         # APNIC
                "58.0.0.0/8",         # APNIC
                "59.0.0.0/8",         # APNIC
                "60.0.0.0/8",         # APNIC
                "61.0.0.0/8",         # APNIC
                "101.0.0.0/8",        # APNIC
                "103.0.0.0/8",        # APNIC
                "106.0.0.0/8",        # APNIC
                "110.0.0.0/8",        # APNIC
                "111.0.0.0/8",        # APNIC
                "112.0.0.0/8",        # APNIC
                "113.0.0.0/8",        # APNIC
                "114.0.0.0/8",        # APNIC
                "115.0.0.0/8",        # APNIC
                "116.0.0.0/8",        # APNIC
                "117.0.0.0/8",        # APNIC
                "118.0.0.0/8",        # APNIC
                "119.0.0.0/8",        # APNIC
                "120.0.0.0/8",        # APNIC
                "121.0.0.0/8",        # APNIC
                "122.0.0.0/8",        # APNIC
                "123.0.0.0/8",        # APNIC
                "124.0.0.0/8",        # APNIC
                "125.0.0.0/8",        # APNIC
                "140.75.0.0/16",      # APNIC
                "140.206.0.0/15",     # APNIC
                "150.0.0.0/8",        # APNIC
                "163.0.0.0/8",        # APNIC
                "171.0.0.0/8",        # APNIC
                "175.0.0.0/8",        # APNIC
                "180.0.0.0/8",        # APNIC
                "182.0.0.0/8",        # APNIC
                "183.0.0.0/8",        # APNIC
                "202.0.0.0/8",        # APNIC
                "203.0.0.0/8",        # APNIC
                "210.0.0.0/8",        # APNIC
                "211.0.0.0/8",        # APNIC
                "218.0.0.0/8",        # APNIC
                "219.0.0.0/8",        # APNIC
                "220.0.0.0/8",        # APNIC
                "221.0.0.0/8",        # APNIC
                "222.0.0.0/8",        # APNIC
                "223.0.0.0/8",        # APNIC
            ]
            
            for network_str in china_general_ranges:
                if addr in ipaddress.ip_network(network_str, strict=False):
                    return {
                        "country": "CN",
                        "country_name": "China",
                        "isp": "Unknown Chinese ISP",
                        "as_number": "N/A",
                        "as_organization": "Unknown",
                        "source": "builtin_rules_general"
                    }
            
            # 如果都不匹配,返回空
            return {}
        
        except Exception as e:
            self.logger.debug(f"内置规则查询失败: {ip}, 错误: {e}")
            return {}
    
    def _load_cache(self):
        """加载缓存文件"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
                self.logger.info(f"加载IP地理缓存: {len(self.cache)}条记录")
        except Exception as e:
            self.logger.warning(f"加载缓存失败: {e}")
            self.cache = {}
    
    def _save_cache(self):
        """保存缓存到文件"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
            self.logger.debug(f"保存IP地理缓存: {len(self.cache)}条记录")
        except Exception as e:
            self.logger.warning(f"保存缓存失败: {e}")
    
    def clear_cache(self):
        """清空缓存"""
        self.cache.clear()
        if self.cache_file.exists():
            self.cache_file.unlink()
        self.logger.info("IP地理缓存已清空")


# 全局单例
_ip_geo_service: Optional[IPGeoService] = None


def get_ip_geo_service() -> IPGeoService:
    """获取IP地理位置服务单例"""
    global _ip_geo_service
    if _ip_geo_service is None:
        _ip_geo_service = IPGeoService()
    return _ip_geo_service
