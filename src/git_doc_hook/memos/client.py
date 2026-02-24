"""MemOS record models for git-doc-hook

Provides data classes and factory methods for creating MemOS records.
Records are written to state files for Claude Code to consume via MCP.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class MemOSRecord:
    """A record to be stored in MemOS

    This is a data model only. Records are written to state files
    and synced by Claude Code using MCP tools.

    Attributes:
        content: The main content of the record
        record_type: Type of record (troubleshooting, adr, practice, security)
        project: Project name
        commit_hash: Associated commit hash
        commit_message: Associated commit message
        files: List of related files
        metadata: Additional metadata
        timestamp: Record timestamp
        cube_id: MemOS cube ID for the record
    """

    content: str
    record_type: str = "general"
    project: str = ""
    commit_hash: str = ""
    commit_message: str = ""
    files: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0
    cube_id: str = "git-doc-hook"

    def __post_init__(self):
        if self.timestamp == 0:
            self.timestamp = datetime.now().timestamp()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for state file storage

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return {
            "content": self.content,
            "record_type": self.record_type,
            "project": self.project,
            "commit_hash": self.commit_hash,
            "commit_message": self.commit_message,
            "files": self.files,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "cube_id": self.cube_id,
        }

    @classmethod
    def create_troubleshooting_record(
        cls,
        problem: str,
        solution: str,
        context: str = "",
        project: str = "",
        commit_hash: str = "",
        files: List[str] = None,
    ) -> "MemOSRecord":
        """Create a troubleshooting record

        Args:
            problem: Problem description
            solution: Solution applied
            context: Additional context
            project: Project name
            commit_hash: Associated commit
            files: Related files

        Returns:
            MemOSRecord object
        """
        content = f"""# Troubleshooting Record

## Problem
{problem}

## Solution
{solution}
"""

        if context:
            content += f"\n## Context\n{context}\n"

        return cls(
            content=content,
            record_type="troubleshooting",
            project=project,
            commit_hash=commit_hash,
            files=files or [],
            metadata={"category": "troubleshooting"},
        )

    @classmethod
    def create_adr_record(
        cls,
        title: str,
        decision: str,
        context: str = "",
        alternatives: List[str] = None,
        project: str = "",
        commit_hash: str = "",
    ) -> "MemOSRecord":
        """Create an Architecture Decision Record

        Args:
            title: Decision title
            decision: Decision description
            context: Context for the decision
            alternatives: Alternative options considered
            project: Project name
            commit_hash: Associated commit

        Returns:
            MemOSRecord object
        """
        content = f"""# ADR: {title}

## Decision
{decision}

## Context
{context}
"""

        if alternatives:
            content += "\n## Alternatives Considered\n"
            for i, alt in enumerate(alternatives, 1):
                content += f"{i}. {alt}\n"

        return cls(
            content=content,
            record_type="adr",
            project=project,
            commit_hash=commit_hash,
            metadata={"category": "adr", "title": title},
        )

    @classmethod
    def create_practice_record(
        cls,
        practice: str,
        category: str = "general",
        context: str = "",
        project: str = "",
        commit_hash: str = "",
        files: List[str] = None,
    ) -> "MemOSRecord":
        """Create a best practice record

        Args:
            practice: Practice description
            category: Practice category
            context: Additional context
            project: Project name
            commit_hash: Associated commit
            files: Related files

        Returns:
            MemOSRecord object
        """
        content = f"""# Best Practice: {category}

## Practice
{practice}
"""

        if context:
            content += f"\n## Context\n{context}\n"

        return cls(
            content=content,
            record_type="practice",
            project=project,
            commit_hash=commit_hash,
            files=files or [],
            metadata={"category": "practice", "subcategory": category},
        )

    @classmethod
    def create_from_commit(
        cls,
        commit_message: str,
        changed_files: List[str],
        diff_summary: str = "",
        project: str = "",
        commit_hash: str = "",
    ) -> "MemOSRecord":
        """Create a record from a commit

        Detects type based on commit message keywords.

        Args:
            commit_message: Commit message
            changed_files: List of changed files
            diff_summary: Summary of changes
            project: Project name
            commit_hash: Commit hash

        Returns:
            MemOSRecord object
        """
        msg_lower = commit_message.lower()

        # Troubleshooting
        if any(kw in msg_lower for kw in ["fix", "bug", "error", "issue"]):
            return cls.create_troubleshooting_record(
                problem=f"Issue fixed in: {commit_message}",
                solution=diff_summary or "See commit for details",
                context=f"Files: {', '.join(changed_files)}",
                project=project,
                commit_hash=commit_hash,
                files=changed_files,
            )

        # ADR
        if any(kw in msg_lower for kw in ["decision", "decide", "选型", "architecture"]):
            return cls.create_adr_record(
                title=commit_message,
                decision=diff_summary or "See commit for details",
                context=f"Files affected: {', '.join(changed_files)}",
                project=project,
                commit_hash=commit_hash,
            )

        # Best practice
        if any(kw in msg_lower for kw in ["refactor", "optimize", "improve", "better"]):
            return cls.create_practice_record(
                practice=diff_summary or commit_message,
                category="general",
                context=f"Files: {', '.join(changed_files)}",
                project=project,
                commit_hash=commit_hash,
                files=changed_files,
            )

        # Security
        if any(kw in msg_lower for kw in ["security", "auth", "vulnerability"]):
            content = f"""# Security Practice

{commit_message}

## Changes
{diff_summary or "See commit for details"}

## Files
{', '.join(changed_files)}
"""
            return cls(
                content=content,
                record_type="security",
                project=project,
                commit_hash=commit_hash,
                files=changed_files,
                metadata={"category": "security"},
            )

        # Default: general record
        content = f"""# Commit: {commit_message}

## Files Changed
{', '.join(changed_files)}

## Summary
{diff_summary or "No detailed summary available"}
"""
        return cls(
            content=content,
            record_type="general",
            project=project,
            commit_hash=commit_hash,
            files=changed_files,
        )


# Backward compatibility: alias for old MemOSClient class
# The class is now deprecated but kept for imports that may reference it
class MemOSClient:
    """Deprecated: Use MemOSRecord factory methods directly

    This class is kept for backward compatibility only.
    All methods are now class methods on MemOSRecord.
    """

    def __init__(self, *args, **kwargs):
        """This class is deprecated. Use MemOSRecord instead."""
        import warnings
        warnings.warn(
            "MemOSClient is deprecated. Use MemOSRecord factory methods directly.",
            DeprecationWarning,
            stacklevel=2
        )

    @classmethod
    def create_troubleshooting_record(cls, *args, **kwargs):
        """Delegate to MemOSRecord.create_troubleshooting_record"""
        return MemOSRecord.create_troubleshooting_record(*args, **kwargs)

    @classmethod
    def create_adr_record(cls, *args, **kwargs):
        """Delegate to MemOSRecord.create_adr_record"""
        return MemOSRecord.create_adr_record(*args, **kwargs)

    @classmethod
    def create_practice_record(cls, *args, **kwargs):
        """Delegate to MemOSRecord.create_practice_record"""
        return MemOSRecord.create_practice_record(*args, **kwargs)

    @classmethod
    def create_from_commit(cls, *args, **kwargs):
        """Delegate to MemOSRecord.create_from_commit"""
        return MemOSRecord.create_from_commit(*args, **kwargs)
