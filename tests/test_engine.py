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

    def test_protocol_package_requires_explicit_open_rights(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "manifest.json").write_text(json.dumps({"protocol": "APSAL 4.0"}), encoding="utf-8")
            errors = engine.validate_protocol_package(root)
            self.assertIn("manifest: missing license", errors)
            self.assertIn("manifest: protocol must be apsal-open", errors)

    def test_complete_modular_package_validates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "modules").mkdir(); (root / "sequences").mkdir(); (root / "jobs").mkdir()
            rights = {"license": "CC-BY-4.0", "status": "original_open_content", "attribution": "Test author", "reference_media": "none"}
            roles = engine.PROTOCOL_TYPES[:11]
            paths = {}
            for role in roles:
                rel = f"modules/{role}.json"; paths[role] = rel
                value = {"schema_version":"1.0.0","namespace":"test","id":f"TEST_{role.upper()}","type":role,"version":"1.0.0","parent_version":None,"changed_fields":["initial_version"],"change_summary":"Original test module.","dependencies":[],"rights":rights,"qa_status":"static_validated","payload":{}}
                (root / rel).write_text(json.dumps(value), encoding="utf-8")
            sequence_rel = "sequences/sequence.json"
            sequence = {"schema_version":"1.0.0","namespace":"test","id":"TEST_SEQUENCE","type":"sequence","version":"1.0.0","parent_version":None,"changed_fields":["initial_version"],"change_summary":"Original sequence.","dependencies":[],"rights":rights,"qa_status":"static_validated","payload":{"shot_ids":["SHOT_01"]}}
            (root / sequence_rel).write_text(json.dumps(sequence), encoding="utf-8")
            job_rel = "jobs/shot_01.json"
            job = {"schema_version":"1.0.0","namespace":"test","id":"TEST_JOB_01","type":"job","version":"1.0.0","parent_version":None,"changed_fields":["initial_version"],"change_summary":"Original job.","dependencies":[],"rights":rights,"qa_status":"visual_qa_pending","payload":{"output":{"independent_image":True,"filename":"shot_01.png"}}}
            (root / job_rel).write_text(json.dumps(job), encoding="utf-8")
            files = [*paths.values(), sequence_rel, job_rel]
            checksums = {rel: __import__("hashlib").sha256((root / rel).read_bytes()).hexdigest() for rel in files}
            manifest = {"protocol":"apsal-open","protocol_version":"0.2.0","id":"TEST_PACKAGE","version":"1.0.0","parent_version":None,"changed_fields":["initial_version"],"change_summary":"Original test package.","license":{"code":"Apache-2.0","content":"CC-BY-4.0"},"rights":{"status":"original_open_content","attribution":"Test author","reference_media":"none","ai_disclosure":True},"modules":paths,"sequence":sequence_rel,"jobs":[job_rel],"checksums":checksums,"output":{"one_job_one_image":True,"count":1},"qa_status":"visual_qa_pending"}
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            self.assertEqual(engine.validate_protocol_package(root), [])

if __name__ == "__main__": unittest.main()
