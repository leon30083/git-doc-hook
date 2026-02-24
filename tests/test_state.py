"""Tests for state management"""
import json
import time
import pytest
from pathlib import Path
from git_doc_hook.core.state import StateManager, PendingUpdate
from git_doc_hook.core.config import Config


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project directory"""
    import uuid
    project = tmp_path / f"test_project_{uuid.uuid4().hex[:8]}"
    project.mkdir()
    # Create .git to make it a valid git repo
    (project / ".git").mkdir()
    return project


@pytest.fixture
def state_manager(temp_project):
    """Create a StateManager instance"""
    return StateManager(str(temp_project))


def test_state_manager_init(temp_project):
    """Test StateManager initialization"""
    state = StateManager(str(temp_project))

    assert state.project_path == temp_project
    assert state.state_dir.exists()


def test_set_pending(state_manager):
    """Test setting pending state"""
    layers = {"traditional", "memo"}
    reason = "Test update"
    triggered_by = "abc123"
    files = ["test.py", "main.py"]
    commit_message = "feat: add feature"

    state_manager.set_pending(
        layers=layers,
        reason=reason,
        triggered_by=triggered_by,
        files=files,
        commit_message=commit_message,
    )

    assert state_manager.is_pending()


def test_get_pending(state_manager):
    """Test getting pending state"""
    layers = {"traditional"}
    reason = "Test reason"

    state_manager.set_pending(
        layers=layers,
        reason=reason,
        triggered_by="abc123",
        files=["test.py"],
        commit_message="test: message",
    )

    pending = state_manager.get_pending()

    assert pending is not None
    assert pending.layers == layers
    assert pending.reason == reason
    assert pending.triggered_by == "abc123"
    assert pending.files == ["test.py"]
    assert pending.commit_message == "test: message"


def test_clear_pending(state_manager):
    """Test clearing pending state"""
    state_manager.set_pending(
        layers={"traditional"},
        reason="Test",
        triggered_by="abc",
        files=[],
        commit_message="test",
    )

    assert state_manager.is_pending()

    state_manager.clear_pending()

    assert not state_manager.is_pending()


def test_is_pending(state_manager):
    """Test is_pending method"""
    assert not state_manager.is_pending()

    state_manager.set_pending(
        layers={"memo"},
        reason="Test",
        triggered_by="abc",
        files=[],
        commit_message="test",
    )

    assert state_manager.is_pending()


def test_get_pending_layers(state_manager):
    """Test getting pending layers"""
    state_manager.set_pending(
        layers={"traditional", "config", "memo"},
        reason="Test",
        triggered_by="abc",
        files=[],
        commit_message="test",
    )

    layers = state_manager.get_pending_layers()

    assert layers == {"traditional", "config", "memo"}


def test_show_summary(state_manager):
    """Test show_summary method"""
    state_manager.set_pending(
        layers={"traditional"},
        reason="Services changed",
        triggered_by="abc123",
        files=["services/auth.py"],
        commit_message="feat: add auth service",
    )

    summary = state_manager.show_summary()

    assert "Pending Update" in summary
    assert "traditional" in summary
    assert "Services changed" in summary
    assert "abc123" in summary


def test_pending_update_to_dict():
    """Test PendingUpdate serialization"""
    pending = PendingUpdate(
        layers={"traditional", "memo"},
        reason="Test",
        triggered_by="abc",
        timestamp=time.time(),
        files=["test.py"],
        commit_message="feat: test",
    )

    data = pending.to_dict()

    assert isinstance(data["layers"], list)
    assert set(data["layers"]) == {"traditional", "memo"}
    assert data["reason"] == "Test"


def test_pending_update_from_dict():
    """Test PendingUpdate deserialization"""
    data = {
        "layers": ["traditional", "config"],
        "reason": "Test reason",
        "triggered_by": "xyz789",
        "timestamp": time.time(),
        "files": ["main.py"],
        "commit_message": "fix: bug",
    }

    pending = PendingUpdate.from_dict(data)

    assert pending.layers == {"traditional", "config"}
    assert pending.reason == "Test reason"
    assert pending.triggered_by == "xyz789"


def test_history_tracking(state_manager):
    """Test that cleared pending goes to history"""
    state_manager.set_pending(
        layers={"traditional"},
        reason="Test",
        triggered_by="abc",
        files=[],
        commit_message="test",
    )

    state_manager.clear_pending()

    history = state_manager.get_history()

    assert len(history) > 0
    assert history[0]["layers"] == ["traditional"]


def test_add_to_history(state_manager):
    """Test adding entry to history"""
    state_manager.add_to_history(
        layers={"memo"},
        action="synced",
        details={"target": "memos"},
    )

    history = state_manager.get_history()

    assert len(history) > 0
    assert history[0]["action"] == "synced"


def test_cleanup(state_manager):
    """Test cleanup method"""
    # Set pending to create state file
    state_manager.set_pending(
        layers={"traditional"},
        reason="Test",
        triggered_by="abc",
        files=[],
        commit_message="test",
    )

    assert state_manager.state_file.exists()

    state_manager.cleanup()

    assert not state_manager.state_file.exists()


def test_get_project_state_dir(state_manager):
    """Test getting state directory"""
    state_dir = state_manager.get_project_state_dir()

    assert state_dir == state_manager.state_dir


def test_state_isolation(tmp_path):
    """Test that different projects have isolated state"""
    project1 = tmp_path / "project1"
    project2 = tmp_path / "project2"

    for p in [project1, project2]:
        p.mkdir()
        (p / ".git").mkdir()

    state1 = StateManager(str(project1))
    state2 = StateManager(str(project2))

    state1.set_pending(
        layers={"traditional"},
        reason="Project1",
        triggered_by="abc",
        files=[],
        commit_message="test",
    )

    assert state1.is_pending()
    assert not state2.is_pending()


def test_history_limit(state_manager):
    """Test that history is limited to 100 entries"""
    # Add more than 100 entries
    for i in range(150):
        state_manager.set_pending(
            layers={"memo"},
            reason=f"Update {i}",
            triggered_by=f"commit{i}",
            files=[],
            commit_message=f"test {i}",
        )
        state_manager.clear_pending()

    history = state_manager.get_history(limit=200)

    assert len(history) <= 100


def test_empty_state_file(state_manager, temp_project):
    """Test handling of empty/corrupt state file"""
    state_file = state_manager.state_file

    # Write empty JSON
    state_file.write_text("{}")

    # Should not crash
    assert not state_manager.is_pending()

    # Write invalid JSON
    state_file.write_text("{invalid}")

    # Should not crash
    assert not state_manager.is_pending()


# MemOS record management tests

def test_add_memos_record(state_manager):
    """Test adding a MemOS record to pending state"""
    # First, set up a pending state
    state_manager.set_pending(
        layers={"memo"},
        reason="Test",
        triggered_by="abc123",
        files=["test.py"],
        commit_message="fix: bug",
    )

    # Add a MemOS record
    record = {
        "content": "# Test Record\n\nTest content",
        "record_type": "troubleshooting",
        "project": "test-project",
        "commit_hash": "abc123",
        "commit_message": "fix: bug",
        "files": ["test.py"],
        "metadata": {"category": "troubleshooting"},
        "timestamp": time.time(),
        "cube_id": "test-cube",
    }
    state_manager.add_memos_record(record)

    # Verify it was added
    records = state_manager.get_pending_memos_records()
    assert len(records) == 1
    assert records[0]["record_type"] == "troubleshooting"


def test_get_pending_memos_records_empty(temp_project):
    """Test getting MemOS records when none exist"""
    # Use a fresh StateManager for this test
    state = StateManager(str(temp_project))
    records = state.get_pending_memos_records()
    assert records == []


def test_get_pending_memos_records(state_manager):
    """Test getting pending MemOS records"""
    # Set up pending state
    state_manager.set_pending(
        layers={"memo"},
        reason="Test",
        triggered_by="abc",
        files=[],
        commit_message="test",
    )

    # Add multiple records
    for i in range(3):
        record = {
            "content": f"Record {i}",
            "record_type": "general",
            "project": "test",
            "commit_hash": f"commit{i}",
            "commit_message": f"Message {i}",
            "files": [],
            "metadata": {},
            "timestamp": time.time(),
            "cube_id": "test-cube",
        }
        state_manager.add_memos_record(record)

    records = state_manager.get_pending_memos_records()
    assert len(records) == 3


def test_clear_pending_memos(state_manager):
    """Test clearing all pending MemOS records"""
    # Set up pending state with records
    state_manager.set_pending(
        layers={"memo"},
        reason="Test",
        triggered_by="abc",
        files=[],
        commit_message="test",
    )

    # Add records
    for i in range(2):
        record = {
            "content": f"Record {i}",
            "record_type": "general",
            "project": "test",
            "commit_hash": f"commit{i}",
            "commit_message": f"Message {i}",
            "files": [],
            "metadata": {},
            "timestamp": time.time(),
            "cube_id": "test-cube",
        }
        state_manager.add_memos_record(record)

    assert len(state_manager.get_pending_memos_records()) == 2

    # Clear all
    count = state_manager.clear_pending_memos(only_synced=False)
    assert count == 2
    assert len(state_manager.get_pending_memos_records()) == 0


def test_clear_pending_memos_only_synced(state_manager):
    """Test clearing only synced MemOS records"""
    # Set up pending state
    state_manager.set_pending(
        layers={"memo"},
        reason="Test",
        triggered_by="abc",
        files=[],
        commit_message="test",
    )

    # Add records, some synced, some not
    for i in range(4):
        record = {
            "content": f"Record {i}",
            "record_type": "general",
            "project": "test",
            "commit_hash": f"commit{i}",
            "commit_message": f"Message {i}",
            "files": [],
            "metadata": {},
            "timestamp": time.time(),
            "cube_id": "test-cube",
            "synced": i % 2 == 0,  # Even indices are synced
        }
        state_manager.add_memos_record(record)

    assert len(state_manager.get_pending_memos_records()) == 4

    # Clear only synced
    count = state_manager.clear_pending_memos(only_synced=True)
    assert count == 2  # 2 records were synced

    records = state_manager.get_pending_memos_records()
    assert len(records) == 2  # 2 unsynced remain


def test_mark_memos_record_synced(state_manager):
    """Test marking a MemOS record as synced"""
    # Set up pending state
    state_manager.set_pending(
        layers={"memo"},
        reason="Test",
        triggered_by="abc",
        files=[],
        commit_message="test",
    )

    # Add a record
    record = {
        "content": "Test",
        "record_type": "general",
        "project": "test",
        "commit_hash": "abc",
        "commit_message": "test",
        "files": [],
        "metadata": {},
        "timestamp": time.time(),
        "cube_id": "test-cube",
    }
    state_manager.add_memos_record(record)

    # Mark as synced
    result = state_manager.mark_memos_record_synced(0)
    assert result is True

    # Verify it's marked
    records = state_manager.get_pending_memos_records()
    assert records[0].get("synced", False) is True


def test_mark_memos_record_synced_invalid_index(state_manager):
    """Test marking an invalid record index as synced"""
    # Set up pending state
    state_manager.set_pending(
        layers={"memo"},
        reason="Test",
        triggered_by="abc",
        files=[],
        commit_message="test",
    )

    result = state_manager.mark_memos_record_synced(99)
    assert result is False


def test_pending_update_with_memos_records_backward_compat():
    """Test PendingUpdate backward compatibility with memos_records"""
    # Old format without memos_records
    old_data = {
        "layers": ["traditional"],
        "reason": "Test",
        "triggered_by": "abc",
        "timestamp": time.time(),
        "files": ["test.py"],
        "commit_message": "test",
    }

    pending = PendingUpdate.from_dict(old_data)

    assert pending.layers == {"traditional"}
    assert pending.memos_records == []  # Should default to empty list

    # New format with memos_records
    new_data = {
        "layers": ["memo"],
        "reason": "Test",
        "triggered_by": "abc",
        "timestamp": time.time(),
        "files": ["test.py"],
        "commit_message": "test",
        "memos_records": [
            {
                "content": "Test",
                "record_type": "general",
                "project": "test",
                "commit_hash": "abc",
                "commit_message": "test",
                "files": [],
                "metadata": {},
                "timestamp": time.time(),
                "cube_id": "test-cube",
            }
        ],
    }

    pending = PendingUpdate.from_dict(new_data)
    assert len(pending.memos_records) == 1
    assert pending.memos_records[0]["record_type"] == "general"
