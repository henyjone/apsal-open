import importlib.util
import hashlib
import json
import os
import stat
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
        self.assertEqual(theme["output"]["size"], "2160x3840")
        self.assertEqual(theme["rendering_contract"]["medium"], "live_action_photography")
    def test_custom_shot_count(self): self.assertEqual(len(engine.new_theme("TEST-THEME", "Test", 4)["shots"]), 4)
    def test_digest_lock_detects_catalog_tampering(self):
        theme = engine.new_theme("TEST-THEME", "Test", native_4k=False, live_action=False)
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
        theme = engine.new_theme("TEST-THEME", "Test", native_4k=False, live_action=False)
        with tempfile.TemporaryDirectory() as tmp:
            first, sha1 = engine.pack_theme(theme, Path(tmp) / "a")
            second, sha2 = engine.pack_theme(theme, Path(tmp) / "b")
            self.assertEqual(sha1, sha2)
            with zipfile.ZipFile(first) as z:
                self.assertEqual(len(z.namelist()), 8)
                self.assertTrue(any(name.endswith("scripts/generate_set.py") for name in z.namelist()))
                skill = next(name for name in z.namelist() if name.endswith("SKILL.md"))
                self.assertIn("does not guarantee native 4K", z.read(skill).decode())

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
            self.assertEqual(stat.S_IMODE(home.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((home / "vault").stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((project / ".apsal").stat().st_mode), 0o700)
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
            self.assertEqual(session["stages"]["character"]["selection"][0]["id"], draft["id"])
            self.assertTrue(list((project / ".apsal/registry").rglob("asset.apsal.json")))
            self.assertFalse(list((home / "registry").rglob("asset.apsal.json")))
            self.assertEqual(len(session["memory_offers"]), 1)
            self.assertTrue(session["memory_offers"][0]["discovery"]["semantic_tags"])

    def test_scene_recommendation_is_explained_and_feedback_affects_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = Path(tmp) / "project", Path(tmp) / "home"; project.mkdir()
            value = engine.recommend_dna("创建九张东方极简窗边安静人像", "world", project_root=project, home=home)
            self.assertEqual(value["count"], 1)
            item = value["recommendations"][0]
            self.assertEqual(item["record"]["asset"]["id"], "OPEN_ENV_WINDOW_001")
            self.assertIn("world.space.coherent", item["matched_tags"])
            self.assertTrue(any("scene facets" in reason for reason in item["reasons"]))
            ref = engine.asset_ref(item["record"]["asset"])
            feedback = engine.record_dna_feedback(ref, "successful", project_root=project, home=home, context="东方极简窗边人像")
            self.assertGreater(feedback["preference_weight"], 0)
            again = engine.recommend_dna("东方极简窗边人像", "world", project_root=project, home=home)
            self.assertTrue(any("personal usage memory" in reason for reason in again["recommendations"][0]["reasons"]))
            self.assertNotIn("东方极简窗边人像", (home / "usage/events.jsonl").read_text(encoding="utf-8"))

    def test_discovery_metadata_rejects_tags_and_facets_from_another_dna_type(self):
        asset = self._custom_asset(namespace="maker")
        asset["discovery"] = {
            "schema_version": "0.6.0", "source": "creator_confirmed",
            "semantic_tags": ["world.space.coherent"],
            "facets": {"world.feature": ["window"]}, "keywords": ["window"],
        }
        errors = engine.validate_registry_asset(asset)
        self.assertTrue(any("tags incompatible with character" in error for error in errors))
        self.assertTrue(any("facets incompatible with character" in error for error in errors))

    def test_new_dna_memory_offer_promotes_only_after_explicit_choice(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = Path(tmp) / "project", Path(tmp) / "home"; project.mkdir()
            session = engine.start_design_session("安静窗边成年人物", project_root=project, home=home, theme_id="TEST-MEMORY")
            draft = self._custom_asset(namespace="maker")
            discovery = engine.suggest_discovery_metadata(draft, session["brief"])
            draft["discovery"] = engine.confirm_discovery_metadata(discovery)
            session = engine.commit_session_stage(session["session_id"], "character", [], project_root=project, home=home, draft_assets=[draft])
            offer = session["memory_offers"][0]
            self.assertFalse(offer["tag_confirmation_required"])
            self.assertFalse(list((home / "registry").rglob("asset.apsal.json")))
            result = engine.resolve_dna_memory_offer(session["session_id"], offer["offer_id"], "save_personal", project_root=project, home=home)
            self.assertEqual(result["offer"]["status"], "saved")
            personal = list((home / "registry").rglob("asset.apsal.json"))
            self.assertEqual(len(personal), 1)
            stored = json.loads(personal[0].read_text(encoding="utf-8"))
            self.assertEqual(stored["discovery"]["source"], "creator_confirmed")
            self.assertTrue((home / "usage/events.jsonl").is_file())

    def test_dna_pack_is_reproducible_installable_and_recommendable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); project_a, home_a = root / "project-a", root / "home-a"; project_a.mkdir()
            asset = self._custom_asset(namespace="maker")
            asset["rights"] = {"license": "CC-BY-4.0", "status": "original_open_content", "attribution": "Test creator", "reference_images_included": False}
            asset["discovery"] = engine.confirm_discovery_metadata(engine.suggest_discovery_metadata(asset, "安静真人摄影人物"))
            saved = engine.save_registry_asset(asset, scope="project", project_root=project_a, home=home_a)
            refs = [saved["ref"]]
            first, sha1 = engine.export_dna_pack(refs, pack_id="quiet-portrait", namespace="maker", version="1.0.0", name="Quiet Portrait DNA", description="Original quiet portrait character DNA.", project_root=project_a, home=home_a, output_dir=root / "one", distribution="public")
            second, sha2 = engine.export_dna_pack(refs, pack_id="quiet-portrait", namespace="maker", version="1.0.0", name="Quiet Portrait DNA", description="Original quiet portrait character DNA.", project_root=project_a, home=home_a, output_dir=root / "two", distribution="public")
            self.assertEqual(sha1, sha2)
            self.assertEqual(engine.validate_dna_pack(first)["asset_count"], 1)
            project_b, home_b = root / "project-b", root / "home-b"; project_b.mkdir()
            installed = engine.install_dna_pack(first, project_root=project_b, home=home_b)
            self.assertTrue(installed["installed"])
            self.assertFalse(engine.install_dna_pack(first, project_root=project_b, home=home_b)["installed"])
            records = engine.load_layered_registry(project_b, home_b)
            extension = next(item for item in records if item["asset"]["namespace"] == "maker")
            self.assertEqual(extension["scope"], "extension")
            self.assertTrue(any(item["scope"] == "extension" for item in engine.search_registry(project_b, "MY_CHAR", "character", home_b)))
            recommendation = engine.recommend_dna("安静真人摄影人物", "character", project_root=project_b, home=home_b)
            self.assertTrue(any(item["record"]["asset"]["namespace"] == "maker" for item in recommendation["recommendations"]))

    def test_contributor_dna_pack_cannot_claim_official_namespace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); project, home = root / "project", root / "home"; project.mkdir()
            with self.assertRaisesRegex(engine.ValidationError, "contributor-owned namespace"):
                engine.export_dna_pack([], pack_id="fake-official", namespace="official", version="1.0.0", name="Fake", description="Must be rejected.", project_root=project, home=home, output_dir=root)

    def test_public_dna_pack_requires_confirmed_tags_and_tampering_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); project, home = root / "project", root / "home"; project.mkdir()
            asset = self._custom_asset(namespace="maker")
            asset["rights"] = {"license": "CC-BY-4.0", "status": "original_open_content", "attribution": "Test creator", "reference_images_included": False}
            asset["discovery"] = engine.suggest_discovery_metadata(asset, "人像")
            saved = engine.save_registry_asset(asset, scope="project", project_root=project, home=home)
            with self.assertRaisesRegex(engine.ValidationError, "public"):
                engine.export_dna_pack([saved["ref"]], pack_id="test-pack", namespace="maker", version="1.0.0", name="Test", description="Test DNA pack.", project_root=project, home=home, output_dir=root, distribution="public")
            asset_v2 = deepcopy(asset); asset_v2["version"] = "1.0.1"; asset_v2["parent_version"] = "1.0.0"; asset_v2["changed_fields"] = ["discovery.source"]; asset_v2["discovery"] = engine.confirm_discovery_metadata(asset_v2["discovery"])
            saved_v2 = engine.save_registry_asset(asset_v2, scope="project", project_root=project, home=home)
            path, _ = engine.export_dna_pack([saved_v2["ref"]], pack_id="test-pack", namespace="maker", version="1.0.1", name="Test", description="Test DNA pack.", project_root=project, home=home, output_dir=root, distribution="public")
            with zipfile.ZipFile(path) as archive: files = {name: archive.read(name) for name in archive.namelist()}
            target = next(name for name in files if name.endswith("asset.apsal.json")); files[target] += b"\n"
            tampered = root / "tampered.zip"; tampered.write_bytes(engine._zip_bytes(files))
            with self.assertRaisesRegex(engine.ValidationError, "checksum mismatch"):
                engine.validate_dna_pack(tampered)

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
            with self.assertRaisesRegex(engine.ValidationError, "n=1"):
                engine.start_generation_run(session["session_id"], project_root=project, home=home, confirmed=True, parameters={"n": 9})
            self.assertEqual(list((project / ".apsal/runs").iterdir()), [])
            run = engine.start_generation_run(session["session_id"], project_root=project, home=home, confirmed=True)
            self.assertEqual(len(run["jobs"]), 9)
            self.assertEqual(len(list((project / ".apsal/runs" / run["run_id"] / "prompts").glob("*.txt"))), 18)
            output = Path(tmp) / "shot.png"; output.write_bytes(self._fake_png())
            run = engine.record_generation_result(run["run_id"], "SHOT_01", "succeeded", project_root=project, output_path=output)
            self.assertEqual(run["status"], "generating")
            self.assertEqual(run["jobs"][0]["output"]["width"], 2160)
            with self.assertRaisesRegex(engine.ValidationError, "local file"):
                engine.record_generation_result(run["run_id"], "SHOT_03", "succeeded", project_root=project, artifact_uri="test://unverifiable")
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
            home = Path(tmp) / "home"; source = Path(tmp) / "person.webp"
            source.write_bytes((ROOT / "plugins/apsal-studio/assets/previews/character.webp").read_bytes())
            stored = engine.store_private_reference(source, home=home)
            self.assertTrue(stored["vault_uri"].startswith("vault:sha256:"))
            stored_path = next((home / "vault/sha256").rglob("reference.webp"))
            self.assertEqual(stat.S_IMODE(stored_path.stat().st_mode), 0o600)
            self.assertNotIn(str(source), json.dumps(engine.new_semantic_theme("TEST-PRIVATE", "Private")))

    def test_private_reference_rejects_non_image_bytes_before_vault_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"; source = Path(tmp) / "person.jpg"; source.write_bytes(b"not-an-image")
            with self.assertRaisesRegex(engine.ValidationError, "unsupported reference image"):
                engine.store_private_reference(source, home=home)
            self.assertFalse((home / "vault").exists())

    def test_mcp_lists_fifteen_tools_and_returns_visual_and_text_card_data(self):
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
            self.assertEqual(responses[0]["result"]["serverInfo"]["version"], "0.6.0")
            self.assertEqual(len(responses[1]["result"]["tools"]), 15)
            cards = responses[2]["result"]["structuredContent"]["cards"]
            self.assertEqual(len(cards), 1)
            self.assertTrue(cards[0]["preview"].startswith("data:image/webp;base64,"))
            self.assertIn("change_summary", cards[0]["summary"] if isinstance(cards[0]["summary"], dict) else {"change_summary": cards[0]["summary"]})

    def test_path_components_reject_traversal(self):
        with self.assertRaises(engine.ValidationError): engine._safe_part("../escape", "test")

    def test_live_action_contract_leads_every_prompt_and_expands_qa(self):
        theme = engine.new_semantic_theme("TEST-LIVE", "Live", native_4k=True, live_action=True)
        self.assertEqual(engine.validate_theme(theme), [])
        image = engine.compile_theme(theme, "image")
        qa = engine.compile_theme(theme, "qa")
        self.assertTrue(all(shot["positive_prompt"].startswith("MEDIUM CONTRACT — LIVE-ACTION PHOTOGRAPHY") for shot in image["shots"]))
        self.assertTrue(all("illustrated_human" in shot["negative_prompt"] for shot in image["shots"]))
        self.assertEqual(image["output_contract"]["size"], "2160x3840")
        self.assertTrue(any(check["id"] == "medium.live_action" for check in qa["global_checks"]))
        self.assertTrue(all(any(check["id"] == "medium.real_adult_human" for check in shot["checks"]) for shot in qa["shots"]))

    def test_private_skill_bundles_sanitized_reference_and_public_export_fails(self):
        theme = engine.new_semantic_theme("TEST-REF", "Reference", native_4k=True, live_action=True)
        source = ROOT / "plugins/apsal-studio/assets/previews/character.webp"
        sha = hashlib.sha256(source.read_bytes()).hexdigest()
        theme["distribution"] = "private_only"
        theme["references"] = [{
            "reference_id": "TEST_STYLE_REF_001", "original_filename": source.name, "original_sha256": sha,
            "uses": ["style"], "allowed_uses": ["palette", "material"],
            "forbidden_uses": ["identity", "pose", "exact composition", "text", "watermark"],
            "applies_to": ["SHOT_01"], "rights": {"copyright_status": "unverified", "portrait_rights": "not_applicable", "attribution": "Test", "redistribution_allowed": False},
        }]
        with tempfile.TemporaryDirectory() as tmp:
            path, first_sha = engine.pack_theme(theme, Path(tmp) / "a", reference_paths={"TEST_STYLE_REF_001": source})
            _, second_sha = engine.pack_theme(theme, Path(tmp) / "b", reference_paths={"TEST_STYLE_REF_001": source})
            self.assertEqual(first_sha, second_sha)
            self.assertTrue(path.name.endswith("-private.zip"))
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
                self.assertTrue(any("assets/references/test_style_ref_001.webp" in name for name in names))
                manifest_name = next(name for name in names if name.endswith("reference_manifest.json"))
                manifest = json.loads(archive.read(manifest_name))
                self.assertEqual(manifest["reference_count"], 1)
                self.assertTrue(manifest["private_media_included"])
                self.assertFalse(manifest["redistribution_allowed"])
                self.assertNotEqual(manifest["references"][0]["packaged_sha256"], "0" * 64)
            with self.assertRaisesRegex(engine.ValidationError, "unredistributable|public"):
                engine.pack_theme(theme, Path(tmp) / "public", reference_paths={"TEST_STYLE_REF_001": source}, distribution="public")
            with self.assertRaisesRegex(engine.ValidationError, "required"):
                engine.pack_theme(theme, Path(tmp) / "missing")

    def test_reference_digest_mismatch_and_unscoped_usage_fail(self):
        theme = engine.new_semantic_theme("TEST-REF", "Reference", native_4k=True, live_action=True)
        theme["distribution"] = "private_only"
        theme["references"] = [{
            "reference_id": "TEST_REF_001", "original_filename": "ref.png", "original_sha256": "0" * 64,
            "uses": ["style"], "allowed_uses": ["palette"], "forbidden_uses": ["pose"],
            "applies_to": ["SHOT_99"], "rights": {"copyright_status": "unverified", "portrait_rights": "unverified", "attribution": "Test", "redistribution_allowed": False},
        }]
        errors = engine.validate_theme(theme)
        self.assertTrue(any("unknown Jobs" in error for error in errors))
        self.assertTrue(any("forbid identity" in error for error in errors))

    def test_public_reference_requires_resolved_rights_and_is_not_marked_private_media(self):
        theme = engine.new_semantic_theme("TEST-PUBLIC-REF", "Public reference", native_4k=True, live_action=True)
        source = ROOT / "plugins/apsal-studio/assets/previews/character.webp"
        ref = {
            "reference_id": "OPEN_STYLE_REF_001", "original_filename": source.name,
            "original_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "uses": ["style"],
            "allowed_uses": ["palette"], "forbidden_uses": ["identity", "pose", "text", "watermark"],
            "applies_to": ["SHOT_01"],
            "rights": {"copyright_status": "unverified", "portrait_rights": "not_applicable", "attribution": "APSAL Open contributors", "redistribution_allowed": True},
        }
        theme["references"] = [ref]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(engine.ValidationError, "unredistributable|public"):
                engine.pack_theme(theme, Path(tmp), reference_paths={"OPEN_STYLE_REF_001": source}, distribution="public")
            ref["rights"]["copyright_status"] = "original_licensed_content"
            path, _ = engine.pack_theme(theme, Path(tmp), reference_paths={"OPEN_STYLE_REF_001": source}, distribution="public")
            with zipfile.ZipFile(path) as archive:
                manifest = json.loads(archive.read(next(name for name in archive.namelist() if name.endswith("reference_manifest.json"))))
            self.assertTrue(manifest["redistribution_allowed"])
            self.assertFalse(manifest["private_media_included"])

    def test_malformed_reference_metadata_reports_errors_instead_of_crashing(self):
        theme = engine.new_semantic_theme("TEST-REF", "Reference", native_4k=True, live_action=True)
        theme["references"] = [{"reference_id": "BAD", "original_sha256": "bad", "uses": None, "allowed_uses": None, "forbidden_uses": None, "applies_to": None, "rights": None}]
        errors = engine.validate_theme(theme)
        self.assertTrue(any("uses must" in error for error in errors))
        self.assertTrue(any("rights must" in error for error in errors))

    @staticmethod
    def _fake_png(width=2160, height=3840):
        return b"\x89PNG\r\n\x1a\n" + (13).to_bytes(4, "big") + b"IHDR" + width.to_bytes(4, "big") + height.to_bytes(4, "big")

    @staticmethod
    def _fake_webp(width=2160, height=3840):
        payload = b"\x00" * 4 + (width - 1).to_bytes(3, "little") + (height - 1).to_bytes(3, "little")
        return b"RIFF" + (22).to_bytes(4, "little") + b"WEBP" + b"VP8X" + (10).to_bytes(4, "little") + payload

    def test_executor_makes_nine_distinct_n1_requests_retries_and_uses_identity_anchor(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = Path(tmp) / "project", Path(tmp) / "home"; project.mkdir()
            session = self._start_and_confirm(project, home, theme_id="TEST-EXECUTE")
            session = engine.finalize_design_session(session["session_id"], project_root=project, home=home)
            run = engine.start_generation_run(session["session_id"], project_root=project, home=home, confirmed=True, adapter="openai-image-api", model="gpt-image-2")
            calls = []; failed_once = set()
            def adapter(request, references):
                calls.append({"request": deepcopy(request), "reference_count": len(references)})
                if request["shot_id"] == "SHOT_04" and request["shot_id"] not in failed_once:
                    failed_once.add(request["shot_id"]); raise RuntimeError("simulated transient failure")
                return {"image_bytes": self._fake_png(), "provider_metadata": {"simulated": True}}
            def visual(path, contract, shot_id):
                self.assertEqual(engine._image_dimensions(path.read_bytes()), (2160, 3840))
                self.assertEqual(contract["medium"], "live_action_photography")
                return {"status": "passed", "findings": ["simulated live-action pass"]}
            completed = engine.execute_generation_run(run["run_id"], project_root=project, home=home, adapter_callable=adapter, visual_qa_callable=visual)
            self.assertEqual(completed["status"], "completed")
            self.assertEqual(len(calls), 10)
            self.assertEqual({call["request"]["n"] for call in calls}, {1})
            self.assertEqual(len({hashlib.sha256(call["request"]["prompt"].encode()).hexdigest() for call in calls}), 9)
            self.assertFalse(calls[0]["request"]["identity_anchor_used"])
            self.assertTrue(all(call["request"]["identity_anchor_used"] for call in calls[1:]))
            self.assertNotIn("RUNTIME_IDENTITY_ANCHOR_SHOT_01", calls[0]["request"]["runtime_reference_ids"])
            self.assertTrue(all("RUNTIME_IDENTITY_ANCHOR_SHOT_01" in call["request"]["runtime_reference_ids"] for call in calls[1:]))
            self.assertTrue(all(job["model_visual_qa"] == "passed" for job in completed["jobs"]))
            self.assertTrue(all(job["human_visual_qa"] == "pending" for job in completed["jobs"]))
            self.assertEqual(len(list((project / ".apsal/runs" / run["run_id"] / "outputs").glob("*.png"))), 9)
            effective_prompt = (project / ".apsal/runs" / run["run_id"] / "prompts" / "SHOT_02.prompt.txt").read_text(encoding="utf-8")
            self.assertIn("Use the SHOT_01 image only to preserve", effective_prompt)
            self.assertIn("Negative constraints:", effective_prompt)
            with self.assertRaisesRegex(engine.ValidationError, "no failed Jobs"):
                engine.start_generation_run(session["session_id"], project_root=project, home=home, confirmed=True, resume_run_id=run["run_id"])

    def test_openai_adapter_sends_n1_and_uses_edits_when_references_exist(self):
        captured = []
        class Response:
            headers = {"x-request-id": "request-test"}
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self):
                import base64
                return json.dumps({"data": [{"b64_json": base64.b64encode(self_data).decode()}]}).encode()
        self_data = self._fake_png()
        def urlopen(request, timeout):
            captured.append(request)
            return Response()
        request = {"model": "gpt-image-2", "prompt": "test", "size": "2160x3840", "quality": "high", "output_format": "png", "n": 1}
        with mock.patch.object(engine.urllib.request, "urlopen", side_effect=urlopen):
            generated = engine._openai_image_api_request(request, [], "TEST_SECRET")
            edited = engine._openai_image_api_request(request, [ROOT / "plugins/apsal-studio/assets/previews/character.webp"], "TEST_SECRET")
        generation_body = json.loads(captured[0].data)
        edit_body = captured[1].data
        self.assertEqual(generation_body["n"], "1")
        self.assertTrue(captured[0].full_url.endswith("/images/generations"))
        self.assertTrue(captured[1].full_url.endswith("/images/edits"))
        self.assertIn(b'name="n"\r\n\r\n1', edit_body)
        self.assertEqual(edit_body.count(b'name="image[]"'), 1)
        self.assertNotIn("TEST_SECRET", json.dumps([generated, edited], default=str))

    def test_executor_requires_model_visual_qa_before_next_live_action_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = Path(tmp) / "project", Path(tmp) / "home"; project.mkdir()
            session = self._start_and_confirm(project, home, theme_id="TEST-QA-GATE")
            session = engine.finalize_design_session(session["session_id"], project_root=project, home=home)
            run = engine.start_generation_run(session["session_id"], project_root=project, home=home, confirmed=True)
            adapter = lambda request, references: {"image_bytes": self._fake_png(), "provider_metadata": {"simulated": True}}
            first = engine.execute_generation_run(run["run_id"], project_root=project, home=home, max_jobs=9, adapter_callable=adapter)
            self.assertEqual(sum(job["status"] == "succeeded" for job in first["jobs"]), 1)
            with self.assertRaisesRegex(engine.ValidationError, "model visual QA"):
                engine.execute_generation_run(run["run_id"], project_root=project, home=home, adapter_callable=adapter)
            engine.record_model_visual_qa(run["run_id"], "SHOT_01", "passed", project_root=project, findings=["real adult human"])
            second = engine.execute_generation_run(run["run_id"], project_root=project, home=home, adapter_callable=adapter)
            self.assertEqual(sum(job["status"] == "succeeded" for job in second["jobs"]), 2)

    def test_executor_rejects_non_native_dimensions_after_three_attempts(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = Path(tmp) / "project", Path(tmp) / "home"; project.mkdir()
            session = self._start_and_confirm(project, home, theme_id="TEST-DIMENSIONS")
            session = engine.finalize_design_session(session["session_id"], project_root=project, home=home)
            run = engine.start_generation_run(session["session_id"], project_root=project, home=home, confirmed=True)
            calls = []
            def adapter(request, references):
                calls.append(deepcopy(request))
                return {"image_bytes": self._fake_png(1024, 1792), "provider_metadata": {"simulated": True}}
            partial = engine.execute_generation_run(run["run_id"], project_root=project, home=home, adapter_callable=adapter)
            first = partial["jobs"][0]
            self.assertEqual(partial["status"], "partial")
            self.assertEqual(first["status"], "failed")
            self.assertEqual(len(first["attempts"]), 3)
            self.assertEqual(len(calls), 3)
            self.assertIn("expected 2160x3840", first["error"])
            self.assertFalse((project / ".apsal/runs" / run["run_id"] / "outputs" / "SHOT_01.png").exists())

    def test_executor_rejects_wrong_format_even_at_exact_dimensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = Path(tmp) / "project", Path(tmp) / "home"; project.mkdir()
            session = self._start_and_confirm(project, home, theme_id="TEST-FORMAT")
            session = engine.finalize_design_session(session["session_id"], project_root=project, home=home)
            run = engine.start_generation_run(session["session_id"], project_root=project, home=home, confirmed=True)
            adapter = lambda request, references: {"image_bytes": self._fake_webp(), "provider_metadata": {"simulated": True}}
            partial = engine.execute_generation_run(run["run_id"], project_root=project, home=home, max_retries=0, adapter_callable=adapter)
            self.assertEqual(partial["jobs"][0]["status"], "failed")
            self.assertIn("not PNG", partial["jobs"][0]["error"])

    def test_success_after_model_qa_rejection_resets_model_qa_to_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = Path(tmp) / "project", Path(tmp) / "home"; project.mkdir()
            session = self._start_and_confirm(project, home, theme_id="TEST-QA-RETRY")
            session = engine.finalize_design_session(session["session_id"], project_root=project, home=home)
            run = engine.start_generation_run(session["session_id"], project_root=project, home=home, confirmed=True)
            adapter = lambda request, references: {"image_bytes": self._fake_png(), "provider_metadata": {"simulated": True}}
            first = engine.execute_generation_run(run["run_id"], project_root=project, home=home, adapter_callable=adapter)
            self.assertEqual(first["jobs"][0]["model_visual_qa"], "pending")
            rejected = engine.record_model_visual_qa(run["run_id"], "SHOT_01", "failed", project_root=project, findings=["illustrated person"])
            self.assertEqual(rejected["jobs"][0]["model_visual_qa"], "failed")
            retried = engine.execute_generation_run(run["run_id"], project_root=project, home=home, adapter_callable=adapter)
            self.assertEqual(retried["jobs"][0]["status"], "succeeded")
            self.assertEqual(retried["jobs"][0]["model_visual_qa"], "pending")

    def test_private_skill_executor_dry_run_contains_nine_distinct_n1_requests(self):
        theme = engine.new_semantic_theme("TEST-SKILL-RUN", "Skill run", native_4k=True, live_action=True)
        source = ROOT / "plugins/apsal-studio/assets/previews/character.webp"
        theme["distribution"] = "private_only"
        theme["references"] = [{
            "reference_id": "TEST_STYLE_REF_001", "original_filename": source.name,
            "original_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "uses": ["style"],
            "allowed_uses": ["palette", "material"], "forbidden_uses": ["identity", "pose", "exact composition", "text", "watermark"],
            "applies_to": [shot["shot_id"] for shot in theme["shots"]],
            "rights": {"copyright_status": "unverified", "portrait_rights": "not_applicable", "attribution": "Test", "redistribution_allowed": False},
        }]
        for shot in theme["shots"]: shot["reference_ids"] = ["TEST_STYLE_REF_001"]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive, _ = engine.pack_theme(theme, root / "packed", reference_paths={"TEST_STYLE_REF_001": source})
            with zipfile.ZipFile(archive) as package: package.extractall(root / "unpacked")
            skill_root = next((root / "unpacked").iterdir())
            run_dir = root / "run"
            result = subprocess.run([sys.executable, "scripts/generate_set.py", "--dry-run", "--run-dir", str(run_dir)], cwd=skill_root, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            requests = json.loads((run_dir / "requests.dry-run.json").read_text(encoding="utf-8"))
            run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(len(requests), 9)
            self.assertEqual({item["n"] for item in requests}, {1})
            self.assertEqual(len({item["prompt_digest"] for item in requests}), 9)
            self.assertTrue(all(item["reference_ids"] == ["TEST_STYLE_REF_001"] for item in requests))
            self.assertEqual(len(list((run_dir / "prompts").glob("*.prompt.txt"))), 9)
            self.assertEqual(run["adapter"], "openai-image-api")
            self.assertEqual(run["parameters"]["n"], 1)
            self.assertEqual(run["theme_digest"], engine.digest(theme))

if __name__ == "__main__": unittest.main()
