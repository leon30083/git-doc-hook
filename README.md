# Git-Doc-Hook

> Universal Git documentation auto-update tool with MemOS integration

[简体中文使用指南](docs/zh-CN.md) | English

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

## How It Works

Git-Doc-Hook integrates with your Git workflow through these steps:

1. **Initialization**: Running `git-doc-hook init` creates:
   - `.git-doc-hook.yml` configuration file
   - Git hooks (pre-push, post-commit) in `.git/hooks/`

2. **Change Detection**: When you push, the pre-push hook:
   - Analyzes changed files using language-specific analyzers
   - Checks commit messages for keywords (fix, decision, refactor, etc.)
   - Evaluates configured rules against file patterns
   - Sets pending state if documentation updates are needed

3. **Documentation Update**: When you run `git-doc-hook update`:
   - Template renderer builds context from project state
   - Document updater executes configured actions:
     - `append_table_row`: Adds rows to Markdown tables
     - `append_record`: Appends content to files
     - `update_section`: Replaces section content
     - `prepend_content`: Adds content at file start

4. **MemOS Sync**: Technical decisions are automatically:
   - Categorized by commit message keywords
   - Formatted as structured records (troubleshooting, ADR, practice)
   - Synced to MemOS or cached offline for later sync

## Template System

Git-Doc-Hook uses Jinja2 templates for generating documentation content:

### Builtin Templates

Located in `templates/prompts/`:
- `traditional.md.j2` - For standard documentation updates
- `config_rule.md.j2` - For AI assistant config files
- `memo.md.j2` - For MemOS record formatting

### Template Context

Templates receive the following context variables:

```jinja2
# Project Information
project_name     # Project directory name
repo_url         # Git remote URL
branch           # Current branch name
commit_hash      # Short commit hash
commit_message   # Full commit message

# Changes
changed_files    # List of changed file paths
services         # List of detected services with metadata

# Updates
updates          # List of pending update actions
reason           # Reason for the update
timestamp        # ISO format timestamp
```

### Custom Templates

To use custom templates:

1. Create a template directory:
   ```bash
   mkdir -p ~/.git-doc-hook/templates
   ```

2. Add your Jinja2 templates:
   ```bash
   cp my-template.md.j2 ~/.git-doc-hook/templates/
   ```

3. Configure in `.git-doc-hook.yml`:
   ```yaml
   templates:
     enabled: true
     dir: "~/.git-doc-hook/templates"
     use_builtin: true  # Fall back to builtin templates
   ```

### Template Fallback

If Jinja2 is unavailable or template rendering fails, git-doc-hook gracefully falls back to simple text formatting:
- Plain text headers and sections
- Bullet lists for changed files
- Basic metadata display

## Configuration Actions

The `action` field in rules determines what happens when a rule matches:

| Action | Description | Example |
|--------|-------------|---------|
| `append_table_row` | Add row to Markdown table | Update service list in README |
| `append_record` | Append content to file | Add troubleshooting entry |
| `update_section` | Replace section content | Update API documentation |
| `prepend_content` | Add content at file start | Add notice at top of file |

### Table Row Configuration

```yaml
actions:
  - target: "README.md"
    section: "Services"
    action: "append_table_row"
    headers: ["Name", "Path", "Type"]      # Optional: define table structure
    row_mapping:                            # Optional: map data to columns
      Name: "{file}"                        # {file} = filename
      Path: "{path}"                        # {path} = relative path
      Type: "{type}"                        # {type} = detected type
```

## Development

See [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md) for detailed documentation.

## License

MIT
