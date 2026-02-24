"""Command-line interface for git-doc-hook

Provides commands for init, status, update, clear, and memos management.
"""
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import click

# Try to import YAML
try:
    import yaml
except ImportError:
    print("Error: pyyaml is required. Install with: pip install pyyaml")
    sys.exit(1)

from git_doc_hook.core.config import Config
from git_doc_hook.core.git import GitManager, GitError
from git_doc_hook.core.state import StateManager
from git_doc_hook.memos.client import MemOSRecord
from git_doc_hook.analyzers import get_analyzer
from git_doc_hook.template import create_renderer
from git_doc_hook.updaters import DocumentUpdater, ConfigFileUpdater, extract_code_patterns


@click.group()
@click.version_option(version="0.1.0", prog_name="git-doc-hook")
def cli():
    """Git-Doc-Hook: Universal documentation auto-update tool

    Automatically updates project documentation based on Git commits
    and syncs technical decisions to MemOS.
    """
    pass


def _find_git_doc_hook_command() -> str:
    """Find the full path to git-doc-hook executable.

    This ensures hooks work even when ~/.local/bin is not in PATH.
    """
    import shutil

    # First try to find via which/shutil
    path = shutil.which("git-doc-hook")
    if path:
        return path

    # Fallback to common locations
    common_paths = [
        Path.home() / ".local" / "bin" / "git-doc-hook",
        Path.home() / ".bin" / "git-doc-hook",
        Path("/usr/local/bin") / "git-doc-hook",
        Path("/usr/bin") / "git-doc-hook",
    ]

    for p in common_paths:
        if p.exists() and p.is_file():
            return str(p)

    # If all else fails, return just "git-doc-hook" and hope it's in PATH
    return "git-doc-hook"


@cli.command()
@click.option(
    "--project", "-p", default=".", help="Path to project directory"
)
@click.option(
    "--force", "-f", is_flag=True, help="Overwrite existing configuration"
)
def init(project: str, force: bool):
    """Initialize git-doc-hook in a project

    Creates default configuration and installs Git hooks.
    """
    project_path = Path(project).resolve()

    # Find the full path to git-doc-hook for hooks
    gdh_command = _find_git_doc_hook_command()

    if not (project_path / ".git").exists():
        click.echo(f"Error: Not a Git repository: {project_path}", err=True)
        sys.exit(1)

    config = Config(str(project_path))
    config_dir = project_path / ".git-doc-hook"

    # Create config directory
    config_dir.mkdir(exist_ok=True)
    click.echo(f"Created directory: {config_dir}")

    # Check for existing config
    if config.config_file.exists() and not force:
        click.echo(f"Configuration already exists: {config.config_file}")
        click.echo("Use --force to overwrite")
        sys.exit(1)

    # Create default config
    config.save()
    click.echo(f"Created configuration: {config.config_file}")

    # Install Git hooks
    hooks_dir = project_path / ".git" / "hooks"
    hooks_installed = []

    # Pre-push hook
    pre_push = hooks_dir / "pre-push"
    if not pre_push.exists() or force:
        pre_push_content = f"""#!/bin/bash
# git-doc-hook pre-push

# Run git-doc-hook check
{gdh_command} check-pre-push "$@"
"""
        pre_push.write_text(pre_push_content)
        pre_push.chmod(0o755)
        hooks_installed.append("pre-push")

    # Post-commit hook
    post_commit = hooks_dir / "post-commit"
    if not post_commit.exists() or force:
        post_commit_content = f"""#!/bin/bash
# git-doc-hook post-commit

# Check if documentation update is needed
{gdh_command} check-post-commit
"""
        post_commit.write_text(post_commit_content)
        post_commit.chmod(0o755)
        hooks_installed.append("post-commit")

    if hooks_installed:
        click.echo(f"Installed Git hooks: {', '.join(hooks_installed)}")

    # Check MemOS configuration
    if config.memos_enabled:
        click.echo(f"✓ MemOS integration enabled")
        click.echo("  Records will be written to state file for Claude Code to sync")

    click.echo("\n✓ git-doc-hook initialized successfully!")
    click.echo("\nNext steps:")
    click.echo("  1. Review configuration: .git-doc-hook.yml")
    click.echo("  2. Commit and push normally")
    click.echo("  3. If prompted, run: git-doc-hook update <layers>")
    if config.memos_enabled:
        click.echo("  4. For MemOS sync: Use Claude Code's /memos-sync command")


