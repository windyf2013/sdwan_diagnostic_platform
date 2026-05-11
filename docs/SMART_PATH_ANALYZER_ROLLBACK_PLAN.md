# 智能路径分流点检测 - 回滚预案

**版本**: 1.0  
**最后更新**: 2026-05-01  
**优先级**: P0（关键）

---

## 📋 **概述**

本文档定义了智能路径分流点检测功能的**回滚策略和应急预案**，确保在出现严重问题时能够快速恢复到稳定状态。

### 回滚触发条件

以下情况需要立即执行回滚：

1. ❌ **准确率大幅下降**：CPE识别准确率从95%+下降到80%以下
2. ❌ **性能严重退化**：单次分析耗时超过1秒（正常应<10ms）
3. ❌ **系统崩溃**：导致诊断平台无法启动或频繁崩溃
4. ❌ **数据错误**：生成错误的CPE位置，影响业务决策
5. ❌ **内存泄漏**：长时间运行后内存占用持续增长

---

## 🔄 **回滚策略**

### 策略1: 快速降级（推荐）

**适用场景**：智能分析器出现问题，但需要保持功能可用

**操作步骤**：

1. **修改配置文件**
   ```yaml
   # config/smart_path_analyzer.yaml
   enabled: false  # 禁用智能分析器
   fallback_mode: true  # 启用降级模式
   ```

2. **重启服务**
   ```bash
   systemctl restart sdwan-diagnostic
   ```

3. **验证回滚效果**
   ```bash
   agentctl quick-check --output test_report.html
   grep "智能路径分析" logs/app.log
   ```

**预期结果**：
- ✅ 系统使用固定的第2跳作为CPE位置（旧逻辑）
- ✅ 功能恢复正常，但准确率降低到~40%
- ✅ 日志中显示"使用降级策略"

**优点**：
- ✅ 快速执行（<1分钟）
- ✅ 无需代码修改
- ✅ 可随时恢复

**缺点**：
- ❌ 准确率大幅下降
- ❌ 失去多维度分析能力

---

### 策略2: 代码回滚

**适用场景**：智能分析器存在严重bug，需要完全移除

**操作步骤**：

1. **备份当前版本**
   ```bash
   git tag backup-before-rollback-$(date +%Y%m%d)
   git push origin --tags
   ```

2. **回滚到Phase 1之前的版本**
   ```bash
   git revert <commit-hash-of-phase1-start>..HEAD
   ```

3. **或者手动删除新增文件**
   ```bash
   # 删除新增的智能分析器模块
   rm src/sdwan_desktop/services/smart_path_analyzer.py
   rm src/sdwan_desktop/services/ip_geo_service.py
   
   # 恢复dns_split.py到旧版本
   git checkout HEAD~10 -- src/sdwan_desktop/services/dns_split.py
   ```

4. **重新部署**
   ```bash
   python setup.py install
   systemctl restart sdwan-diagnostic
   ```

5. **验证回滚效果**
   ```bash
   agentctl quick-check --output test_report.html
   python tests/integration/test_smart_path_analyzer.py --sample
   ```

**预期结果**：
- ✅ 系统完全回到Phase 1之前的状态
- ✅ 使用固定的第2跳作为CPE位置
- ✅ 所有新功能被移除

**优点**：
- ✅ 彻底解决问题
- ✅ 代码干净，无残留

**缺点**：
- ❌ 执行时间较长（5-10分钟）
- ❌ 丢失所有改进
- ❌ 需要重新测试

---

### 策略3: 部分禁用

**适用场景**：某个特定功能模块有问题，其他功能正常

**操作步骤**：

1. **禁用AS号分析**
   ```python
   # 在 smart_path_analyzer.py 的 analyze 方法中
   # as_feature = self._identify_by_as_change(full_path)  # 注释掉
   as_feature = None  # 强制设为None
   ```

2. **禁用地理位置查询**
   ```python
   # 在 smart_path_analyzer.py 的 analyze 方法中
   # self._enrich_hops_with_geo_info(full_path)  # 注释掉
   pass  # 跳过地理位置填充
   ```

3. **重启服务**
   ```bash
   systemctl restart sdwan-diagnostic
   ```

**预期结果**：
- ✅ 保留Hostname匹配和RTT突变功能
- ✅ 准确率达到~70%（介于Phase 1和Phase 2之间）
- ✅ 性能提升（不再查询IP地理信息）

