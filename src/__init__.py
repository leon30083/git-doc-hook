"""Git-Doc-Hook: Universal Git documentation auto-update tool"""

__version__ = "0.1.0"

# Import core modules for easier access
from core.config import Config
from core.git import GitManager
from core.state import StateManager

__all__ = [
    "Config",
    "GitManager",
    "StateManager",
]