@cli.command()
@click.option(
    "--project", "-p", default=".", help="Path to project directory"
)
@click.option(
    "--json", "output_json", is_flag=True, help="Output as JSON"
)
def status(project: str, output_json: bool):
    """Show pending documentation updates

    Displays any pending documentation updates detected by Git hooks.
    """
    project_path = Path(project).resolve()
    state = StateManager(str(project_path))

    if output_json:
        pending = state.get_pending()
        result = {
            "has_pending": pending is not None,
            "pending": pending.to_dict() if pending else None,
        }
        click.echo(json.dumps(result, indent=2))
        return

    if not state.is_pending():
        click.echo("No pending documentation updates")
        return

    click.echo(state.show_summary())

    # Show MemOS pending records
    memos_records = state.get_pending_memos_records()
    if memos_records:
        click.echo(f"\n⚠ MemOS: {len(memos_records)} record(s) pending sync")
        click.echo("   Run Claude Code's /memos-sync to sync these records")


@cli.command()
@click.argument("layers")
@click.option(
    "--project", "-p", default=".", help="Path to project directory"
)
@click.option(
    "--commit", "-c", is_flag=True, help="Commit changes after update"
)
def update(layers: str, project: str, commit: bool):
    """Execute documentation update

    LAYERS: Comma-separated list of layers to update (e.g., traditional,config)

    Example: git-doc-hook update traditional,config
    """
    project_path = Path(project).resolve()
    state = StateManager(str(project_path))

    if not state.is_pending():
        click.echo("No pending updates to process")
        return

    pending = state.get_pending()
    layer_list = [l.strip() for l in layers.split(",")]

    # Validate layers
    valid_layers = set(pending.layers)
    requested = set(layer_list)
    invalid = requested - valid_layers

    if invalid:
        click.echo(f"Invalid layers: {', '.join(invalid)}", err=True)
        click.echo(f"Valid layers: {', '.join(sorted(valid_layers))}")
        sys.exit(1)

    click.echo(f"Updating layers: {', '.join(sorted(requested))}")
    click.echo(f"Reason: {pending.reason}")

    # Process each layer
    updated = []

    for layer in requested:
        if layer == "traditional":
            if _update_traditional_docs(project_path):
                updated.append("traditional")

        elif layer == "config":
            if _update_config_rules(project_path):
                updated.append("config")

        elif layer == "memo":
            if _sync_to_memos(project_path, pending):
                updated.append("memo")

    if updated:
        click.echo(f"\n✓ Updated: {', '.join(updated)}")

        # Update state
        remaining = valid_layers - set(updated)
        if remaining:
            # Still have pending layers
            state.set_pending(
                layers=remaining,
                reason=pending.reason,
                triggered_by=pending.triggered_by,
                files=pending.files,
                commit_message=pending.commit_message,
            )
            click.echo(f"\n⚠ Remaining: {', '.join(sorted(remaining))}")
        else:
            # All done
            state.clear_pending()
            click.echo("\n✓ All pending updates completed")

        # Commit if requested
        if commit:
            config = Config(str(project_path))
            message = config.get("commit.message_template", "docs: auto-update").format(
                layers=", ".join(updated),
                reason=pending.reason,
            )
            _git_commit(project_path, message)
    else:
        click.echo("\nNo changes made")


@cli.command()
@click.option(
    "--project", "-p", default=".", help="Path to project directory"
)
def clear(project: str):
    """Clear pending update state

    Removes the pending update flag without making changes.
    """
    project_path = Path(project).resolve()
    state = StateManager(str(project_path))

    if not state.is_pending():
        click.echo("No pending updates to clear")
        return

    pending = state.get_pending()
    click.echo(f"Clearing pending update: {', '.join(sorted(pending.layers))}")

    if click.confirm("Are you sure?"):
        state.clear_pending()
        click.echo("✓ Pending state cleared")


