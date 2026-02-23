"""Tests for Git operations"""
import pytest
from pathlib import Path
from core.git import GitManager, GitError, Commit, FileChange, DiffResult


@pytest.fixture
def git_repo(tmp_path):
    """Create a temporary Git repository"""
    repo = tmp_path / "test_repo"
    repo.mkdir()

    # Initialize git repo
    import subprocess
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


@pytest.fixture
def git_manager(git_repo):
    """Create a GitManager instance"""
    return GitManager(str(git_repo))


def test_git_manager_init(git_repo):
    """Test GitManager initialization"""
    manager = GitManager(str(git_repo))

    assert manager.repo_path == git_repo


def test_git_manager_invalid_repo(tmp_path):
    """Test GitManager with invalid repository"""
    with pytest.raises(GitError):
        GitManager(str(tmp_path))


def test_get_current_branch(git_manager):
    """Test getting current branch"""
    branch = git_manager.get_current_branch()

    # Default branch should be main or master
    assert branch in ["main", "master"]


def test_get_repo_name(git_manager):
    """Test getting repository name"""
    name = git_manager.get_repo_name()

    assert name == "test_repo"


def test_commit_dataclass():
    """Test Commit dataclass"""
    commit = Commit(
        hash="abc123",
        message="Test commit",
        author="Test User",
        date=None,
        files=["test.py"],
    )

    assert commit.short_hash == "abc123"
    assert commit.contains_keywords(["test"])
    assert not commit.contains_keywords(["fix"])


def test_commit_type_extraction():
    """Test commit type extraction"""
    commit = Commit(
        hash="abc",
        message="feat: add feature",
        author="Test",
        date=None,
        files=[],
    )

    assert commit.get_type() == "feat"


def test_commit_scope_extraction():
    """Test commit scope extraction"""
    commit = Commit(
        hash="abc",
        message="feat(auth): add login",
        author="Test",
        date=None,
        files=[],
    )

    assert commit.get_scope() == "auth"


def test_file_change_dataclass():
    """Test FileChange dataclass"""
    change = FileChange(
        path="test.py",
        status="M",
        additions=10,
        deletions=5,
    )

    assert change.is_modified
    assert not change.is_added
    assert not change.is_deleted
    assert change.extension == "py"


def test_diff_result_dataclass():
    """Test DiffResult dataclass"""
    diff = DiffResult(
        commits=[],
        files=set(),
        file_changes=[],
    )

    assert not diff.has_changes


def test_diff_result_has_changes():
    """Test DiffResult has_changes property"""
    diff = DiffResult(
        commits=[Commit(
            hash="abc",
            message="test",
            author="test",
            date=None,
            files=[],
        )],
        files=set(),
        file_changes=[],
    )

    assert diff.has_changes


def test_get_files_by_extension(git_repo, git_manager):
    """Test getting files by extension"""
    # Create some files
    (git_repo / "test.py").write_text("print('test')")
    (git_repo / "test.js").write_text("console.log('test')")

    import subprocess
    subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "test"],
        cwd=git_repo,
        capture_output=True,
    )

    diff = git_manager.get_diff("HEAD^")

    py_files = diff.get_files_by_extension("py")
    assert any("test.py" in f for f in py_files)


def test_is_dirty(git_repo, git_manager):
    """Test checking if repo is dirty"""
    assert not git_manager.is_dirty()

    # Create uncommitted change
    (git_repo / "dirty.txt").write_text("dirty")

    assert git_manager.is_dirty()


def test_get_head_commit(git_repo, git_manager):
    """Test getting HEAD commit"""
    # Make a commit
    (git_repo / "test.txt").write_text("test")
    import subprocess
    subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=git_repo,
        capture_output=True,
    )

    commit = git_manager.get_head_commit()

    assert commit is not None
    assert commit.message == "initial"


def test_get_staged_files(git_repo, git_manager):
    """Test getting staged files"""
    (git_repo / "staged.txt").write_text("staged")

    import subprocess
    subprocess.run(["git", "add", "staged.txt"], cwd=git_repo, capture_output=True)

    staged = git_manager.get_staged_files()

    assert "staged.txt" in staged


def test_get_commits(git_repo, git_manager):
    """Test getting commits"""
    # Make some commits
    for i in range(3):
        (git_repo / f"file{i}.txt").write_text(f"content{i}")
        import subprocess
        subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", f"commit {i}"],
            cwd=git_repo,
            capture_output=True,
        )

    commits = git_manager.get_commits(limit=10)

    assert len(commits) == 3


def test_get_file_content(git_repo, git_manager):
    """Test getting file content"""
    (git_repo / "content.txt").write_text("test content")

    import subprocess
    subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "add file"],
        cwd=git_repo,
        capture_output=True,
    )

    content = git_manager.get_file_content("content.txt")

    assert content == "test content"


def test_get_diff(git_repo, git_manager):
    """Test getting diff"""
    # Create initial commit
    (git_repo / "initial.txt").write_text("initial")
    import subprocess
    subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=git_repo,
        capture_output=True,
    )

    # Make changes
    (git_repo / "changed.txt").write_text("changed")
    subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "changes"],
        cwd=git_repo,
        capture_output=True,
    )

    diff = git_manager.get_diff("HEAD^")

    assert diff.has_changes
    assert "changed.txt" in diff.files


def test_get_remote_url(git_repo, git_manager):
    """Test getting remote URL"""
    # Add a remote
    import subprocess
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/test/repo.git"],
        cwd=git_repo,
        capture_output=True,
    )

    url = git_manager.get_remote_url()

    assert url == "https://github.com/test/repo.git"
