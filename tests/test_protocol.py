import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "plugins/apsal-studio/scripts"
sys.path.insert(0, str(SCRIPTS))

import apsal_protocol as protocol
import apsal_engine as engine
import apsal_frontend
import apsal_mcp
from apsal_engine import ValidationError


class ProtocolTests(unittest.TestCase):
    def _rpc(self, method, params, env=None):
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS / "apsal_rpc.py")],
            input=json.dumps({"jsonrpc": "2.0", "id": 9, "method": method, "params": params}) + "\n",
            text=True,
            capture_output=True,
            check=True,
            env=env,
        )
        response = json.loads(completed.stdout)
        if response.get("error"):
            raise AssertionError(response["error"])
        return response["result"]

    def test_project_preview_commit_idempotency_view_and_undo(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            initialized = protocol.init_protocol_project(project)
            self.assertEqual(initialized["project"]["revision"], 0)
            self.assertEqual(initialized["project"]["protocol_version"], "0.15.0")

            started = protocol.handle_domain_method(
                "design.start",
                {
                    "project_root": str(project),
                    "brief": "一组安静克制的窗边人像",
                    "language": "zh-CN",
                    "expected_revision": 0,
                    "operation_id": "OP-START",
                },
            )
            session_id = started["session_id"]
            self.assertEqual(started["revision"], 1)
            self.assertEqual(len(started["snapshot"]["elements"]), 13)

            preview = protocol.handle_domain_method(
                "design.propose",
                {
                    "project_root": str(project),
                    "session_id": session_id,
                    "layer": "direction",
                    "decisions": {"emotion": {"values": {"tone": "quiet confidence"}}},
                    "refs": [],
                    "expected_revision": 1,
                    "operation_id": "OP-PREVIEW",
                },
            )
            self.assertEqual(preview["revision"], 2)
            self.assertEqual(preview["base_revision"], 2)
            self.assertTrue(all(item["ghost"] is True for item in preview["elements"]))
            self.assertTrue(all(item["participatesInPrompt"] is False for item in preview["elements"]))
            self.assertTrue(all(item["preview_id"] == preview["preview_id"] for item in preview["elements"]))
            self.assertEqual(
                len({item["preview_element_id"] for item in preview["elements"]}),
                len(preview["elements"]),
            )
            self.assertEqual(protocol.project_snapshot(project, session_id)["previews"][0]["preview_id"], preview["preview_id"])
            replay = protocol.handle_domain_method(
                "design.propose",
                {
                    "project_root": str(project),
                    "session_id": session_id,
                    "layer": "direction",
                    "decisions": {"emotion": {"values": {"tone": "quiet confidence"}}},
                    "refs": [],
                    "expected_revision": 1,
                    "operation_id": "OP-PREVIEW",
                },
            )
            self.assertTrue(replay["idempotent_replay"])
            self.assertEqual(replay["preview_id"], preview["preview_id"])
            with self.assertRaisesRegex(ValidationError, "different intent"):
                protocol.handle_domain_method(
                    "design.propose",
                    {
                        "project_root": str(project),
                        "session_id": session_id,
                        "layer": "direction",
                        "decisions": {"emotion": {"values": {"tone": "different"}}},
                        "refs": [],
                        "expected_revision": 1,
                        "operation_id": "OP-PREVIEW",
                    },
                )

            committed = protocol.handle_domain_method(
                "design.commit_preview",
                {
                    "project_root": str(project),
                    "session_id": session_id,
                    "preview_id": preview["preview_id"],
                    "expected_revision": 2,
                    "operation_id": "OP-COMMIT",
                },
            )
            self.assertEqual(committed["revision"], 3)
            self.assertEqual(committed["snapshot"]["session"]["layers"]["direction"]["status"], "confirmed")
            self.assertEqual(committed["snapshot"]["previews"], [])

            before_view = committed["snapshot"]["theme"]["digest"]
            protocol.handle_domain_method(
                "studio.view.save",
                {
                    "project_root": str(project),
                    "view": {"nodes": {"x": {"x": 42, "y": 24}}, "viewport": {"zoom": 0.8}},
                },
            )
            after_view = protocol.project_snapshot(project, session_id)
            self.assertEqual(after_view["revision"], 3)
            self.assertEqual(after_view["theme"]["digest"], before_view)
            (project / ".apsal" / "studio" / "view.json").write_text("{broken", encoding="utf-8")
            recovered_view = protocol.handle_domain_method(
                "studio.view.get", {"project_root": str(project)}
            )
            self.assertTrue(recovered_view["recovered_from_invalid_view"])
            self.assertEqual(recovered_view["nodes"], {})
            after_broken_view = protocol.project_snapshot(project, session_id)
            self.assertEqual(after_broken_view["revision"], 3)
            self.assertEqual(after_broken_view["theme"]["digest"], before_view)

            undone = protocol.handle_domain_method(
                "project.undo",
                {
                    "project_root": str(project),
                    "target_operation_id": "OP-COMMIT",
                    "expected_revision": 3,
                    "operation_id": "OP-UNDO",
                },
            )
            self.assertEqual(undone["revision"], 4)
            self.assertEqual(undone["snapshot"]["session"]["layers"]["direction"]["status"], "pending")

    def test_stale_revision_and_missing_mutation_metadata_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            protocol.init_protocol_project(project)
            with self.assertRaisesRegex(ValidationError, "expected_revision is required"):
                protocol.handle_domain_method(
                    "design.start", {"project_root": str(project), "brief": "test", "operation_id": "OP"}
                )
            protocol.handle_domain_method(
                "design.start",
                {
                    "project_root": str(project),
                    "brief": "test",
                    "language": "en",
                    "expected_revision": 0,
                    "operation_id": "OP-START",
                },
            )
            with self.assertRaisesRegex(ValidationError, "revision mismatch"):
                protocol.handle_domain_method(
                    "design.start",
                    {
                        "project_root": str(project),
                        "brief": "another",
                        "language": "en",
                        "expected_revision": 0,
                        "operation_id": "OP-STALE",
                    },
                )

    def test_incompatible_project_is_read_only_and_never_upgraded_in_place(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "legacy"
            workspace = project / ".apsal"
            workspace.mkdir(parents=True)
            manifest_path = workspace / "project.json"
            legacy = {
                "schema_version": "0.6.0",
                "project_id": "PROJECT-LEGACY000001",
                "revision": 7,
                "storage": "local_first",
            }
            original = json.dumps(legacy, sort_keys=True).encode("utf-8")
            manifest_path.write_bytes(original)

            snapshot = protocol.handle_domain_method(
                "project.open", {"project_root": str(project)}
            )
            self.assertFalse(snapshot["compatible"])
            self.assertTrue(snapshot["read_only"])
            self.assertEqual(snapshot["revision"], 7)
            self.assertEqual(manifest_path.read_bytes(), original)
            with self.assertRaisesRegex(ValidationError, "not upgraded in place"):
                protocol.handle_domain_method("project.init", {"project_root": str(project)})
            self.assertEqual(manifest_path.read_bytes(), original)

    def test_operation_and_frontend_descriptor_paths_are_restricted(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            protocol.init_protocol_project(project)
            with self.assertRaisesRegex(ValidationError, "safe 1-128 character token"):
                protocol.handle_domain_method(
                    "design.start",
                    {
                        "project_root": str(project),
                        "brief": "unsafe operation id",
                        "expected_revision": 0,
                        "operation_id": "../../escape",
                    },
                )

            descriptor = Path(tmp) / "frontend-link.json"
            previous = os.environ.get("APSAL_FRONTEND_DESCRIPTOR")
            os.environ["APSAL_FRONTEND_DESCRIPTOR"] = str(descriptor)
            try:
                descriptor.write_text(
                    json.dumps(
                        {
                            "schema_version": "0.1.0",
                            "base_url": "http://example.com:8080",
                            "token": "test-token",
                        }
                    ),
                    encoding="utf-8",
                )
                self.assertIsNone(apsal_frontend._descriptor())
                descriptor.write_text(
                    json.dumps(
                        {
                            "schema_version": "0.1.0",
                            "base_url": "http://127.0.0.1:49152",
                            "token": "test-token",
                        }
                    ),
                    encoding="utf-8",
                )
                self.assertEqual(
                    apsal_frontend._descriptor()["base_url"], "http://127.0.0.1:49152"
                )
            finally:
                if previous is None:
                    os.environ.pop("APSAL_FRONTEND_DESCRIPTOR", None)
                else:
                    os.environ["APSAL_FRONTEND_DESCRIPTOR"] = previous

    def test_incomplete_transaction_is_rolled_back_on_sidecar_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            protocol.init_protocol_project(project)
            started = protocol.handle_domain_method(
                "design.start",
                {
                    "project_root": str(project), "brief": "recovery test", "language": "en",
                    "expected_revision": 0, "operation_id": "RECOVERY-START",
                },
            )
            session_id = started["session_id"]
            expected = protocol.project_snapshot(project, session_id)
            history = protocol._snapshot_before_mutation(project, "RECOVERY-CRASH", session_id)
            manifest_path = project / ".apsal" / "project.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["revision"] = 999
            protocol._atomic_json(manifest_path, manifest)
            (project / ".apsal" / "drafts" / session_id / "session.json").write_text("{broken", encoding="utf-8")
            protocol._atomic_json(
                project / ".apsal" / "cache" / "protocol-transaction.json",
                {"operation_id": "RECOVERY-CRASH", "session_id": session_id, "history": str(history)},
            )

            recovered = protocol.project_snapshot(project, session_id)
            self.assertEqual(protocol.digest(recovered), protocol.digest(expected))
            self.assertFalse((project / ".apsal" / "cache" / "protocol-transaction.json").exists())

    def test_concurrent_writes_are_serialized_without_duplicate_previews(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            protocol.init_protocol_project(project)
            started = protocol.handle_domain_method(
                "design.start",
                {
                    "project_root": str(project), "brief": "concurrency", "language": "en",
                    "expected_revision": 0, "operation_id": "CONCURRENT-START",
                },
            )
            session_id = started["session_id"]

            def propose(index):
                return protocol.handle_domain_method(
                    "design.propose",
                    {
                        "project_root": str(project), "session_id": session_id, "layer": "direction",
                        "decisions": {"emotion": {"values": {"tone": f"choice-{index}"}}},
                        "expected_revision": 1, "operation_id": f"CONCURRENT-{index}",
                    },
                )

            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(propose, index) for index in range(2)]
                outcomes = []
                for future in futures:
                    try:
                        outcomes.append(future.result())
                    except ValidationError as error:
                        outcomes.append(error)
            self.assertEqual(sum(isinstance(item, dict) for item in outcomes), 1)
            self.assertEqual(sum("revision mismatch" in str(item) for item in outcomes if isinstance(item, Exception)), 1)
            snapshot = protocol.project_snapshot(project, session_id)
            self.assertEqual(snapshot["revision"], 2)
            self.assertEqual(len(snapshot["previews"]), 1)

    def test_stdio_json_rpc_matches_in_process_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            expected = protocol.handle_domain_method("project.init", {"project_root": str(project)})
            request = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 7,
                    "method": "project.open",
                    "params": {"project_root": str(project)},
                }
            )
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS / "apsal_rpc.py")],
                input=request + "\n",
                text=True,
                capture_output=True,
                check=True,
            )
            response = json.loads(completed.stdout)
            self.assertEqual(response["result"]["project"], expected["project"])
            self.assertEqual(response["result"]["revision"], 0)

    def test_mcp_uses_same_engine_without_frontend_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            previous = os.environ.get("APSAL_FRONTEND_DESCRIPTOR")
            os.environ["APSAL_FRONTEND_DESCRIPTOR"] = str(Path(tmp) / "missing-link.json")
            try:
                status = apsal_mcp.call_tool("apsal_frontend_status", {})["structuredContent"]
                self.assertEqual(status["code"], "frontend_not_linked")
                started = apsal_mcp.call_tool(
                    "start_design_session",
                    {"project_root": str(project), "brief": "offline project", "language": "en"},
                )["structuredContent"]
                self.assertEqual(started["revision"], 1)
                self.assertTrue((project / ".apsal" / "project.json").is_file())
            finally:
                if previous is None:
                    os.environ.pop("APSAL_FRONTEND_DESCRIPTOR", None)
                else:
                    os.environ["APSAL_FRONTEND_DESCRIPTOR"] = previous

    def test_golden_contract_replays_every_step_and_final_zip_identically(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            home = Path(tmp) / "home"
            environment = {**os.environ, "APSAL_HOME": str(home)}
            previous_home = os.environ.get("APSAL_HOME")
            os.environ["APSAL_HOME"] = str(home)
            try:
                protocol.init_protocol_project(project)
                start_params = {
                    "project_root": str(project), "brief": "九张东方极简窗边真人摄影",
                    "theme_id": "TEST-GOLDEN-015", "language": "zh-CN",
                    "expected_revision": 0, "operation_id": "GOLDEN-START",
                }
                direct = protocol.handle_domain_method("design.start", start_params)
                replay = self._rpc("design.start", start_params, environment)
                self.assertTrue(replay["idempotent_replay"])
                self.assertEqual(protocol.digest(direct["snapshot"]), protocol.digest(replay["snapshot"]))
                session_id = direct["session_id"]
                revision = direct["revision"]
                assets = engine.load_catalog()["assets"]
                for layer in engine.CREATIVE_LAYERS:
                    refs = [engine.asset_ref(item) for item in assets if item["type"] in engine.LAYER_TYPES[layer]]
                    params = {
                        "project_root": str(project), "session_id": session_id, "layer": layer, "refs": refs,
                        "expected_revision": revision, "operation_id": f"GOLDEN-{layer.upper()}",
                    }
                    direct = protocol.handle_domain_method("design.commit_layer", params)
                    replay = self._rpc("design.commit_layer", params, environment)
                    self.assertTrue(replay["idempotent_replay"])
                    self.assertEqual(protocol.digest(direct["snapshot"]), protocol.digest(replay["snapshot"]))
                    revision = direct["revision"]

                finalize_params = {
                    "project_root": str(project), "session_id": session_id,
                    "expected_revision": revision, "operation_id": "GOLDEN-FINALIZE",
                }
                direct = protocol.handle_domain_method("design.finalize", finalize_params)
                replay = self._rpc("design.finalize", finalize_params, environment)
                direct_package = Path(direct["theme_artifact"]["prompt_package"]["path"])
                replay_package = Path(replay["theme_artifact"]["prompt_package"]["path"])
                self.assertEqual(direct_package.read_bytes(), replay_package.read_bytes())
                self.assertEqual(
                    direct["theme_artifact"]["prompt_package"]["sha256"],
                    replay["theme_artifact"]["prompt_package"]["sha256"],
                )
                self.assertEqual(protocol.digest(direct["snapshot"]), protocol.digest(replay["snapshot"]))
            finally:
                if previous_home is None:
                    os.environ.pop("APSAL_HOME", None)
                else:
                    os.environ["APSAL_HOME"] = previous_home


if __name__ == "__main__":
    unittest.main()