@cli.command()
@click.option(
    "--project", "-p", default=".", help="Path to project directory"
)
def memos_sync(project: str):
    """Show MemOS records pending sync

    Displays records waiting to be synced to MemOS by Claude Code.
    Actual sync is performed by Claude Code using MCP tools.
    """
    project_path = Path(project).resolve()
    state = StateManager(str(project_path))
    records = state.get_pending_memos_records()

    if not records:
        click.echo("No MemOS records pending sync")
        return

    click.echo(f"MemOS records pending sync: {len(records)}")
    click.echo("Run Claude Code's /memos-sync to sync these records\n")

    for i, record in enumerate(records, 1):
        record_type = record.get("record_type", "unknown")
        commit_msg = record.get("commit_message", "")[:50]
        click.echo(f"  {i}. [{record_type}] {commit_msg}...")


@cli.command("check-memos", hidden=True)
@click.option(
    "--project", "-p", default=".", help="Path to project directory"
)
@click.option(
    "--json", "output_json", is_flag=True, help="Output as JSON"
)
def check_memos(project: str, output_json: bool):
    """Check and output pending MemOS records

    Internal command for Claude Code to read pending records.
    """
    project_path = Path(project).resolve()
    state = StateManager(str(project_path))
    records = state.get_pending_memos_records()

    if output_json:
        result = {
            "count": len(records),
            "records": records,
        }
        click.echo(json.dumps(result, indent=2))
    else:
        click.echo(f"MemOS pending: {len(records)} records")
        for record in records:
            click.echo(f"  - {record.get('record_type', 'unknown')}: {record.get('commit_message', '')[:50]}")


@cli.command("clear-memos", hidden=True)
@click.option(
    "--project", "-p", default=".", help="Path to project directory"
)
@click.option(
    "--synced", is_flag=True, help="Only clear synced records"
)
def clear_memos(project: str, synced: bool):
    """Clear MemOS pending records

    Internal command for Claude Code to clear synced records.
    """
    project_path = Path(project).resolve()
    state = StateManager(str(project_path))
    count = state.clear_pending_memos(only_synced=synced)

    click.echo(f"Cleared {count} MemOS record(s)")


@cli.command(hidden=True)
@click.argument("remote", required=False)
@click.argument("url", required=False)
def check_pre_push(remote: Optional[str], url: Optional[str]):
    """Internal: Called by pre-push hook

    Checks if push should be blocked for documentation update.
    """
    project = "."
    try:
        git = GitManager(project)
        config = Config(project)
        state = StateManager(project)

        # Get diff
        target = remote or "origin/main"
        diff = git.get_diff(target_ref=target)

        if not diff.has_changes:
            return  # Nothing to do

        # Analyze changes
        layers_to_update = set()

        for commit in diff.commits:
            msg = commit.message.lower()

            # Check for troubleshooting
            if any(kw in msg for kw in config.keywords.get("troubleshooting", [])):
                layers_to_update.add("memo")

            # Check for decisions
            if any(kw in msg for kw in config.keywords.get("decisions", [])):
                layers_to_update.add("memo")

        # Check for service changes
        for file_path in diff.files:
            for rule in config.get_rules_for_pattern(file_path):
                layers_to_update.update(rule.get("layers", []))

        if layers_to_update:
            # Set pending state
            state.set_pending(
                layers=layers_to_update,
                reason=f"Changes detected in {len(diff.files)} files",
                triggered_by=diff.commits[0].hash if diff.commits else "manual",
                files=list(diff.files),
                commit_message=diff.commits[0].message if diff.commits else "",
            )

            click.echo("\n⚠ Documentation update needed")
            click.echo(f"Run: git-doc-hook update {','.join(sorted(layers_to_update))}")
            sys.exit(1)

    except GitError:
        pass  # Not in git repo or other error


@cli.command(hidden=True)
def check_post_commit():
    """Internal: Called by post-commit hook

    Marks commit for potential documentation update.
    """
    # Post-commit check - lightweight version
    try:
        git = GitManager(".")
        commit = git.get_head_commit()

        if commit and any(
            kw in commit.message.lower()
            for kw in ["fix", "feat", "refactor", "decision", "bug"]
        ):
            click.echo("ℹ Commit detected. Run 'git-doc-hook status' after push.")

    except GitError:
        pass


