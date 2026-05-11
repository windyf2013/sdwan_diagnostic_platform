# 当前上下文

## 当前冲刺
- **冲刺名称**: Sprint 8 - 发布准备
- **状态**: 🔄 进行中（阶段 8.3 完成 ✅）
- **时间范围**: 第10周

## Sprint 8 完成情况总结

### ✅ 阶段 8.1: PyInstaller打包配置与构建（已完成）
1. **打包脚本** (`scripts/build.py`)
   - 实现了基于 PyInstaller 的自动化构建流程。
   - 配置了 `--onefile` 单文件模式及 `--windowed` 无控制台模式（针对 GUI）。
   - 处理了 `paramiko`, `playwright`, `pyside6` 等复杂依赖的隐藏导入。

2. **便携版支持** (`scripts/pack.py`)
   - 实现了将构建产物与资源文件（configs, templates）自动压缩为 zip 包的功能。

3. **入口点完善** (`pyproject.toml`)
   - 补全了 `sdwan-deep-dive` 和 `sdwan-quick-check` 等 CLI 命令的定义。

### ✅ 阶段 8.2: 安装包验证与签名（已完成）
1. **验证脚本** (`scripts/verify_build.py`)
   - 实现了对打包产物（EXE）的存在性、体积限制及核心模块完整性的自动化检查。
   - 仿真测试通过：GUI 产物约 17.68MB，符合 <200MB 的目标。

### ✅ 阶段 8.3: 用户手册编写 (docs/user_guide.md)（已完成）

---

## 技术决策

### PyInstaller 模块搜索路径最终方案
1. **显式路径声明**: 在 `scripts/build.py` 中使用 `--paths=src` 参数。
2. **运行时路径注入**: 在 `main_window.py` 中增加了针对 `sys.frozen` 的多路径尝试逻辑。

### Sprint 8 架构决策
1. **资源自包含**: 决定将所有配置和模板嵌入可执行文件，确保“解压即用”或“安装即用”，减少环境依赖问题。
2. **动态版本注入**: 在打包脚本中预留了从 `pyproject.toml` 读取版本的逻辑接口，便于 CI/CD 自动化。

---

## 下一步计划
- **阶段 8.3**: 重点攻克用户手册的编写，确保覆盖所有功能模块的操作指南和故障排查建议。

---

## 版本信息
- **项目版本**: 1.0.0-rc1
- **Python版本**: 3.13.2
- **规范版本**: SDWAN_SPEC.md v1.0
- **当前状态**: Sprint 8 阶段 8.3 ✅ 完成，准备进入阶段 8.4
