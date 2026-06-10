from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))

    import app  # noqa: PLC0415

    report = app.build_release_package()
    summary = {
        "zip_path": report.get("zip_path"),
        "latest_zip_path": report.get("latest_zip_path"),
        "included_file_count": report.get("included_file_count"),
        "zip_size_label": report.get("zip_size_label"),
        "sha256": report.get("sha256"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
