# Git-Doc-Hook 使用指南

> 通用 Git 文档自动化工具，支持 MemOS 知识库集成

[English](../README.md) | 简体中文

## 简介

Git-Doc-Hook 是一个独立的工具，能够根据 Git 提交自动更新项目文档。它分析代码变更，检测提交信息中的模式，并将技术决策同步到 MemOS 以供将来参考。

### 核心特性

- **通用性**：适用于任何语言或框架的 Git 项目
- **可配置**：通过 `.git-doc-hook.yml` 实现基于规则的配置
- **多语言支持**：内置 Python、JavaScript/TypeScript、Bash 分析器
- **MemOS 集成**：自动同步故障排查记录、架构决策和最佳实践
- **Git Hooks**：通过 pre-push 和 post-commit hooks 无缝集成工作流

---

## 安装

### 快速安装

```bash
curl -fsSL https://raw.githubusercontent.com/leon30083/git-doc-hook/main/install.sh | bash
```

### 使用 pip 安装

```bash
pip install git+https://github.com/leon30083/git-doc-hook.git
```

### 开发模式安装

```bash
git clone https://github.com/leon30083/git-doc-hook.git
cd git-doc-hook
pip install -e .
```

### 验证安装

```bash
git-doc-hook --version
git-doc-hook --help
```

---

## 快速开始

```bash
# 1. 在你的项目中初始化
cd my-project
git-doc-hook init

# 2. （可选）编辑配置文件
vim .git-doc-hook.yml

# 3. 正常提交和推送代码
git add .
git commit -m "fix(auth): 解决竞态条件问题"
git push origin main

# 4. 如果 hook 检测到变更，运行更新命令
git-doc-hook update traditional,config
```

---

## 工作流程

```
┌─────────────────────────────────────────────────────────────┐
│                      开发与提交                              │
│  git add . → git commit → git push                          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Git Hook 触发                            │
│  • pre-push: 分析代码变更                                    │
│  • post-commit: 检测提交消息关键词                           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    规则匹配与状态记录                        │
│  • 评估 .git-doc-hook.yml 中的规则                          │
│  • 将待更新写入 ~/.git-doc-hook/<项目>/pending.json          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    用户执行更新                              │
│  git-doc-hook status     # 查看待处理更新                    │
│  git-doc-hook update ... # 执行文档更新                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    MemOS 同步（可选）                        │
│  git-doc-hook update memo  # 创建 MemOS 记录                │
│  /memos-sync               # Claude Code 中同步到 MemOS      │
└─────────────────────────────────────────────────────────────┘
```

---

## 配置文件

在项目根目录创建 `.git-doc-hook.yml`：

```yaml
version: "1.0"

# 项目标识（用于状态隔离）
project_name: "my-project"

# MemOS 集成配置
memos:
  enabled: true              # 是否启用 MemOS
  api_url: "http://localhost:8000"
  cube_id: "git-doc-hook"
  auto_sync: true

# 文档层级定义
layers:
  traditional:
    name: "传统文档"
    docs:
      - "README.md"
      - "docs/**/*.md"

  config:
    name: "配置规则"
    docs:
      - ".clinerules"
      - ".cursorrules"

# 触发规则
rules:
  # 示例：服务层代码变更时更新 README
  - pattern: "services/**/*.py"
    layers: ["traditional", "config"]
    when:
      - file_exists
    actions:
      - target: "README.md"
        section: "Services"
        action: "append_table_row"

  # 示例：API 变更时更新文档
  - pattern: "api/**/*.ts"
    layers: ["traditional"]
    when:
      - file_exists
      - commit_contains: "api"
    actions:
      - target: "docs/api.md"
        section: "Endpoints"
        action: "append_table_row"
```

### 配置说明

| 字段 | 说明 | 示例 |
|------|------|------|
| `project_name` | 项目唯一标识 | `"my-project"` |
| `memos.enabled` | 启用 MemOS 集成 | `true` / `false` |
| `layers` | 定义的文档层级 | `traditional`, `config`, `memo` |
| `rules` | 触发规则列表 | 见下方规则详解 |

---

## 规则系统详解

### 触发条件 (when)

| 条件 | 说明 | 示例 |
|------|------|------|
| `file_exists` | 变更中包含匹配的文件 | 文件 `services/auth.py` 存在 |
| `commit_contains` | 提交消息包含关键词 | `"fix"`, `"decision"` |
| `complexity_high` | 复杂度超过阈值 | 圈复杂度 > 10 |

### 动作类型 (action)

| 动作 | 说明 | 适用场景 |
|------|------|----------|
| `append_table_row` | 向 Markdown 表格添加行 | 服务列表、API 文档 |
| `append_record` | 追加内容到文件 | 日志记录、变更历史 |
| `update_section` | 替换章节内容 | 更新 API 说明 |
| `prepend_content` | 在文件开头添加内容 | 添加通知/警告 |

### 表格行配置

```yaml
actions:
  - target: "README.md"
    section: "Services"
    action: "append_table_row"
    headers: ["名称", "路径", "类型"]           # 定义表头
    row_mapping:                               # 数据映射
      名称: "{file}"                           # {file} = 文件名
      路径: "{path}"                           # {path} = 相对路径
      类型: "{type}"                           # {type} = 检测到的类型
```

---

## CLI 命令参考

| 命令 | 说明 | 示例 |
|------|------|------|
| `git-doc-hook init` | 初始化当前项目 | `git-doc-hook init` |
| `git-doc-hook init --force` | 强制覆盖已安装的 hooks | `git-doc-hook init -f` |
| `git-doc-hook status` | 查看待处理的更新 | `git-doc-hook status` |
| `git-doc-hook update <layers>` | 执行文档更新 | `git-doc-hook update traditional` |
| `git-doc-hook clear` | 清除待处理状态 | `git-doc-hook clear` |
| `git-doc-hook check-memos` | 检查 MemOS 同步状态 | `git-doc-hook check-memos --json` |

