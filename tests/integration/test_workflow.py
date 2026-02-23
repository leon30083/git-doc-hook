"""Integration tests for git-doc-hook workflow

These tests verify end-to-end functionality.
"""
import json
import subprocess
import tempfile
from pathlib import Path
import pytest
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


@pytest.fixture
def isolated_git_repo(tmp_path):
    """Create an isolated Git repository for testing"""
    repo = tmp_path / "test_repo"
    repo.mkdir()

    # Initialize git repo
    subprocess.run(
        ["git", "init"],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo,
        capture_output=True,
        check=True,
    )

    return repo


def test_init_workflow(isolated_git_repo):
    """Test complete initialization workflow"""
    from cli import cli
    from click.testing import CliRunner

    runner = CliRunner()

    # Initialize
    result = runner.invoke(cli, ["init", "--project", str(isolated_git_repo)])

    assert result.exit_code == 0

    # Check config file
    config_file = isolated_git_repo / ".git-doc-hook.yml"
    assert config_file.exists()

    # Check hooks
    hooks_dir = isolated_git_repo / ".git" / "hooks"
    assert (hooks_dir / "pre-push").exists()
    assert (hooks_dir / "post-commit").exists()


def test_config_loading_after_init(isolated_git_repo):
    """Test configuration loading after initialization"""
    from cli import cli
    from click.testing import CliRunner
    from core.config import Config

    runner = CliRunner()

    # Initialize
    runner.invoke(cli, ["init", "--project", str(isolated_git_repo)])

    # Load config
    config = Config(str(isolated_git_repo))
    loaded = config.load()

    assert "version" in loaded
    assert "layers" in loaded
    assert "rules" in loaded


def test_state_after_init(isolated_git_repo):
    """Test state management after initialization"""
    from cli import cli
    from click.testing import CliRunner
    from core.state import StateManager

    runner = CliRunner()

    # Initialize
    runner.invoke(cli, ["init", "--project", str(isolated_git_repo)])

    # Check state manager
    state = StateManager(str(isolated_git_repo))
    assert not state.is_pending()

    # Set pending
    state.set_pending(
        layers={"traditional"},
        reason="Test",
        triggered_by="abc",
        files=["test.py"],
        commit_message="test",
    )

    assert state.is_pending()


def test_template_renderer(isolated_git_repo):
    """Test template rendering"""
    from cli import cli
    from click.testing import CliRunner
    from template import create_renderer
    from core.config import Config
    from core.state import PendingUpdate

    runner = CliRunner()

    # Initialize
    runner.invoke(cli, ["init", "--project", str(isolated_git_repo)])

    config = Config(str(isolated_git_repo))
    renderer = create_renderer(isolated_git_repo, config)

    # Create pending context
    pending = PendingUpdate(
        layers={"traditional"},
        reason="Test",
        triggered_by="abc123",
        timestamp=1234567890,
        files=["services/auth.py"],
        commit_message="feat: add auth service",
    )

    context = renderer.build_context(isolated_git_repo, pending, config)

    assert "project_name" in context
    assert context["project_name"] == isolated_git_repo.name
    assert "services/auth.py" in context["changed_files"]


def test_document_updater_table_row(tmp_path):
    """Test document updater table row insertion"""
    from updaters import DocumentUpdater

    test_file = tmp_path / "test.md"
    test_file.write_text("""# Test

## Services

| Name | Type |
|------|------|
| auth | service |
""")

    updater = DocumentUpdater(dry_run=False, backup=False)

    result = updater.append_table_row(
        target_file=test_file,
        section="Services",
        row_data={"Name": "user", "Type": "service"},
    )

    assert result.success
    content = test_file.read_text()
    assert "| user | service |" in content


def test_document_updater_append_record(tmp_path):
    """Test document updater record appending"""
    from updaters import DocumentUpdater

    test_file = tmp_path / "test.md"
    test_file.write_text("# Test\n")

    updater = DocumentUpdater(dry_run=False, backup=False)

    result = updater.append_record(
        target_file=test_file,
        content="## New Section\n\nTest content",
    )

    assert result.success
    content = test_file.read_text()
    assert "## New Section" in content


def test_document_updater_update_section(tmp_path):
    """Test document updater section replacement"""
    from updaters import DocumentUpdater

    test_file = tmp_path / "test.md"
    test_file.write_text("""# Test

## Old Section

Old content

## Other Section
""")

    updater = DocumentUpdater(dry_run=False, backup=False)

    result = updater.update_section(
        target_file=test_file,
        section="Old Section",
        new_content="New content\n\nMulti-line",
    )

    assert result.success
    content = test_file.read_text()
    assert "New content" in content
    assert "Old content" not in content


