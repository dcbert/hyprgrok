import unittest
from pathlib import Path

from hyprgrok.config import (
    Config,
    default_config,
    find_grok_binary,
    load_config,
    package_root,
)


class ConfigTests(unittest.TestCase):
    def test_default_config_loads(self) -> None:
        cfg = default_config()
        self.assertIsInstance(cfg, Config)
        self.assertEqual(cfg.panel.position, "right")
        self.assertGreater(cfg.panel.port, 0)

    def test_package_root_has_ui(self) -> None:
        root = package_root()
        self.assertTrue((root / "ui" / "index.html").is_file())
        self.assertTrue((root / "configs" / "default.toml").is_file())

    def test_find_grok_binary(self) -> None:
        # May or may not exist in CI; function should not raise
        result = find_grok_binary()
        self.assertTrue(result is None or Path(result).exists())

    def test_load_config_without_user_file(self) -> None:
        cfg = load_config(Path("/nonexistent/hyprgrok-config.toml"))
        self.assertEqual(cfg.grok_binary, "grok")


if __name__ == "__main__":
    unittest.main()
