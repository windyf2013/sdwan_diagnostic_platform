"""
ConfigLoader 单元测试

测试配置加载器的以下功能：
1. 从 YAML 文件加载配置
2. 配置解析为 QuickCheckConfig 数据类
3. 默认配置处理
4. 配置不存在时的降级行为
5. 配置重新加载

遵循 SDWAN_SPEC_PATCHES.md PATCH-001 覆盖率门槛
遵循 SDWAN_SPEC_PATCHES.md PATCH-002 dict边界规则
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from sdwan_desktop.core.config.loader import (
    ConfigLoader,
    ProbeTargetConfig,
    QuickCheckConfig,
    ThresholdConfig,
)


class TestProbeTargetConfig:
    """ProbeTargetConfig 数据类测试"""

    def test_default_type(self):
        """测试默认协议类型为 icmp"""
        config = ProbeTargetConfig(host="8.8.8.8")
        assert config.host == "8.8.8.8"
        assert config.type == "icmp"

    def test_custom_type(self):
        """测试自定义协议类型"""
        config = ProbeTargetConfig(host="www.baidu.com", type="http")
        assert config.host == "www.baidu.com"
        assert config.type == "http"

    def test_slots(self):
        """测试 slots 生效"""
        config = ProbeTargetConfig(host="test.com")
        with pytest.raises(AttributeError):
            config.non_existent_attr = "value"


class TestThresholdConfig:
    """ThresholdConfig 数据类测试"""

    def test_default_values(self):
        """测试默认阈值"""
        config = ThresholdConfig()
        assert config.gateway_rtt_warning_ms == 100
        assert config.gateway_loss_warning_pct == 5
        assert config.dns_timeout_ms == 2000
        assert config.dns_slow_ms == 500
        assert config.international_loss_warning_pct == 10

    def test_custom_values(self):
        """测试自定义阈值"""
        config = ThresholdConfig(
            gateway_rtt_warning_ms=200,
            gateway_loss_warning_pct=10,
            dns_timeout_ms=3000,
            dns_slow_ms=1000,
            international_loss_warning_pct=20,
        )
        assert config.gateway_rtt_warning_ms == 200
        assert config.gateway_loss_warning_pct == 10
        assert config.dns_timeout_ms == 3000
        assert config.dns_slow_ms == 1000
        assert config.international_loss_warning_pct == 20


class TestQuickCheckConfig:
    """QuickCheckConfig 数据类测试"""

    def test_default_values(self):
        """测试默认配置值"""
        config = QuickCheckConfig()

        # 采集开关
        assert config.collection_adapters is True
        assert config.collection_routes is True
        assert config.collection_dns is True
        assert config.collection_proxy is True
        assert config.collection_firewall is True
        assert config.collection_arp is True
        assert config.collection_ipv6 is True

        # DNS 服务器
        assert "114.114.114.114" in config.domestic_dns_servers
        assert "223.5.5.5" in config.domestic_dns_servers
        assert "8.8.8.8" in config.international_dns_servers
        assert "1.1.1.1" in config.international_dns_servers

        # 连通性目标
        assert len(config.domestic_targets) == 2
        assert config.domestic_targets[0].host == "www.baidu.com"
        assert config.domestic_targets[0].type == "http"
        assert config.domestic_targets[1].host == "114.114.114.114"
        assert config.domestic_targets[1].type == "icmp"

        assert len(config.international_targets) == 2
        assert config.international_targets[0].host == "www.google.com"
        assert config.international_targets[0].type == "http"
        assert config.international_targets[1].host == "8.8.8.8"
        assert config.international_targets[1].type == "icmp"

        # DNS 分流测试域名
        assert "www.google.com" in config.dns_split_domains
        assert "www.baidu.com" in config.dns_split_domains
        assert "github.com" in config.dns_split_domains

        # 阈值
        assert config.thresholds.gateway_rtt_warning_ms == 100

        # 并发控制
        assert config.max_concurrent_probes == 5
        assert config.max_concurrent_dns_queries == 3
        assert config.probe_interval == 0.5

    def test_to_target_dicts(self):
        """测试 to_target_dicts 方法"""
        config = QuickCheckConfig()
        targets = [
            ProbeTargetConfig(host="test1.com", type="icmp"),
            ProbeTargetConfig(host="test2.com", type="http"),
        ]
        result = config.to_target_dicts(targets)

        assert len(result) == 2
        assert result[0] == {"host": "test1.com", "type": "icmp"}
        assert result[1] == {"host": "test2.com", "type": "http"}

    def test_to_target_dicts_empty(self):
        """测试空列表转换"""
        config = QuickCheckConfig()
        result = config.to_target_dicts([])
        assert result == []


class TestConfigLoader:
    """ConfigLoader 测试类"""

    def _create_temp_config(self, content: dict) -> str:
        """创建临时配置文件"""
        tmp_dir = tempfile.mkdtemp()
        config_path = os.path.join(tmp_dir, "quick_check.yaml")
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(content, f)
        return config_path

    def test_load_default_when_file_not_exists(self):
        """测试配置文件不存在时返回默认配置"""
        loader = ConfigLoader(config_path="/nonexistent/path/config.yaml")
        config = loader.load()

        assert isinstance(config, QuickCheckConfig)
        assert config.collection_adapters is True
        assert "114.114.114.114" in config.domestic_dns_servers

    def test_load_empty_file(self):
        """测试空文件返回默认配置"""
        tmp_dir = tempfile.mkdtemp()
        config_path = os.path.join(tmp_dir, "empty.yaml")
        Path(config_path).touch()

        loader = ConfigLoader(config_path=config_path)
        config = loader.load()

        assert isinstance(config, QuickCheckConfig)

    def test_load_full_config(self):
        """测试加载完整配置"""
        config_content = {
            "quick_check": {
                "collection": {
                    "adapters": True,
                    "routes": False,
                    "dns": True,
                    "proxy": False,
                    "firewall": True,
                    "arp": False,
                    "ipv6": False,
                },
                "targets": {
                    "dns_servers": {
                        "domestic": ["114.114.114.114"],
                        "international": ["8.8.8.8"],
                    },
                    "connectivity": {
                        "domestic": [
                            {"host": "www.baidu.com", "type": "http"},
                        ],
                        "international": [
                            {"host": "www.google.com", "type": "http"},
                        ],
                    },
                    "dns_split_domains": ["www.google.com"],
                },
                "thresholds": {
                    "gateway_rtt_warning_ms": 200,
                    "gateway_loss_warning_pct": 10,
                    "dns_timeout_ms": 3000,
                    "dns_slow_ms": 1000,
                    "international_loss_warning_pct": 20,
                },
                "max_concurrent_probes": 10,
                "max_concurrent_dns_queries": 5,
                "probe_interval": 1.0,
                "config_version": "2.0.0",
            }
        }

        config_path = self._create_temp_config(config_content)
        loader = ConfigLoader(config_path=config_path)
        config = loader.load()

        # 验证采集开关
        assert config.collection_adapters is True
        assert config.collection_routes is False
        assert config.collection_dns is True
        assert config.collection_proxy is False
        assert config.collection_firewall is True
        assert config.collection_arp is False
        assert config.collection_ipv6 is False

        # 验证 DNS 服务器
        assert config.domestic_dns_servers == ["114.114.114.114"]
        assert config.international_dns_servers == ["8.8.8.8"]

        # 验证连通性目标
        assert len(config.domestic_targets) == 1
        assert config.domestic_targets[0].host == "www.baidu.com"
        assert config.domestic_targets[0].type == "http"

        assert len(config.international_targets) == 1
        assert config.international_targets[0].host == "www.google.com"
        assert config.international_targets[0].type == "http"

        # 验证 DNS 分流测试域名
        assert config.dns_split_domains == ["www.google.com"]

        # 验证阈值
        assert config.thresholds.gateway_rtt_warning_ms == 200
        assert config.thresholds.gateway_loss_warning_pct == 10
        assert config.thresholds.dns_timeout_ms == 3000
        assert config.thresholds.dns_slow_ms == 1000
        assert config.thresholds.international_loss_warning_pct == 20

        # 验证并发控制
        assert config.max_concurrent_probes == 10
        assert config.max_concurrent_dns_queries == 5
        assert config.probe_interval == 1.0

        # 验证元信息
        assert config.config_version == "2.0.0"

    def test_load_partial_config(self):
        """测试加载部分配置（缺失字段使用默认值）"""
        config_content = {
            "quick_check": {
                "collection": {
                    "adapters": False,
                },
                "targets": {
                    "dns_servers": {
                        "domestic": ["1.1.1.1"],
                    },
                },
            }
        }

        config_path = self._create_temp_config(config_content)
        loader = ConfigLoader(config_path=config_path)
        config = loader.load()

        # 显式设置的字段
        assert config.collection_adapters is False
        assert config.domestic_dns_servers == ["1.1.1.1"]

        # 未设置的字段使用默认值
        assert config.collection_routes is True
        assert "8.8.8.8" in config.international_dns_servers
        assert config.thresholds.gateway_rtt_warning_ms == 100

    def test_load_without_quick_check_key(self):
        """测试配置没有 quick_check 顶层键"""
        config_content = {
            "collection": {
                "adapters": False,
            },
            "targets": {
                "dns_servers": {
                    "domestic": ["1.1.1.1"],
                },
            },
        }

        config_path = self._create_temp_config(config_content)
        loader = ConfigLoader(config_path=config_path)
        config = loader.load()

        assert config.collection_adapters is False
        assert config.domestic_dns_servers == ["1.1.1.1"]

    def test_reload(self):
        """测试重新加载配置"""
        config_content_v1 = {
            "quick_check": {
                "config_version": "1.0.0",
                "targets": {
                    "dns_servers": {
                        "domestic": ["114.114.114.114"],
                    },
                },
            }
        }

        config_path = self._create_temp_config(config_content_v1)
        loader = ConfigLoader(config_path=config_path)
        config_v1 = loader.load()

        assert config_v1.config_version == "1.0.0"
        assert config_v1.domestic_dns_servers == ["114.114.114.114"]

        # 修改配置文件
        config_content_v2 = {
            "quick_check": {
                "config_version": "2.0.0",
                "targets": {
                    "dns_servers": {
                        "domestic": ["223.5.5.5"],
                    },
                },
            }
        }

        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_content_v2, f)

        config_v2 = loader.reload()

        assert config_v2.config_version == "2.0.0"
        assert config_v2.domestic_dns_servers == ["223.5.5.5"]

    def test_find_default_config(self):
        """测试查找默认配置文件"""
        # 不传 config_path，应自动查找默认路径
        loader = ConfigLoader()
        assert "quick_check.yaml" in loader.config_path

    def test_parse_targets_empty(self):
        """测试解析空目标列表"""
        loader = ConfigLoader()
        result = loader._parse_targets([])
        assert result == []

    def test_parse_targets_with_items(self):
        """测试解析目标列表"""
        loader = ConfigLoader()
        raw = [
            {"host": "test1.com", "type": "icmp"},
            {"host": "test2.com", "type": "http"},
            {"host": "test3.com"},  # 缺少 type
        ]
        result = loader._parse_targets(raw)

        assert len(result) == 3
        assert result[0].host == "test1.com"
        assert result[0].type == "icmp"
        assert result[1].host == "test2.com"
        assert result[1].type == "http"
        assert result[2].host == "test3.com"
        assert result[2].type == "icmp"  # 默认值

    def test_yaml_parse_error(self):
        """测试 YAML 解析错误"""
        tmp_dir = tempfile.mkdtemp()
        config_path = os.path.join(tmp_dir, "bad.yaml")
        with open(config_path, "w", encoding="utf-8") as f:
            f.write("invalid: yaml: : : : broken")

        loader = ConfigLoader(config_path=config_path)
        with pytest.raises(Exception):
            loader.load()