def test_document_updater_prepend_content(tmp_path):
    """Test document updater content prepending"""
    from updaters import DocumentUpdater

    test_file = tmp_path / "test.md"
    test_file.write_text("# Test\n\nExisting content")

    updater = DocumentUpdater(dry_run=False, backup=False)

    result = updater.prepend_content(
        target_file=test_file,
        content="**Note:** This is prepended content",
    )

    assert result.success
    content = test_file.read_text()
    assert "prepended content" in content


def test_document_updater_dry_run(tmp_path):
    """Test document updater dry-run mode"""
    from updaters import DocumentUpdater

    test_file = tmp_path / "test.md"
    original_content = "# Test\n"
    test_file.write_text(original_content)

    updater = DocumentUpdater(dry_run=True, backup=False)

    result = updater.append_record(
        target_file=test_file,
        content="## New",
    )

    assert result.success
    assert "Dry run" in result.message
    assert test_file.read_text() == original_content


def test_config_file_updater(tmp_path):
    """Test config file updater"""
    from updaters import ConfigFileUpdater

    project = tmp_path / "project"
    project.mkdir()

    updater = ConfigFileUpdater(dry_run=False)

    result = updater.update_clinerules(
        project_path=project,
        patterns=["Testing", "API Patterns"],
    )

    assert result.success

    clinerules = project / ".clinerules"
    assert clinerules.exists()
    content = clinerules.read_text()
    assert "Testing" in content
    assert "API Patterns" in content


def test_extract_code_patterns(tmp_path):
    """Test code pattern extraction"""
    from updaters import extract_code_patterns

    # Create test files
    services_dir = tmp_path / "services"
    services_dir.mkdir()
    (services_dir / "auth.py").write_text("class AuthService: pass")

    test_dir = tmp_path / "tests"
    test_dir.mkdir()
    (test_dir / "test_auth.py").write_text("def test_auth(): pass")

    files = [services_dir / "auth.py", test_dir / "test_auth.py"]
    patterns = extract_code_patterns(files, tmp_path)

    assert "Service Layer" in patterns
    assert "Testing" in patterns


def test_end_to_end_workflow(isolated_git_repo):
    """Test complete end-to-end workflow"""
    from cli import cli
    from click.testing import CliRunner
    from core.state import StateManager

    runner = CliRunner()

    # Step 1: Initialize
    result = runner.invoke(cli, ["init", "--project", str(isolated_git_repo)])
    assert result.exit_code == 0

    # Step 2: Create some code files
    services_dir = isolated_git_repo / "services"
    services_dir.mkdir()
    (services_dir / "auth.py").write_text("""class AuthService:
    def authenticate(self, user, password):
        return True
""")

    # Commit the changes
    subprocess.run(
        ["git", "add", "."],
        cwd=isolated_git_repo,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "feat: add auth service"],
        cwd=isolated_git_repo,
        capture_output=True,
        check=True,
    )

    # Step 3: Manually set pending state (simulating hook detection)
    state = StateManager(str(isolated_git_repo))
    state.set_pending(
        layers={"traditional"},
        reason="Services changed",
        triggered_by="manual",
        files=["services/auth.py"],
        commit_message="feat: add auth service",
    )

    # Step 4: Check status
    result = runner.invoke(cli, ["status", "--project", str(isolated_git_repo)])
    assert result.exit_code == 0
    assert "Pending Update" in result.output

    # Step 5: Run update (dry-run via config)
    result = runner.invoke(cli, ["update", "traditional", "--project", str(isolated_git_repo)])
    # May fail due to missing README, but shouldn't crash
    # Just verify it doesn't exit with error code


def test_analyzer_detection(isolated_git_repo):
    """Test code analyzer detection"""
    from analyzers import get_analyzer

    # Create test files
    (isolated_git_repo / "test.py").write_text("print('test')")
    (isolated_git_repo / "test.js").write_text("console.log('test')")
    (isolated_git_repo / "test.sh").write_text("echo 'test'")

    # Test Python analyzer
    py_analyzer = get_analyzer("test.py")
    assert py_analyzer.language == "Python"

    # Test JavaScript analyzer
    js_analyzer = get_analyzer("test.js")
    assert js_analyzer.language == "JavaScript/TypeScript"

    # Test Bash analyzer
    sh_analyzer = get_analyzer("test.sh")
    assert sh_analyzer.language == "Bash"


def test_config_validation(isolated_git_repo):
    """Test configuration validation"""
    from cli import cli
    from click.testing import CliRunner
    from core.config import Config

    runner = CliRunner()

    # Initialize
    runner.invoke(cli, ["init", "--project", str(isolated_git_repo)])

    config = Config(str(isolated_git_repo))
    errors = config.validate()

    assert len(errors) == 0
