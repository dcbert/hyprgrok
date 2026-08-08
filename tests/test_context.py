import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hyprgrok.context import find_project_root, gather_context


class ContextTests(unittest.TestCase):
    def test_is_hyprgrok_window(self) -> None:
        from hyprgrok.context import is_hyprgrok_window

        self.assertTrue(is_hyprgrok_window({"title": "HyprGrok", "class": "Google-chrome"}))
        self.assertTrue(is_hyprgrok_window({"title": "x", "class": "hyprgrok-panel"}))
        self.assertFalse(is_hyprgrok_window({"title": "README.md - Code", "class": "code-oss"}))
        self.assertFalse(is_hyprgrok_window(None))

    def test_get_active_window_skips_panel(self) -> None:
        from hyprgrok import context as ctxmod

        panel = {
            "address": "0x1",
            "title": "HyprGrok",
            "class": "Google-chrome",
            "focusHistoryID": 0,
            "mapped": True,
        }
        editor = {
            "address": "0x2",
            "title": "README.md - Code",
            "class": "code-oss",
            "focusHistoryID": 1,
            "mapped": True,
        }
        with mock.patch.object(ctxmod, "hyprctl_json") as hj:
            def side_effect(args):
                if args == ["activewindow"]:
                    return panel
                if args == ["clients"]:
                    return [panel, editor]
                return None

            hj.side_effect = side_effect
            win = ctxmod.get_active_window(skip_hyprgrok=True)
        self.assertIsNotNone(win)
        self.assertEqual(win["class"], "code-oss")

    def test_find_project_root_git(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            nested = root / "a" / "b"
            nested.mkdir(parents=True)
            self.assertEqual(find_project_root(nested), str(root.resolve()))

    def test_find_project_root_pyproject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
            self.assertEqual(find_project_root(root / "src"), str(root.resolve()))

    def test_gather_context_returns_dictish(self) -> None:
        ctx = gather_context(include_screenshot=False)
        data = ctx.to_dict()
        self.assertIn("window_title", data)
        self.assertIn("cwd", data)
        self.assertTrue(ctx.cwd)
        text = ctx.format_for_prompt()
        self.assertIn("HyprGrok Desktop Context", text)

    def test_smart_cwd_exists(self) -> None:
        from hyprgrok.context import smart_launch_cwd

        cwd = smart_launch_cwd()
        self.assertTrue(os.path.isdir(cwd))


if __name__ == "__main__":
    unittest.main()
