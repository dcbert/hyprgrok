import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hyprgrok import grok_store


class GrokStoreTests(unittest.TestCase):
    def test_list_sessions_from_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sessions = root / "sessions" / "%2Ftmp%2Fproj" / "019fe000-0000-0000-0000-000000000001"
            sessions.mkdir(parents=True)
            (sessions / "summary.json").write_text(
                json.dumps(
                    {
                        "info": {"id": "019fe000-0000-0000-0000-000000000001", "cwd": "/tmp/proj"},
                        "generated_title": "Test Session Title",
                        "created_at": "2026-01-01T00:00:00Z",
                        "updated_at": "2026-01-02T00:00:00Z",
                        "current_model_id": "grok-4.5",
                        "num_messages": 3,
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(grok_store, "grok_home", return_value=root), mock.patch.object(
                grok_store, "load_active_sessions", return_value={}
            ):
                rows = grok_store.list_sessions(limit=10, include_first_prompt=False, include_todos=False)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["title"], "Test Session Title")
            self.assertEqual(rows[0]["cwd"], "/tmp/proj")
            self.assertEqual(rows[0]["model"], "grok-4.5")

    def test_prompt_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hist_dir = root / "sessions" / "%2Ftmp%2Fproj"
            hist_dir.mkdir(parents=True)
            (hist_dir / "prompt_history.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "timestamp": "2026-01-02T00:00:00Z",
                                "session_id": "abc",
                                "prompt": "newer prompt",
                            }
                        ),
                        json.dumps(
                            {
                                "timestamp": "2026-01-01T00:00:00Z",
                                "session_id": "def",
                                "prompt": "older prompt",
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            with mock.patch.object(grok_store, "grok_home", return_value=root):
                rows = grok_store.list_prompt_history(limit=10)
            self.assertEqual(rows[0]["prompt"], "newer prompt")
            self.assertEqual(rows[0]["cwd"], "/tmp/proj")


if __name__ == "__main__":
    unittest.main()
