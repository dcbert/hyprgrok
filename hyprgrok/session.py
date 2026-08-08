"""Session tracking for Grok Build processes started by HyprGrok."""

from __future__ import annotations

import json
import os
import signal
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from hyprgrok.config import STATE_DIR, ensure_dirs


SESSIONS_PATH = STATE_DIR / "sessions.json"
HISTORY_PATH = STATE_DIR / "prompt_history.json"


@dataclass
class SessionRecord:
    id: str
    kind: str  # headless | interactive
    created_at: float
    cwd: str
    prompt: str = ""
    pid: int | None = None
    status: str = "running"  # running | completed | failed | stopped
    response_preview: str = ""
    error: str = ""
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SessionManager:
    sessions: list[SessionRecord] = field(default_factory=list)
    max_history: int = 80

    def __post_init__(self) -> None:
        self.load()

    def load(self) -> None:
        ensure_dirs()
        if not SESSIONS_PATH.is_file():
            self.sessions = []
            return
        try:
            data = json.loads(SESSIONS_PATH.read_text(encoding="utf-8"))
            rows = []
            for item in data.get("sessions", []):
                if not isinstance(item, dict):
                    continue
                # Tolerate older records missing new fields
                allowed = set(SessionRecord.__dataclass_fields__.keys())
                filtered = {k: v for k, v in item.items() if k in allowed}
                try:
                    rows.append(SessionRecord(**filtered))
                except TypeError:
                    continue
            self.sessions = rows
        except (OSError, json.JSONDecodeError, TypeError):
            self.sessions = []

    def save(self) -> None:
        ensure_dirs()
        payload = {"sessions": [s.to_dict() for s in self.sessions[: self.max_history]]}
        SESSIONS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def add(
        self,
        *,
        kind: str,
        cwd: str,
        prompt: str = "",
        pid: int | None = None,
        status: str = "running",
        response_preview: str = "",
        error: str = "",
        label: str = "",
    ) -> SessionRecord:
        if not label:
            label = (prompt[:48] + "…") if len(prompt) > 48 else (prompt or kind)
        record = SessionRecord(
            id=str(uuid.uuid4()),
            kind=kind,
            created_at=time.time(),
            cwd=cwd,
            prompt=prompt,
            pid=pid,
            status=status,
            response_preview=response_preview[:800],
            error=error[:500],
            label=label[:80],
        )
        self.sessions.insert(0, record)
        self.sessions = self.sessions[: self.max_history]
        self.save()
        return record

    def get(self, session_id: str) -> SessionRecord | None:
        for session in self.sessions:
            if session.id == session_id:
                return session
        return None

    def update(self, session_id: str, **kwargs: Any) -> SessionRecord | None:
        for session in self.sessions:
            if session.id == session_id:
                for key, value in kwargs.items():
                    if hasattr(session, key):
                        if key in {"response_preview"} and isinstance(value, str):
                            value = value[:800]
                        if key in {"error"} and isinstance(value, str):
                            value = value[:500]
                        if key in {"label"} and isinstance(value, str):
                            value = value[:80]
                        setattr(session, key, value)
                self.save()
                return session
        return None

    def list_recent(self, limit: int = 30) -> list[dict[str, Any]]:
        self.reaping_note()
        return [s.to_dict() for s in self.sessions[:limit]]

    def list_running(self) -> list[dict[str, Any]]:
        self.reaping_note()
        return [s.to_dict() for s in self.sessions if s.status == "running"]

    def stop(self, session_id: str) -> bool:
        session = self.get(session_id)
        if not session or not session.pid:
            return False
        try:
            os.kill(session.pid, signal.SIGTERM)
        except OSError:
            # Try process group
            try:
                os.killpg(session.pid, signal.SIGTERM)
            except OSError:
                self.update(session_id, status="stopped")
                return False
        self.update(session_id, status="stopped")
        return True

    def reaping_note(self) -> None:
        """Mark interactive sessions dead if their pid no longer exists."""
        changed = False
        for session in self.sessions:
            if session.status != "running" or not session.pid:
                continue
            if session.kind not in {"interactive"}:
                continue
            try:
                os.kill(session.pid, 0)
            except OSError:
                session.status = "completed"
                changed = True
        if changed:
            self.save()

    def summary(self) -> dict[str, Any]:
        self.reaping_note()
        running = [s for s in self.sessions if s.status == "running"]
        return {
            "total": len(self.sessions),
            "running": len(running),
            "interactive_running": sum(1 for s in running if s.kind == "interactive"),
            "last_prompt": self.sessions[0].prompt if self.sessions else "",
            "last_status": self.sessions[0].status if self.sessions else "",
        }


def load_prompt_history(limit: int = 40) -> list[str]:
    ensure_dirs()
    if not HISTORY_PATH.is_file():
        return []
    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        items = data.get("prompts", [])
        return [str(x) for x in items[:limit] if str(x).strip()]
    except (OSError, json.JSONDecodeError, TypeError):
        return []


def push_prompt_history(prompt: str, limit: int = 40) -> None:
    prompt = prompt.strip()
    if not prompt:
        return
    ensure_dirs()
    items = load_prompt_history(limit=limit)
    items = [p for p in items if p != prompt]
    items.insert(0, prompt)
    items = items[:limit]
    HISTORY_PATH.write_text(json.dumps({"prompts": items}, indent=2), encoding="utf-8")