**优点**：
- ✅ 灵活控制，可针对性禁用问题模块
- ✅ 保留部分改进

**缺点**：
- ❌ 需要代码修改
- ❌ 可能引入新的不一致性

---

## 🚨 **应急响应流程**

### 阶段1: 问题识别（0-5分钟）

**监控指标**：
```bash
# 检查错误日志
tail -f logs/app.log | grep "ERROR.*智能路径分析"

# 检查性能指标
grep "耗时=" logs/app.log | tail -20

# 检查置信度分布
grep "置信度=" logs/app.log | awk -F'置信度=' '{print $2}' | sort | uniq -c
```

**判断标准**：
- ❌ 错误率 > 10% → 需要回滚
- ❌ 平均耗时 > 500ms → 需要回滚
- ❌ 低置信度(<0.3)占比 > 50% → 需要调查

---

### 阶段2: 快速评估（5-15分钟）

**评估步骤**：

1. **收集问题样本**
   ```bash
   # 导出最近100次分析的日志
   grep "智能路径分析" logs/app.log | tail -100 > /tmp/analysis_samples.log
   ```

2. **运行测试套件**
   ```bash
   python tests/integration/test_smart_path_analyzer.py \
     --domains-file tests/integration/test_cases_smart_path.json \
     --phase phase2
   ```

3. **对比历史数据**
   ```bash
   # 查看之前的测试报告
   cat tests/reports/smart_path_analyzer_phase2_report.json
   ```

**决策矩阵**：

| 问题类型 | 严重程度 | 建议操作 |
|---------|---------|---------|
| 准确率下降10%以内 | 低 | 继续观察，收集更多数据 |
| 准确率下降10-20% | 中 | 部分禁用问题模块 |
| 准确率下降20%以上 | 高 | 快速降级或代码回滚 |
| 系统崩溃 | 紧急 | 立即代码回滚 |

---

### 阶段3: 执行回滚（15-30分钟）

**根据评估结果选择回滚策略**：

#### 选项A: 快速降级（推荐首选）
```bash
# 1. 修改配置
sed -i 's/enabled: true/enabled: false/' config/smart_path_analyzer.yaml

# 2. 重启服务
systemctl restart sdwan-diagnostic

# 3. 验证
agentctl quick-check --output rollback_test.html
```

**预计耗时**：5分钟

---

#### 选项B: 部分禁用
```bash
# 1. 编辑代码
vim src/sdwan_desktop/services/smart_path_analyzer.py
# 注释掉有问题的功能模块

# 2. 重新安装
python setup.py install

# 3. 重启服务
systemctl restart sdwan-diagnostic

# 4. 验证
python tests/integration/test_smart_path_analyzer.py --sample
```

**预计耗时**：15分钟

---

#### 选项C: 代码回滚
```bash
# 1. 备份当前版本
git tag emergency-rollback-$(date +%Y%m%d-%H%M%S)

# 2. 回滚代码
git revert <commit-range>

# 3. 重新部署
python setup.py install
systemctl restart sdwan-diagnostic

# 4. 全面测试
python tests/integration/test_smart_path_analyzer.py --sample
agentctl quick-check --output full_rollback_test.html
```

**预计耗时**：30分钟

---

### 阶段4: 验证和监控（30-60分钟）

**验证步骤**：

1. **功能验证**
   ```bash
   # 运行完整测试套件
   python tests/integration/test_smart_path_analyzer.py \
     --domains-file tests/integration/test_cases_smart_path.json
   ```

2. **性能验证**
   ```bash
   # 监控10分钟内的性能指标
   watch -n 60 'grep "耗时=" logs/app.log | tail -10'
   ```

3. **用户反馈**
   - 联系关键用户确认功能是否正常
   - 收集HTML报告样例

**监控指标**：
- ✅ 错误率 < 1%
- ✅ 平均耗时 < 50ms
- ✅ 准确率 > 80%（降级模式）或 > 90%（部分禁用）

---

## 📊 **回滚后恢复计划**

### 短期（1-3天）

1. **根因分析**
   - 分析问题日志和测试报告
   - 定位具体问题模块
   - 制定修复方案

2. **修复开发**
   - 修复bug或优化算法
   - 增加单元测试覆盖
   - 进行回归测试

3. **灰度发布**
   - 在小范围环境测试修复版本
   - 收集反馈和数据
   - 逐步扩大测试范围

---

