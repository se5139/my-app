from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app
from modules.performance_dashboard import PerformanceDashboardEngine


BAD_TEXT_MARKERS = ["誘", "諛", "泥", "移", "蹂", "媛", "쨌", "珥", "�"]
SECRET_MARKERS = [
    "TEST_GEMINI_SECRET_123",
    "TEST_YOUTUBE_SECRET_123",
    "TEST_NAVER_SECRET_123",
    "TEST_KAKAO_SECRET_123",
]


def fail(message: str) -> None:
    raise AssertionError(message)


def main() -> int:
    sample_report = {
        "project_name": "v100_dashboard_web_check",
        "plus_rows": [
            {"emoticon_name": "샘플", "series_name": "직장편", "sent_count": 20, "user_count": 7},
        ],
        "sales_details": [
            {"emoticon_title": "샘플", "series_name": "직장편", "sales_count": 2, "amount": 5000},
        ],
        "performance_scores": [
            {
                "emoticon_name": "샘플",
                "series_name": "직장편",
                "sent_count": 20,
                "user_count": 7,
                "sales_count": 2,
                "sales_amount": 5000,
            },
        ],
        "period": {"start_date": "2026-06-01", "end_date": "2026-06-10"},
    }

    with tempfile.TemporaryDirectory() as tmp:
        report = PerformanceDashboardEngine().build_report(Path(tmp), kakao_excel_report=sample_report)
        data = report.to_dict()
        text = json.dumps(data, ensure_ascii=False)
        html_text = Path(report.files["html_path"]).read_text(encoding="utf-8")

    if not data["dashboard_rows"]:
        fail("dashboard_rows is empty")
    if not data["strategy_recommendations"]:
        fail("strategy_recommendations is empty")
    if "성과 대시보드" not in html_text:
        fail("Korean dashboard title missing")
    if any(marker in text or marker in html_text for marker in BAD_TEXT_MARKERS):
        fail("mojibake marker found in dashboard report")
    if any(secret in text or secret in html_text for secret in SECRET_MARKERS):
        fail("secret marker leaked into dashboard report")

    page = app.performance_dashboard_page(report=data)
    if "/performance-dashboard/run" not in page:
        fail("dashboard run form is missing")
    if "외부 API 호출이나 비용 발생 호출은 없습니다" not in page:
        fail("API cost safety notice is missing")
    if "샘플" not in page:
        fail("dashboard page did not render sample row")

    print("v100_performance_dashboard_web_check PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
