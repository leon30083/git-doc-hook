# Git-Doc-Hook

> Universal Git documentation auto-update tool with MemOS integration

## Overview

Git-Doc-Hook is a standalone tool that automatically updates project documentation based on Git commits. It analyzes code changes, detects patterns in commit messages, and syncs technical decisions to MemOS for future reference.

## Features

- **Universal**: Works with any Git project regardless of language or framework
- **Configurable**: Rule-based system via `.git-doc-hook.yml`
- **Multi-language**: Built-in analyzers for Python, JavaScript/TypeScript, and Bash
- **MemOS Integration**: Automatically syncs troubleshooting records, ADRs, and best practices
- **Git Hooks**: Pre-push and post-commit hooks for seamless workflow

## Installation

### Quick Install

```bash
curl -fsSL https://raw.githubusercontent.com/leon30083/git-doc-hook/main/install.sh | bash
```

### pip Install

```bash
pip install git+https://github.com/leon30083/git-doc-hook.git
```

### Development Install

```bash
git clone https://github.com/leon30083/git-doc-hook.git
cd git-doc-hook
pip install -e .
```

## Quick Start

```bash
# Initialize in your project
cd my-project
git-doc-hook init

# Configure MemOS (optional)
vim .git-doc-hook.yml

# Commit and push normally
git add .
git commit -m "fix(auth): resolve race condition"
git push origin main

# If hook detects changes, run update
git-doc-hook update traditional,config
```

## Configuration

Create `.git-doc-hook.yml` in your project root:

```yaml
version: "1.0"

# MemOS integration
memos:
  enabled: true
  api_url: "http://localhost:8000"
  cube_id: "git-doc-hook"
  auto_sync: true

# Document layers
layers:
  traditional:
    name: "Traditional Docs"
    docs:
      - "README.md"
      - "docs/**/*.md"

  config:
    name: "Config Rules"
    docs:
      - ".clinerules"
      - ".cursorrules"

# Rules for when to update
rules:
  - pattern: "services/**/*.py"
    layers: ["traditional", "config"]
    when:
      - file_exists
    actions:
      - target: "README.md"
        section: "Services"
        action: "append_table_row"
```

## MemOS Record Types

| Type | Trigger | Format |
|------|---------|--------|
| troubleshooting | commit contains "fix", "bug", "error" | Problem/Solution/Context |
| adr | commit contains "decision", "选型", "architecture" | ADR standard format |
| best-practice | commit contains "refactor", "optimize", "improve" | Practice/Category/Context |
| security | commit contains "security", "auth" | Security practice record |

## CLI Commands

| Command | Description |
|---------|-------------|
| `git-doc-hook init` | Initialize in current project |
| `git-doc-hook status` | Show pending updates |
| `git-doc-hook update <layers>` | Execute documentation update |
| `git-doc-hook clear` | Clear pending state |
| `git-doc-hook memos-sync` | Sync to MemOS manually |

## Architecture

```
Git Push → Pre-Push Hook → Code Analysis
                                    ↓
                          ┌─────────────────┐
                          │  Trigger Detect │
                          └─────────────────┘
                                    ↓
                    ┌───────────────┴───────────────┐
                    ↓                               ↓
              ┌───────────┐                   ┌─────────┐
              │   Docs    │                   │  MemOS  │
              │   Update  │                   │  Sync   │
              └───────────┘                   └─────────┘
```

## Development

See [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md) for detailed documentation.

## License

MIT
