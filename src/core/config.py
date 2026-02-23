"""Configuration parser for git-doc-hook

Handles loading, validation, and default values for .git-doc-hook.yml
"""
from pathlib import Path
from typing import Any, Dict, List, Optional
import copy


class Config:
    """Configuration manager for git-doc-hook

    Loads configuration from .git-doc-hook.yml with sensible defaults.
    Supports project-specific overrides and MemOS integration settings.
    """

    # Default configuration template
    DEFAULT_CONFIG: Dict[str, Any] = {
        "version": "1.0",
        "state": {
            "dir": "~/.git-doc-hook",
            "project_key": None,  # Will be set to repo name
        },
        "memos": {
            "enabled": True,
            "api_url": "http://localhost:8000",
            "cube_id": "git-doc-hook",
            "auto_sync": True,
            "categories": {
                "troubleshooting": {
                    "memos_type": "troubleshooting",
                    "keywords": ["fix", "bug", "error", "issue", "debug"],
                },
                "decisions": {
                    "memos_type": "adr",
                    "keywords": ["decision", "decide", "选型", "architecture"],
                },
                "best_practices": {
                    "memos_type": "practice",
                    "keywords": ["refactor", "optimize", "improve", "better"],
                },
                "security": {
                    "memos_type": "security",
                    "keywords": ["security", "auth", "vulnerability", "xss"],
                },
            },
        },
        "layers": {
            "traditional": {
                "name": "Traditional Docs",
                "docs": ["README.md", "docs/**/*.md"],
            },
            "config": {
                "name": "Config Rules",
                "docs": [".clinerules", ".cursorrules"],
            },
            "memo": {
                "name": "MemOS Records",
                "docs": [],  # Virtual layer, no physical files
            },
        },
        "rules": [
            {
                "pattern": "services/**/*.py",
                "layers": ["traditional", "config"],
                "when": ["file_exists"],
                "actions": [
                    {
                        "target": "README.md",
                        "section": "Services",
                        "action": "append_table_row",
                    }
                ],
            },
            {
                "pattern": "**/*.py",
                "layers": ["memo"],
                "when": [
                    {"commit_contains": ["fix", "bug"]},
                    {"complexity_high": True},
                ],
                "actions": [
                    {"target": "docs/troubleshooting.md", "action": "append_record"}
                ],
            },
        ],
        "complexity": {
            "high_line_count": 100,
            "high_nesting_depth": 4,
            "high_param_count": 6,
        },
        "keywords": {
            "troubleshooting": ["fix", "bug", "error", "issue", "debug"],
            "decisions": ["decision", "decide", "选型", "architecture"],
            "best_practices": ["refactor", "optimize", "improve", "better"],
            "security": ["security", "auth", "vulnerability"],
        },
        "commit": {
            "message_template": "docs(auto): update {layers} - {reason}",
            "auto_push": False,
        },
    }

    def __init__(self, project_path: str = "."):
        """Initialize configuration for a project

        Args:
            project_path: Path to the project root directory
        """
        self.project_path = Path(project_path).resolve()
        self.config_file = self.project_path / ".git-doc-hook.yml"
        self._config: Optional[Dict[str, Any]] = None

    def load(self) -> Dict[str, Any]:
        """Load and merge configuration

        Returns:
            Merged configuration dict with defaults applied
        """
        if self._config is None:
            self._config = copy.deepcopy(self.DEFAULT_CONFIG)

            if self.config_file.exists():
                import yaml

                user_config = yaml.safe_load(self.config_file.read_text())
                if user_config:
                    self._config = self._merge_config(self._config, user_config)

            # Set project key if not configured
            if not self._config["state"]["project_key"]:
                self._config["state"]["project_key"] = self.project_path.name

        return self._config

    def _merge_config(
        self, default: Dict[str, Any], user: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deep merge user config with defaults

        Args:
            default: Default configuration
            user: User-provided configuration

        Returns:
            Merged configuration
        """
        result = copy.deepcopy(default)

        for key, value in user.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value

        return result

    def save(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Save configuration to file

        Args:
            config: Configuration to save, or current config if None
        """
        import yaml

        to_save = config or self._config or self.load()
        self.config_file.write_text(yaml.dump(to_save, default_flow_style=False, sort_keys=False))
        self._config = to_save

    @property
    def state_dir(self) -> Path:
        """Get the state directory path"""
        path = Path(self.get("state.dir", "~/.git-doc-hook")).expanduser()
        project_key = self.get("state.project_key", self.project_path.name)
        return path / project_key

    @property
    def memos_enabled(self) -> bool:
        """Check if MemOS integration is enabled"""
        return self.get("memos.enabled", True)

    @property
    def memos_api_url(self) -> str:
        """Get MemOS API URL"""
        return self.get("memos.api_url", "http://localhost:8000")

    @property
    def memos_cube_id(self) -> str:
        """Get MemOS cube ID"""
        return self.get("memos.cube_id", "git-doc-hook")

    @property
    def layers(self) -> Dict[str, Dict[str, Any]]:
        """Get configured document layers"""
        return self.get("layers", {})

    @property
    def rules(self) -> List[Dict[str, Any]]:
        """Get configured rules"""
        return self.get("rules", [])

    @property
    def complexity_thresholds(self) -> Dict[str, int]:
        """Get complexity thresholds"""
        return self.get("complexity", {})

    @property
    def keywords(self) -> Dict[str, List[str]]:
        """Get keyword mappings"""
        return self.get("keywords", {})

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by dot-notation key

        Args:
            key: Dot-notation key (e.g., "memos.enabled")
            default: Default value if not found

        Returns:
            Configuration value or default
        """
        config = self._config or self.load()
        keys = key.split(".")

        value = config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_memos_category(self, category: str) -> Optional[Dict[str, Any]]:
        """Get MemOS category configuration

        Args:
            category: Category name (troubleshooting, decisions, etc.)

        Returns:
            Category config or None
        """
        return self.get(f"memos.categories.{category}")

    def get_layer_docs(self, layer: str) -> List[str]:
        """Get document patterns for a layer

        Args:
            layer: Layer name

        Returns:
            List of file patterns
        """
        layer_config = self.get(f"layers.{layer}")
        if layer_config:
            return layer_config.get("docs", [])
        return []

    def get_rules_for_pattern(self, pattern: str) -> List[Dict[str, Any]]:
        """Get rules that match a file pattern

        Args:
            pattern: File pattern to match

        Returns:
            List of matching rules
        """
        from fnmatch import fnmatch

        matching = []
        for rule in self.rules:
            rule_pattern = rule.get("pattern", "")
            if fnmatch(pattern, rule_pattern):
                matching.append(rule)
        return matching

    def validate(self) -> List[str]:
        """Validate current configuration

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check required structure
        config = self.load()
        if "layers" not in config:
            errors.append("Missing 'layers' section")
        if "rules" not in config:
            errors.append("Missing 'rules' section")

        # Validate layer references in rules
        for i, rule in enumerate(self.rules):
            for layer in rule.get("layers", []):
                if layer not in self.layers:
                    errors.append(f"Rule {i}: Unknown layer '{layer}'")

        return errors
