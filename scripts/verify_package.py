from __future__ import annotations

import ast
import json
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "app.py",
    "README.md",
    "QUICK_START_OTHER_PC_KO.txt",
    "requirements.txt",
    "START_HERE.bat",
    "START_WINDOWS.bat",
    "RUN_SERVER_NO_BROWSER.bat",
    "VERIFY_PACKAGE.bat",
    "scripts/verify_package.py",
    "scripts/stop_port.py",
    "scripts/wait_for_port.py",
]

FORBIDDEN_DIRS = [
    ".git",
    ".venv",
    "outputs",
    "output",
    "data",
    "secrets",
    "__pycache__",
]

SECRET_NAME_MARKERS = [".env", "secret", "token", "api_key", "apikey"]
MOJIBAKE_MARKERS = ["誘", "諛", "泥", "移", "蹂", "媛", "쨌", "珥", "�"]


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def fail(message: str) -> None:
    print(f"[FAIL] {message}")
    raise SystemExit(1)


def ok(message: str) -> None:
    print(f"[OK] {message}")


def warn(message: str) -> None:
    print(f"[WARN] {message}")


def check_required_files() -> None:
    missing = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    if missing:
        fail("required files missing: " + ", ".join(missing))
    ok("required files")


def check_forbidden_dirs() -> None:
    present = [name for name in FORBIDDEN_DIRS if (ROOT / name).exists()]
    allowed_in_dev = {".git", ".venv", "__pycache__", "outputs", "output"}
    unexpected = [name for name in present if name not in allowed_in_dev]
    if unexpected:
        fail("forbidden runtime/data folders found in package root: " + ", ".join(unexpected))
    if present:
        warn("development-only folders present locally: " + ", ".join(present))
    ok("forbidden folders")


def check_launcher_text() -> None:
    start_here = (ROOT / "START_HERE.bat").read_text(encoding="utf-8", errors="replace")
    start_windows = (ROOT / "START_WINDOWS.bat").read_text(encoding="utf-8", errors="replace")
    if "VERIFY_PACKAGE.bat" not in start_here or "START_WINDOWS.bat" not in start_here:
        fail("START_HERE.bat must verify first and then call START_WINDOWS.bat")
    if "python app.py" not in start_windows:
        fail("START_WINDOWS.bat must launch python app.py")
    ok("launcher text")


def check_python_syntax() -> None:
    for path in [ROOT / "app.py", ROOT / "scripts" / "verify_package.py"]:
        ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    ok("python syntax")


def check_docs_encoding() -> None:
    for name in ["README.md", "QUICK_START_OTHER_PC_KO.txt"]:
        text = (ROOT / name).read_text(encoding="utf-8", errors="replace")
        if any(marker in text for marker in MOJIBAKE_MARKERS):
            fail(f"mojibake marker found in {name}")
    ok("Korean docs encoding")


def check_release_manifest_if_present() -> None:
    manifest = ROOT / "RELEASE_MANIFEST.json"
    if not manifest.exists():
        warn("RELEASE_MANIFEST.json not found; skipping packaged-folder strict check in development tree")
        return
    data = json.loads(manifest.read_text(encoding="utf-8"))
    included = data.get("included_files", [])
    if "START_WINDOWS.bat" not in included:
        fail("RELEASE_MANIFEST.json does not include START_WINDOWS.bat")
    if "scripts/verify_package.py" not in included:
        fail("RELEASE_MANIFEST.json does not include scripts/verify_package.py")
    ok("release manifest")


def check_latest_zip_if_present() -> None:
    zip_path = ROOT / "release" / "kakao_emoticon_v100_clean_latest.zip"
    if not zip_path.exists():
        warn("latest release ZIP not found; skipping ZIP content check")
        return
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
    secret_like = [name for name in names if any(marker in name.lower() for marker in SECRET_NAME_MARKERS)]
    if secret_like:
        fail("secret-like files found in latest ZIP: " + ", ".join(secret_like[:10]))
    required_in_zip = [
        "kakao_emoticon_v100_clean/START_HERE.bat",
        "kakao_emoticon_v100_clean/START_WINDOWS.bat",
        "kakao_emoticon_v100_clean/scripts/verify_package.py",
    ]
    missing = [name for name in required_in_zip if name not in names]
    if missing:
        warn("latest ZIP is older than working tree; missing: " + ", ".join(missing))
        return
    ok("latest ZIP content")


def main() -> int:
    print(f"[check] root: {ROOT}")
    check_required_files()
    check_forbidden_dirs()
    check_launcher_text()
    check_python_syntax()
    check_docs_encoding()
    check_release_manifest_if_present()
    check_latest_zip_if_present()
    print("[check] package is ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
