"""
Python Bridge Module

Provides JSON-RPC communication between Tauri (Rust) and Python ML backend.
"""

from .handlers import CommandHandler
from .server import BridgeServer, run_server

__all__ = ["BridgeServer", "run_server", "CommandHandler"]
