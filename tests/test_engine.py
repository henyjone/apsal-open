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

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("apsal_engine", ROOT / "plugins/apsal-studio/scripts/apsal_engine.py")
engine = importlib.util.module_from_spec(spec); spec.loader.exec_module(engine)

class EngineTests(unittest.TestCase):
    def test_catalog_is_complete_and_open(self): self.assertEqual(engine.validate_catalog(), [])
    def test_semantic_registry_covers_roles_categories_and_fields(self): self.assertEqual(engine.validate_semantic_registry(), [])
    def test_five_layers_cover_all_thirteen_roles_and_seven_dna_types_once(self):
        self.assertEqual(engine.validate_creative_layers(), [])
        self.assertEqual([role for layer in engine.CREATIVE_LAYERS for role in engine.LAYER_ROLES[layer]], list(dict.fromkeys(role for layer in engine.CREATIVE_LAYERS for role in engine.LAYER_ROLES[layer])))
        self.assertEqual({role for layer in engine.CREATIVE_LAYERS for role in engine.LAYER_ROLES[layer]}, set(engine.PROTOCOL_TYPES))
        self.assertEqual({kind for layer in engine.CREATIVE_LAYERS for kind in engine.LAYER_TYPES[layer]}, set(engine.CATEGORIES))
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
        self.assertEqual(engine.load_yaml_text(engine.dump_yaml({"values": ["Tone: quiet joy"], "empty": [], "object": {}})), {"values": ["Tone: quiet joy"], "empty": [], "object": {}})

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
                self.assertEqual(len([name for name in z.namelist() if name.endswith(".full.txt")]), 9)
                self.assertTrue(any(name.endswith("scripts/validate_prompt_pack.py") for name in z.namelist()))
                self.assertFalse(any(name.endswith("scripts/generate_set.py") for name in z.namelist()))
                self.assertTrue(any(name.endswith("PROMPT_GUIDE.md") for name in z.namelist()))
                skill = next(name for name in z.namelist() if name.endswith("SKILL.md"))
                skill_text = z.read(skill).decode()
                self.assertIn("built-in image-generation", skill_text)
                self.assertIn("Do not call an image API", skill_text)

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
            self.assertEqual(item["visual_qa_status"], "human_review_pending")
            self.assertTrue(item["rights"]["ai_disclosure"])
            self.assertEqual(item["rights"]["reference_media"], "none")

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
        for layer in engine.CREATIVE_LAYERS:
            refs = [engine.asset_ref(item) for item in assets if item["type"] in engine.LAYER_TYPES[layer]]
            session = engine.commit_element_layer(session["session_id"], layer, refs, project_root=project, home=home)
        return session

    def _confirm_direction(self, session, project: Path, home: Path):
        return engine.commit_element_layer(session["session_id"], "direction", [], project_root=project, home=home)

    def test_direction_classifies_emotion_and_requires_creator_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = Path(tmp) / "project", Path(tmp) / "home"; project.mkdir()
            session = engine.start_design_session("设计一套欢喜、明亮但克制的九张窗边真人摄影", project_root=project, home=home, theme_id="TEST-MOOD")
            layer = engine.present_element_layer(session["session_id"], "direction", project_root=project)
            self.assertEqual([card["role"] for card in layer["cards"]], ["content", "emotion"])
            emotion = next(card for card in layer["cards"] if card["role"] == "emotion")
            self.assertEqual(emotion["values"]["primary_tone"], "quiet_joy")
            self.assertEqual(set(emotion["values"]["arc"]), {"start", "turn", "end"})
            self.assertEqual(emotion["status"], "proposed")
            with self.assertRaisesRegex(engine.ValidationError, "all five creative layers"):
                engine.finalize_design_session(session["session_id"], project_root=project, home=home)
            confirmed = engine.commit_element_layer(session["session_id"], "direction", [], project_root=project, home=home)
            self.assertEqual(confirmed["state"], "worldbuilding_pending")
            _, theme = engine.load_design_session(session["session_id"], project)
            self.assertTrue(all(theme["element_decisions"][role]["source"] == "creator_confirmed" for role in ("content", "emotion")))

            mixed = engine.propose_element_decisions("悲伤中仍然保留希望", engine.new_semantic_theme("TEST-MIXED", "Mixed"))["emotion"]["values"]
            self.assertEqual(mixed["primary_tone"], "sorrow")
            self.assertIn("hope", mixed["secondary_tones"])
            self.assertEqual(mixed["valence"], "mixed")

    def test_bilingual_session_auto_detection_ambiguity_and_switch_are_presentation_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = Path(tmp) / "project", Path(tmp) / "home"; project.mkdir()
            english = engine.start_design_session(
                "Create a restrained live-action portrait story beside a window",
                project_root=project, home=home, theme_id="TEST-LANGUAGE-EN",
            )
            self.assertEqual(english["language"]["code"], "en")
            layer = engine.present_element_layer(english["session_id"], "direction", project_root=project)
            self.assertEqual(layer["language"], "en")
            self.assertEqual(layer["title"], "Direction and Emotion")
            self.assertEqual(layer["cards"][0]["title"], "Content")

            ambiguous = engine.start_design_session("APSAL", project_root=project, home=home, theme_id="TEST-LANGUAGE-PENDING")
            self.assertEqual(ambiguous["language"]["status"], "pending")
            with self.assertRaisesRegex(engine.ValidationError, "English or Chinese|English 或中文"):
                engine.present_element_layer(ambiguous["session_id"], "direction", project_root=project)
            selected = engine.set_session_language(ambiguous["session_id"], "zh-CN", project_root=project)
            self.assertEqual(selected["language"]["code"], "zh-CN")
            self.assertEqual(engine.present_element_layer(ambiguous["session_id"], "direction", project_root=project)["title"], "创作命题与情绪")

            confirmed = self._start_and_confirm(project, home, theme_id="TEST-LANGUAGE-DIGEST")
            before_session, before_theme = engine.load_design_session(confirmed["session_id"], project)
            before_compiled = engine.compile_theme(before_theme, "image")
            switched = engine.set_session_language(confirmed["session_id"], "en", project_root=project)
            after_session, after_theme = engine.load_design_session(confirmed["session_id"], project)
            after_compiled = engine.compile_theme(after_theme, "image")
            self.assertEqual(before_session["theme_digest"], switched["theme_digest"])
            self.assertEqual(before_session["theme_digest"], after_session["theme_digest"])
            self.assertEqual(before_compiled["compiled_digest"], after_compiled["compiled_digest"])

    def test_cannot_skip_layers_and_each_layer_recommends_its_required_dna_types(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = Path(tmp) / "project", Path(tmp) / "home"; project.mkdir()
            session = engine.start_design_session("悲伤但克制的室内真人摄影", project_root=project, home=home, theme_id="TEST-ORDER")
            assets = engine.load_catalog()["assets"]
            refs = [engine.asset_ref(item) for item in assets if item["type"] in engine.LAYER_TYPES["worldbuilding"]]
            with self.assertRaisesRegex(engine.ValidationError, "confirm direction"):
                engine.commit_element_layer(session["session_id"], "worldbuilding", refs, project_root=project, home=home)
            for layer in engine.CREATIVE_LAYERS:
                recommendation = engine.recommend_layer_dna(session["brief"], layer, project_root=project, home=home, session_id=session["session_id"])
                self.assertEqual(set(recommendation["by_type"]), set(engine.LAYER_TYPES[layer]))
                self.assertTrue(all(recommendation["by_type"][kind] for kind in engine.LAYER_TYPES[layer]))

    def test_final_theme_compiles_confirmed_thirteen_elements_into_image_and_qa(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = Path(tmp) / "project", Path(tmp) / "home"; project.mkdir()
            session = self._start_and_confirm(project, home, theme_id="TEST-THIRTEEN")
            _, theme = engine.load_design_session(session["session_id"], project)
            self.assertEqual(set(theme["element_decisions"]), set(engine.PROTOCOL_TYPES))
            self.assertTrue(all(item["status"] == "confirmed" for item in theme["element_decisions"].values()))
            image = engine.compile_theme(theme, "image")
            qa = engine.compile_theme(theme, "qa")
            first = image["shots"][0]["positive_prompt"]
            self.assertIn("APSAL CONFIRMED ELEMENT DESIGN", first)
            self.assertIn("LIGHT:", first)
            self.assertIn("COLOR POST:", first)
            self.assertIn("EMOTION:", first)
            covered = {check["source"].removeprefix("element_decisions.") for check in qa["global_checks"] if check.get("source", "").startswith("element_decisions.")}
            self.assertEqual(covered, set(engine.PROTOCOL_TYPES))

    def test_legacy_four_stage_session_remains_readable_and_finalizable(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = Path(tmp) / "project", Path(tmp) / "home"; project.mkdir(); engine.init_workspace(project, home)
            theme = engine.new_semantic_theme("TEST-LEGACY-SESSION", "Legacy", native_4k=True, live_action=True)
            session = {
                "schema_version": "0.6.0", "session_id": "SESSION-LEGACY-060", "brief": "legacy session",
                "project_root": str(project.resolve()), "state": "character_pending", "shot_count": 9,
                "stages": {stage: {"status": "pending", "selection": [], "confirmed_at": None} for stage in engine.INTERACTION_STAGES},
                "private_references": [], "memory_offers": [], "invalidations": [],
                "created_at": "2026-07-16T00:00:00Z", "updated_at": "2026-07-16T00:00:00Z", "theme_artifact": None,
            }
            engine._write_session(session, theme, project)
            assets = engine.load_catalog()["assets"]
            for stage in engine.INTERACTION_STAGES:
                refs = [engine.asset_ref(item) for item in assets if item["type"] in engine.STAGE_TYPES[stage]]
                session = engine.commit_session_stage(session["session_id"], stage, refs, project_root=project, home=home)
            self.assertEqual(session["state"], "review_pending")
            ready = engine.finalize_design_session(session["session_id"], project_root=project, home=home)
            self.assertEqual(ready["state"], "ready")

    def test_element_contract_rejects_weakening_delivery_and_visual_qa_rules(self):
        theme = engine.new_semantic_theme("TEST-ELEMENT-GUARD", "Guard")
        decisions = engine.propose_element_decisions("安静人像", theme)
        decisions["job"]["values"]["one_job_one_image"] = False
        decisions["quality_control"]["values"]["human_visual_qa"] = "visual_qa_passed"
        errors = engine.validate_element_decisions(decisions, require_confirmed=False)
        self.assertTrue(any("one_job_one_image" in error for error in errors))
        self.assertTrue(any("cannot pass without evidence" in error for error in errors))

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
            assets = engine.load_catalog()["assets"]
            refs = [engine.asset_ref(custom)] + [engine.asset_ref(item) for item in assets if item["type"] == "environment"]
            changed = engine.commit_element_layer(session["session_id"], "worldbuilding", refs, project_root=project, home=home)
            self.assertEqual(changed["state"], "narrative_pending")
            self.assertEqual(changed["layers"]["worldbuilding"]["status"], "confirmed")
            self.assertTrue(all(changed["layers"][name]["status"] == "pending" for name in ("narrative", "image", "delivery")))
            self.assertEqual({item["invalidated"] for item in changed["invalidations"]}, {"narrative", "image", "delivery"})

    def test_confirmed_natural_language_draft_becomes_project_dna_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = Path(tmp) / "project", Path(tmp) / "home"; project.mkdir()
            session = engine.start_design_session("设计人物", project_root=project, home=home, theme_id="TEST-DRAFT")
            session = self._confirm_direction(session, project, home)
            draft = self._custom_asset(namespace="mine")
            assets = engine.load_catalog()["assets"]
            refs = [engine.asset_ref(draft)] + [engine.asset_ref(item) for item in assets if item["type"] == "environment"]
            session = engine.commit_element_layer(session["session_id"], "worldbuilding", refs, project_root=project, home=home, draft_assets=[draft])
            self.assertEqual(session["state"], "narrative_pending")
            self.assertEqual(next(ref for ref in session["layers"]["worldbuilding"]["selection"] if ref["type"] == "character")["id"], draft["id"])
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
            session = self._confirm_direction(session, project, home)
            draft = self._custom_asset(namespace="maker")
            discovery = engine.suggest_discovery_metadata(draft, session["brief"])
            draft["discovery"] = engine.confirm_discovery_metadata(discovery)
            assets = engine.load_catalog()["assets"]
            refs = [engine.asset_ref(draft)] + [engine.asset_ref(item) for item in assets if item["type"] == "environment"]
            session = engine.commit_element_layer(session["session_id"], "worldbuilding", refs, project_root=project, home=home, draft_assets=[draft])
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
            refs = [engine.asset_ref(item) for item in assets if item["type"] in engine.LAYER_TYPES["narrative"]]
            changed = engine.commit_element_layer(session["session_id"], "narrative", refs, project_root=project, home=home, shots=shots)
            self.assertEqual(changed["state"], "image_pending")
            self.assertEqual(changed["layers"]["image"]["status"], "pending")

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
            package = Path(ready["theme_artifact"]["prompt_package"]["path"])
            self.assertTrue(package.is_file())
            self.assertEqual(hashlib.sha256(package.read_bytes()).hexdigest(), ready["theme_artifact"]["prompt_package"]["sha256"])
            with zipfile.ZipFile(package) as archive:
                names = archive.namelist()
                self.assertTrue(any(name.endswith("PROMPT_GUIDE.md") for name in names))
                self.assertEqual(len([name for name in names if name.endswith(".full.txt")]), 9)
            again = engine.finalize_design_session(session["session_id"], project_root=project, home=home)
            self.assertEqual(again["theme_artifact"]["digest"], ready["theme_artifact"]["digest"])
            self.assertEqual(again["theme_artifact"]["prompt_package"]["sha256"], ready["theme_artifact"]["prompt_package"]["sha256"])

    def test_generation_requires_confirmation_and_preserves_success_on_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = Path(tmp) / "project", Path(tmp) / "home"; project.mkdir()
            session = self._start_and_confirm(project, home)
            session = engine.finalize_design_session(session["session_id"], project_root=project, home=home)
            with self.assertRaisesRegex(engine.ValidationError, "explicit confirmation"):
                engine.start_generation_run(session["session_id"], project_root=project, home=home)
            with self.assertRaisesRegex(engine.ValidationError, "Codex manages image parameters"):
                engine.start_generation_run(session["session_id"], project_root=project, home=home, confirmed=True, parameters={"n": 9})
            self.assertEqual(list((project / ".apsal/runs").iterdir()), [])
            run = engine.start_generation_run(session["session_id"], project_root=project, home=home, confirmed=True)
            self.assertEqual(len(run["jobs"]), 9)
            self.assertFalse(run["direct_api_calls"])
            self.assertFalse(run["api_key_required"])
            self.assertFalse(run["returned_dimensions_guaranteed"])
            self.assertFalse(run["output_contract"]["provider_native"])
            self.assertEqual(run["output_contract"]["size"], "not_guaranteed")
            self.assertEqual(len(list((project / ".apsal/runs" / run["run_id"] / "prompts").glob("*.txt"))), 18)
            output = Path(tmp) / "shot.png"; output.write_bytes(self._fake_png())
            run = engine.record_generation_result(run["run_id"], "SHOT_01", "succeeded", project_root=project, output_path=output)
            self.assertEqual(run["status"], "generating")
            self.assertEqual(run["jobs"][0]["output"]["width"], 2160)
            run = engine.record_generation_result(run["run_id"], "SHOT_03", "succeeded", project_root=project, artifact_uri="not_reported")
            self.assertEqual(run["jobs"][2]["output"]["sha256"], "not_reported")
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

    def test_mcp_lists_twenty_one_tools_and_returns_text_only_card_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = Path(tmp) / "project", Path(tmp) / "home"; project.mkdir()
            session = engine.start_design_session("欢喜但克制的窗边真人摄影", project_root=project, home=home, theme_id="TEST-MCP-ELEMENTS")
            reference = ROOT / "plugins/apsal-studio/assets/previews/character.webp"
            engine.store_private_reference(reference, home=home)
            legacy_archive, _ = self._legacy_run_zip(Path(tmp), reference)
            requests = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "present_dna_cards", "arguments": {"project_root": str(project), "stage": "character"}}},
                {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "present_element_layer", "arguments": {"project_root": str(project), "session_id": session["session_id"], "layer": "direction"}}},
                {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "import_apsal_package", "arguments": {"project_root": str(project), "source": str(legacy_archive)}}},
            ]
            env = {**os.environ, "APSAL_HOME": str(home)}
            process = subprocess.run([sys.executable, "scripts/apsal_mcp.py"], cwd=ROOT / "plugins/apsal-studio", input="".join(json.dumps(item) + "\n" for item in requests), text=True, capture_output=True, env=env, check=True)
            responses = [json.loads(line) for line in process.stdout.splitlines()]
            self.assertEqual(responses[0]["result"]["serverInfo"]["version"], "0.10.0")
            self.assertEqual(len(responses[1]["result"]["tools"]), 21)
            names = {item["name"] for item in responses[1]["result"]["tools"]}
            self.assertIn("set_session_language", names)
            self.assertIn("get_next_codex_job", names)
            self.assertIn("import_apsal_package", names)
            self.assertIn("bind_import_reference", names)
            self.assertNotIn("execute_generation_run", names)
            cards = responses[2]["result"]["structuredContent"]["cards"]
            self.assertEqual(len(cards), 1)
            self.assertNotIn("preview", cards[0])
            self.assertNotIn("preview_metadata", cards[0])
            self.assertIn("change_summary", cards[0]["summary"] if isinstance(cards[0]["summary"], dict) else {"change_summary": cards[0]["summary"]})
            elements = responses[3]["result"]["structuredContent"]["cards"]
            self.assertEqual([card["role"] for card in elements], ["content", "emotion"])
            self.assertTrue(all("values" in card and "observable" in card and "qa_expectations" in card for card in elements))
            self.assertNotIn("preview", json.dumps(elements))
            imported = responses[4]["result"]["structuredContent"]
            self.assertTrue(imported["ready_for_codex"])
            self.assertEqual(imported["next_job"]["shot_id"], "SHOT_01")

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

    def test_codex_run_prepares_one_job_at_a_time_and_uses_recent_identity_anchor(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = Path(tmp) / "project", Path(tmp) / "home"; project.mkdir()
            session = self._start_and_confirm(project, home, theme_id="TEST-CODEX-RUN")
            session = engine.finalize_design_session(session["session_id"], project_root=project, home=home)
            run = engine.start_generation_run(session["session_id"], project_root=project, home=home, confirmed=True)
            first = engine.get_next_codex_job(run["run_id"], project_root=project, home=home)
            self.assertEqual(first["shot_id"], "SHOT_01")
            self.assertEqual(first["codex_tool"], "built_in_image_generation")
            self.assertEqual(set(first["codex_tool_arguments"]), {"prompt"})
            self.assertFalse(first["direct_api_calls"])
            run = engine.record_generation_result(run["run_id"], "SHOT_01", "succeeded", project_root=project, artifact_uri="not_reported", provider_metadata={"surface": "codex_imagegen"})
            with self.assertRaisesRegex(engine.ValidationError, "Codex visual QA"):
                engine.get_next_codex_job(run["run_id"], project_root=project, home=home)
            engine.record_model_visual_qa(run["run_id"], "SHOT_01", "passed", project_root=project, findings=["real adult human"])
            second = engine.get_next_codex_job(run["run_id"], project_root=project, home=home)
            self.assertEqual(second["shot_id"], "SHOT_02")
            self.assertEqual(second["identity_anchor"], "recent_previous_image")
            self.assertEqual(second["codex_tool_arguments"]["num_last_images_to_include"], 1)
            self.assertIn("do not inherit its pose", second["prompt"])

    def test_direct_image_api_execution_is_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = Path(tmp) / "project", Path(tmp) / "home"; project.mkdir()
            session = self._start_and_confirm(project, home, theme_id="TEST-NO-API")
            session = engine.finalize_design_session(session["session_id"], project_root=project, home=home)
            with self.assertRaisesRegex(engine.ValidationError, "direct image API adapters are disabled"):
                engine.start_generation_run(session["session_id"], project_root=project, home=home, confirmed=True, adapter="openai-image-api")
            run = engine.start_generation_run(session["session_id"], project_root=project, home=home, confirmed=True)
            with self.assertRaisesRegex(engine.ValidationError, "direct provider execution was removed"):
                engine.execute_generation_run(run["run_id"], project_root=project)
            source = (ROOT / "plugins/apsal-studio/scripts/apsal_engine.py").read_text(encoding="utf-8")
            self.assertNotIn("/v1/images/generations", source)
            self.assertNotIn('os.environ.get("OPENAI_API_KEY")', source)

    def test_codex_result_accepts_reported_non_4k_without_false_guarantee(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = Path(tmp) / "project", Path(tmp) / "home"; project.mkdir()
            session = self._start_and_confirm(project, home, theme_id="TEST-CODEX-SIZE")
            session = engine.finalize_design_session(session["session_id"], project_root=project, home=home)
            self.assertEqual(session["theme_artifact"]["output"]["size"], "not_guaranteed")
            self.assertEqual(session["theme_artifact"]["output"]["requested_size"], "2160x3840")
            run = engine.start_generation_run(session["session_id"], project_root=project, home=home, confirmed=True)
            output = Path(tmp) / "codex-output.png"; output.write_bytes(self._fake_png(1024, 1792))
            run = engine.record_generation_result(run["run_id"], "SHOT_01", "succeeded", project_root=project, output_path=output)
            self.assertEqual(run["jobs"][0]["output"]["width"], 1024)
            self.assertFalse(run["returned_dimensions_guaranteed"])

    def test_codex_job_uses_local_references_without_mixing_recent_image_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = Path(tmp) / "project", Path(tmp) / "home"; project.mkdir()
            session = engine.start_design_session("安静窗边真人摄影", project_root=project, home=home, theme_id="TEST-CODEX-REF")
            assets = engine.load_catalog()["assets"]
            session = engine.commit_element_layer(session["session_id"], "direction", [], project_root=project, home=home)
            refs = [engine.asset_ref(item) for item in assets if item["type"] in engine.LAYER_TYPES["worldbuilding"]]
            source = ROOT / "plugins/apsal-studio/assets/previews/character.webp"
            session = engine.commit_element_layer(session["session_id"], "worldbuilding", refs, project_root=project, home=home, reference_path=source)
            for layer in ("narrative", "image", "delivery"):
                refs = [engine.asset_ref(item) for item in assets if item["type"] in engine.LAYER_TYPES[layer]]
                session = engine.commit_element_layer(session["session_id"], layer, refs, project_root=project, home=home)
            session = engine.finalize_design_session(session["session_id"], project_root=project, home=home)
            run = engine.start_generation_run(session["session_id"], project_root=project, home=home, confirmed=True)
            job = engine.get_next_codex_job(run["run_id"], project_root=project, home=home)
            self.assertIn("referenced_image_paths", job["codex_tool_arguments"])
            self.assertNotIn("num_last_images_to_include", job["codex_tool_arguments"])
            self.assertTrue(all(Path(path).is_file() for path in job["reference_paths"]))

    def test_prompt_skill_package_validates_and_contains_documented_prompts(self):
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
            result = subprocess.run([sys.executable, "scripts/validate_prompt_pack.py", "--list"], cwd=skill_root, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            listing = json.loads(result.stdout)
            self.assertEqual(len(listing["jobs"]), 9)
            self.assertTrue(all(item["reference_ids"] == ["TEST_STYLE_REF_001"] for item in listing["jobs"]))
            self.assertEqual(len(list((skill_root / "prompts").glob("*.prompt.txt"))), 9)
            self.assertEqual(len(list((skill_root / "prompts").glob("*.negative.txt"))), 9)
            self.assertEqual(len(list((skill_root / "prompts").glob("*.full.txt"))), 9)
            manifest = json.loads((skill_root / "references/manifest.json").read_text(encoding="utf-8"))
            self.assertFalse(manifest["direct_api_calls"])
            self.assertFalse(manifest["api_key_required"])
            self.assertFalse(manifest["returned_dimensions_guaranteed"])
            guide_index = (skill_root / "PROMPT_GUIDE.md").read_text(encoding="utf-8")
            guide_zh = (skill_root / "PROMPT_GUIDE.zh-CN.md").read_text(encoding="utf-8")
            guide_en = (skill_root / "PROMPT_GUIDE.en.md").read_text(encoding="utf-8")
            self.assertIn("PROMPT_GUIDE.en.md", guide_index)
            self.assertIn("继续下一张", guide_zh)
            self.assertIn("不需要 `OPENAI_API_KEY`", guide_zh)
            self.assertIn("continue to the next image", guide_en)
            self.assertIn("does not require `OPENAI_API_KEY`", guide_en)

    @staticmethod
    def _legacy_run_zip(root: Path, reference: Path, *, include_reference: bool = False) -> tuple[Path, str]:
        reference_data = reference.read_bytes(); reference_sha = hashlib.sha256(reference_data).hexdigest()
        run = {
            "schema_version": "0.5.0", "run_id": "RUN-LEGACY-001", "session_id": "SESSION-LEGACY-001",
            "mode": "prompts", "status": "completed",
            "theme": {"path": "/private/old-machine/theme", "theme_id": "APSAL-LEGACY-GARDEN", "version": "1.0.0", "distribution": "private_only"},
            "dna": [], "engine_version": "0.6.0", "adapter": "openai-image-api", "model": "gpt-image-2",
            "parameters": {"size": "2160x3840", "quality": "high", "output_format": "png", "n": 1},
            "output_contract": {"count": 2, "aspect_ratio": "9:16", "size": "2160x3840", "quality": "high", "format": "png", "provider_native": True, "independent_images": True, "forbid": ["grid", "text"]},
            "rendering_contract": engine.live_action_rendering_contract(),
            "reference_manifest": {"references": [{
                "reference_id": "REF_LEGACY_001", "original_sha256": reference_sha, "sha256": reference_sha,
                "original_filename": reference.name, "uses": ["style"], "allowed_uses": ["palette", "material"],
                "forbidden_uses": ["identity", "pose", "exact composition"], "applies_to": ["*"],
                "rights": {"license": "unconfirmed", "redistribution_allowed": False},
            }]},
            "jobs": [
                {"shot_id": shot_id, "status": "saved", "prompt_digest": "0" * 64, "reference_ids": ["REF_LEGACY_001"], "attempts": [], "output": None, "error": None, "model_visual_qa": "pending", "human_visual_qa": "pending"}
                for shot_id in ("SHOT_01", "SHOT_02")
            ],
        }
        archive = root / "legacy-run.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as package:
            package.writestr("run.json", json.dumps(run, ensure_ascii=False))
            for shot_id in ("SHOT_01", "SHOT_02"):
                package.writestr(f"prompts/{shot_id}.prompt.txt", f"Live-action finished photograph for {shot_id}.\n")
                package.writestr(f"prompts/{shot_id}.negative.txt", "no illustration, no grid, no text\n")
            if include_reference: package.writestr(f"assets/references/{reference.name}", reference_data)
        return archive, reference_sha

    def test_legacy_run_zip_recovers_vault_reference_and_becomes_codex_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); project, home = root / "project", root / "home"; project.mkdir()
            reference = ROOT / "plugins/apsal-studio/assets/previews/character.webp"
            stored = engine.store_private_reference(reference, home=home)
            archive, expected_sha = self._legacy_run_zip(root, reference)
            self.assertEqual(stored["sha256"], expected_sha)
            result = engine.import_apsal_package(archive, project_root=project, home=home)
            run = result["run"]
            self.assertTrue(result["ready_for_codex"])
            self.assertEqual(run["adapter"], "codex-imagegen")
            self.assertEqual(run["source"]["historical_adapter"], "openai-image-api")
            self.assertFalse(run["output_contract"]["provider_native"])
            self.assertEqual(run["reference_manifest"]["references"][0]["recovered_from"], "local_vault")
            self.assertEqual(result["next_job"]["shot_id"], "SHOT_01")
            self.assertIn("referenced_image_paths", result["next_job"]["codex_tool_arguments"])
            self.assertIn("Do not show code, JSON, a terminal", result["next_job"]["prompt"])
            skill_zip = Path(run["prompt_package"]["path"]); self.assertTrue(skill_zip.is_file())
            with zipfile.ZipFile(skill_zip) as package:
                self.assertTrue(any(name.endswith("PROMPT_GUIDE.md") for name in package.namelist()))
                self.assertTrue(any(name.endswith("PROMPT_GUIDE.en.md") for name in package.namelist()))
                self.assertTrue(any(name.endswith("PROMPT_GUIDE.zh-CN.md") for name in package.namelist()))
                self.assertTrue(any("assets/references/REF_LEGACY_001" in name for name in package.namelist()))
                self.assertFalse(any(name.endswith("generate_set.py") for name in package.namelist()))
                package.extractall(root / "skill")
            skill_root = next((root / "skill").iterdir())
            validation = subprocess.run([sys.executable, "scripts/validate_prompt_pack.py", "--list"], cwd=skill_root, text=True, capture_output=True)
            self.assertEqual(validation.returncode, 0, validation.stderr)
            self.assertEqual(len(json.loads(validation.stdout)["jobs"]), 2)

    def test_legacy_run_import_asks_only_for_missing_reference_then_binds_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); project, home = root / "project", root / "empty-home"; project.mkdir()
            reference = ROOT / "plugins/apsal-studio/assets/previews/character.webp"
            archive, _ = self._legacy_run_zip(root, reference)
            result = engine.import_apsal_package(archive, project_root=project, home=home)
            self.assertFalse(result["ready_for_codex"])
            self.assertEqual([item["reference_id"] for item in result["missing_references"]], ["REF_LEGACY_001"])
            run_id = result["run"]["run_id"]
            with self.assertRaisesRegex(engine.ValidationError, "reattach missing reference"):
                engine.get_next_codex_job(run_id, project_root=project, home=home)
            rebound = engine.bind_import_reference(run_id, "REF_LEGACY_001", reference, project_root=project)
            self.assertTrue(rebound["ready_for_codex"])
            self.assertEqual(rebound["next_job"]["shot_id"], "SHOT_01")
            self.assertTrue(Path(rebound["run"]["prompt_package"]["path"]).is_file())

    def test_legacy_run_import_rejects_archive_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); project = root / "project"; project.mkdir(); archive = root / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("run.json", "{}")
                package.writestr("../escape.txt", "unsafe")
            with self.assertRaisesRegex(engine.ValidationError, "unsafe APSAL package path"):
                engine.import_apsal_package(archive, project_root=project, home=root / "home")

if __name__ == "__main__": unittest.main()
