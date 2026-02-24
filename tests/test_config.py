"""Tests for configuration management"""
import pytest
from pathlib import Path
from git_doc_hook.core.config import Config


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project directory"""
    # Use unique name for each test
    import uuid
    project = tmp_path / f"test_project_{uuid.uuid4().hex[:8]}"
    project.mkdir()
    return project


@pytest.fixture
def sample_config(temp_project):
    """Create a sample configuration file"""
    config_file = temp_project / ".git-doc-hook.yml"
    config_content = """
version: "1.0"
memos:
  enabled: false
layers:
  custom:
    name: "Custom Layer"
    docs: ["CUSTOM.md"]
rules:
  - pattern: "test/**/*.py"
    layers: ["custom"]
    when: ["file_exists"]
    actions:
      - target: "CUSTOM.md"
        action: "append_record"
"""
    config_file.write_text(config_content)
    return temp_project


def test_config_load_default(temp_project):
    """Test loading default configuration"""
    config = Config(str(temp_project))
    loaded = config.load()

    assert "version" in loaded
    assert "memos" in loaded
    assert "layers" in loaded
    assert "rules" in loaded


def test_config_merge_user_config(sample_config):
    """Test merging user config with defaults"""
    config = Config(str(sample_config))
    loaded = config.load()

    # User override
    assert loaded["memos"]["enabled"] is False

    # Default values preserved
    assert "traditional" in loaded["layers"]


def test_config_save(temp_project):
    """Test saving configuration"""
    config = Config(str(temp_project))
    config.save()

    assert temp_project.exists()


def test_state_dir_property(temp_project):
    """Test state_dir property"""
    config = Config(str(temp_project))
    state_dir = config.state_dir

    # Should contain project name
    assert temp_project.name in str(state_dir)


def test_memos_properties(sample_config):
    """Test MemOS-related properties"""
    config = Config(str(sample_config))

    assert config.memos_enabled is False


def test_layers_property(sample_config):
    """Test layers property"""
    config = Config(str(sample_config))
    layers = config.layers

    assert "traditional" in layers
    assert "custom" in layers
    assert layers["custom"]["name"] == "Custom Layer"


def test_rules_property(sample_config):
    """Test rules property"""
    config = Config(str(sample_config))
    rules = config.rules

    assert len(rules) >= 1
    assert rules[0]["pattern"] == "test/**/*.py"


def test_keywords_property(temp_project):
    """Test keywords property"""
    config = Config(str(temp_project))
    keywords = config.keywords

    assert "troubleshooting" in keywords
    assert "decisions" in keywords
    assert isinstance(keywords["troubleshooting"], list)


def test_get_method(temp_project):
    """Test get method with dot notation"""
    config = Config(str(temp_project))

    # Get existing value - default is False
    assert config.get("memos.enabled") is False

    # Get with default
    assert config.get("nonexistent.key", "default") == "default"


def test_get_rules_for_pattern(temp_project):
    """Test pattern matching in rules"""
    config = Config(str(temp_project))

    # Should match default rule
    matches = config.get_rules_for_pattern("services/auth.py")
    assert len(matches) > 0


def test_validate_valid_config(temp_project):
    """Test validation of valid configuration"""
    config = Config(str(temp_project))
    errors = config.validate()

    assert len(errors) == 0


def test_validate_invalid_config(temp_project):
    """Test validation of invalid configuration"""
    config = Config(str(temp_project))
    # Manually create invalid config
    config._config = {"layers": {}}
    errors = config.validate()

    assert len(errors) > 0


def test_get_layer_docs(temp_project):
    """Test getting document patterns for a layer"""
    config = Config(str(temp_project))
    docs = config.get_layer_docs("traditional")

    assert isinstance(docs, list)
    assert "README.md" in docs


def test_templates_properties(temp_project):
    """Test template-related properties"""
    config = Config(str(temp_project))

    assert config.templates_enabled is True
    assert isinstance(config.template_dir, Path)
    assert config.use_builtin_templates is True


def test_updaters_properties(temp_project):
    """Test updater-related properties"""
    config = Config(str(temp_project))

    assert config.dry_run is False
    assert config.backup_enabled is True


def test_deep_merge(temp_project):
    """Test deep merge behavior"""
    config_file = temp_project / ".git-doc-hook.yml"
    config_content = """
keywords:
  troubleshooting:
    - fix
    - bug
    - issue
"""
    config_file.write_text(config_content)

    config = Config(str(temp_project))
    loaded = config.load()

    # Should have user keywords
    assert "fix" in loaded["keywords"]["troubleshooting"]

    # Should preserve other keyword categories
    assert "decisions" in loaded["keywords"]
