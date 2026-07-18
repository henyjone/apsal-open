from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / "apps" / "apsal-studio"


class StudioFrontendTests(unittest.TestCase):
    def test_component_versions_and_single_engine_source_are_locked(self) -> None:
        versions = json.loads((ROOT / "manifest" / "CURRENT_VERSION_MAP.json").read_text())
        package = json.loads((STUDIO / "package.json").read_text())
        frontend = versions["studio_frontend"]

        self.assertEqual(package["name"], "@apsal/studio")
        self.assertTrue(package["private"])
        self.assertEqual(package["version"], frontend["version"])
        self.assertEqual(frontend["mode"], "codex_plugin_visual_frontend")
        self.assertEqual(frontend["launch_owner"], "codex_plugin_after_creator_choice")
        self.assertFalse(frontend["standalone_link"])
        self.assertFalse(frontend["local_generation"])
        self.assertFalse(frontend["legacy_aiphoto_mode"])
        self.assertEqual(
            package["build"]["extraResources"],
            [{"from": ".build/apsal-engine", "to": "apsal-engine"}],
        )
        self.assertEqual(package["build"]["mac"]["icon"], "assets/icon.icns")
        icon = STUDIO / "assets" / "icon.icns"
        self.assertEqual(
            hashlib.sha256(icon.read_bytes()).hexdigest(),
            "f9ca13d319fb069818f2696299c6ab3cbf258cc21564fd172b3479d383569e89",
        )
        renderer_icon = STUDIO / "src" / "assets" / "apsal-icon.png"
        self.assertEqual(
            hashlib.sha256(renderer_icon.read_bytes()).hexdigest(),
            "1cbe79912cef5286560df5f655cd452b675c0039400496649e775f7790507113",
        )

        preparation = (STUDIO / "scripts" / "prepare-engine.mjs").read_text()
        self.assertIn("plugins', 'apsal-studio", preparation)
        self.assertNotIn("/Users/", preparation)
        self.assertNotIn("AiMePhoto", preparation)

    def test_renderer_is_protocol_frontend_not_a_local_generation_app(self) -> None:
        self.assertFalse((STUDIO / "native").exists())
        self.assertFalse((STUDIO / "public").exists())
        self.assertFalse((STUDIO / "src" / "engine").exists())
        self.assertFalse((STUDIO / "resources").exists())

        source_files = [
            *sorted((STUDIO / "src").rglob("*.ts")),
            *sorted((STUDIO / "src").rglob("*.tsx")),
            *sorted((STUDIO / "electron").rglob("*.mjs")),
            *sorted((STUDIO / "electron").rglob("*.cjs")),
        ]
        source = "\n".join(path.read_text() for path in source_files)
        for forbidden in ("ComfyUI", "MLX", "apsal-runtime:", "apsal-mlx:", "aiphoto:"):
            self.assertNotIn(forbidden, source)

        main = (STUDIO / "electron" / "main.mjs").read_text()
        renderer_methods = re.search(
            r"const RENDERER_METHODS = new Set\(\[(.*?)\]\)", main, re.DOTALL
        )
        self.assertIsNotNone(renderer_methods)
        renderer_contract = renderer_methods.group(1)
        self.assertIn("design.propose", renderer_contract)
        self.assertIn("design.commit_preview", renderer_contract)
        self.assertIn("studio.view.save", renderer_contract)
        self.assertNotIn("generation.start", renderer_contract)
        self.assertNotIn("generation.record", renderer_contract)
        self.assertNotIn("qa.record", renderer_contract)

    def test_codex_bridge_keeps_full_domain_route_without_arbitrary_proxy(self) -> None:
        bridge = (STUDIO / "electron" / "apsal-link.mjs").read_text()
        self.assertIn("design.authoring_mode", bridge)
        self.assertIn("generation.start", bridge)
        self.assertIn("qa.record", bridge)
        self.assertIn("ui.focus_elements", bridge)
        self.assertIn("127.0.0.1", bridge)
        self.assertIn("timingSafeEqual", bridge)
        self.assertNotIn("filesystem.read", bridge)

    def test_existing_project_can_be_opened_from_the_command_line(self) -> None:
        main = (STUDIO / "electron" / "main.mjs").read_text()
        startup = (STUDIO / "electron" / "startup-args.mjs").read_text()
        preload = (STUDIO / "electron" / "preload.cjs").read_text()
        app = (STUDIO / "src" / "App.tsx").read_text()
        self.assertIn("--project-root", startup)
        self.assertIn("--codex-link", startup)
        self.assertIn("handleCodexLaunch(commandLine)", main)
        self.assertTrue((STUDIO / "electron" / "startup-args.node-test.mjs").is_file())
        self.assertIn(".apsal', 'project.json", main)
        self.assertNotIn("apsal-link:set-enabled", main)
        self.assertNotIn("setLinkEnabled", preload)
        self.assertIn("单独打开 Studio 不会连接 Codex", app)
        self.assertIn("发送给 Codex", app)
        self.assertIn("全自动创作", app)
        self.assertIn("origin: 'studio'", (STUDIO / "src" / "protocol" / "store.ts").read_text())


if __name__ == "__main__":
    unittest.main()
