"""MemOS integration for git-doc-hook

Provides client for syncing documentation records to MemOS.
"""
from .client import MemOSClient, MemOSRecord

__all__ = ["MemOSClient", "MemOSRecord"]
