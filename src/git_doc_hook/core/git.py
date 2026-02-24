"""Git operations wrapper for git-doc-hook

Provides abstraction over Git commands for repo detection,
diff parsing, and commit analysis.
"""
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set


@dataclass
class Commit:
    """Represents a Git commit"""

    hash: str
    message: str
    author: str
    date: datetime
    files: List[str]

    @property
    def short_hash(self) -> str:
        """Get short commit hash"""
        return self.hash[:7]

    def contains_keywords(self, keywords: List[str]) -> bool:
        """Check if commit message contains any keywords

        Args:
            keywords: List of keywords to search for

        Returns:
            True if any keyword found (case-insensitive)
        """
        message_lower = self.message.lower()
        return any(kw.lower() in message_lower for kw in keywords)

    def get_type(self) -> str:
        """Extract commit type from conventional commit message

        Returns:
            Type like "feat", "fix", "docs", etc. or "unknown"
        """
        match = re.match(r"^(\w+)(\(.+\))?:", self.message)
        if match:
            return match.group(1)
        return "unknown"

    def get_scope(self) -> Optional[str]:
        """Extract scope from conventional commit message

        Returns:
            Scope like "auth", "api", etc. or None
        """
        match = re.match(r"^\w+\((.+)\):", self.message)
        if match:
            return match.group(1)
        return None


@dataclass
class FileChange:
    """Represents a file change in a commit"""

    path: str
    status: str  # A (added), M (modified), D (deleted), R (renamed)
    additions: int
    deletions: int
    patch: Optional[str] = None

    @property
    def is_added(self) -> bool:
        return self.status == "A"

    @property
    def is_modified(self) -> bool:
        return self.status == "M"

    @property
    def is_deleted(self) -> bool:
        return self.status == "D"

    @property
    def extension(self) -> str:
        """Get file extension"""
        return Path(self.path).suffix.lstrip(".")


@dataclass
class DiffResult:
    """Result of a Git diff operation"""

    commits: List[Commit]
    files: Set[str]
    file_changes: List[FileChange]

    @property
    def has_changes(self) -> bool:
        """Check if there are any changes"""
        return len(self.commits) > 0 or len(self.files) > 0

    def get_files_by_extension(self, extension: str) -> List[str]:
        """Get all changed files with a specific extension

        Args:
            extension: File extension (e.g., "py", "js")

        Returns:
            List of file paths
        """
        ext = extension.lstrip(".")
        return [f for f in self.files if f.endswith(f".{ext}")]

    def get_files_matching_pattern(self, pattern: str) -> List[str]:
        """Get files matching a glob pattern

        Args:
            pattern: Glob pattern (e.g., "services/**/*.py")

        Returns:
            List of matching file paths
        """
        from fnmatch import fnmatch

        return [f for f in self.files if fnmatch(f, pattern)]


class GitError(Exception):
    """Exception raised for Git-related errors"""

    pass


