"""MemOS MCP client for git-doc-hook

Handles synchronization of documentation records to MemOS via MCP protocol
with graceful offline fallback.
"""
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MemOSRecord:
    """A record to be stored in MemOS

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
        """Convert to dictionary for API

        Returns:
            Dictionary representation
        """
        return {
            "content": self.content,
            "metadata": {
                "type": self.record_type,
                "project": self.project,
                "commit": self.commit_hash,
                "commit_message": self.commit_message,
                "files": self.files,
                "timestamp": self.timestamp,
                **self.metadata,
            },
        }


class MemOSClient:
    """Client for interacting with MemOS via MCP protocol

    Provides methods to sync documentation records to MemOS
    with offline support when MCP is unavailable.
    """

    # Default configuration from MCP server
    DEFAULT_USER_ID = "local-user"
    DEFAULT_CUBE_ID = "default-cube"

    def __init__(
        self,
        api_url: str = None,  # Kept for compatibility, unused in MCP mode
        cube_id: str = "git-doc-hook",
        timeout: float = 5.0,  # Kept for compatibility, unused in MCP mode
        enabled: bool = True,
        user_id: str = None,
    ):
        """Initialize MemOS client

        Args:
            api_url: Kept for compatibility, unused in MCP mode
            cube_id: Cube ID for storing records
            timeout: Kept for compatibility, unused in MCP mode
            enabled: Whether MemOS sync is enabled
            user_id: User ID for memos-local (defaults to local-user)
        """
        self.cube_id = cube_id
        self.enabled = enabled
        self.user_id = user_id or os.environ.get("MEMOS_DEFAULT_USER_ID", self.DEFAULT_USER_ID)
        self._offline_cache: List[MemOSRecord] = []
        self._cache_file = Path.home() / ".git-doc-hook" / "memos_cache.json"

        # Detect if MCP is available
        self._mcp_available = self._detect_mcp_available()

        # Load offline cache
        self._load_cache()

        if self._mcp_available:
            logger.info("MemOS MCP tool detected, will use MCP protocol")
        elif self.enabled:
            logger.info("MCP not available, using offline cache only")

    def _detect_mcp_available(self) -> bool:
        """Detect if MCP memos-local tool is available

        Returns:
            True if MCP tool functions are available in the current environment
        """
        if not self.enabled:
            return False

        try:
            # Check if MCP tool functions are in global scope
            import inspect
            frame = inspect.currentframe()

            while frame:
                frame_locals = frame.f_locals
                # Look for memos-local MCP tools (try different naming)
                if any(key in frame_locals for key in [
                    "mcp__memos_local__add_message",
                    "mcp__memos-local__add_message",
                ]):
                    logger.debug("Found memos-local MCP tools in call stack")
                    return True
                frame = frame.f_back

            return False

        except Exception:
            return False

    def _mcp_add_message(self, record: MemOSRecord) -> bool:
        """Add message via MCP protocol

        Uses the mcp__memos-local__add_message tool from the MCP server.

        Args:
            record: Record to add

        Returns:
            True if successful
        """
        try:
            import inspect

            # Build parameters matching MCP server's add_message format
            params = {
                "messages": [
                    {
                        "role": "user",
                        "content": record.content,
                    }
                ],
                "cube_id": self.cube_id,
                "async_mode": "sync",
            }

            # Try to find and call the MCP tool
            frame = inspect.currentframe()
            while frame:
                frame_locals = frame.f_locals

                # Try different naming conventions
                for tool_name in [
                    "mcp__memos_local__add_message",
                    "mcp__memos-local__add_message",
                ]:
                    if tool_name in frame_locals and callable(frame_locals[tool_name]):
                        result = frame_locals[tool_name](**params)
                        # MCP tools typically return success or throw exceptions
                        logger.debug(f"MCP add_message result: {result}")
                        return True

                frame = frame.f_back

            logger.debug("MCP tool not found in call stack")
            return False

        except Exception as e:
            logger.debug(f"MCP add_message failed: {e}")
            return False

    def _load_cache(self) -> None:
        """Load offline cache from disk"""
        if self._cache_file.exists():
            try:
                data = json.loads(self._cache_file.read_text())
                self._offline_cache = [MemOSRecord(**r) for r in data]
            except (json.JSONDecodeError, TypeError):
                self._offline_cache = []

    def _save_cache(self) -> None:
        """Save offline cache to disk"""
        self._cache_file.parent.mkdir(parents=True, exist_ok=True)
        data = [r.__dict__ for r in self._offline_cache]
        self._cache_file.write_text(json.dumps(data, indent=2))

    @property
    def api_url(self) -> str:
        """Property for backward compatibility with tests"""
        return "http://localhost:8000"  # Placeholder, not used in MCP mode

    def is_available(self) -> bool:
        """Check if MemOS is available

        Returns:
            True if MCP tool is available
        """
        if not self.enabled:
            return False
        return self._mcp_available

    def add_record(self, record: MemOSRecord) -> bool:
        """Add a record to MemOS via MCP protocol

        Args:
            record: Record to add

        Returns:
            True if synced successfully, False if cached offline
        """
        if not self.enabled:
            return False

        # Attach cube_id to record
        record.cube_id = self.cube_id

        # Try MCP
        if self._mcp_available:
            if self._mcp_add_message(record):
                logger.info(f"Record synced via MCP: {self.cube_id}")
                return True
            else:
                logger.debug("MCP sync failed")

        # Offline: add to cache
        self._offline_cache.append(record)
        self._save_cache()
        logger.info(f"Record cached offline (count: {len(self._offline_cache)})")
        return False

    def sync_offline_cache(self) -> int:
        """Sync offline cached records to MemOS

        Returns:
            Number of records successfully synced
        """
        if not self._offline_cache:
            return 0

        if not self._mcp_available:
            logger.debug(f"MCP not available, {len(self._offline_cache)} records remain cached")
            return 0

        synced = 0
        remaining = []

        for record in self._offline_cache:
            record.cube_id = self.cube_id
            if self._mcp_add_message(record):
                synced += 1
            else:
                remaining.append(record)

        self._offline_cache = remaining
        self._save_cache()

        if synced > 0:
            logger.info(f"Synced {synced} cached records to MemOS via MCP")

        return synced

    def get_stats(self) -> Optional[Dict]:
        """Get MemOS statistics

        Returns:
            Statistics dict or None
        """
        if not self.enabled or not self._mcp_available:
            return None

        try:
            import inspect
            frame = inspect.currentframe()

            while frame:
                frame_locals = frame.f_locals

                # Try get_memory_stats tool
                for tool_name in [
                    "mcp__memos_local__get_memory_stats",
                    "mcp__memos-local__get_memory_stats",
                ]:
                    if tool_name in frame_locals and callable(frame_locals[tool_name]):
                        return frame_locals[tool_name](
                            user_id=self.user_id,
                            cube_id=self.cube_id,
                        )

                frame = frame.f_back

        except Exception:
            pass

        return None

    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """Search MemOS for records

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching records
        """
        if not self.enabled or not self._mcp_available:
            return []

        try:
            import inspect
            frame = inspect.currentframe()

            while frame:
                frame_locals = frame.f_locals

                for tool_name in [
                    "mcp__memos_local__search_memory",
                    "mcp__memos-local__search_memory",
                ]:
                    if tool_name in frame_locals and callable(frame_locals[tool_name]):
                        result = frame_locals[tool_name](
                            query=query,
                            limit=limit,
                            user_id=self.user_id,
                            cube_id=self.cube_id,
                        )
                        if result and isinstance(result, dict):
                            data = result.get("data", {})
                            return data.get("text_mem", [])

                frame = frame.f_back

        except Exception:
            pass

        return []

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

        return MemOSRecord(
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

        return MemOSRecord(
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

        return MemOSRecord(
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
            return MemOSRecord(
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
        return MemOSRecord(
            content=content,
            record_type="general",
            project=project,
            commit_hash=commit_hash,
            files=changed_files,
        )
