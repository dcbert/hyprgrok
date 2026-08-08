"""Read-only access to official Grok Build on-disk sessions & history.

Layout under ``~/.grok`` (not owned by HyprGrok)::

    ~/.grok/active_sessions.json
    ~/.grok/sessions/<url-encoded-cwd>/<session-uuid>/summary.json
    ~/.grok/sessions/<url-encoded-cwd>/prompt_history.jsonl
    ~/.grok/sessions/session_search.sqlite

HyprGrok never writes auth or session files here — only reads them and
launches ``grok -r`` / ``grok -c`` for resume.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote


def grok_home() -> Path:
    env = os.environ.get("GROK_HOME") or os.environ.get("GROK_DIR")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".grok"


def sessions_root() -> Path:
    return grok_home() / "sessions"


def active_sessions_path() -> Path:
    return grok_home() / "active_sessions.json"


def search_db_path() -> Path:
    return sessions_root() / "session_search.sqlite"


@dataclass
class GrokSession:
    id: str
    title: str = ""
    cwd: str = ""
    created_at: str = ""
    updated_at: str = ""
    last_active_at: str = ""
    model: str = ""
    agent_name: str = ""
    num_messages: int = 0
    num_chat_messages: int = 0
    path: str = ""
    active: bool = False
    active_pid: int | None = None
    first_prompt: str = ""
    todos: list[dict[str, Any]] = field(default_factory=list)
    reasoning_effort: str = ""
    sandbox_profile: str = ""
    source: str = "grok-build"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_iso_ts(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        # handle trailing Z
        v = value.replace("Z", "+00:00")
        return datetime.fromisoformat(v).timestamp()
    except (TypeError, ValueError):
        return 0.0


def _cwd_from_encoded_dir(name: str) -> str:
    # dirs are percent-encoded paths like %2Fhome%2Fdbert%2FProjects
    try:
        return unquote(name)
    except Exception:
        return name


def load_active_sessions() -> dict[str, dict[str, Any]]:
    path = active_sessions_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(data, list):
        return out
    for item in data:
        if not isinstance(item, dict):
            continue
        sid = str(item.get("session_id") or "")
        if not sid:
            continue
        pid = item.get("pid")
        alive = False
        if pid is not None:
            try:
                os.kill(int(pid), 0)
                alive = True
            except (OSError, ValueError):
                alive = False
        out[sid] = {
            "pid": int(pid) if pid is not None else None,
            "cwd": str(item.get("cwd") or ""),
            "opened_at": str(item.get("opened_at") or ""),
            "alive": alive,
        }
    return out


def _extract_todos(session_dir: Path) -> list[dict[str, Any]]:
    res = session_dir / "resources_state.json"
    if not res.is_file():
        return []
    try:
        data = json.loads(res.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    todos_map = (
        data.get("state", {})
        .get("grok_build.Todo", {})
        .get("todos", {})
    )
    if not isinstance(todos_map, dict):
        return []
    rows: list[dict[str, Any]] = []
    for tid, todo in todos_map.items():
        if not isinstance(todo, dict):
            continue
        rows.append(
            {
                "id": str(tid),
                "content": str(todo.get("content") or ""),
                "status": str(todo.get("status") or ""),
                "priority": str(todo.get("priority") or ""),
            }
        )
    # in_progress first, then pending, then done
    order = {"in_progress": 0, "pending": 1, "completed": 2, "cancelled": 3}
    rows.sort(key=lambda r: order.get(r["status"], 9))
    return rows


def _first_user_prompt(session_dir: Path, max_len: int = 240) -> str:
    # Prefer prompt_history sibling is not per-session; use updates.jsonl user chunks
    updates = session_dir / "updates.jsonl"
    if updates.is_file():
        try:
            with updates.open(encoding="utf-8", errors="ignore") as fh:
                for i, line in enumerate(fh):
                    if i > 80:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    upd = (obj.get("params") or {}).get("update") or {}
                    if upd.get("sessionUpdate") == "user_message_chunk":
                        content = upd.get("content") or {}
                        text = content.get("text") if isinstance(content, dict) else None
                        if text:
                            text = str(text).strip()
                            return text[:max_len] + ("…" if len(text) > max_len else "")
        except OSError:
            pass

    chat = session_dir / "chat_history.jsonl"
    if chat.is_file():
        try:
            with chat.open(encoding="utf-8", errors="ignore") as fh:
                for i, line in enumerate(fh):
                    if i > 40:
                        break
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if obj.get("type") in {"user", "human"} or obj.get("role") == "user":
                        content = obj.get("content") or obj.get("text") or ""
                        if isinstance(content, list):
                            parts = []
                            for block in content:
                                if isinstance(block, dict) and block.get("text"):
                                    parts.append(str(block["text"]))
                                elif isinstance(block, str):
                                    parts.append(block)
                            content = "\n".join(parts)
                        text = str(content).strip()
                        if text:
                            return text[:max_len] + ("…" if len(text) > max_len else "")
        except OSError:
            pass
    return ""


def list_sessions(
    *,
    limit: int = 40,
    cwd_filter: str | None = None,
    include_first_prompt: bool = True,
    include_todos: bool = True,
) -> list[dict[str, Any]]:
    root = sessions_root()
    if not root.is_dir():
        return []

    active = load_active_sessions()
    sessions: list[GrokSession] = []

    for summary_path in root.rglob("summary.json"):
        if summary_path.name != "summary.json":
            continue
        # skip lock files already filtered by name
        try:
            raw = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        info = raw.get("info") or {}
        sid = str(info.get("id") or summary_path.parent.name)
        cwd = str(info.get("cwd") or "")
        if not cwd:
            # parent of session uuid is encoded cwd
            cwd = _cwd_from_encoded_dir(summary_path.parent.parent.name)
        if cwd_filter and os.path.abspath(cwd) != os.path.abspath(cwd_filter):
            continue

        title = (
            str(raw.get("generated_title") or raw.get("session_summary") or "").strip()
            or "Untitled session"
        )
        act = active.get(sid) or {}
        sess = GrokSession(
            id=sid,
            title=title,
            cwd=cwd,
            created_at=str(raw.get("created_at") or ""),
            updated_at=str(raw.get("updated_at") or raw.get("last_active_at") or ""),
            last_active_at=str(raw.get("last_active_at") or raw.get("updated_at") or ""),
            model=str(raw.get("current_model_id") or ""),
            agent_name=str(raw.get("agent_name") or ""),
            num_messages=int(raw.get("num_messages") or 0),
            num_chat_messages=int(raw.get("num_chat_messages") or 0),
            path=str(summary_path.parent),
            active=bool(act.get("alive")),
            active_pid=act.get("pid") if act.get("alive") else None,
            reasoning_effort=str(raw.get("reasoning_effort") or ""),
            sandbox_profile=str(raw.get("sandbox_profile") or ""),
        )
        if include_first_prompt:
            sess.first_prompt = _first_user_prompt(summary_path.parent)
        if include_todos:
            sess.todos = _extract_todos(summary_path.parent)
        sessions.append(sess)

    sessions.sort(
        key=lambda s: max(_parse_iso_ts(s.last_active_at), _parse_iso_ts(s.updated_at)),
        reverse=True,
    )
    return [s.to_dict() for s in sessions[:limit]]


def get_session(session_id: str) -> dict[str, Any] | None:
    for s in list_sessions(limit=500, include_first_prompt=True, include_todos=True):
        if s["id"] == session_id:
            return s
    # direct path walk for missing from limit
    root = sessions_root()
    if not root.is_dir():
        return None
    for summary_path in root.rglob("summary.json"):
        try:
            raw = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        info = raw.get("info") or {}
        if str(info.get("id") or summary_path.parent.name) == session_id:
            rows = list_sessions(limit=1000)
            for r in rows:
                if r["id"] == session_id:
                    return r
    return None


def list_prompt_history(*, limit: int = 50, cwd_filter: str | None = None) -> list[dict[str, Any]]:
    root = sessions_root()
    if not root.is_dir():
        return []

    items: list[dict[str, Any]] = []
    for hist in root.rglob("prompt_history.jsonl"):
        # only project-level files (next to session dirs), not inside uuid dirs
        # actually they live as sibling: sessions/%2Fpath/prompt_history.jsonl
        if hist.parent.name.count("-") >= 4 and len(hist.parent.name) > 30:
            # looks like a uuid dir — skip (none expected)
            continue
        cwd = _cwd_from_encoded_dir(hist.parent.name)
        if cwd_filter and os.path.abspath(cwd) != os.path.abspath(cwd_filter):
            continue
        try:
            with hist.open(encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    prompt = str(obj.get("prompt") or "").strip()
                    if not prompt:
                        continue
                    items.append(
                        {
                            "prompt": prompt,
                            "timestamp": str(obj.get("timestamp") or ""),
                            "session_id": str(obj.get("session_id") or ""),
                            "cwd": cwd,
                            "source": "grok-build",
                        }
                    )
        except OSError:
            continue

    items.sort(key=lambda x: _parse_iso_ts(x.get("timestamp")), reverse=True)

    # de-dupe by exact prompt keeping newest
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for it in items:
        key = it["prompt"]
        if key in seen:
            continue
        seen.add(key)
        unique.append(it)
        if len(unique) >= limit:
            break
    return unique


def search_sessions(query: str, *, limit: int = 20) -> list[dict[str, Any]]:
    """Use Grok's session_search.sqlite FTS when available; else filter titles."""
    query = (query or "").strip()
    if not query:
        return list_sessions(limit=limit)

    db = search_db_path()
    if db.is_file():
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            cur = con.cursor()
            # FTS if present
            try:
                rows = cur.execute(
                    """
                    SELECT d.session_id, d.cwd, d.updated_at, d.title, d.content
                    FROM session_docs_fts f
                    JOIN session_docs d ON d.rowid = f.rowid
                    WHERE session_docs_fts MATCH ?
                    ORDER BY d.updated_at DESC
                    LIMIT ?
                    """,
                    (query, limit),
                ).fetchall()
            except sqlite3.Error:
                rows = cur.execute(
                    """
                    SELECT session_id, cwd, updated_at, title, content
                    FROM session_docs
                    WHERE title LIKE ? OR content LIKE ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (f"%{query}%", f"%{query}%", limit),
                ).fetchall()
            con.close()
            active = load_active_sessions()
            out: list[dict[str, Any]] = []
            for sid, cwd, updated_at, title, content in rows:
                act = active.get(str(sid)) or {}
                preview = str(content or "")[:200]
                out.append(
                    {
                        "id": str(sid),
                        "title": str(title or "Untitled session"),
                        "cwd": str(cwd or ""),
                        "updated_at": (
                            datetime.fromtimestamp(int(updated_at), tz=timezone.utc).isoformat()
                            if updated_at
                            else ""
                        ),
                        "created_at": "",
                        "last_active_at": "",
                        "model": "",
                        "agent_name": "",
                        "num_messages": 0,
                        "num_chat_messages": 0,
                        "path": "",
                        "active": bool(act.get("alive")),
                        "active_pid": act.get("pid") if act.get("alive") else None,
                        "first_prompt": preview,
                        "todos": [],
                        "reasoning_effort": "",
                        "sandbox_profile": "",
                        "source": "grok-build",
                    }
                )
            return out
        except sqlite3.Error:
            pass

    q = query.lower()
    return [
        s
        for s in list_sessions(limit=200)
        if q in (s.get("title") or "").lower()
        or q in (s.get("first_prompt") or "").lower()
        or q in (s.get("cwd") or "").lower()
    ][:limit]


def store_summary() -> dict[str, Any]:
    sessions = list_sessions(limit=500, include_first_prompt=False, include_todos=False)
    active = [s for s in sessions if s.get("active")]
    prompts = list_prompt_history(limit=5)
    return {
        "grok_home": str(grok_home()),
        "sessions_root": str(sessions_root()),
        "total_sessions": len(sessions),
        "active_sessions": len(active),
        "has_search_db": search_db_path().is_file(),
        "recent_titles": [s.get("title") for s in sessions[:5]],
        "recent_prompts": [p.get("prompt", "")[:80] for p in prompts],
    }
