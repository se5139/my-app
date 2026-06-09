from __future__ import annotations

import argparse
import json

from .weekly_planner import TopicInsight, create_weekly_plan
from .workflow import create_draft_package


def command_new_draft(args: argparse.Namespace) -> None:
    result = create_draft_package(args.topic, args.source_notes)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def command_plan_week(args: argparse.Namespace) -> None:
    insights = [TopicInsight(topic=topic) for topic in args.topic]
    plan = create_weekly_plan(insights, args.count)
    print(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-shorts", description="AI Shorts Auto Generator local CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    draft = sub.add_parser("new-draft", help="Create an autosaved local draft and manual upload package")
    draft.add_argument("topic", help="Shorts topic")
    draft.add_argument("--source-notes", default="", help="Optional inspiration/source notes")
    draft.set_defaults(func=command_new_draft)

    plan = sub.add_parser("plan-week", help="Create a 2 to 3 draft weekly plan")
    plan.add_argument("--count", type=int, default=2, help="Target draft count, clamped to 2 or 3")
    plan.add_argument("--topic", action="append", default=[], help="Candidate topic. Can be repeated.")
    plan.set_defaults(func=command_plan_week)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
