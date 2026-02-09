"""
Bridge Server

JSON-RPC server for Tauri-Python communication.
High-performance async server optimized for real-time ML operations.
"""

import json
import logging
import signal
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .handlers import CommandHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("bridge")


@dataclass
class RPCRequest:
    """JSON-RPC 2.0 Request."""

    jsonrpc: str
    method: str
    params: Dict[str, Any]
    id: Optional[int] = None


@dataclass
class RPCResponse:
    """JSON-RPC 2.0 Response."""

    jsonrpc: str = "2.0"
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[int] = None

    def to_json(self) -> str:
        data = {"jsonrpc": self.jsonrpc, "id": self.id}
        if self.error:
            data["error"] = self.error
        else:
            data["result"] = self.result
        return json.dumps(data)


class EventEmitter:
    """
    Event emitter for sending real-time updates to Tauri.

    Events are written to stdout with a special prefix for parsing.
    """

    EVENT_PREFIX = "@@EVENT@@"

    def __init__(self):
        self._lock = threading.Lock()

    def emit(self, event_type: str, data: Any):
        """Emit an event to Tauri."""
        event = {
            "type": event_type,
            "data": data,
        }
        with self._lock:
            # Use special prefix so Rust can distinguish events from responses
            print(f"{self.EVENT_PREFIX}{json.dumps(event)}", flush=True)


class BridgeServer:
    """
    High-performance bridge server for Tauri-Python IPC.

    Features:
    - Async command handling
    - Thread pool for CPU-bound ML operations
    - Real-time event emission
    - Graceful shutdown
    """

    def __init__(self, max_workers: int = 4):
        self.handler = CommandHandler()
        self.events = EventEmitter()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.running = False
        self._shutdown_event = threading.Event()

        # Register event emitter with handler
        self.handler.set_event_emitter(self.events)

    def parse_request(self, line: str) -> Optional[RPCRequest]:
        """Parse a JSON-RPC request from input line."""
        try:
            data = json.loads(line.strip())
            return RPCRequest(
                jsonrpc=data.get("jsonrpc", "2.0"),
                method=data["method"],
                params=data.get("params", {}),
                id=data.get("id"),
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse request: {e}")
            return None

    def handle_request(self, request: RPCRequest) -> RPCResponse:
        """Handle a single RPC request."""
        try:
            # Get handler method
            method_name = f"handle_{request.method.replace('.', '_')}"
            handler_func = getattr(self.handler, method_name, None)

            if handler_func is None:
                return RPCResponse(
                    error={"code": -32601, "message": f"Method not found: {request.method}"},
                    id=request.id,
                )

            # Execute handler
            result = handler_func(**request.params)

            return RPCResponse(result=result, id=request.id)

        except Exception as e:
            logger.exception(f"Error handling {request.method}")
            return RPCResponse(
                error={"code": -32000, "message": str(e)},
                id=request.id,
            )

    def run(self):
        """Run the bridge server (blocking)."""
        self.running = True
        logger.info("Bridge server started")

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        try:
            while self.running and not self._shutdown_event.is_set():
                try:
                    # Read line from stdin (blocking with timeout)
                    line = sys.stdin.readline()

                    if not line:
                        # EOF - parent process closed pipe
                        logger.info("EOF received, shutting down")
                        break

                    line = line.strip()
                    if not line:
                        continue

                    # Parse and handle request
                    request = self.parse_request(line)
                    if request is None:
                        continue

                    # Handle in thread pool for CPU-bound operations
                    future = self.executor.submit(self.handle_request, request)
                    response = future.result(timeout=300)  # 5 min timeout

                    # Send response to stdout
                    print(response.to_json(), flush=True)

                except Exception as e:
                    logger.exception(f"Error in main loop: {e}")

        finally:
            self.shutdown()

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down")
        self.running = False
        self._shutdown_event.set()

    def shutdown(self):
        """Clean shutdown of the server."""
        logger.info("Shutting down bridge server")
        self.running = False
        self._shutdown_event.set()

        # Cleanup handler resources
        self.handler.cleanup()

        # Shutdown thread pool
        self.executor.shutdown(wait=True, cancel_futures=True)

        logger.info("Bridge server stopped")


def run_server():
    """Entry point for bridge server."""
    server = BridgeServer()
    server.run()


if __name__ == "__main__":
    run_server()
