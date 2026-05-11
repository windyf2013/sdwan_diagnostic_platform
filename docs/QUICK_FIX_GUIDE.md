# 打包后HTML报告为空 - 快速修复指南

## 问题现象
- `agentctl quick-check` 正常生成报告
- 打包后的GUI工具一键体检生成的HTML报告内容为空

## 根本原因
1. 模板文件路径配置错误
2. PyInstaller环境未适配
3. GUI缺少evidences数据链

## 修复步骤（已完成）

### ✅ 1. 修正构建脚本
**文件**: `scripts/build.py`
```python
# 修改前
'--add-data=templates;templates',

# 修改后
'--add-data=src/sdwan_desktop/reporting/templates;sdwan_desktop/reporting/templates',
```

### ✅ 2. 支持PyInstaller环境
**文件**: `src/sdwan_desktop/services/reporter/html_builder.py`
```python
import sys
if getattr(sys, 'frozen', False):
    base_path = Path(sys._MEIPASS)
    template_dir = base_path / "sdwan_desktop" / "reporting" / "templates"
else:
    template_dir = Path(__file__).parent.parent.parent / "reporting" / "templates"
```

### ✅ 3. 补全GUI证据链
**文件**: `src/sdwan_desktop/interface/gui/tabs/quick_check_tab.py`

在`step_conclusion`中添加：
```python
evidence_connectivity = ctx.get("evidence_connectivity")
evidences = [evidence_connectivity] if evidence_connectivity else []

diagnosis_result = DiagnosisResult(
    # ... 其他字段 ...
    evidences=evidences,  # 添加这一行
)
```

在`step_report`中添加DNS和CPE证据填充（参考CLI实现）

## 验证步骤

```bash
# 1. 运行测试
pytest tests/flow/test_packaged_html_report.py -v

# 2. 清理并重新打包
python scripts/clean_cache.py
python scripts/build.py

# 3. 测试打包后的工具
dist/sdwan-diagnostic-gui.exe
```

## 检查清单

打包后生成的HTML报告应包含：
- [ ] Trace ID
- [ ] 系统信息（网卡、IP、网关）
- [ ] 连通性测试结果
- [ ] DNS解析结果
- [ ] DNS分流检测详情
- [ ] 根因分析和建议（如果有问题）

文件大小应 > 10KB

## 相关文件
- 详细文档: `docs/packaged_html_report_fix.md`
- 测试脚本: `tests/flow/test_packaged_html_report.py`
- CLI参考: `src/sdwan_desktop/interface/cli/commands/quick_check.py`
