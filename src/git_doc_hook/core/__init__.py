"""Core modules for git-doc-hook"""

from .config import Config, glob_match
from .git import GitManager
from .state import StateManager

__all__ = ["Config", "GitManager", "StateManager", "glob_match"]
