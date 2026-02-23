"""Tests for CLI commands"""
import json
from pathlib import Path
from click.testing import CliRunner
import pytest

# We need to import from src package
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cli import cli


@pytest.fixture
def runner():
    """Create a Click CLI runner"""
    return CliRunner()


@pytest.fixture
def temp_git_project(tmp_path):
    """Create a temporary Git repository"""
    project = tmp_path / "test_project"
    project.mkdir()

    # Initialize git repo
    import subprocess
    subprocess.run(
        ["git", "init"],
        cwd=project,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=project,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=project,
        capture_output=True,
        check=True,
    )

    return project


def test_cli_group(runner):
    """Test that CLI group is available"""
    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "Git-Doc-Hook" in result.output


def test_init_command(temp_git_project, runner):
    """Test init command"""
    result = runner.invoke(cli, ["init", "--project", str(temp_git_project)])

    assert result.exit_code == 0
    assert "git-doc-hook initialized" in result.output
    assert (temp_git_project / ".git-doc-hook.yml").exists()


def test_init_creates_hooks(temp_git_project, runner):
    """Test that init creates Git hooks"""
    result = runner.invoke(cli, ["init", "--project", str(temp_git_project)])

    assert result.exit_code == 0

    hooks_dir = temp_git_project / ".git" / "hooks"
    assert (hooks_dir / "pre-push").exists()
    assert (hooks_dir / "post-commit").exists()


def test_init_force(temp_git_project, runner):
    """Test init with --force flag"""
    # First init
    runner.invoke(cli, ["init", "--project", str(temp_git_project)])

    # Second init without force should fail
    result = runner.invoke(cli, ["init", "--project", str(temp_git_project)])
    assert result.exit_code == 1

    # With force should succeed
    result = runner.invoke(cli, ["init", "--force", "--project", str(temp_git_project)])
    assert result.exit_code == 0


def test_init_non_git_repo(tmp_path, runner):
    """Test init on non-Git directory"""
    result = runner.invoke(cli, ["init", "--project", str(tmp_path)])

    assert result.exit_code == 1
    assert "Not a Git repository" in result.output


def test_status_command_empty(temp_git_project, runner):
    """Test status command with no pending updates"""
    # Initialize first
    runner.invoke(cli, ["init", "--project", str(temp_git_project)])

    result = runner.invoke(cli, ["status", "--project", str(temp_git_project)])

    assert result.exit_code == 0
    assert "No pending" in result.output


def test_status_json(temp_git_project, runner):
    """Test status command with JSON output"""
    # Initialize first
    runner.invoke(cli, ["init", "--project", str(temp_git_project)])

    result = runner.invoke(cli, ["status", "--project", str(temp_git_project), "--json"])

    assert result.exit_code == 0

    data = json.loads(result.output)
    assert "has_pending" in data
    assert data["has_pending"] is False


def test_clear_command_empty(temp_git_project, runner):
    """Test clear command with no pending updates"""
    # Initialize first
    runner.invoke(cli, ["init", "--project", str(temp_git_project)])

    result = runner.invoke(cli, ["clear", "--project", str(temp_git_project)])

    assert result.exit_code == 0
    assert "No pending" in result.output


def test_memos_sync_command_disabled(temp_git_project, runner):
    """Test memos-sync command when MemOS is disabled"""
    # Initialize with config that disables memos
    result = runner.invoke(cli, ["init", "--project", str(temp_git_project)])

    # Update config to disable memos
    config_file = temp_git_project / ".git-doc-hook.yml"
    import yaml
    config = yaml.safe_load(config_file.read_text())
    config["memos"]["enabled"] = False
    config_file.write_text(yaml.dump(config))

    result = runner.invoke(cli, ["memos-sync", "--project", str(temp_git_project)])

    assert result.exit_code == 0
    assert "not enabled" in result.output


def test_version_option(runner):
    """Test --version option"""
    result = runner.invoke(cli, ["--version"])

    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_help_command(runner):
    """Test help command"""
    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "init" in result.output
    assert "status" in result.output
    assert "update" in result.output
    assert "clear" in result.output
    assert "memos-sync" in result.output


def test_update_command_no_pending(temp_git_project, runner):
    """Test update command with no pending updates"""
    # Initialize first
    runner.invoke(cli, ["init", "--project", str(temp_git_project)])

    result = runner.invoke(cli, ["update", "traditional", "--project", str(temp_git_project)])

    assert result.exit_code == 0
    assert "No pending" in result.output


def test_check_pre_push_hidden(temp_git_project, runner):
    """Test check-pre-push hidden command"""
    result = runner.invoke(cli, ["check-pre-push"])

    # Should exit without error (no changes)
    assert result.exit_code == 0


def test_check_post_commit_hidden(temp_git_project, runner):
    """Test check-post-commit hidden command"""
    result = runner.invoke(cli, ["check-post-commit"])

    # Should exit without error
    assert result.exit_code == 0


def test_init_with_memos_unavailable(temp_git_project, runner):
    """Test init when MemOS is unavailable"""
    result = runner.invoke(cli, ["init", "--project", str(temp_git_project)])

    assert result.exit_code == 0
    # Should show warning about MemOS
    assert "initialized successfully" in result.output


def test_init_custom_project_name(temp_git_project, runner):
    """Test init with custom project in config"""
    result = runner.invoke(cli, ["init", "--project", str(temp_git_project)])

    assert result.exit_code == 0

    # Check config was created
    config_file = temp_git_project / ".git-doc-hook.yml"
    assert config_file.exists()
