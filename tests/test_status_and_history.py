import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hyprgrok.context import find_project_root
from hyprgrok.session import SessionManager, load_prompt_history, push_prompt_history
from hyprgrok.status import build_status, waybar_json


class ProjectDetectionTests(unittest.TestCase):
    def test_prefers_git_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / "package.json").write_text("{}", encoding="utf-8")
            nested = root / "packages" / "app" / "src"
            nested.mkdir(parents=True)
            self.assertEqual(find_project_root(nested), str(root.resolve()))

    def test_uv_lock_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "uv.lock").write_text("", encoding="utf-8")
            self.assertEqual(find_project_root(root / "src"), str(root.resolve()))


class HistoryTests(unittest.TestCase):
    def test_push_and_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hist = Path(tmp) / "prompt_history.json"
            with mock.patch("hyprgrok.session.HISTORY_PATH", hist), mock.patch(
                "hyprgrok.session.ensure_dirs", lambda: None
            ):
                push_prompt_history("first")
                push_prompt_history("second")
                push_prompt_history("first")
                items = load_prompt_history()
                self.assertEqual(items[0], "first")
                self.assertEqual(items[1], "second")
                self.assertEqual(len(items), 2)


class SessionManagerTests(unittest.TestCase):
    def test_add_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sessions.json"
            with mock.patch("hyprgrok.session.SESSIONS_PATH", path), mock.patch(
                "hyprgrok.session.ensure_dirs", lambda: None
            ):
                mgr = SessionManager()
                mgr.sessions = []
                rec = mgr.add(kind="headless", cwd="/tmp", prompt="hello", status="completed")
                self.assertTrue(rec.id)
                summary = mgr.summary()
                self.assertEqual(summary["total"], 1)
                self.assertEqual(summary["running"], 0)


class StatusTests(unittest.TestCase):
    def test_waybar_json_shape(self) -> None:
        data = json.loads(waybar_json())
        self.assertIn("text", data)
        self.assertIn("class", data)
        self.assertIn("tooltip", data)
        status = build_status()
        self.assertIn("sessions", status)
        self.assertIn("grok_found", status)


if __name__ == "__main__":
    unittest.main()
