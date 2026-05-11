"""
HAR解析器单元测试

使用样本HAR数据验证HarParser的解析逻辑。
"""

import json
import os
import pytest
import tempfile

from sdwan_desktop.services.parser.har_parser import HarParser


@pytest.fixture
def sample_har_content():
    """创建样本HAR内容"""
    return {
        "log": {
            "version": "1.2",
            "creator": {"name": "Test", "version": "1.0"},
            "pages": [{"startedDateTime": "https://example.com"}],
            "entries": [
                {
                    "request": {"url": "https://example.com/index.html", "method": "GET"},
                    "response": {"status": 200, "bodySize": 1024, "content": {"mimeType": "text/html"}},
                    "timings": {"dns": 10, "connect": 20, "ssl": 30, "wait": 100, "receive": 50}
                },
                {
                    "request": {"url": "https://example.com/style.css", "method": "GET"},
                    "response": {"status": 200, "bodySize": 512, "content": {"mimeType": "text/css"}},
                    "timings": {"dns": 5, "connect": 10, "ssl": -1, "wait": 50, "receive": 20}
                }
            ]
        }
    }


@pytest.fixture
def har_file(sample_har_content):
    """创建临时HAR文件"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.har', delete=False) as f:
        json.dump(sample_har_content, f)
        f.flush()
        yield f.name
    os.unlink(f.name)


def test_har_parser_parse(har_file):
    """测试HAR解析基本功能"""
    parser = HarParser()
    result = parser.parse(har_file, trace_id="test-trace-123")
    
    assert result.trace_id == "test-trace-123"
    assert result.total_requests == 2
    assert result.total_size_bytes == 1536  # 1024 + 512
    assert len(result.resources) == 2
    
    # 验证第一个资源
    res1 = result.resources[0]
    assert res1.url == "https://example.com/index.html"
    assert res1.dns_time == 10
    assert res1.connect_time == 20
    assert res1.ssl_time == 30
    assert res1.wait_time == 100
    assert res1.download_time == 50
    assert res1.is_render_blocking is False
    
    # 验证第二个资源（CSS应标记为渲染阻塞）
    res2 = result.resources[1]
    assert res2.mime_type == "text/css"
    assert res2.is_render_blocking is True
    assert res2.ssl_time == 0  # -1 should be converted to 0


def test_har_parser_stats_calculation(har_file):
    """测试统计信息计算"""
    parser = HarParser()
    result = parser.parse(har_file)
    
    # 验证最慢资源排序
    assert len(result.slowest_resources) > 0
    # 第一个资源总耗时 210ms，第二个 85ms
    assert result.slowest_resources[0].url == "https://example.com/index.html"
    
    # 验证渲染阻塞计数
    assert result.render_blocking_count == 1


def test_har_parser_invalid_file():
    """测试无效HAR文件处理"""
    parser = HarParser()
    with pytest.raises(Exception):
        parser.parse("non_existent_file.har")
