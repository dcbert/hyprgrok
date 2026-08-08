"""Process runtime markers for the panel server (pid/port)."""

from __future__ import annotations

import os
import socket

from hyprgrok.config import PID_PATH, PORT_PATH, ensure_dirs


def write_runtime_files(port: int) -> None:
    ensure_dirs()
    PID_PATH.write_text(str(os.getpid()), encoding="utf-8")
    PORT_PATH.write_text(str(port), encoding="utf-8")


def clear_runtime_files() -> None:
    for path in (PID_PATH, PORT_PATH):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def read_running_port() -> int | None:
    if not PORT_PATH.is_file():
        return None
    try:
        return int(PORT_PATH.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def is_server_alive(port: int | None = None) -> bool:
    port = port or read_running_port()
    if not port:
        return False
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.4):
            return True
    except OSError:
        return False
