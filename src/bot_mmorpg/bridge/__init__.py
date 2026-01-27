"""
Python Bridge Module

Provides JSON-RPC communication between Tauri (Rust) and Python ML backend.
"""

from .server import BridgeServer, run_server
from .handlers import CommandHandler

__all__ = ["BridgeServer", "run_server", "CommandHandler"]
