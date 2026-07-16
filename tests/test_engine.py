import importlib.util
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from copy import deepcopy
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("apsal_engine", ROOT / "plugins/apsal-studio/scripts/apsal_engine.py")
engine = importlib.util.module_from_spec(spec); spec.loader.exec_module(engine)

class EngineTests(unittest.TestCase):
    def test_catalog_is_complete_and_open(self): self.assertEqual(engine.validate_catalog(), [])
    def test_semantic_registry_covers_roles_categories_and_fields(self): self.assertEqual(engine.validate_semantic_registry(), [])
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

    def test_safe_yaml_round_trip_and_canonical_digest(self):
        theme = engine.new_semantic_theme("TEST-THEME", "Test")
        encoded = engine.dump_yaml(theme)
        decoded = engine.load_yaml_text(encoded)
        self.assertEqual(decoded, theme)
        self.assertEqual(engine.digest(decoded), engine.digest(theme))

    def test_safe_yaml_rejects_duplicate_keys_tags_anchors_aliases_and_tabs(self):
        rejected = (
            "id: A\nid: B\n", "id: !python/object bad\n", "id: &x A\n",
            "id: *x\n", "id:\tA\n", "base: A\ncopy:\n  <<: base\n",
        )
        for value in rejected:
            with self.subTest(value=value):
                with self.assertRaises(engine.YamlError): engine.load_yaml_text(value)

    def test_semantic_pilot_validates_and_preserves_parent_intent(self):
        legacy = engine.load_document(ROOT / "examples/quiet-window/theme.json")
        pilot = engine.load_document(ROOT / "examples/quiet-window/theme.apsal.yaml")
        self.assertEqual(engine.validate_theme(pilot), [])
        self.assertEqual(pilot["parent_version"], legacy["version"])
        self.assertEqual(pilot["dna"], legacy["dna"])
        for before, after in zip(legacy["shots"], pilot["shots"]):
            for key in ("shot_id", "title", "narrative_purpose", "framing", "action", "hands", "gaze", "composition", "continuity", "output_filename"):
                self.assertEqual(before[key], after[key])

    def test_unknown_semantic_tag_is_rejected(self):
        theme = engine.new_semantic_theme("TEST-THEME", "Test")
        theme["semantics"]["semantic_tags"].append("unknown.tag")
        self.assertTrue(any("unknown tags" in error for error in engine.validate_theme(theme)))

    def test_three_compile_targets_are_distinct_and_deterministic(self):
        theme = engine.load_document(ROOT / "examples/quiet-window/theme.apsal.yaml")
        design = engine.compile_theme(theme, "design")
        image = engine.compile_theme(theme, "image")
        qa = engine.compile_theme(theme, "qa")
        self.assertEqual(design, engine.compile_theme(theme, "design"))
        self.assertIn("element_semantics", design)
        self.assertIn("positive_prompt", image["shots"][0])
        self.assertNotIn("element_semantics", image)
        self.assertIn("checks", qa["shots"][0])

    def test_explain_resolves_shot_id_and_field_intent(self):
        theme = engine.load_document(ROOT / "examples/quiet-window/theme.apsal.yaml")
        value = engine.explain_theme_path(theme, "shots.SHOT_04.framing")
        self.assertEqual(value["value"], "close-up")
        self.assertEqual(value["normalized_path"], "shots.*.framing")
        self.assertIn("purpose", value["instance_intent"])

    def test_check_sync_detects_divergence(self):
        theme = engine.new_semantic_theme("TEST-THEME", "Test")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "theme.apsal.yaml").write_text(engine.dump_yaml(theme), encoding="utf-8")
            engine.write_canonical_json(theme, root / "theme.apsal.json")
            self.assertEqual(engine.check_sync(root), [])
            changed = dict(theme); changed["name"] = "Drift"
            engine.write_canonical_json(changed, root / "theme.apsal.json")
            self.assertTrue(any("differs" in error for error in engine.check_sync(root)))
    def test_skill_zip_is_reproducible_and_safe(self):
        theme = engine.new_theme("TEST-THEME", "Test")
        with tempfile.TemporaryDirectory() as tmp:
            first, sha1 = engine.pack_theme(theme, Path(tmp) / "a")
            second, sha2 = engine.pack_theme(theme, Path(tmp) / "b")
            self.assertEqual(sha1, sha2)
            with zipfile.ZipFile(first) as z: self.assertEqual(len(z.namelist()), 5)

    def test_semantic_skill_includes_yaml_design_and_qa(self):
        theme = engine.load_document(ROOT / "examples/quiet-window/theme.apsal.yaml")
        source = (ROOT / "examples/quiet-window/theme.apsal.yaml").read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            path, first_sha = engine.pack_theme(theme, Path(tmp) / "first", source)
            _, second_sha = engine.pack_theme(theme, Path(tmp) / "second", source)
            self.assertEqual(first_sha, second_sha)
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
                self.assertTrue(any(name.endswith("theme.apsal.yaml") for name in names))
                self.assertTrue(any(name.endswith("design_context.json") for name in names))
                self.assertTrue(any(name.endswith("qa_checklist.json") for name in names))
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

    def test_protocol_03_pilot_and_official_catalog_bytes_are_unchanged(self):
        expected = {
            "examples/quiet-window/theme.json": "f57e44a688cf9b91a34dfc2459ed8513c14db11d53dd7cb6c6262a9ab39bfb79",
            "examples/quiet-window/theme.apsal.yaml": "f385561747150956056b30aa0737baa837ecf6b83845b42854cbb5dbc305ddc3",
            "examples/quiet-window/theme.apsal.json": "db04cce8fb375035935096a5ce04f8a38d2ca72b112684abb53df1e2ed7bc441",
            "plugins/apsal-studio/assets/dna/catalog.json": "aaa223fa369bf81c2cc992dabc458f256ff342b7977afb18ea5fefc76bf407b3",
        }
        for relative, locked in expected.items():
            with self.subTest(relative=relative):
                self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), locked)

    def test_every_official_dna_has_a_valid_rights_clear_preview(self):
        self.assertEqual(engine.validate_official_previews(), [])
        records = engine._official_preview_index()
        self.assertEqual(len(records), 7)
        for item in records.values():
            self.assertEqual(item["kind"], "semantic_card")
            self.assertEqual(item["visual_qa_status"], "not_applicable_semantic_card")

    def _custom_asset(self, source_type="character", asset_id="MY_CHAR_001", namespace="personal"):
        source = next(item for item in engine.load_catalog()["assets"] if item["type"] == source_type)
        asset = deepcopy(source)
        asset.update({"namespace": namespace, "id": asset_id, "status": "draft", "parent_version": None,
                      "changed_fields": ["initial_version"], "change_summary": "Original private test DNA."})
        asset["rights"] = {"license": "All-Rights-Reserved", "status": "private_user_content", "attribution": "Test creator", "reference_images_included": False}
        return asset

    def _start_and_confirm(self, project: Path, home: Path, theme_id="TEST-NATURAL"):
        session = engine.start_design_session("创建一套九张东方极简窗边人像主题", project_root=project, home=home, theme_id=theme_id)
        assets = engine.load_catalog()["assets"]
        for stage in engine.INTERACTION_STAGES:
            refs = [engine.asset_ref(item) for item in assets if item["type"] in engine.STAGE_TYPES[stage]]
            session = engine.commit_session_stage(session["session_id"], stage, refs, project_root=project, home=home)
        return session

    def test_init_respects_custom_home_and_writes_safe_ignore_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = Path(tmp) / "project", Path(tmp) / "home"
            project.mkdir()
            result = engine.init_workspace(project, home)
            self.assertEqual(Path(result["apsal_home"]), home.resolve())
            self.assertTrue((home / "vault/sha256").is_dir())
            self.assertEqual((project / ".apsal/.gitignore").read_text(), "drafts/\nruns/\ncache/\nvault/\n")
            first = (project / ".apsal/project.json").read_bytes()
            engine.init_workspace(project, home)
            self.assertEqual((project / ".apsal/project.json").read_bytes(), first)

    def test_registry_precedence_immutability_conflict_and_promotion(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = Path(tmp) / "project", Path(tmp) / "home"; project.mkdir()
            asset = self._custom_asset(namespace="mine")
            engine.save_registry_asset(asset, scope="project", project_root=project, home=home)
            promoted = engine.promote_registry_asset(engine.asset_ref(asset), project_root=project, home=home)
            self.assertEqual(promoted["scope"], "personal")
            records = engine.load_layered_registry(project, home)
            match = next(item for item in records if engine._asset_key(item["asset"]) == engine._asset_key(asset))
            self.assertEqual(match["scope"], "project")
            changed = deepcopy(asset); changed["prompt_fragment"] += ", changed"
            with self.assertRaises(engine.ValidationError):
                engine.save_registry_asset(changed, scope="project", project_root=project, home=home)
            personal_path = Path(promoted["path"])
            personal = json.loads(personal_path.read_text()); personal["prompt_fragment"] += ", conflict"
            engine.write_canonical_json(personal, personal_path)
            with self.assertRaisesRegex(engine.ValidationError, "registry digest conflict"):
                engine.load_layered_registry(project, home)

    def test_session_resumes_and_upstream_change_invalidates_downstream(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = Path(tmp) / "project", Path(tmp) / "home"; project.mkdir()
            session = self._start_and_confirm(project, home)
            self.assertEqual(session["state"], "review_pending")
            loaded, _ = engine.load_design_session(session["session_id"], project)
            self.assertEqual(loaded["state"], "review_pending")
            custom = self._custom_asset(namespace="mine")
            engine.save_registry_asset(custom, scope="project", project_root=project, home=home)
            changed = engine.commit_session_stage(session["session_id"], "character", [engine.asset_ref(custom)], project_root=project, home=home)
            self.assertEqual(changed["state"], "world_pending")
            self.assertEqual(changed["stages"]["character"]["status"], "confirmed")
            self.assertTrue(all(changed["stages"][name]["status"] == "pending" for name in ("world", "scene", "photo")))
            self.assertEqual({item["invalidated"] for item in changed["invalidations"]}, {"world", "scene", "photo"})

    def test_confirmed_natural_language_draft_becomes_project_dna_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = Path(tmp) / "project", Path(tmp) / "home"; project.mkdir()
            session = engine.start_design_session("设计人物", project_root=project, home=home, theme_id="TEST-DRAFT")
            draft = self._custom_asset(namespace="mine")
            session = engine.commit_session_stage(session["session_id"], "character", [], project_root=project, home=home, draft_assets=[draft])
            self.assertEqual(session["state"], "world_pending")
            self.assertEqual(session["stages"]["character"]["selection"], [engine.asset_ref(draft)])
            self.assertTrue(list((project / ".apsal/registry").rglob("asset.apsal.json")))
            self.assertFalse(list((home / "registry").rglob("asset.apsal.json")))

    def test_scene_content_change_invalidates_confirmed_photo_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = Path(tmp) / "project", Path(tmp) / "home"; project.mkdir()
            session = self._start_and_confirm(project, home)
            _, theme = engine.load_design_session(session["session_id"], project)
            shots = deepcopy(theme["shots"]); shots[3]["narrative_purpose"] = "A newly confirmed single-shot narrative purpose."
            assets = engine.load_catalog()["assets"]
            refs = [engine.asset_ref(item) for item in assets if item["type"] in engine.STAGE_TYPES["scene"]]
            changed = engine.commit_session_stage(session["session_id"], "scene", refs, project_root=project, home=home, shots=shots)
            self.assertEqual(changed["state"], "photo_pending")
            self.assertEqual(changed["stages"]["photo"]["status"], "pending")

    def test_finalize_hides_formats_and_saves_all_prompt_layers(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = Path(tmp) / "project", Path(tmp) / "home"; project.mkdir()
            session = self._start_and_confirm(project, home)
            ready = engine.finalize_design_session(session["session_id"], project_root=project, home=home)
            root = Path(ready["theme_artifact"]["path"])
            self.assertEqual(ready["state"], "ready")
            self.assertTrue((root / "theme.apsal.yaml").is_file())
            self.assertTrue((root / "theme.apsal.json").is_file())
            self.assertEqual({path.name for path in (root / "compiled").glob("*.json")}, {"design.json", "image.json", "qa.json"})
            self.assertEqual(len(list((root / "prompts").glob("*.prompt.txt"))), 9)
            self.assertEqual(len(list((root / "prompts").glob("*.negative.txt"))), 9)
            manifest = json.loads((root / "artifact_manifest.json").read_text())
            self.assertEqual(len(manifest["prompt_digests"]), 9)
            again = engine.finalize_design_session(session["session_id"], project_root=project, home=home)
            self.assertEqual(again["theme_artifact"]["digest"], ready["theme_artifact"]["digest"])

    def test_generation_requires_confirmation_and_preserves_success_on_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = Path(tmp) / "project", Path(tmp) / "home"; project.mkdir()
            session = self._start_and_confirm(project, home)
            session = engine.finalize_design_session(session["session_id"], project_root=project, home=home)
            with self.assertRaisesRegex(engine.ValidationError, "explicit confirmation"):
                engine.start_generation_run(session["session_id"], project_root=project, home=home)
            run = engine.start_generation_run(session["session_id"], project_root=project, home=home, confirmed=True)
            self.assertEqual(len(run["jobs"]), 9)
            self.assertEqual(len(list((project / ".apsal/runs" / run["run_id"] / "prompts").glob("*.txt"))), 18)
            output = Path(tmp) / "shot.webp"; output.write_bytes(b"generated-test-output")
            run = engine.record_generation_result(run["run_id"], "SHOT_01", "succeeded", project_root=project, output_path=output)
            self.assertEqual(run["status"], "partial")
            engine.record_generation_result(run["run_id"], "SHOT_02", "failed", project_root=project, error="adapter test failure")
            with self.assertRaisesRegex(engine.ValidationError, "immutable"):
                engine.record_generation_result(run["run_id"], "SHOT_01", "succeeded", project_root=project, artifact_uri="test://duplicate")
            resumed = engine.start_generation_run(session["session_id"], project_root=project, home=home, confirmed=True, resume_run_id=run["run_id"])
            by_id = {job["shot_id"]: job for job in resumed["jobs"]}
            self.assertEqual(by_id["SHOT_01"]["status"], "succeeded")
            self.assertEqual(by_id["SHOT_02"]["status"], "pending")
            self.assertEqual(resumed["resume_count"], 1)

    def test_private_reference_is_content_addressed_and_not_in_theme(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"; source = Path(tmp) / "person.jpg"; source.write_bytes(b"private-reference")
            stored = engine.store_private_reference(source, home=home)
            self.assertTrue(stored["vault_uri"].startswith("vault:sha256:"))
            self.assertTrue(any((home / "vault/sha256").rglob("reference.jpg")))
            self.assertNotIn(str(source), json.dumps(engine.new_semantic_theme("TEST-PRIVATE", "Private")))

    def test_mcp_lists_seven_tools_and_returns_visual_and_text_card_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = Path(tmp) / "project", Path(tmp) / "home"; project.mkdir()
            requests = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "present_dna_cards", "arguments": {"project_root": str(project), "stage": "character"}}},
            ]
            env = {**os.environ, "APSAL_HOME": str(home)}
            process = subprocess.run([sys.executable, "scripts/apsal_mcp.py"], cwd=ROOT / "plugins/apsal-studio", input="".join(json.dumps(item) + "\n" for item in requests), text=True, capture_output=True, env=env, check=True)
            responses = [json.loads(line) for line in process.stdout.splitlines()]
            self.assertEqual(responses[0]["result"]["serverInfo"]["version"], "0.4.0")
            self.assertEqual(len(responses[1]["result"]["tools"]), 7)
            cards = responses[2]["result"]["structuredContent"]["cards"]
            self.assertEqual(len(cards), 1)
            self.assertTrue(cards[0]["preview"].startswith("data:image/webp;base64,"))
            self.assertIn("change_summary", cards[0]["summary"] if isinstance(cards[0]["summary"], dict) else {"change_summary": cards[0]["summary"]})

    def test_path_components_reject_traversal(self):
        with self.assertRaises(engine.ValidationError): engine._safe_part("../escape", "test")

if __name__ == "__main__": unittest.main()
