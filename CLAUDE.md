# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Git-Doc-Hook is a universal Git documentation automation tool. It analyzes code changes on Git push/commit and automatically updates project documentation based on configurable rules, with optional sync to MemOS for building a knowledge base of technical decisions.

**Core Philosophy**: Configuration-driven, language-agnostic, non-invasive hooks, MemOS-integrated.

## Development Commands

```bash
# Install in editable mode (for development)
pip install -e .

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Type checking
mypy src/

# Code formatting
black src/

# Manual testing - initialize in a test project
cd /tmp/test-project && git init
git-doc-hook init

# Check pending updates
git-doc-hook status

# Execute documentation update
git-doc-hook update traditional,config

# Clear pending state
git-doc-hook clear

# Manual MemOS sync
git-doc-hook memos-sync
```

## Architecture

The project follows a layered plugin architecture:

```
Git Hook (pre-push/post-commit)
    ↓
CLI (src/cli.py)
    ↓
Core Components:
    ├── Config (src/core/config.py) - YAML config with deep merge defaults
    ├── Git (src/core/git.py) - Git operations via subprocess
    ├── State (src/core/state.py) - Per-project pending state in ~/.git-doc-hook/
    └── Analyzers (src/analyzers/) - Language-specific code analysis
    └── MemOS (src/memos/client.py) - HTTP client with offline caching
```

### Key Design Patterns

1. **Analyzer Pattern**: All language analyzers inherit from `BaseAnalyzer` (src/analyzers/base.py) and implement `can_analyze()` and `analyze()`. Add new languages by creating a new analyzer class and registering it in `src/analyzers/__init__.py`.

2. **Deep Merge Configuration**: User config (`.git-doc-hook.yml`) is deep-merged with `DEFAULT_CONFIG` in `Config` class. Add new config options to `DEFAULT_CONFIG` and they'll be automatically available.

3. **Per-Project State**: Each project gets isolated state in `~/.git-doc-hook/<project_name>/pending.json`. The `project_key` defaults to repo name but can be customized.

4. **Graceful Degradation**: MemOS sync failures are cached to `~/.git-doc-hook/memos_cache.json` and retried on next connection. Hooks are optional - tool works even if not installed.

### Data Flow

1. **Trigger**: Git push → pre-push hook executes
2. **Detection**: `GitManager.get_diff()` identifies changed files
3. **Analysis**: Appropriate `Analyzer` processes each file
4. **Decision**: `Config` rules determine which layers need updates
5. **State**: `StateManager.set_pending()` records pending updates
6. **Action**: User runs `git-doc-hook update` to apply changes
7. **Sync**: `MemOSClient` uploads records if enabled

### Entry Point

The entry point is defined in `setup.py` as `git-doc-hook=cli:main`. The actual CLI is in `src/cli.py` with Click commands. Note the import structure uses relative imports within the `src/` package (e.g., `from core.config import Config`).

## Module Reference

| Module | Purpose | Key Classes/Functions |
|--------|---------|----------------------|
| `src/core/config.py` | Configuration loading/validation | `Config.load()`, `Config.get()`, `Config.get_rules_for_pattern()` |
| `src/core/git.py` | Git operations wrapper | `GitManager.get_diff()`, `GitManager.get_commits()`, `Commit`, `FileChange`, `DiffResult` |
| `src/core/state.py` | Pending state persistence | `StateManager.set_pending()`, `StateManager.get_pending()`, `StateManager.clear_pending()` |
| `src/analyzers/base.py` | Analyzer interface | `BaseAnalyzer`, `AnalysisResult`, `ComplexityMetrics`, `FunctionInfo`, `ClassInfo` |
| `src/memos/client.py` | MemOS integration | `MemOSClient.add_record()`, `MemOSClient.sync_offline_cache()`, `MemOSRecord` factory methods |
| `src/cli.py` | Command-line interface | `init`, `status`, `update`, `clear`, `memos-sync`, `check-pre-push`, `check-post-commit` |

## Document Layers

Layers define what gets updated:

- **traditional**: README.md, docs/**/*.md - Standard documentation files
- **config**: .clinerules, .cursorrules - AI assistant configuration files
- **memo**: Virtual layer - syncs to MemOS instead of files

Add new layers by:
1. Adding to `DEFAULT_CONFIG["layers"]` in `Config` class
2. Adding handler in `update()` command in cli.py (see `_update_traditional_docs` pattern)
3. Optionally adding Jinja template in `templates/prompts/`

## Adding a New Language Analyzer

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

    def analyze(self, file_path: str, context: Optional[Dict[str, Any]] = None) -> AnalysisResult:
        # Parse Rust code, extract functions/classes, calculate complexity
        return AnalysisResult(
            file_path=file_path,
            language=self.language,
            layers=self.detect_layers(file_path, context),
            actions=[],
        )
```

Then register in `src/analyzers/__init__.py`:
```python
from .rust import RustAnalyzer
# Add to get_analyzer() function
```

## Rule System

Rules in `.git-doc-hook.yml` define when documentation updates are triggered:

```yaml
rules:
  - pattern: "services/**/*.py"      # Glob pattern for files
    layers: ["traditional", "config"] # Which layers to update
    when:
      - file_exists                   # Trigger condition
    actions:                          # What to do
      - target: "README.md"
        section: "Services"
        action: "append_table_row"
```

Trigger conditions:
- `file_exists`: File matching pattern exists in changes
- `commit_contains`: Commit message contains keyword(s)
- `complexity_high`: Complexity exceeds configured thresholds

## MemOS Record Types

Records are auto-created based on commit message keywords:

| Type | Keywords | Format |
|------|----------|--------|
| troubleshooting | fix, bug, error, issue, debug | Problem/Solution/Context |
| adr | decision, decide, 选型, architecture | ADR standard format |
| practice | refactor, optimize, improve, better | Practice/Category/Context |
| security | security, auth, vulnerability, xss | Security practice record |

## Important Constraints

- **No blocking on MemOS**: Always cache offline, never fail sync
- **State is per-project**: Use `project_key` for isolation between repos
- **Hooks are optional**: Tool should work even if hooks aren't installed
- **Config is merged**: User config overrides defaults via deep merge
- **Python 3.8+**: Minimum version requirement
