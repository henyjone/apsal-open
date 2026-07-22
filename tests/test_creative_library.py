import hashlib
import json
import os
import struct
import sys
import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "plugins" / "apsal-studio" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import apsal_creative as creative
import apsal_protocol as protocol
from apsal_engine import ValidationError


def fake_png(path: Path, rgb: tuple[int, int, int] = (40, 60, 80)) -> Path:
    raw = b"\x00" + bytes(rgb)

    def chunk(kind: bytes, payload: bytes) -> bytes:
        checksum = zlib.crc32(kind + payload) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)

    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
    return path


def confirmed_rights(*, redistribute: bool = False) -> dict:
    return {
        "copyright_status": "owned",
        "portrait_rights": "not_applicable",
        "redistribution_allowed": redistribute,
        "ai_modification_allowed": True,
        "identity_use_allowed": False,
        "attribution": "test owner",
    }


def image_analysis_result() -> dict:
    value = {
        key: []
        for key in ("observed", "inferred", "reference_roles", "locks", "variables", "risks", "uncertainties")
    }
    value["observed"] = ["soft side light", "muted warm palette"]
    value["elements"] = {role: {} for role in creative.ANALYSIS_ROLES}
    return value


def synthesis_result() -> dict:
    return {
        "common_visual_dna": ["quiet editorial restraint"],
        "conflicts": [],
        "complements": ["space and light reinforce the narrative"],
        "recommended_directions": ["quiet window-side editorial portrait"],
        "element_decisions": {role: {} for role in creative.ANALYSIS_ROLES},
    }


class CreativeLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.previous_home = os.environ.get("APSAL_HOME")
        os.environ["APSAL_HOME"] = str(self.root / "home")

    def tearDown(self):
        if self.previous_home is None:
            os.environ.pop("APSAL_HOME", None)
        else:
            os.environ["APSAL_HOME"] = self.previous_home
        self.temporary.cleanup()

    def create_project(self, name: str = "Reference Project", *, redistribute: bool = False):
        project = self.root / name.replace(" ", "-").lower()
        first = fake_png(self.root / f"{project.name}-one.png", (40, 60, 80))
        second = fake_png(self.root / f"{project.name}-two.png", (90, 70, 50))
        protocol.init_protocol_project(project)
        created = protocol.handle_domain_method(
            "project.create_from_references",
            {
                "project_root": str(project),
                "name": name,
                "references": [
                    {
                        "path": str(first),
                        "uses": ["style", "world", "composition"],
                        "role": "style",
                        "rights": confirmed_rights(redistribute=redistribute),
                    },
                    {
                        "path": str(second),
                        "uses": ["lighting", "color"],
                        "role": "lighting",
                        "rights": confirmed_rights(redistribute=redistribute),
                    },
                ],
                "expected_revision": 0,
                "operation_id": f"CREATE-{project.name.upper()}",
            },
        )
        return project, created

    def complete_analysis(self, project: Path, revision: int):
        started = protocol.handle_domain_method(
            "analysis.start",
            {
                "project_root": str(project),
                "expected_revision": revision,
                "operation_id": "ANALYSIS-START",
            },
        )
        analysis_id = started["analysis_id"]
        revision = started["revision"]
        seen = []
        while True:
            job = protocol.handle_domain_method(
                "analysis.next", {"project_root": str(project), "analysis_id": analysis_id}
            )
            if job.get("job_id") is None:
                break
            result = image_analysis_result() if job["kind"] == "image" else synthesis_result()
            recorded = protocol.handle_domain_method(
                "analysis.record",
                {
                    "project_root": str(project),
                    "analysis_id": analysis_id,
                    "job_id": job["job_id"],
                    "status": "succeeded",
                    "result": result,
                    "expected_revision": revision,
                    "operation_id": f"ANALYSIS-{len(seen) + 1}",
                },
            )
            seen.append(job["job_id"])
            revision = recorded["revision"]
        return analysis_id, revision, seen

    def test_multi_reference_analysis_is_resumable_schema_checked_and_builds_skill(self):
        project, created = self.create_project()
        references = created["references"]["references"]
        self.assertEqual(created["revision"], 1)
        self.assertEqual(len(references), 2)
        self.assertTrue(all("vault_uri" in item for item in references))
        self.assertFalse(any(item["identity_lock_allowed"] for item in references))

        analysis_id, revision, jobs = self.complete_analysis(project, created["revision"])
        self.assertEqual(len(jobs), 3)
        self.assertEqual(jobs[-1], "SET-SYNTHESIS")
        status = protocol.handle_domain_method(
            "analysis.status", {"project_root": str(project), "analysis_id": analysis_id}
        )
        self.assertEqual(status["status"], "completed")

        first_job = status["jobs"][0]
        replay = protocol.handle_domain_method(
            "analysis.record",
            {
                "project_root": str(project),
                "analysis_id": analysis_id,
                "job_id": first_job["job_id"],
                "status": "succeeded",
                "result": first_job["result"],
                "expected_revision": revision,
                "operation_id": "ANALYSIS-IDEMPOTENT",
            },
        )
        self.assertEqual(replay["revision"], revision + 1)
        revision = replay["revision"]

        built = protocol.handle_domain_method(
            "design.build_from_analysis",
            {
                "project_root": str(project),
                "analysis_id": analysis_id,
                "shot_count": 2,
                "language": "en",
                "expected_revision": revision,
                "operation_id": "BUILD-FROM-ANALYSIS",
            },
        )
        self.assertEqual(built["state"], "ready")
        self.assertEqual(built["theme_artifact"]["reference_count"], 2)
        self.assertTrue(Path(built["theme_artifact"]["prompt_package"]["path"]).is_file())
        self.assertEqual(built["snapshot"]["project"]["project_kind"], "root")

        with self.assertRaisesRegex(ValidationError, "thirteen APSAL roles"):
            creative._validate_analysis_result("image", {**image_analysis_result(), "elements": {}})
        with self.assertRaisesRegex(ValidationError, "strict schema"):
            creative._validate_analysis_result("image", {**image_analysis_result(), "unexpected": True})

    def test_failed_analysis_job_can_be_retried_and_identity_requires_portrait_authorization(self):
        project, created = self.create_project("Retry Project")
        started = protocol.handle_domain_method(
            "analysis.start",
            {
                "project_root": str(project),
                "expected_revision": created["revision"],
                "operation_id": "RETRY-START",
            },
        )
        first = protocol.handle_domain_method(
            "analysis.next", {"project_root": str(project), "analysis_id": started["analysis_id"]}
        )
        claimed = protocol.handle_domain_method(
            "analysis.status", {"project_root": str(project), "analysis_id": started["analysis_id"]}
        )
        self.assertEqual(claimed["jobs"][0]["status"], "in_progress")
        self.assertEqual(first["claim_status"], "claimed")
        self.assertEqual([event["type"] for event in claimed["activity"]], ["analysis_started", "job_claimed"])
        failed = protocol.handle_domain_method(
            "analysis.record",
            {
                "project_root": str(project), "analysis_id": started["analysis_id"],
                "job_id": first["job_id"], "status": "failed", "error": "temporary interruption",
                "expected_revision": started["revision"], "operation_id": "RETRY-FAIL",
            },
        )
        second = protocol.handle_domain_method(
            "analysis.next", {"project_root": str(project), "analysis_id": started["analysis_id"]}
        )
        succeeded = protocol.handle_domain_method(
            "analysis.record",
            {
                "project_root": str(project), "analysis_id": started["analysis_id"],
                "job_id": second["job_id"], "status": "succeeded", "result": image_analysis_result(),
                "expected_revision": failed["revision"], "operation_id": "RETRY-SECOND",
            },
        )
        retry = protocol.handle_domain_method(
            "analysis.next", {"project_root": str(project), "analysis_id": started["analysis_id"]}
        )
        self.assertEqual(retry["job_id"], first["job_id"])
        self.assertEqual(retry["attempt_count"], 1)
        self.assertEqual(retry["last_error"], "temporary interruption")
        self.assertEqual(retry["claim_status"], "claimed")
        recovered = protocol.handle_domain_method(
            "analysis.record",
            {
                "project_root": str(project), "analysis_id": started["analysis_id"],
                "job_id": retry["job_id"], "status": "succeeded", "result": image_analysis_result(),
                "expected_revision": succeeded["revision"], "operation_id": "RETRY-SUCCEED",
            },
        )
        self.assertEqual(recovered["status"], "analyzing")

        with self.assertRaisesRegex(ValidationError, "identity authorization"):
            creative._validate_rights(
                {**confirmed_rights(), "identity_use_allowed": True, "portrait_rights": "not_applicable"},
                ["identity"],
            )

    def test_fork_generation_library_export_import_and_share_handoff(self):
        project, created = self.create_project("Root Project")
        analysis_id, revision, _ = self.complete_analysis(project, created["revision"])
        built = protocol.handle_domain_method(
            "design.build_from_analysis",
            {
                "project_root": str(project),
                "analysis_id": analysis_id,
                "shot_count": 1,
                "expected_revision": revision,
                "operation_id": "BUILD-ROOT",
            },
        )
        revision = built["revision"]
        parent_before = hashlib.sha256((project / ".apsal" / "project.json").read_bytes()).hexdigest()
        child = self.root / "child-project"
        forked = protocol.handle_domain_method(
            "project.fork",
            {
                "project_root": str(project),
                "target_project_root": str(child),
                "name": "Light Variation",
                "fork_type": "lighting_variation",
                "source_asset_ids": [created["references"]["references"][0]["reference_id"]],
                "expected_revision": revision,
                "operation_id": "FORK-LIGHT",
            },
        )
        self.assertEqual(forked["project"]["project_kind"], "fork")
        self.assertEqual(forked["project"]["lineage"]["parent_project_id"], created["project"]["project_id"])
        self.assertEqual(forked["child_snapshot"]["session"]["session_id"], built["session_id"])
        self.assertEqual(hashlib.sha256((project / ".apsal" / "project.json").read_bytes()).hexdigest(), parent_before)

        run = protocol.handle_domain_method(
            "generation.start",
            {
                "project_root": str(project),
                "session_id": built["session_id"],
                "confirmed": True,
                "expected_revision": forked["revision"],
                "operation_id": "RUN-START",
            },
        )
        output = fake_png(self.root / "generated.png", (120, 100, 80))
        shot_id = run["jobs"][0]["shot_id"]
        recorded = protocol.handle_domain_method(
            "generation.record",
            {
                "project_root": str(project),
                "run_id": run["run_id"],
                "shot_id": shot_id,
                "status": "succeeded",
                "output_path": str(output),
                "expected_revision": run["revision"],
                "operation_id": "RUN-RESULT",
            },
        )
        generated_path = Path(recorded["jobs"][0]["output"]["path"])
        library = protocol.handle_domain_method("library.get", {"project_root": str(project)})
        outputs = [item for item in library["assets"] if item["kind"] == "output"]
        self.assertEqual(len(outputs), 1)
        self.assertTrue(Path(outputs[0]["archived_path"]).is_file())
        self.assertEqual(
            protocol.handle_domain_method("library.status", {"project_root": str(project)})["asset_count"],
            3,
        )
        lineage = protocol.handle_domain_method("library.lineage", {"project_root": str(child)})
        self.assertEqual(lineage["ancestors"][0]["project_id"], created["project"]["project_id"])
        self.assertTrue(lineage["comparison"]["available"])
        self.assertEqual(set(lineage["comparison"]["inherited"]), set(creative.ANALYSIS_ROLES))

        with self.assertRaisesRegex(ValidationError, "public-release confirmation"):
            protocol.handle_domain_method(
                "project.export",
                {"project_root": str(project), "distribution": "public", "output_dir": str(self.root / "exports")},
            )
        public_export = protocol.handle_domain_method(
            "project.export",
            {
                "project_root": str(project),
                "distribution": "public",
                "output_dir": str(self.root / "exports"),
                "confirmed_public": True,
            },
        )
        with zipfile.ZipFile(public_export["path"]) as archive:
            names = archive.namelist()
            payload = b"\n".join(archive.read(name) for name in names if not name.startswith("media/"))
        self.assertIn("index.html", names)
        self.assertIn("SKILL.md", names)
        self.assertFalse(any("assets/references/" in name for name in names))
        self.assertFalse(any(name.endswith(".zip") for name in names))
        self.assertNotIn(str(project).encode(), payload)
        self.assertNotIn(b"vault_uri", payload)
        self.assertIn("提示词示例".encode(), payload)
        self.assertIn("项目谱系".encode(), payload)
        self.assertIn("使用说明".encode(), payload)

        private_export = protocol.handle_domain_method(
            "project.export",
            {"project_root": str(project), "distribution": "private", "output_dir": str(self.root / "exports")},
        )
        imported_root = self.root / "imported"
        imported = protocol.handle_domain_method(
            "project.import",
            {"project_root": str(imported_root), "source": private_export["path"], "name": "Imported Copy"},
        )
        self.assertEqual(imported["project"]["project_kind"], "imported")
        self.assertNotEqual(imported["project"]["project_id"], created["project"]["project_id"])
        self.assertEqual(creative.load_project_references(imported_root)["reference_count"], 2)

        draft = protocol.handle_domain_method(
            "share.draft",
            {
                "project_root": str(project),
                "platform": "xiaohongshu",
                "image_paths": [str(generated_path)],
                "expected_revision": recorded["revision"],
                "operation_id": "SHARE-DRAFT",
            },
        )
        confirmed = protocol.handle_domain_method(
            "share.confirm",
            {
                "project_root": str(project),
                "share_id": draft["share_id"],
                "confirmed_public": True,
                "expected_revision": draft["revision"],
                "operation_id": "SHARE-CONFIRM",
            },
        )
        handoff = protocol.handle_domain_method(
            "share.publish",
            {
                "project_root": str(project),
                "share_id": draft["share_id"],
                "confirmation_token": confirmed["confirmation_token"],
                "expected_revision": confirmed["revision"],
                "operation_id": "SHARE-PUBLISH",
            },
        )
        self.assertEqual(handoff["status"], "awaiting_external_confirmation")
        self.assertFalse(handoff["publication"]["published"])
        self.assertIn("APSAL", handoff["publication"]["copy_text"])
        self.assertEqual(len(handoff["publication"]["exported_images"]), 1)
        self.assertTrue(Path(handoff["publication"]["exported_images"][0]).is_file())

    def test_legacy_project_copy_migration_never_changes_source(self):
        source = self.root / "legacy"
        workspace = source / ".apsal"
        workspace.mkdir(parents=True)
        legacy = {
            "schema_version": "0.15.0",
            "protocol_version": "0.15.0",
            "engine_version": "0.15.0",
            "project_id": "PROJECT-LEGACY015",
            "revision": 7,
            "storage": "local_first",
        }
        source_bytes = json.dumps(legacy, sort_keys=True).encode()
        (workspace / "project.json").write_bytes(source_bytes)
        target = self.root / "migrated"

        preview = protocol.handle_domain_method(
            "project.migration_preview",
            {"project_root": str(source), "target_project_root": str(target)},
        )
        self.assertEqual(preview["mode"], "copy_preserving_original")
        with self.assertRaisesRegex(ValidationError, "explicit migration confirmation"):
            protocol.handle_domain_method(
                "project.migrate",
                {"project_root": str(source), "target_project_root": str(target), "confirmed": False},
            )
        migrated = protocol.handle_domain_method(
            "project.migrate",
            {"project_root": str(source), "target_project_root": str(target), "confirmed": True},
        )
        self.assertEqual((workspace / "project.json").read_bytes(), source_bytes)
        self.assertEqual(migrated["project"]["protocol_version"], "0.16.0")
        self.assertEqual(migrated["project"]["lineage"]["origin_project_id"], legacy["project_id"])

    def test_x_publication_uses_official_media_and_post_endpoints_without_network(self):
        image = fake_png(self.root / "x-post.png")
        content = {
            "images": [{"path": str(image)}],
            "text": "APSAL traceable photography project",
            "hashtags": ["APSAL", "AIPhotography"],
            "project_url": "https://example.test/apsal-project",
        }
        with patch.object(creative, "_x_request", side_effect=[
            {"data": {"id": "MEDIA-123"}},
            {"data": {"id": "POST-456"}},
        ]) as request:
            published = creative._publish_x(content, "keychain-user-token")
        self.assertEqual(published["remote_id"], "POST-456")
        self.assertEqual(request.call_count, 2)
        media_call, post_call = request.call_args_list
        self.assertEqual(media_call.args[0], "https://api.x.com/2/media/upload")
        self.assertEqual(media_call.args[1], "keychain-user-token")
        self.assertEqual(media_call.args[2]["media_category"], "tweet_image")
        self.assertNotIn("keychain-user-token", json.dumps(media_call.args[2]))
        self.assertEqual(post_call.args[0], "https://api.x.com/2/tweets")
        self.assertEqual(post_call.args[2]["media"]["media_ids"], ["MEDIA-123"])
        self.assertTrue(post_call.args[2]["made_with_ai"])

        oversized = self.root / "oversized.png"
        with oversized.open("wb") as handle:
            handle.truncate(creative.X_MAX_IMAGE_BYTES + 1)
        with self.assertRaisesRegex(ValidationError, "5 MB"):
            creative._publish_x({**content, "images": [{"path": str(oversized)}]}, "token")


if __name__ == "__main__":
    unittest.main()
