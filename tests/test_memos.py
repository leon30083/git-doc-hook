"""Tests for MemOS record models"""
import time
import pytest

from git_doc_hook.memos.client import MemOSRecord


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
    assert data["record_type"] == "test"
    assert data["project"] == "proj"


def test_memos_record_auto_timestamp():
    """Test that timestamp is auto-generated"""
    before = time.time()
    record = MemOSRecord(content="Test")
    after = time.time()

    assert before <= record.timestamp <= after


def test_create_troubleshooting_record():
    """Test creating troubleshooting record"""
    record = MemOSRecord.create_troubleshooting_record(
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
    record = MemOSRecord.create_adr_record(
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
    record = MemOSRecord.create_practice_record(
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


def test_memos_record_cube_id():
    """Test MemOSRecord cube_id"""
    record = MemOSRecord(
        content="Test",
        cube_id="test-cube",
    )

    assert record.cube_id == "test-cube"
    data = record.to_dict()
    assert data["cube_id"] == "test-cube"
