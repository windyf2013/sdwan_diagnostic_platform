"""
性能基准测试共享 Fixtures

提供用于性能监控的工具和配置。
"""

import pytest
import time
import psutil
import os


@pytest.fixture
def perf_monitor():
    """提供一个性能监控器，用于记录开始和结束时间及内存占用"""
    class Monitor:
        def __init__(self):
            self.start_time = 0
            self.end_time = 0
            self.start_mem = 0
            self.end_mem = 0
            
        def start(self):
            self.start_time = time.perf_counter()
            self.start_mem = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024  # MB
            
        def stop(self):
            self.end_time = time.perf_counter()
            self.end_mem = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024  # MB
            
        @property
        def duration_ms(self):
            return (self.end_time - self.start_time) * 1000
            
        @property
        def memory_delta_mb(self):
            return self.end_mem - self.start_mem
            
    return Monitor()
