"""State management for git-doc-hook

Manages pending update state with multi-project isolation.
"""
import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from .config import Config


@dataclass
class PendingUpdate:
    """Represents a pending documentation update"""

    layers: Set[str]
    reason: str
    triggered_by: str  # commit hash or "manual"
    timestamp: float
    files: List[str]
    commit_message: str

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "layers": list(self.layers),
            "reason": self.reason,
            "triggered_by": self.triggered_by,
            "timestamp": self.timestamp,
            "files": self.files,
            "commit_message": self.commit_message,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "PendingUpdate":
        """Create from dictionary"""
        return cls(
            layers=set(data.get("layers", [])),
            reason=data.get("reason", ""),
            triggered_by=data.get("triggered_by", ""),
            timestamp=data.get("timestamp", time.time()),
            files=data.get("files", []),
            commit_message=data.get("commit_message", ""),
        )


class StateManager:
    """Manages pending update state for git-doc-hook

    Provides persistent storage of pending documentation updates
    with multi-project isolation support.
    """

    STATE_FILE = "pending.json"

    def __init__(self, project_path: str = ".", config: Optional[Config] = None):
        """Initialize state manager

        Args:
            project_path: Path to project root
            config: Optional Config instance
        """
        self.project_path = Path(project_path).resolve()
        self.config = config or Config(project_path)
        self.state_dir = self.config.state_dir
        self.state_file = self.state_dir / self.STATE_FILE

        # Ensure state directory exists
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _load_state(self) -> Dict:
        """Load state from file

        Returns:
            State dictionary
        """
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text())
            except (json.JSONDecodeError, IOError):
                pass
        return {"pending": None, "history": []}

    def _save_state(self, state: Dict) -> None:
        """Save state to file

        Args:
            state: State dictionary to save
        """
        self.state_file.write_text(json.dumps(state, indent=2))

    def set_pending(
        self,
        layers: Set[str],
        reason: str,
        triggered_by: str,
        files: List[str],
        commit_message: str,
    ) -> None:
        """Set a pending update

        Args:
            layers: Set of layer names that need updating
            reason: Human-readable reason for the update
            triggered_by: Commit hash or "manual"
            files: List of changed files
            commit_message: Associated commit message
        """
        state = self._load_state()

        pending = PendingUpdate(
            layers=layers,
            reason=reason,
            triggered_by=triggered_by,
            timestamp=time.time(),
            files=files,
            commit_message=commit_message,
        )

        state["pending"] = pending.to_dict()
        self._save_state(state)

    def get_pending(self) -> Optional[PendingUpdate]:
        """Get current pending update

        Returns:
            PendingUpdate or None if no pending update
        """
        state = self._load_state()
        pending_data = state.get("pending")
        if pending_data:
            return PendingUpdate.from_dict(pending_data)
        return None

    def clear_pending(self) -> None:
        """Clear pending update state"""
        state = self._load_state()

        # Move current pending to history
        if state.get("pending"):
            state["history"].insert(0, {
                **state["pending"],
                "completed_at": time.time(),
            })
            # Keep only last 100 history entries
            state["history"] = state["history"][:100]

        state["pending"] = None
        self._save_state(state)

    def is_pending(self) -> bool:
        """Check if there's a pending update

        Returns:
            True if there's a pending update
        """
        return self.get_pending() is not None

    def get_pending_layers(self) -> Set[str]:
        """Get layers with pending updates

        Returns:
            Set of layer names
        """
        pending = self.get_pending()
        if pending:
            return pending.layers
        return set()

    def show_summary(self) -> str:
        """Get a human-readable summary of pending state

        Returns:
            Summary string
        """
        pending = self.get_pending()
        if not pending:
            return "No pending updates"

        timestamp = datetime.fromtimestamp(pending.timestamp).strftime("%Y-%m-%d %H:%M:%S")

        lines = [
            f"Pending Update (since {timestamp}):",
            f"  Layers: {', '.join(sorted(pending.layers))}",
            f"  Reason: {pending.reason}",
            f"  Triggered by: {pending.triggered_by}",
            f"  Files: {len(pending.files)}",
        ]

        if pending.commit_message:
            lines.append(f"  Commit: {pending.commit_message[:60]}...")

        return "\n".join(lines)

    def get_history(self, limit: int = 10) -> List[Dict]:
        """Get recent update history

        Args:
            limit: Maximum number of history entries

        Returns:
            List of history entries
        """
        state = self._load_state()
        return state.get("history", [])[:limit]

    def add_to_history(
        self,
        layers: Set[str],
        action: str,
        details: Optional[Dict] = None,
    ) -> None:
        """Add entry to history without clearing pending

        Args:
            layers: Layers affected
            action: Action performed
            details: Optional additional details
        """
        state = self._load_state()

        entry = {
            "layers": list(layers),
            "action": action,
            "timestamp": time.time(),
            "details": details or {},
        }

        state["history"].insert(0, entry)
        state["history"] = state["history"][:100]

        self._save_state(state)

    def get_project_state_dir(self) -> Path:
        """Get the state directory for this project

        Returns:
            Path to state directory
        """
        return self.state_dir

    def cleanup(self) -> None:
        """Clean up state files for this project"""
        if self.state_file.exists():
            self.state_file.unlink()

    @classmethod
    def list_all_projects(cls, base_dir: Optional[Path] = None) -> List[Dict]:
        """List all projects with pending updates

        Args:
            base_dir: Base state directory (defaults to ~/.git-doc-hook)

        Returns:
            List of project info dictionaries
        """
        if base_dir is None:
            base_dir = Path("~/.git-doc-hook").expanduser()

        projects = []

        if not base_dir.exists():
            return projects

        for project_dir in base_dir.iterdir():
            if not project_dir.is_dir():
                continue

            state_file = project_dir / cls.STATE_FILE
            if state_file.exists():
                try:
                    state = json.loads(state_file.read_text())
                    if state.get("pending"):
                        pending = state["pending"]
                        projects.append({
                            "name": project_dir.name,
                            "path": str(project_dir),
                            "pending": pending,
                        })
                except (json.JSONDecodeError, IOError):
                    pass

        return projects
