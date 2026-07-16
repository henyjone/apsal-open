#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, re, subprocess, sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "apsal-studio"
VERSION = "0.10.0"
DENY = re.compile("(" + "|".join(("gh" + "o_", "github" + "_pat_", "s" + "k-[A-Za-z0-9]", "BEGIN (RSA|OPENSSH|EC)" + " PRIVATE KEY", "APSAL_ACCESS" + r"_TOKEN\s*=")) + ")")

def check_tree() -> list[str]:
    errors = []
    listed = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True).stdout
    for encoded in listed.split(b"\0"):
        if not encoded: continue
        rel = Path(encoded.decode("utf-8")); path = ROOT / rel
        if not path.is_file(): continue
        if "__pycache__" in rel.parts or path.suffix in {".pyc", ".pyo"}: continue
        if path.stat().st_size > 2_000_000: errors.append(f"large file: {rel}")
        if any(part in {"private", "generated"} for part in rel.parts): errors.append(f"forbidden path: {rel}")
        try: text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError: continue
        if DENY.search(text): errors.append(f"possible secret: {rel}")
    return errors

def build() -> tuple[Path, str]:
    subprocess.run([sys.executable, str(ROOT / "scripts/build_example.py")], check=True)
    subprocess.run([sys.executable, str(ROOT / "scripts/migrate_quiet_window_1_1.py"), "--check"], check=True)
    subprocess.run([sys.executable, str(ROOT / "scripts/generate_semantic_docs.py"), "--check"], check=True)
    subprocess.run([sys.executable, str(ROOT / "scripts/generate_preview_cards.py"), "--check"], check=True)
    subprocess.run([sys.executable, str(ROOT / "scripts/validate_plugin_bundle.py")], check=True)
    subprocess.run([sys.executable, str(PLUGIN / "scripts/apsal.py"), "validate", str(ROOT / "examples/quiet-window/theme.json")], check=True)
    subprocess.run([sys.executable, str(PLUGIN / "scripts/apsal.py"), "validate", str(ROOT / "examples/quiet-window/theme.apsal.yaml")], check=True)
    subprocess.run([sys.executable, str(PLUGIN / "scripts/apsal.py"), "check-sync", str(ROOT / "examples/quiet-window")], check=True)
    dist = ROOT / "dist"; dist.mkdir(exist_ok=True)
    out = dist / f"apsal-studio-codex-plugin-v{VERSION}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(p for p in PLUGIN.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
            info = zipfile.ZipInfo(str(Path("apsal-studio") / path.relative_to(PLUGIN)), (1980, 1, 1, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED; info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    sha = hashlib.sha256(out.read_bytes()).hexdigest()
    checksum = dist / (out.name + ".sha256"); checksum.write_text(f"{sha}  {out.name}\n", encoding="utf-8")
    return out, sha

def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--check", action="store_true"); args = parser.parse_args()
    errors = check_tree()
    if errors: print("\n".join(errors)); return 1
    if args.check: print("release tree checks passed"); return 0
    out, sha = build(); print(f"{out}\nsha256 {sha}"); return 0
if __name__ == "__main__": raise SystemExit(main())
