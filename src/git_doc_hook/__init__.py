"""Git-Doc-Hook: Universal Git documentation auto-update tool"""

__version__ = "0.1.0"

# Import core modules for easier access
from git_doc_hook.core.config import Config
from git_doc_hook.core.git import GitManager
from git_doc_hook.core.state import StateManager

__all__ = [
    "Config",
    "GitManager",
    "StateManager",
]