# Helper functions

def _update_traditional_docs(project_path: Path) -> bool:
    """Update traditional documentation

    Args:
        project_path: Path to project

    Returns:
        True if updated successfully
    """
    try:
        from template import create_renderer
        from updaters import DocumentUpdater
    except ImportError:
        click.echo("  Warning: Template/updater modules not available")
        return False

    state = StateManager(str(project_path))
    config = Config(str(project_path))
    pending = state.get_pending()

    if not pending:
        click.echo("  No pending updates to process")
        return False

    # Create renderer and updater
    renderer = create_renderer(project_path, config)
    updater = DocumentUpdater(
        dry_run=config.dry_run,
        backup=config.backup_enabled,
    )

    # Build template context
    context = renderer.build_context(project_path, pending, config)

    any_updated = False

    # Process each file's rules
    for file_path in pending.files:
        matching_rules = config.get_rules_for_pattern(file_path)

        for rule in matching_rules:
            # Only process rules that target traditional docs
            if "traditional" not in rule.get("layers", []):
                continue

            for action in rule.get("actions", []):
                target = action.get("target", "")
                action_type = action.get("action", "")
                section = action.get("section", "")

                if not target:
                    continue

                target_path = project_path / target

                try:
                    if action_type == "append_table_row":
                        # Build row data from context
                        row_data = _build_row_data(file_path, context, action)

                        # Get table headers from action or use defaults
                        headers = action.get("headers", _get_default_headers(section))

                        result = updater.append_table_row(
                            target_file=target_path,
                            section=section or "Documentation",
                            row_data=row_data,
                            table_headers=headers,
                        )

                        if result.success:
                            click.echo(f"  ✓ Updated {target}: {section}")
                            any_updated = True

                    elif action_type == "append_record":
                        # Generate content from template
                        content = renderer.render_traditional(context)

                        result = updater.append_record(
                            target_file=target_path,
                            content=content,
                        )

                        if result.success:
                            click.echo(f"  ✓ Appended to {target}")
                            any_updated = True

                    elif action_type == "update_section":
                        # Generate content from template
                        content = renderer.render_traditional(context)

                        result = updater.update_section(
                            target_file=target_path,
                            section=section or "Updates",
                            new_content=content,
                        )

                        if result.success:
                            click.echo(f"  ✓ Updated section '{section}' in {target}")
                            any_updated = True

                    elif action_type == "prepend_content":
                        content = renderer.render_traditional(context)

                        result = updater.prepend_content(
                            target_file=target_path,
                            content=content,
                        )

                        if result.success:
                            click.echo(f"  ✓ Prepended to {target}")
                            any_updated = True

                except Exception as e:
                    click.echo(f"  ✗ Error updating {target}: {e}")

    # If no specific rules matched, try default README update
    if not any_updated:
        readme = project_path / "README.md"
        if readme.exists():
            content = renderer.render_traditional(context)
            result = updater.append_record(
                target_file=readme,
                content=f"\n## Recent Changes\n\n{content}\n",
            )
            if result.success:
                click.echo(f"  ✓ Updated README.md")
                any_updated = True

    return any_updated


def _build_row_data(file_path: str, context: Dict[str, Any], action: Dict[str, Any]) -> Dict[str, str]:
    """Build row data for table insertion

    Args:
        file_path: File path being processed
        context: Template context
        action: Action configuration

    Returns:
        Dictionary of column name to value
    """
    # Get row mapping from action or use defaults
    row_mapping = action.get("row_mapping", {})

    if row_mapping:
        # Use explicit mapping
        return {col: _extract_value(file_path, context, value_expr)
                for col, value_expr in row_mapping.items()}

    # Default mapping based on section type
    path = Path(file_path)
    return {
        "File": path.name,
        "Path": str(path),
        "Type": _get_file_type(file_path),
    }


