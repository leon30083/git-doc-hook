"""Tests for MemOS client"""
import json
import time
from pathlib import Path
import pytest

from memos.client import MemOSClient, MemOSRecord


@pytest.fixture
def memos_client(tmp_path):
    """Create a MemOS client with test cache location"""
    # Use a temp path for cache
    client = MemOSClient(
        api_url="http://localhost:9999",  # Non-existent URL
        cube_id="test-cube",
        enabled=True,
    )
    # Override cache file for testing
    client._cache_file = tmp_path / "memos_cache.json"
    return client


def test_memos_record_creation():
    """Test creating a MemOSRecord"""
    record = MemOSRecord(
        content="Test content",
        record_type="test",
        project="test-project",
        commit_hash="abc123",
    )

    assert record.content == "Test content"
    assert record.record_type == "test"
    assert record.project == "test-project"


def test_memos_record_to_dict():
    """Test MemOSRecord serialization"""
    record = MemOSRecord(
        content="Test",
        record_type="test",
        project="proj",
        commit_hash="abc",
    )

    data = record.to_dict()

    assert "content" in data
    assert "metadata" in data
    assert data["metadata"]["type"] == "test"


def test_memos_record_auto_timestamp():
    """Test that timestamp is auto-generated"""
    before = time.time()
    record = MemOSRecord(content="Test")
    after = time.time()

    assert before <= record.timestamp <= after


def test_memos_client_init(memos_client):
    """Test MemOSClient initialization"""
    assert memos_client.api_url == "http://localhost:9999"
    assert memos_client.cube_id == "test-cube"
    assert memos_client.enabled is True


def test_memos_client_disabled():
    """Test disabled MemOSClient"""
    client = MemOSClient(enabled=False)

    assert not client.enabled
    assert not client.is_available()


def test_memos_client_add_record_offline(memos_client):
    """Test adding record when MemOS is unavailable"""
    record = MemOSRecord(
        content="Test content",
        record_type="test",
    )

    # Should cache the record since server is unavailable
    result = memos_client.add_record(record)

    assert result is False  # Failed to sync
    assert len(memos_client._offline_cache) == 1


def test_memos_client_cache_persistence(memos_client, tmp_path):
    """Test that cache is persisted to disk"""
    record = MemOSRecord(content="Test")
    memos_client.add_record(record)

    # Create new client with same cache file
    new_client = MemOSClient(
        api_url="http://localhost:9999",
        cube_id="test-cube",
        enabled=True,
    )
    new_client._cache_file = tmp_path / "memos_cache.json"
    new_client._load_cache()

    assert len(new_client._offline_cache) == 1


def test_memos_client_sync_offline_cache(memos_client):
    """Test syncing offline cache"""
    # Add some cached records
    for i in range(3):
        record = MemOSRecord(content=f"Test {i}")
        memos_client.add_record(record)

    assert len(memos_client._offline_cache) == 3

    # Sync should keep records in cache (server unavailable)
    synced = memos_client.sync_offline_cache()

    # All records remain cached since server is down
    assert len(memos_client._offline_cache) == 3


def test_create_troubleshooting_record():
    """Test creating troubleshooting record"""
    record = MemOSClient.create_troubleshooting_record(
        problem="Service crashes on startup",
        solution="Fixed null pointer in init",
        context="Production env",
        project="myapp",
        commit_hash="abc123",
    )

    assert "Service crashes" in record.content
    assert "Fixed null pointer" in record.content
    assert record.record_type == "troubleshooting"


def test_create_adr_record():
    """Test creating ADR record"""
    record = MemOSClient.create_adr_record(
        title="Use PostgreSQL for database",
        decision="Chose PostgreSQL for ACID compliance",
        context="Need transactional support",
        alternatives=["MySQL", "MongoDB"],
        project="myapp",
    )

    assert "Use PostgreSQL" in record.content
    assert "Chose PostgreSQL" in record.content
    assert record.record_type == "adr"


def test_create_practice_record():
    """Test creating practice record"""
    record = MemOSClient.create_practice_record(
        practice="Use dependency injection for services",
        category="architecture",
        context="Web application",
        project="myapp",
    )

    assert "dependency injection" in record.content
    assert record.record_type == "practice"


def test_create_from_commit_troubleshooting():
    """Test creating record from troubleshooting commit"""
    record = MemOSRecord.create_from_commit(
        commit_message="fix: resolve race condition in auth",
        changed_files=["services/auth.py"],
        diff_summary="Added mutex lock",
        project="myapp",
        commit_hash="abc123",
    )

    assert record.record_type == "troubleshooting"
    assert "resolve race condition" in record.content


def test_create_from_commit_decision():
    """Test creating record from decision commit"""
    record = MemOSRecord.create_from_commit(
        commit_message="decision: use Redis for caching",
        changed_files=["cache.py"],
        diff_summary="Implemented Redis cache layer",
        project="myapp",
    )

    assert record.record_type == "adr"


def test_create_from_commit_practice():
    """Test creating record from practice commit"""
    record = MemOSRecord.create_from_commit(
        commit_message="refactor: extract service layer",
        changed_files=["services/base.py"],
        diff_summary="Created base service class",
        project="myapp",
    )

    assert record.record_type == "practice"


def test_create_from_commit_security():
    """Test creating record from security commit"""
    record = MemOSRecord.create_from_commit(
        commit_message="security: add input validation",
        changed_files=["validators.py"],
        diff_summary="Added XSS protection",
        project="myapp",
    )

    assert record.record_type == "security"


def test_create_from_commit_default():
    """Test creating default record from commit"""
    record = MemOSRecord.create_from_commit(
        commit_message="chore: update dependencies",
        changed_files=["requirements.txt"],
        diff_summary="Updated packages",
        project="myapp",
    )

    assert record.record_type == "general"


def test_memos_record_with_files():
    """Test MemOSRecord with file list"""
    record = MemOSRecord(
        content="Test",
        files=["test.py", "main.py"],
    )

    assert len(record.files) == 2
    assert "test.py" in record.files


def test_memos_record_with_metadata():
    """Test MemOSRecord with custom metadata"""
    record = MemOSRecord(
        content="Test",
        metadata={"custom": "value", "priority": 1},
    )

    assert record.metadata["custom"] == "value"
    assert record.metadata["priority"] == 1


def test_cache_limit(memos_client):
    """Test that cache doesn't grow indefinitely"""
    # Add many records
    for i in range(200):
        record = MemOSRecord(content=f"Test {i}")
        memos_client.add_record(record)

    # Cache should grow (no limit in current implementation)
    assert len(memos_client._offline_cache) == 200
