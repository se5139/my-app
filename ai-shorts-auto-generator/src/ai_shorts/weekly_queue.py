from __future__ import annotations

import uuid
from typing import Any

from .paths import DATA_DIR, ensure_data_dirs
from .state import now_iso, read_json, write_json


WEEKLY_PLAN_QUEUE_PATH = DATA_DIR / "weekly_plan_queue.json"


def save_weekly_plan_queue(plan: dict[str, Any]) -> dict[str, Any]:
    ensure_data_dirs()
    slots = []
    for slot in plan.get("slots", []):
        slots.append(
            {
                "queue_id": str(uuid.uuid4()),
                "slot_no": slot.get("slot_no"),
                "topic": str(slot.get("topic", "")).strip(),
                "reason": str(slot.get("reason", "")).strip(),
                "target_status": slot.get("target_status", "draft_only"),
                "promoted_project_id": "",
                "status": "queued",
            }
        )

    queue = {
        "saved_at": now_iso(),
        "week_start": plan.get("week_start", ""),
        "target_count": plan.get("target_count", len(slots)),
        "automation_note": plan.get("automation_note", ""),
        "slots": slots,
    }
    write_json(WEEKLY_PLAN_QUEUE_PATH, queue)
    return queue


def mark_slot_promoted(topic: str, project_id: str) -> dict[str, Any]:
    queue = read_json(WEEKLY_PLAN_QUEUE_PATH, {"slots": []})
    for slot in queue.get("slots", []):
        if slot.get("topic") == topic and not slot.get("promoted_project_id"):
            slot["promoted_project_id"] = project_id
            slot["status"] = "promoted_to_draft"
            slot["promoted_at"] = now_iso()
            break
    write_json(WEEKLY_PLAN_QUEUE_PATH, queue)
    return queue
