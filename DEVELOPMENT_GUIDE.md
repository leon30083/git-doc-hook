# Git-Doc-Hook Project Development Guide

> **AI Handoff Guide** - Everything needed to understand and extend this project

## 1. Project Overview

### Goals

Git-Doc-Hook is a **universal Git documentation automation tool** that:
- Analyzes code changes on Git push/commit
- Automatically updates project documentation based on configurable rules
- Syncs technical decisions and troubleshooting records to MemOS for future reference
- Works with any programming language through an extensible analyzer system

### Core Philosophy

1. **Configuration-Driven**: All behavior controlled by `.git-doc-hook.yml`
2. **Language Agnostic**: Plugin-based analyzer architecture supports any language
3. **Non-Invasive**: Hooks are optional; tool degrades gracefully if unavailable
4. **MemOS-Integrated**: Automatically builds a knowledge base of technical decisions

### Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| CLI | Click 8.0+ | Command-line interface |
| Config | PyYAML 6.0+ | Configuration parsing |
| Git Ops | Git CLI via subprocess | Repository operations |
| MemOS | HTTP (requests) | Knowledge base sync |
| Templates | Jinja2 3.1+ | Content generation |

## 2. Architecture Design

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        User Workflow                        │
├─────────────────────────────────────────────────────────────┤
│  git commit → git push → pre-push hook → analysis → prompt  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    git-doc-hook Components                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────┐    ┌──────────┐    ┌──────────────┐          │
│  │   CLI    │───▶│  Config  │───▶│ State Manager│          │
│  │ (cli.py) │    │(config.py│    │  (state.py)  │          │
│  └──────────┘    └──────────┘    └──────────────┘          │
│        │                                │                   │
│        ↓                                ↓                   │
│  ┌──────────┐                    ┌──────────────┐          │
│  │   Git    │                    │    MemOS     │          │
│  │(git.py)  │                    │ (memos/)     │          │
│  └──────────┘                    │  (client.py) │          │
│        │                          └──────────────┘          │
│        ↓                                ↑                   │
│  ┌──────────────────────────────────────────────┐          │
│  │            Analyzers (analyzers/)            │          │
│  │  ┌────────┐ ┌──────────┐ ┌─────────┐        │          │
│  │  │ Base   │ │  Python  │ │   JS    │  ...   │          │
│  │  │(base.py│ │(python.py│ │(js.py)  │        │          │
│  │  └────────┘ └──────────┘ └─────────┘        │          │
│  └──────────────────────────────────────────────┘          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Trigger Phase**: Git push → pre-push hook executes
2. **Detection Phase**: `GitManager.get_diff()` identifies changed files
3. **Analysis Phase**: Appropriate `Analyzer` processes each file
4. **Decision Phase**: `Config` rules determine which layers need updates
5. **State Phase**: `StateManager` records pending updates
6. **Action Phase**: User runs `git-doc-hook update` to apply changes
7. **Sync Phase**: `MemOSClient` uploads records if enabled

## 3. Core Module Details

### 3.1 Configuration System (`core/config.py`)

#### Structure

```python
Config
├── load()              # Load and merge with defaults
├── save()              # Persist to file
├── get(key, default)   # Dot-notation access
├── validate()          # Return list of errors
└── Properties:
    ├── state_dir       # ~/.git-doc-hook/<project>
    ├── memos_enabled   # Boolean
    ├── layers          # Dict of layer configs
    ├── rules           # List of rule dicts
    └── keywords        # Category → keywords mapping
```

#### Configuration Format

```yaml
version: "1.0"
state:
  dir: "~/.git-doc-hook"
  project_key: "auto-detected"
memos:
  enabled: true
  api_url: "http://localhost:8000"
  cube_id: "git-doc-hook"
layers:
  traditional:
    name: "Traditional Docs"
    docs: ["README.md", "docs/**/*.md"]
rules:
  - pattern: "services/**/*.py"
    layers: ["traditional", "config"]
    when: [file_exists]
    actions: [...]
```

#### Adding New Configuration Options

1. Add to `DEFAULT_CONFIG` in `Config` class
2. Add property getter if commonly accessed
3. Update `.git-doc-hook.yml` template

### 3.2 Git Operations (`core/git.py`)

#### Key Classes

```python
GitManager
├── get_repo_name()           # Extract from remote or directory
├── get_current_branch()      # Get branch name
├── get_commits(since_ref)    # Get commit history
├── get_diff(target_ref)      # Get DiffResult
├── get_staged_files()        # Get staged file list
├── is_dirty()                # Check for uncommitted changes
└── get_head_commit()         # Get HEAD commit info
```

#### Data Classes

```python
@dataclass Commit:
    hash, message, author, date, files

@dataclass FileChange:
    path, status, additions, deletions, patch

@dataclass DiffResult:
    commits, files (Set), file_changes
```

#### Extending Git Operations

- Add new methods to `GitManager` for additional Git commands
- Return structured data (dataclasses) for easy consumption
- Handle errors by raising `GitError`

### 3.3 State Management (`core/state.py`)

#### Design

State is stored per-project in `~/.git-doc-hook/<project>/pending.json`:

```json
{
  "pending": {
    "layers": ["traditional", "memo"],
    "reason": "Services changed",
    "triggered_by": "abc123",
    "timestamp": 1234567890.0,
    "files": ["services/auth.py"],
    "commit_message": "feat: add OAuth"
  },
  "history": [...]
}
```

#### Key Methods

```python
StateManager
├── set_pending(...)          # Mark layers as needing update
├── get_pending() → Optional[PendingUpdate]
├── clear_pending()           # Move to history, clear pending
├── is_pending() → bool
├── show_summary() → str      # Human-readable status
└── list_all_projects()       # Find all projects with pending
```

### 3.4 Code Analyzers (`analyzers/`)

#### Base Class Interface

All analyzers must inherit from `BaseAnalyzer` and implement:

```python
class BaseAnalyzer(ABC):
    @property
    @abstractmethod
    def language(self) -> str:
        """Return language name"""

    @abstractmethod
    def can_analyze(file_path: str) -> bool:
        """Check if file is supported"""

    @abstractmethod
    def analyze(file_path: str, context: Dict) -> AnalysisResult:
        """Return analysis results"""
```

#### Analysis Result Structure

```python
AnalysisResult:
├── file_path: str
├── language: str
├── layers: List[str]              # Which docs to update
├── actions: List[Dict]            # Specific actions to take
├── complexity: ComplexityMetrics
├── functions: List[FunctionInfo]
├── classes: List[ClassInfo]
└── metadata: Dict
```

#### Adding a New Language Analyzer

1. Create `src/analyzers/<language>.py`
2. Inherit from `BaseAnalyzer`
3. Implement required methods
4. Add to `src/analyzers/__init__.py`:
   ```python
   from .<language> import <Language>Analyzer
   ```
5. Add to `get_analyzer()` function

### 3.5 MemOS Client (`memos/client.py`)

#### API Endpoints Used

```
GET  /api/status              # Check availability
POST /api/memos               # Add memory
GET  /api/memos/stats         # Get statistics
GET  /api/memos/search        # Search memories
```

#### Record Types

| Type | Trigger | Template |
|------|---------|----------|
| troubleshooting | "fix", "bug", "error" | Problem/Solution/Context |
| adr | "decision", "选型" | ADR format |
| practice | "refactor", "optimize" | Practice/Category |
| security | "security", "auth" | Security practice |
| general | fallback | Commit summary |

#### Offline Behavior

- Failed requests cache records locally
- Cache: `~/.git-doc-hook/memos_cache.json`
- `sync_offline_cache()` retries on next connection

### 3.6 CLI Tool (`cli.py`)

#### Command Structure

```
git-doc-hook
├── init [--force]            # Initialize project
├── status [--json]           # Show pending state
├── update <layers> [--commit] # Execute updates
├── clear                     # Clear pending state
├── memos-sync                # Sync to MemOS
├── check-pre-push            # Internal: pre-push hook
└── check-post-commit         # Internal: post-commit hook
```

#### Adding New Commands

```python
@cli.command()
@click.option("--project", "-p", default=".")
def new_command(project: str):
    """Command description"""
    # Implementation
    pass
```

## 4. Development Environment Setup

### Local Development

```bash
# Clone repository
git clone https://github.com/leon30083/git-doc-hook.git
cd git-doc-hook

# Install in editable mode
pip install -e .

# Or with dev dependencies
pip install -e ".[dev]"
```

### Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/test_config.py -v

# Run integration tests only
pytest tests/integration/ -v

# Type checking
mypy src/

# Code formatting
black src/
```

### Manual Testing

```bash
# Run the manual test script
bash tests/manual_test.sh

# Or create test project manually
mkdir /tmp/test-project && cd /tmp/test-project
git init
git-doc-hook init

# Make a test commit
echo "# Test" > README.md
git add .
git commit -m "feat: initial commit"

# Check status
git-doc-hook status
```

## 5. Extension Guide

### Adding a New Analyzer

```python
# src/analyzers/rust.py
from .base import BaseAnalyzer, AnalysisResult
from typing import Dict, Any, Optional

class RustAnalyzer(BaseAnalyzer):
    extensions = [".rs"]

    @property
    def language(self) -> str:
        return "Rust"

    def can_analyze(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() in self.extensions

    def analyze(
        self, file_path: str, context: Optional[Dict[str, Any]] = None
    ) -> AnalysisResult:
        # Implementation: parse Rust code
        # Use regex or external parser
        return AnalysisResult(
            file_path=file_path,
            language=self.language,
            layers=self.detect_layers(file_path, context),
            actions=[],
        )
```

### Adding a New Document Layer

1. Add to `DEFAULT_CONFIG["layers"]`:
   ```python
   "api": {
       "name": "API Docs",
       "docs": ["docs/api/**/*.md"]
   }
   ```

2. Add handler in `update()` command:
   ```python
   elif layer == "api":
       if _update_api_docs(project_path):
           updated.append("api")
   ```

### Adding Templates

Templates use Jinja2 and are located in `templates/prompts/`:

1. **Create a new template**:
   ```bash
   # Custom template location
   mkdir -p ~/.git-doc-hook/templates
   vim ~/.git-doc-hook/templates/custom.md.j2
   ```

2. **Template structure**:
   ```jinja2
   # Custom Documentation

   ## Context
   - Project: {{ project_name }}
   - Commit: {{ commit_hash }}

   ## Changes
   {% for file in changed_files %}
   - {{ file }}
   {% endfor %}

   ## Content
   {{ generated_content }}
   ```

3. **Use in code**:
   ```python
   from template import TemplateRenderer

   renderer = TemplateRenderer(
       template_dir=Path("~/.git-doc-hook/templates").expanduser(),
       use_builtin=True,
   )

   context = {"project_name": "myapp", ...}
   content = renderer.render("custom.md.j2", context)
   ```

4. **Available context variables**:
   - `project_name`: Project directory name
   - `repo_url`: Git remote URL
   - `branch`: Current branch name
   - `commit_hash`: Short commit hash
   - `commit_message`: Full commit message
   - `changed_files`: List of changed file paths
   - `services`: List of detected services
   - `updates`: List of pending update actions
   - `reason`: Reason for the update
   - `timestamp`: ISO format timestamp

### Testing Guide

#### Test Structure

```
tests/
├── __init__.py
├── test_config.py      # Configuration tests
├── test_state.py       # State management tests
├── test_git.py         # Git operations tests
├── test_memos.py       # MemOS client tests
├── test_cli.py         # CLI command tests
├── integration/
│   ├── __init__.py
│   └── test_workflow.py  # End-to-end tests
└── manual_test.sh      # Manual testing script
```

#### Writing Tests

```python
# Example test
def test_config_loading(temp_project):
    """Test loading default configuration"""
    config = Config(str(temp_project))
    loaded = config.load()

    assert "version" in loaded
    assert "memos" in loaded
```

#### Running Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=html

# Specific module
pytest tests/test_config.py -v

# Integration tests only
pytest tests/integration/ -v
```

### Adding a New Rule Type

Rules support these triggers:
- `file_exists`: File matches pattern exists
- `commit_contains`: Commit message contains keyword(s)
- `complexity_high`: Complexity exceeds threshold

## 6. Deployment Flow

### Release Process

```bash
# 1. Update version in setup.py
# 2. Tag release
git tag v0.1.0
git push origin v0.1.0

# 3. Build distribution
python -m build

# 4. Upload to PyPI (optional)
twine upload dist/*
```

### Installation Methods

| Method | Command | Use Case |
|--------|---------|----------|
| pip install | `pip install git-doc-hook` | Production |
| pip editable | `pip install -e .` | Development |
| Install script | `curl ... | bash` | Quick setup |

## 7. Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Hook not triggered | Not executable | `chmod +x .git/hooks/pre-push` |
| Config not found | Wrong project path | Use `--project` flag |
| MemOS unavailable | Service down | Records cached automatically |
| Import errors | Not installed | `pip install -e .` |

### Debug Mode

Set environment variable for verbose logging:
```bash
GIT_DOC_HOOK_DEBUG=1 git-doc-hook status
```

### Log Locations

| Component | Log Location |
|-----------|--------------|
| State | `~/.git-doc-hook/<project>/pending.json` |
| MemOS cache | `~/.git-doc-hook/memos_cache.json` |
| Git hooks | `.git/hooks/pre-push`, `.git/hooks/post-commit` |

## 8. AI Handoff Quick Reference

### File Navigation

| Want to find... | Look in... |
|-----------------|------------|
| Configuration parsing | `src/core/config.py` |
| Git operations | `src/core/git.py` |
| Pending state | `src/core/state.py` |
| Language analyzers | `src/analyzers/` |
| MemOS sync | `src/memos/client.py` |
| CLI commands | `src/cli.py` |
| Template rendering | `src/template.py` |
| Document updates | `src/updaters.py` |
| Default config | `examples/.git-doc-hook.yml` |
| Builtin templates | `templates/prompts/` |
| Hook templates | `.git/hooks/` (installed) |

### Key Patterns

1. **Adding CLI option**: Add `@click.option` decorator
2. **Adding config key**: Update `DEFAULT_CONFIG` + add property
3. **Adding language**: Create analyzer + register in `__init__.py`
4. **Adding MemOS record type**: Add factory in `MemOSRecord.create_*`
5. **Adding template**: Create `.j2` file in `templates/prompts/`
6. **Adding document action**: Add method to `DocumentUpdater` in `src/updaters.py`
7. **Modifying hook**: Edit templates in `src/hooks/`

### Important Constraints

- **No blocking on MemOS**: Always cache offline, never fail sync
- **State is per-project**: Use `project_key` for isolation
- **Hooks are optional**: Tool should work even if hooks aren't installed
- **Config is merged**: User config overrides defaults (deep merge)

### Next Developer

To extend this project:
1. Read this guide
2. Examine existing analyzer implementations
3. Add tests for new functionality
4. Update this guide with any architecture changes