### 层级参数

可以指定一个或多个层级，用逗号分隔：

```bash
# 只更新传统文档
git-doc-hook update traditional

# 更新传统文档和 AI 配置
git-doc-hook update traditional,config

# 只同步 MemOS
git-doc-hook update memo
```

---

## MemOS 集成

### 记录类型

MemOS 记录根据提交消息关键词自动创建：

| 类型 | 触发关键词 | 格式 |
|------|-----------|------|
| **故障排查** | fix, bug, error, issue, debug | 问题/解决方案/上下文 |
| **架构决策** | decision, decide, 选型, architecture | ADR 标准格式 |
| **最佳实践** | refactor, optimize, improve, better | 实践/类别/上下文 |
| **安全记录** | security, auth, vulnerability, xss | 安全实践记录 |

### 提交消息示例

```bash
# 会创建故障排查记录
git commit -m "fix(auth): 解决用户登录时的竞态条件问题"

# 会创建架构决策记录
git commit -m "decision: 使用 Redis 替代 Memcached 作为缓存层"

# 会创建最佳实践记录
git commit -m "refactor(db): 优化数据库查询以减少 N+1 问题"
```

### 同步工作流

```bash
# 1. 推送代码后创建 MemOS 记录
git push origin main
git-doc-hook update memo

# 2. 在 Claude Code 中检查待同步记录
git-doc-hook status

# 3. 执行同步命令（在 Claude Code 中）
/memos-sync

# 4. 确认并同步
# 命令会显示记录摘要，要求你确认
```

`★ Insight ─────────────────────────────────────`
MemOS 同步采用**延迟确认**设计：记录先写入本地状态文件，需要用户在 Claude Code 中明确确认后才同步。这样设计是为了让你能够**审查**将要同步的内容，确保知识库的质量。
`─────────────────────────────────────────────────`

---

## 高级用法

### 自定义模板

Git-Doc-Hook 使用 Jinja2 模板生成文档内容：

1. 创建模板目录：
   ```bash
   mkdir -p ~/.git-doc-hook/templates
   ```

2. 添加你的 Jinja2 模板：
   ```bash
   cp my-template.md.j2 ~/.git-doc-hook/templates/
   ```

3. 在 `.git-doc-hook.yml` 中配置：
   ```yaml
   templates:
     enabled: true
     dir: "~/.git-doc-hook/templates"
     use_builtin: true  # 回退到内置模板
   ```

### 模板上下文变量

```jinja2
# 项目信息
project_name     # 项目目录名
repo_url         # Git 远程 URL
branch           # 当前分支名
commit_hash      # 短提交哈希
commit_message   # 完整提交消息

# 变更
changed_files    # 变更文件路径列表
services         # 检测到的服务及元数据

# 更新
updates          # 待执行的操作列表
reason           # 更新原因
timestamp        # ISO 格式时间戳
```

---

## 状态存储

每个项目的状态独立存储在 `~/.git-doc-hook/` 目录：

```
~/.git-doc-hook/
├── <project_name>/
│   └── pending.json          # 待处理的更新
└── memos_cache.json          # MemOS 离线缓存
```

### 状态文件结构

```json
{
  "project_name": "my-project",
  "last_update": "2025-01-15T10:30:00",
  "pending": {
    "traditional": [...],
    "config": [...],
    "memo": [...]
  },
  "memos_records": [...]
}
```

---

## 故障排查

### Hook 未执行

```bash
# 检查 hook 是否安装
ls -la .git/hooks/pre-push
ls -la .git/hooks/post-commit

# 检查 hook 权限
chmod +x .git/hooks/pre-push
chmod +x .git/hooks/post-commit

# 手动测试 hook
.git/hooks/pre-push
```

### PATH 问题

如果 `~/.local/bin` 不在 PATH 中，hook 可能无法找到 `git-doc-hook` 命令。

**解决方案**：使用完整路径重新初始化：

```bash
# 先找到 git-doc-hook 的路径
which git-doc-hook

# 使用完整路径初始化
git-doc-hook init --force
```

或者将 `~/.local/bin` 添加到 PATH：

```bash
# 添加到 ~/.bashrc 或 ~/.zshrc
export PATH="$HOME/.local/bin:$PATH"
```

### MemOS 同步失败

```bash
# 检查待同步记录
git-doc-hook check-memos --json

# 查看离线缓存
cat ~/.git-doc-hook/memos_cache.json

# 清除待处理状态重新开始
git-doc-hook clear
```

---

## 常见问题

### Q: Hook 会阻止我推送代码吗？

**A**: 不会。pre-push hook 只分析变更并记录状态，即使失败也不会阻止推送。

### Q: 我可以禁用 hook 吗？

**A**: 可以。运行以下命令：
```bash
git config --local --unset hooks.pre-push
git config --local --unset hooks.post-commit
```

或使用 `--no-verify` 跳过 hook：
```bash
git push --no-verify
```

### Q: 支持哪些编程语言？

**A**: 内置支持 Python、JavaScript/TypeScript、Bash。可以通过添加新的 Analyzer 支持更多语言。

### Q: MemOS 是必须的吗？

**A**: 不是。MemOS 是可选功能，不启用时工具仍可正常更新文档。

---

## 开发

详见 [开发指南](../CLAUDE.md)。

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest tests/

# 类型检查
mypy src/

# 代码格式化
black src/
```

---

## 许可证

MIT