class GitManager:
    """Git operations manager

    Provides high-level interface to Git operations needed by
    git-doc-hook for analyzing commits and changes.
    """

    def __init__(self, repo_path: str = "."):
        """Initialize Git manager for a repository

        Args:
            repo_path: Path to the Git repository

        Raises:
            GitError: If not a valid Git repository
        """
        self.repo_path = Path(repo_path).resolve()
        self._validate_repo()

    def _validate_repo(self) -> None:
        """Check if path is a valid Git repository"""
        git_dir = self.repo_path / ".git"
        if not git_dir.exists():
            # Also check if we're inside a worktree
            result = self._run_git(["rev-parse", "--git-dir"], capture=True, check=False)
            if result.returncode != 0:
                raise GitError(f"Not a Git repository: {self.repo_path}")

    def _run_git(
        self,
        args: List[str],
        capture: bool = True,
        check: bool = True,
        cwd: Optional[Path] = None,
    ) -> subprocess.CompletedProcess:
        """Run a Git command

        Args:
            args: Git command arguments
            capture: Whether to capture stdout/stderr
            check: Whether to raise on non-zero exit
            cwd: Working directory (defaults to repo_path)

        Returns:
            CompletedProcess result
        """
        cmd = ["git"] + args
        work_dir = cwd or self.repo_path

        try:
            result = subprocess.run(
                cmd,
                cwd=work_dir,
                capture_output=capture,
                text=capture,
                check=check,
            )
            return result
        except subprocess.CalledProcessError as e:
            raise GitError(f"Git command failed: {' '.join(cmd)}") from e
        except FileNotFoundError:
            raise GitError("Git not found in PATH")

    def get_repo_name(self) -> str:
        """Get repository name from directory or remote

        Returns:
            Repository name
        """
        # Try to get from remote origin
        result = self._run_git(
            ["remote", "get-url", "origin"], check=False, capture=True
        )
        if result.returncode == 0 and result.stdout:
            # Extract name from URL
            url = result.stdout.strip()
            name = url.rstrip(".git").split("/")[-1]
            return name

        # Fallback to directory name
        return self.repo_path.name

    def get_current_branch(self) -> str:
        """Get current branch name

        Returns:
            Branch name
        """
        result = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        return result.stdout.strip()

    def get_remote_url(self, remote: str = "origin") -> Optional[str]:
        """Get remote repository URL

        Args:
            remote: Remote name

        Returns:
            Remote URL or None
        """
        result = self._run_git(["remote", "get-url", remote], check=False)
        if result.returncode == 0:
            return result.stdout.strip()
        return None

    def get_commits(
        self, since_ref: Optional[str] = None, limit: int = 10
    ) -> List[Commit]:
        """Get recent commits

        Args:
            since_ref: Starting reference (e.g., "origin/main")
            limit: Maximum number of commits

        Returns:
            List of commits
        """
        args = ["log", f"-{limit}", "--pretty=format:%H|%s|%an|%ai", "--name-only"]
        if since_ref:
            args.append(f"{since_ref}..HEAD")

        result = self._run_git(args)
        commits = []
        current_commit = None

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue

            # Check if this is a commit line or a file line
            parts = line.split("|")
            if len(parts) >= 4:
                # This is a commit line
                if current_commit:
                    commits.append(current_commit)

                commit_hash, message, author, date_str = parts[:4]
                try:
                    date = datetime.fromisoformat(date_str)
                except ValueError:
                    date = datetime.now()

                current_commit = Commit(
                    hash=commit_hash,
                    message=message,
                    author=author,
                    date=date,
                    files=[],
                )
            elif current_commit is not None:
                # This is a file line
                current_commit.files.append(line)

        # Don't forget the last commit
        if current_commit:
            commits.append(current_commit)

        return commits

    def get_diff(self, target_ref: Optional[str] = None) -> DiffResult:
        """Get diff between current state and target reference

        Args:
            target_ref: Target reference (defaults to origin/main or origin/master)

        Returns:
            DiffResult with commits, changed files, and file details
        """
        # Determine target ref
        if target_ref is None:
            # Try to find upstream branch
            for candidate in ["origin/main", "origin/master", "main", "master"]:
                result = self._run_git(["rev-parse", candidate], check=False)
                if result.returncode == 0:
                    target_ref = candidate
                    break
            if target_ref is None:
                target_ref = "HEAD^"  # Fallback to previous commit

        # Get commits since target
        commits = self.get_commits(since_ref=target_ref, limit=50)

        # Get changed files
        result = self._run_git(["diff", "--name-status", target_ref])
        file_changes = []
        files = set()

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue

            # Parse status and path
            parts = line.split("\t")
            if len(parts) >= 2:
                status, path = parts[0], parts[1]
                files.add(path)

                # Get additions/deletions if available
                numstat_result = self._run_git(
                    ["diff", "--numstat", target_ref, "--", path], check=False
                )
                additions, deletions = 0, 0
                if numstat_result.returncode == 0 and numstat_result.stdout.strip():
                    stats = numstat_result.stdout.strip().split("\n")[0].split()
                    if len(stats) >= 2:
                        try:
                            additions = int(stats[0])
                            deletions = int(stats[1])
                        except ValueError:
                            pass

                file_changes.append(
                    FileChange(
                        path=path,
                        status=status,
                        additions=additions,
                        deletions=deletions,
                    )
                )

        return DiffResult(commits=commits, files=files, file_changes=file_changes)

    def get_staged_files(self) -> Set[str]:
        """Get list of staged files

        Returns:
            Set of staged file paths
        """
        result = self._run_git(["diff", "--cached", "--name-only"])
        files = set()
        for line in result.stdout.strip().split("\n"):
            if line:
                files.add(line)
        return files

    def get_file_content(self, file_path: str, ref: str = "HEAD") -> Optional[str]:
        """Get file content at a specific reference

        Args:
            file_path: Path to file (relative to repo root)
            ref: Git reference (defaults to HEAD)

        Returns:
            File content or None if not found
        """
        result = self._run_git(["show", f"{ref}:{file_path}"], check=False)
        if result.returncode == 0:
            return result.stdout
        return None

    def get_changed_functions(
        self, file_path: str, since_ref: Optional[str] = None
    ) -> List[str]:
        """Get list of changed functions in a Python file

        Args:
            file_path: Path to Python file
            since_ref: Reference to compare against

        Returns:
            List of function names that were changed
        """
        # This is a simplified implementation
        # Full implementation would parse AST and compare
        result = self._run_git(["diff", since_ref or "HEAD^", "--", file_path], check=False)
        if result.returncode != 0:
            return []

        # Look for function definitions in the diff
        functions = set()
        for line in result.stdout.split("\n"):
            if line.startswith("+") and "def " in line:
                match = re.search(r"def\s+(\w+)\s*\(", line)
                if match:
                    functions.add(match.group(1))

        return list(functions)

    def is_dirty(self) -> bool:
        """Check if working directory has uncommitted changes

        Returns:
            True if there are uncommitted changes
        """
        result = self._run_git(["status", "--porcelain"])
        return len(result.stdout.strip()) > 0

    def get_head_commit(self) -> Optional[Commit]:
        """Get the HEAD commit

        Returns:
            HEAD commit or None
        """
        try:
            result = self._run_git(["log", "-1", "--pretty=format:%H|%s|%an|%ai"])
            if not result.stdout.strip():
                return None

            parts = result.stdout.strip().split("|")
            if len(parts) >= 4:
                return Commit(
                    hash=parts[0],
                    message=parts[1],
                    author=parts[2],
                    date=datetime.fromisoformat(parts[3]),
                    files=[],
                )
        except GitError:
            pass
        return None
