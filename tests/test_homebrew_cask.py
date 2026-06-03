from pathlib import Path
import importlib.util
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "generate_homebrew_cask.py"


def load_module():
    spec = importlib.util.spec_from_file_location("generate_homebrew_cask", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class HomebrewCaskGenerationTests(unittest.TestCase):
    def test_render_cask_contains_release_url_and_postflight_commands(self):
        module = load_module()

        cask = module.render_cask("1.2.3", "a" * 64)

        self.assertIn('cask "hackclub-ai"', cask)
        self.assertIn('version "1.2.3"', cask)
        self.assertIn('sha256 "' + ("a" * 64) + '"', cask)
        self.assertIn(
            'url "https://github.com/random-guy-05/hackclub-ai/releases/download/v#{version}/HackClub-AI.dmg"',
            cask,
        )
        self.assertIn('app "HackClub AI.app"', cask)
        self.assertIn('xattr', cask)
        self.assertIn('com.apple.quarantine', cask)
        self.assertIn('open', cask)
        self.assertIn('#{appdir}/HackClub AI.app', cask)

    def test_read_version_text_strips_surrounding_whitespace(self):
        module = load_module()

        self.assertEqual(module.read_version_text("1.2.3\n"), "1.2.3")


if __name__ == "__main__":
    unittest.main()