def _extract_value(file_path: str, context: Dict[str, Any], expr: str) -> str:
    """Extract a value using an expression

    Args:
        file_path: File path
        context: Template context
        expr: Expression to evaluate

    Returns:
        Extracted value
    """
    # Simple substitution
    substitutions = {
        "{file}": Path(file_path).name,
        "{path}": file_path,
        "{type}": _get_file_type(file_path),
    }

    for key, value in substitutions.items():
        if key in expr:
            return expr.replace(key, value)

    return expr


def _get_file_type(file_path: str) -> str:
    """Determine file type from path

    Args:
        file_path: File path

    Returns:
        File type string
    """
    path = Path(file_path)
    parent = path.parent.name.lower()

    type_map = {
        "service": "Service",
        "model": "Model",
        "entity": "Model",
        "controller": "Controller",
        "util": "Utility",
        "helper": "Utility",
        "test": "Test",
    }

    return type_map.get(parent, "Module")


def _get_default_headers(section: str) -> List[str]:
    """Get default table headers for a section

    Args:
        section: Section name

    Returns:
        List of headers
    """
    header_map = {
        "Services": ["Name", "Path", "Type"],
        "Components": ["Name", "Path", "Type"],
        "Modules": ["File", "Path", "Description"],
    }

    return header_map.get(section, ["Name", "Path", "Type"])


def _update_config_rules(project_path: Path) -> bool:
    """Update config rule documentation

    Args:
        project_path: Path to project

    Returns:
        True if updated successfully
    """
    try:
        from template import create_renderer
        from updaters import ConfigFileUpdater, extract_code_patterns
    except ImportError:
        click.echo("  Warning: Template/updater modules not available")
        return False

    state = StateManager(str(project_path))
    config = Config(str(project_path))
    pending = state.get_pending()

    if not pending:
        return False

    updater = ConfigFileUpdater(dry_run=config.dry_run)
    any_updated = False

    # Extract patterns from changed files
    file_paths = [project_path / f for f in pending.files]
    patterns = extract_code_patterns(file_paths, project_path)

    if not patterns:
        click.echo("  No code patterns detected")
        return False

    # Update .clinerules
    clinerules_path = project_path / ".clinerules"
    result = updater.update_clinerules(project_path, patterns)

    if result.success and result.message != "All patterns already documented":
        click.echo(f"  ✓ Updated .clinerules: {result.message}")
        any_updated = True

    # Update .cursorrules
    cursorrules_path = project_path / ".cursorrules"
    result = updater.update_cursorrules(project_path, patterns)

    if result.success:
        click.echo(f"  ✓ Updated .cursorrules: {result.message}")
        any_updated = True

    return any_updated


def _sync_to_memos(project_path: Path, pending) -> bool:
    """Create MemOS record and write to state file

    Records are written to state for Claude Code to sync via MCP.

    Args:
        project_path: Path to project
        pending: Pending update info

    Returns:
        True if record was created successfully
    """
    config = Config(str(project_path))
    state = StateManager(str(project_path))

    # Generate cube_id from project name
    cube_id = f"{config.project_path.name}-{config.get('state.project_key', config.project_path.name)}"

    # Create record from pending info
    record = MemOSRecord.create_from_commit(
        commit_message=pending.commit_message,
        changed_files=pending.files,
        diff_summary=pending.reason,
        project=config.project_path.name,
        commit_hash=pending.triggered_by,
    )

    # Update cube_id
    record_dict = record.to_dict()
    record_dict["cube_id"] = cube_id

    # Add to pending state
    state.add_memos_record(record_dict)

    total_records = len(state.get_pending_memos_records())
    click.echo(f"  Created MemOS record: {record.record_type}")
    click.echo(f"  Total pending: {total_records} record(s)")
    click.echo("  Run Claude Code's /memos-sync to sync to MemOS")

    return True


def _git_commit(project_path: Path, message: str) -> bool:
    """Create a git commit

    Args:
        project_path: Path to project
        message: Commit message

    Returns:
        True if successful
    """
    try:
        import subprocess

        subprocess.run(
            ["git", "add", "-A"],
            cwd=project_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=project_path,
            check=True,
            capture_output=True,
        )
        click.echo(f"✓ Committed: {message}")
        return True
    except subprocess.CalledProcessError:
        return False


def main():
    """Main entry point"""
    cli()


if __name__ == "__main__":
    main()