### 中期（1-2周）

1. **全面测试**
   - 运行完整的集成测试套件
   - A/B测试对比修复前后效果
   - 性能基准测试

2. **正式发布**
   - 更新版本号
   - 编写发布说明
   - 通知用户

3. **持续监控**
   - 设置告警阈值
   - 定期生成测试报告
   - 收集用户反馈

---

## 🛡️ **预防措施**

### 1. 自动化测试

**CI/CD集成**：
```yaml
# .github/workflows/test.yml
name: Smart Path Analyzer Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Run integration tests
        run: |
          python tests/integration/test_smart_path_analyzer.py \
            --domains-file tests/integration/test_cases_smart_path.json \
            --phase phase2
      
      - name: Check accuracy
        run: |
          ACCURACY=$(python -c "import json; data=json.load(open('tests/reports/smart_path_analyzer_phase2_report.json')); print(data['accuracy'])")
          if (( $(echo "$ACCURACY < 0.9" | bc -l) )); then
            echo "Accuracy too low: $ACCURACY"
            exit 1
          fi
```

---

### 2. 性能监控

**Prometheus指标**：
```python
# 在 smart_path_analyzer.py 中添加
from prometheus_client import Counter, Histogram

ANALYSIS_TOTAL = Counter('smart_path_analysis_total', 'Total path analyses')
ANALYSIS_DURATION = Histogram('smart_path_analysis_duration_seconds', 'Analysis duration')
ANALYSIS_CONFIDENCE = Histogram('smart_path_analysis_confidence', 'Analysis confidence')

def analyze(self, full_path):
    with ANALYSIS_DURATION.time():
        result = self._do_analyze(full_path)
    
    ANALYSIS_TOTAL.inc()
    ANALYSIS_CONFIDENCE.observe(result.confidence)
    
    return result
```

**告警规则**：
```yaml
# prometheus/alerts.yml
groups:
  - name: smart_path_analyzer
    rules:
      - alert: HighErrorRate
        expr: rate(smart_path_analysis_errors_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Smart path analyzer error rate is high"
      
      - alert: SlowAnalysis
        expr: histogram_quantile(0.95, rate(smart_path_analysis_duration_seconds_bucket[5m])) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Smart path analysis is slow"
```

---

### 3. 灰度发布

**发布策略**：
1. **Canary发布**：先在5%的用户中启用新功能
2. **监控指标**：密切监控错误率、性能、用户反馈
3. **逐步扩大**：如果指标正常，逐步扩大到20%、50%、100%
4. **快速回滚**：如果发现问题，立即回滚Canary组

**实施步骤**：
```python
# 在配置中添加灰度开关
config = {
    "smart_path_analyzer": {
        "enabled": True,
        "canary_mode": True,  # Canary模式
        "canary_percentage": 5,  # 5%的流量
    }
}

# 在代码中实现灰度逻辑
import random

def should_use_smart_analyzer(user_id):
    if not config["smart_path_analyzer"]["enabled"]:
        return False
    
    if config["smart_path_analyzer"]["canary_mode"]:
        # Canary模式：只对部分用户启用
        hash_value = hash(user_id) % 100
        return hash_value < config["smart_path_analyzer"]["canary_percentage"]
    
    return True
```

---

## 📞 **紧急联系人**

| 角色 | 姓名 | 联系方式 | 职责 |
|------|------|---------|------|
| **技术负责人** | Python Tech Lead | tech-lead@company.com | 决策回滚策略 |
| **运维工程师** | DevOps Team | devops@company.com | 执行回滚操作 |
| **QA工程师** | QA Team | qa@company.com | 验证回滚效果 |
| **产品经理** | Product Manager | pm@company.com | 评估业务影响 |

---

## 📝 **回滚检查清单**

### 回滚前
- [ ] 确认问题严重程度
- [ ] 选择合适的回滚策略
- [ ] 通知相关团队
- [ ] 备份当前状态（Git标签、数据库快照）

### 回滚中
- [ ] 执行回滚操作
- [ ] 监控系统指标
- [ ] 记录回滚过程和时间点

### 回滚后
- [ ] 验证功能恢复正常
- [ ] 运行完整测试套件
- [ ] 收集用户反馈
- [ ] 编写事故报告
- [ ] 制定修复计划

---

**文档维护**: DevOps团队  
**最后更新**: 2026-05-01  
**审查周期**: 每季度审查一次
