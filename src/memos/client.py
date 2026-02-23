"""MemOS API client for git-doc-hook

Handles synchronization of documentation records to MemOS
with graceful offline fallback.
"""
import json
import logging
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
    """

    content: str
    record_type: str = "general"
    project: str = ""
    commit_hash: str = ""
    commit_message: str = ""
    files: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0

    def __post_init__(self):
        if self.timestamp == 0:
            self.timestamp = datetime.now().timestamp()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API"""
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
    """Client for interacting with MemOS API

    Provides methods to sync documentation records to MemOS
    with offline support when MemOS is unavailable.
    """

    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        cube_id: str = "git-doc-hook",
        timeout: float = 5.0,
        enabled: bool = True,
    ):
        """Initialize MemOS client

        Args:
            api_url: Base URL for MemOS API
            cube_id: Cube ID for storing records
            timeout: Request timeout in seconds
            enabled: Whether MemOS sync is enabled
        """
        self.api_url = api_url.rstrip("/")
        self.cube_id = cube_id
        self.timeout = timeout
        self.enabled = enabled
        self._offline_cache: List[MemOSRecord] = []
        self._cache_file = Path.home() / ".git-doc-hook" / "memos_cache.json"

        # Load offline cache
        self._load_cache()

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

    def _make_request(
        self, endpoint: str, method: str = "GET", data: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Make HTTP request to MemOS API

        Args:
            endpoint: API endpoint path
            method: HTTP method
            data: Request body data

        Returns:
            Response data or None if request failed
        """
        if not self.enabled:
            return None

        try:
            import requests

            url = f"{self.api_url}{endpoint}"
            headers = {"Content-Type": "application/json"}

            if method == "GET":
                response = requests.get(url, timeout=self.timeout, headers=headers)
            elif method == "POST":
                response = requests.post(
                    url, json=data, timeout=self.timeout, headers=headers
                )
            elif method == "DELETE":
                response = requests.delete(url, timeout=self.timeout, headers=headers)
            else:
                return None

            if response.ok:
                return response.json()

            logger.warning(f"MemOS API error: {response.status_code}")
            return None

        except ImportError:
            logger.warning("requests library not available")
            return None
        except Exception as e:
            logger.debug(f"MemOS request failed: {e}")
            return None

    def is_available(self) -> bool:
        """Check if MemOS API is available

        Returns:
            True if MemOS is responding
        """
        if not self.enabled:
            return False

        result = self._make_request("/api/status", "GET")
        return result is not None

    def add_record(self, record: MemOSRecord) -> bool:
        """Add a record to MemOS

        Args:
            record: Record to add

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False

        # Try to sync
        result = self._make_request(
            "/api/memos",
            "POST",
            {
                "messages": [
                    {
                        "role": "user",
                        "content": record.content,
                    }
                ],
                "cube_id": self.cube_id,
            },
        )

        if result is not None:
            return True

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

        synced = 0
        remaining = []

        for record in self._offline_cache:
            if self.add_record(record):
                synced += 1
            else:
                remaining.append(record)

        self._offline_cache = remaining
        self._save_cache()

        return synced

    def get_stats(self) -> Optional[Dict]:
        """Get MemOS statistics

        Returns:
            Statistics dict or None
        """
        if not self.enabled:
            return None

        return self._make_request(f"/api/memos/stats?cube_id={self.cube_id}", "GET")

    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """Search MemOS for records

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching records
        """
        if not self.enabled:
            return []

        result = self._make_request(
            f"/api/memos/search?query={query}&limit={limit}&cube_id={self.cube_id}",
            "GET",
        )

        if result:
            return result.get("results", [])
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
