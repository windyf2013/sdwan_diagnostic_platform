"""
RAISECOM MSG5200D 配置解析器

针对 Raisecom 5200D CPE（x86，PV **D.00**，如 ``MSG5200-2GEC-4E-X4``）：
与 5200B 命令与解析逻辑基本一致，指纹见 ``templates/feature_config_5200d.txt``。

**诊断视图**：5200D 与 5200B 相同，在 enable（host#）下使用 ``su`` 进入 Linux shell；
x86 固件提示符常为 ``root@host:/#``（采集器须识别，见 ``CpeCollector``）。

遵循 SDWAN_SPEC.md 工具与数据契约相关章节。
"""

from sdwan_desktop.services.parser.vendor.raisecom_msg5200 import (
    RaisecomMsg5200Parser,
    is_raisecom_msg5200d_version_output,
)


class RaisecomMsg5200DParser(RaisecomMsg5200Parser):
    """RAISECOM MSG5200D 系列（5200D CPE）配置解析器。"""

    def get_vendor_name(self) -> str:
        """返回厂商/型号标识，用于注册表与采集命令模板路由。"""
        return "raisecom_msg5200d"

    def detect_vendor(self, raw_output: str) -> bool:
        """检测是否为 MSG5200D（PV D.00 / PN MSG5200-2GEC 等；与 B/A 互斥）。"""
        if not raw_output:
            return False
        lowered = raw_output.lower()
        base = any(x in lowered for x in ("raisecom", "msg5200", "rcios"))
        if not base:
            return False
        return is_raisecom_msg5200d_version_output(raw_output)
