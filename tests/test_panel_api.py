import json
import threading
import unittest
from urllib.request import urlopen

from hyprgrok.config import load_config
from hyprgrok.panel_server import clear_runtime_files, start_server


class PanelApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cfg = load_config()
        # Use an ephemeral high port
        cls.server = start_server(cfg=cfg, port=18765)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        clear_runtime_files()

    def _get(self, path: str) -> dict:
        with urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def test_status(self) -> None:
        data = self._get("/api/status")
        self.assertTrue(data["ok"])
        self.assertIn("grok_found", data)
        self.assertIn("version", data)

    def test_context(self) -> None:
        data = self._get("/api/context")
        self.assertTrue(data["ok"])
        self.assertIn("context", data)
        self.assertIn("formatted", data)

    def test_config(self) -> None:
        data = self._get("/api/config")
        self.assertTrue(data["ok"])
        self.assertIn("theme", data["config"])

    def test_index_html(self) -> None:
        with urlopen(f"http://127.0.0.1:{self.port}/", timeout=5) as resp:
            body = resp.read().decode("utf-8")
        self.assertIn("HyprGrok", body)
        self.assertIn("Get quick answer", body)
        self.assertIn("Grok Build sessions", body)


if __name__ == "__main__":
    unittest.main()
