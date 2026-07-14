import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("apsal_engine", ROOT / "plugins/apsal-studio/scripts/apsal_engine.py")
engine = importlib.util.module_from_spec(spec); spec.loader.exec_module(engine)

class EngineTests(unittest.TestCase):
    def test_catalog_is_complete_and_open(self): self.assertEqual(engine.validate_catalog(), [])
    def test_default_theme_has_nine_unique_independent_outputs(self):
        theme = engine.new_theme("TEST-THEME", "Test", 9)
        self.assertEqual(engine.validate_theme(theme), [])
        self.assertEqual(len({s["output_filename"] for s in theme["shots"]}), 9)
    def test_custom_shot_count(self): self.assertEqual(len(engine.new_theme("TEST-THEME", "Test", 4)["shots"]), 4)
    def test_digest_lock_detects_catalog_tampering(self):
        theme = engine.new_theme("TEST-THEME", "Test")
        theme["dna"][0]["content_digest"] = "0" * 64
        self.assertTrue(any("digest mismatch" in e for e in engine.validate_theme(theme)))
    def test_compilation_is_deterministic(self):
        theme = engine.new_theme("TEST-THEME", "Test")
        self.assertEqual(engine.compile_theme(theme), engine.compile_theme(theme))
    def test_skill_zip_is_reproducible_and_safe(self):
        theme = engine.new_theme("TEST-THEME", "Test")
        with tempfile.TemporaryDirectory() as tmp:
            first, sha1 = engine.pack_theme(theme, Path(tmp) / "a")
            second, sha2 = engine.pack_theme(theme, Path(tmp) / "b")
            self.assertEqual(sha1, sha2)
            with zipfile.ZipFile(first) as z: self.assertEqual(len(z.namelist()), 5)
    def test_visual_pass_requires_evidence(self):
        theme = engine.new_theme("TEST-THEME", "Test"); theme["qa_status"] = "visual_qa_passed"
        self.assertTrue(any("requires evidence" in e for e in engine.validate_theme(theme)))

if __name__ == "__main__": unittest.main()
