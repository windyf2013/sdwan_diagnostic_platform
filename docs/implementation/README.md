# `docs/implementation/` — 实现层文档（镜像 + 地图 + 索引）

本目录约定见 [spec/00_core/implementation_doc_mirror.md](../../spec/00_core/implementation_doc_mirror.md)；Cursor 强制摘要见 [.cursor/AI_SPEC_GUIDE.md](../../.cursor/AI_SPEC_GUIDE.md) 核心强制约束第 8 条。

## Agent / 评审推荐阅读顺序

1. **流程地图**（按任务选一篇）：  
   - [FLOW_quick_check.md](FLOW_quick_check.md)（一键体检）  
   - [FLOW_deep_dive.md](FLOW_deep_dive.md)（深度诊断）  
   - [FLOW_business_diagnose.md](FLOW_business_diagnose.md)（业务路径诊断）
2. **全树索引**：[SRC_INDEX.md](SRC_INDEX.md)（路径、是否已有镜像文档、职责摘要列）
3. **单文件深描**：[`src/`](./src/) 下与 `src/**/*.py` 一比一的 `.md`
4. **按需** `read_file` 局部源码与 `spec/` 契约

## 路径约定（镜像）

```text
src/<REL>/<NAME>.py   →   docs/implementation/src/<REL>/<NAME>.md
```

非 Python 模板等不要求逐文件 `.md`；须在负责组装的 Python 模块镜像文档中写「非 Python 资产说明」（规范 §2.4）。

## `SRC_INDEX.md`（自动生成）

- **生成**：在仓库根目录执行  
  `python scripts/generate_implementation_index.py`
- **校验**：`python scripts/generate_implementation_index.py --check`（与已提交的 `SRC_INDEX.md` 字节级一致）
- **职责列**：优先 [src_roles.yaml](src_roles.yaml) 中的 `roles`；否则从对应镜像 `.md` 的 `## 职责概述` 首行抽取；否则标 **TODO**
- **禁止**手工编辑 `SRC_INDEX.md` 正文表格（会被脚本覆盖）；改 `src_roles.yaml` 或镜像 `.md` 后重新运行生成命令

## 提交前准备（脚本）

在仓库根目录：

- **仅准备（不提交）**：`python scripts/prepare_git_commit.py`  
  加 `--auto-add-index` 可在 `SRC_INDEX.md` 变化时自动 `git add` 该文件。  
  加 `--pre-commit-all` 会再跑完整 `pre-commit run --all-files`（含 ruff/mypy，较慢）。
- **准备 + `git commit`（PowerShell）**：`.\scripts\git-commit.ps1 -m "your message"`  
  全量 pre-commit：`.\scripts\git-commit.ps1 -PreCommitAll -m "your message"`
- **准备 + `git commit`（Git Bash / Linux）**：`./scripts/git-commit.sh -m "your message"`  
  全量：`./scripts/git-commit.sh --pre-commit-all -m "your message"`

依赖：已安装 `pre-commit` 且在 PATH 中（`pip install pre-commit`）。

与仅手动跑生成器等价：变更 `src/`、`docs/implementation/src/`、`src_roles.yaml` 或 `scripts/generate_implementation_index.py` 后，索引须与树一致；本地钩子 `implementation-src-index` 在提交时以 `--check` 校验。
