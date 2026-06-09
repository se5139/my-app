from __future__ import annotations

import html
import hashlib
import io
import json
import math
import os
import re
import shutil
import socketserver
import sys
import time
import webbrowser
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, quote, unquote, urlparse
from urllib.request import Request, urlopen

try:
    from PIL import Image, ImageDraw, ImageFont
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Pillow is required. Install it with: python -m pip install -r requirements.txt"
    ) from exc


APP_NAME = "Kakao Emoticon Maker v100 Clean"
APP_VERSION = "v100-clean"
HOST = "127.0.0.1"
PORT = 8520
CANVAS_SIZE = 360
STATIC_COUNT = 32
ANIMATED_COUNT = 24
OUTPUT_ROOT = Path("outputs")
RELEASE_ROOT = Path("release")
MEMORY_ROOT = Path("memory")
EVOLUTION_MEMORY_PATH = MEMORY_ROOT / "evolution_memory.json"
API_USAGE_LEDGER_PATH = MEMORY_ROOT / "api_usage_ledger.json"
MAX_STATIC_BYTES = 2 * 1024 * 1024
MAX_ANIMATED_BYTES = 500 * 1024
STATIC_SUBMISSION_MAX_BYTES = 150 * 1024
ANIMATED_SUBMISSION_MAX_BYTES = 650 * 1024

WORKFLOW_MODES = {
    "prototype_only": "아이디어 참고용 프로토타입",
    "human_origin_review": "직접 제작 원본 검수",
}

WORKFLOW_OUTPUT_GUIDANCE = {
    "prototype_only": {
        "zip_prefix": "prototype_reference",
        "purpose_label": "참고용 ZIP",
        "decision": "카카오 제출 금지",
        "action": "아이디어와 구도 확인용입니다. 실제 제출 전 직접 선화, 채색, 문구 검수와 원본 증빙을 별도로 준비하세요.",
    },
    "human_origin_review": {
        "zip_prefix": "submit_ready_review",
        "purpose_label": "제출 준비 검토 ZIP",
        "decision": "사람 검수 후 제출 후보",
        "action": "직접 제작 원본, 레이어 파일, 수정 기록, 권리 메모를 함께 확인한 뒤 제출 후보로 검토하세요.",
    },
}


def workflow_guidance(workflow_mode: str) -> dict[str, str]:
    return WORKFLOW_OUTPUT_GUIDANCE.get(workflow_mode, WORKFLOW_OUTPUT_GUIDANCE["prototype_only"])

PRODUCT_MODES = {
    "standard_static": {
        "label": "일반 이모티콘 - 정지형",
        "static_count": 32,
        "animated_count": 0,
        "canvas_px": 360,
        "static_target_bytes": STATIC_SUBMISSION_MAX_BYTES,
        "animated_target_bytes": ANIMATED_SUBMISSION_MAX_BYTES,
        "zip_allows": ["png"],
        "note": "정지형 중심 세트입니다. 실제 제안 전 카카오 스튜디오 최신 화면에서 용량/개수를 다시 확인하세요.",
    },
    "standard_animated": {
        "label": "일반 이모티콘 - 움직이는",
        "static_count": 21,
        "animated_count": 3,
        "canvas_px": 360,
        "static_target_bytes": STATIC_SUBMISSION_MAX_BYTES,
        "animated_target_bytes": ANIMATED_SUBMISSION_MAX_BYTES,
        "zip_allows": ["png", "gif"],
        "note": "움직이는 이모티콘 제안 시안용 모드입니다. 본 제작 단계에서는 전체 움직임 파일 요구가 달라질 수 있습니다.",
    },
    "mini_static": {
        "label": "미니 이모티콘 - 정지형",
        "static_count": 24,
        "animated_count": 0,
        "canvas_px": 360,
        "static_target_bytes": STATIC_SUBMISSION_MAX_BYTES,
        "animated_target_bytes": ANIMATED_SUBMISSION_MAX_BYTES,
        "zip_allows": ["png"],
        "note": "미니 정지형 참고 모드입니다. 미니 이모티콘은 노출 크기와 가독성을 더 엄격히 확인하세요.",
    },
    "mini_animated": {
        "label": "미니 이모티콘 - 움직이는",
        "static_count": 21,
        "animated_count": 3,
        "canvas_px": 360,
        "static_target_bytes": STATIC_SUBMISSION_MAX_BYTES,
        "animated_target_bytes": ANIMATED_SUBMISSION_MAX_BYTES,
        "zip_allows": ["png", "gif"],
        "note": "움직이는 미니 참고 모드입니다. 실제 제출 형식은 카카오 WebP 애니메이터/스튜디오 최신 안내를 확인하세요.",
    },
}

CHARACTER_STYLES = {
    "soft_bear": "말랑곰",
    "bounce_rabbit": "통통토끼",
    "wink_cat": "윙크고양이",
    "round_blob": "동글이",
}

EMOTION_PRESETS = [
    {"key": "happy", "label": "기쁨", "effect": "sparkles", "motion": [0, -6, -10, -6, 0, 4, 0, -3]},
    {"key": "thanks", "label": "감사", "effect": "hearts", "motion": [0, -3, -6, -3, 0, 2, 0, -2]},
    {"key": "cheer", "label": "응원", "effect": "bursts", "motion": [0, -10, -15, -10, 0, 6, 0, -6]},
    {"key": "sorry", "label": "미안", "effect": "sweat", "motion": [0, 2, 4, 2, 0, -2, 0, 2]},
    {"key": "love", "label": "애정", "effect": "big_heart", "motion": [0, -4, -8, -4, 0, 3, 0, -3]},
    {"key": "surprise", "label": "놀람", "effect": "marks", "motion": [0, -12, 2, -10, 3, -8, 0, -4]},
    {"key": "rest", "label": "휴식", "effect": "clouds", "motion": [0, 1, 2, 1, 0, -1, 0, 1]},
    {"key": "party", "label": "축하", "effect": "confetti", "motion": [0, -9, -13, -7, 0, 5, 0, -5]},
]

DEFAULT_PHRASES = [
    "좋아!",
    "고마워",
    "화이팅",
    "괜찮아",
    "축하해",
    "미안해",
    "보고싶어",
    "안녕",
    "완전 좋아",
    "잠깐만",
    "배고파",
    "최고야",
    "응원해",
    "오늘도 굿",
    "쉬자",
    "놀자",
]

PHRASE_BANK = {
    "happy": ["좋아!", "완전 좋아", "기분 최고", "좋은데?", "히히 좋아", "나이스", "행복해", "웃자"],
    "thanks": ["고마워", "덕분이야", "감사해", "마음 받았어", "진짜 고마워", "센스 최고", "고마운 마음", "감동이야"],
    "cheer": ["화이팅", "할 수 있어", "응원해", "조금만 더", "가보자!", "힘내자", "잘 될 거야", "믿고 있어"],
    "sorry": ["미안해", "괜찮아?", "내가 미안", "조심할게", "마음 풀어", "실수했어", "다시 해볼게", "서운했지"],
    "love": ["보고싶어", "좋아해", "내 마음", "생각났어", "안아줄게", "소중해", "함께하자", "내 편이야"],
    "surprise": ["어머!", "진짜?", "깜짝이야", "잠깐만", "대박", "뭐라고?", "헉!", "이럴수가"],
    "rest": ["쉬자", "천천히 해", "괜찮아", "오늘도 수고", "잠깐 쉬어", "무리하지 마", "숨 돌리자", "편히 있어"],
    "party": ["축하해", "최고야", "잘했어", "파티다!", "오늘 주인공", "멋지다", "대성공", "박수!"],
}

PHRASE_EMOTION_KEYWORDS = {
    "thanks": ["고마", "감사", "덕분", "감동", "센스"],
    "cheer": ["화이팅", "파이팅", "응원", "할 수", "가보자", "힘내", "잘 될", "믿고"],
    "sorry": ["미안", "죄송", "괜찮아?", "조심", "실수", "서운", "마음 풀"],
    "love": ["보고싶", "좋아해", "사랑", "하트", "소중", "내 편", "안아"],
    "surprise": ["헉", "어머", "진짜?", "깜짝", "대박", "뭐라고", "잠깐", "이럴수가", "오잉"],
    "rest": ["쉬", "수고", "천천", "무리하지", "숨 돌", "편히", "괜찮아", "잠"],
    "party": ["축하", "최고", "잘했", "파티", "성공", "박수", "주인공", "멋지"],
    "happy": ["좋아", "굿", "나이스", "행복", "기분", "히히", "웃자", "안녕"],
}

PHRASE_RISK_KEYWORDS = [
    "혐오",
    "차별",
    "욕",
    "비하",
    "죽어",
    "꺼져",
    "정치",
    "종교",
    "도박",
    "마약",
    "브랜드",
    "로고",
    "연예인",
    "유명인",
]

TREND_KEYWORDS = {
    "cute": ["귀여", "말랑", "동글", "작고", "미니", "cute", "kawaii"],
    "daily": ["일상", "출근", "퇴근", "학교", "친구", "커플", "daily"],
    "reaction": ["리액션", "짤", "반응", "감정", "표정", "reaction"],
    "comfort": ["위로", "힐링", "괜찮", "수고", "토닥", "comfort"],
    "funny": ["개그", "웃긴", "밈", "장난", "킹받", "funny", "meme"],
    "simple": ["심플", "단순", "선화", "라인", "simple", "minimal"],
    "motion": ["움직", "모션", "gif", "webp", "animation", "animated"],
}

LEGAL_KEYWORDS = {
    "copyright": ["저작권", "copyright", "복제", "표절", "트레이싱", "원저작", "라이선스", "무단"],
    "trademark": ["상표", "브랜드", "로고", "trademark", "부정경쟁"],
    "portrait": ["초상권", "퍼블리시티", "연예인", "유명인", "실존 인물", "portrait"],
    "ai_policy": ["생성형 ai", "인공지능", "ai 생성", "ai-generated", "aigc"],
    "harmful_expression": ["혐오", "차별", "폭력", "선정", "욕설", "비하", "정치", "종교", "도박", "마약"],
}

AUTO_RESEARCH_SEEDS = [
    "https://emoticonstudio.kakao.com/guideline",
    "https://emoticonstudio.kakao.com/pages/faq?from=with_faq",
    "https://emoticonstudio.kakao.com/terms",
    "https://emoticonstudio.kakao.com/webp-animator",
    "https://www.copyright.or.kr/",
    "https://www.mcst.go.kr/",
]

PLATFORM_OFFICIAL_HOSTS = [
    "emoticonstudio.kakao.com",
    "kakao.com",
]

LEGAL_OFFICIAL_HOSTS = [
    "copyright.or.kr",
    "mcst.go.kr",
    "law.go.kr",
    "kipo.go.kr",
    "kcc.go.kr",
]

TREND_REFERENCE_HOSTS = [
    "youtube.com",
    "youtu.be",
]

USER_GENERATED_HOST_HINTS = [
    "blog.",
    "cafe.",
    "tistory.com",
    "brunch.co.kr",
    "post.naver.com",
]

API_KEY_ENV_VARS = {
    "youtube": "YOUTUBE_API_KEY",
    "search": "SEARCH_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
}

API_31D_LIMIT_ENV_VARS = {
    "youtube": "YOUTUBE_API_31D_CALL_LIMIT",
    "search": "SEARCH_API_31D_CALL_LIMIT",
    "gemini": "GEMINI_API_31D_CALL_LIMIT",
    "openai": "OPENAI_API_31D_CALL_LIMIT",
}

API_DAILY_LIMIT_ENV_VARS = {
    "youtube": "YOUTUBE_API_DAILY_CALL_LIMIT",
    "search": "SEARCH_API_DAILY_CALL_LIMIT",
    "gemini": "GEMINI_API_DAILY_CALL_LIMIT",
}

API_LEGACY_30D_LIMIT_ENV_VARS = {
    "youtube": "YOUTUBE_API_30D_CALL_LIMIT",
    "search": "SEARCH_API_30D_CALL_LIMIT",
    "gemini": "GEMINI_API_30D_CALL_LIMIT",
    "openai": "OPENAI_API_30D_CALL_LIMIT",
}

KST = timezone(timedelta(hours=9))
PACIFIC_STANDARD = timezone(timedelta(hours=-8))
PACIFIC_DAYLIGHT = timezone(timedelta(hours=-7))
API_SAFETY_WINDOW_DAYS = 31
DAILY_RESET_PROVIDERS = {"youtube", "search", "gemini"}
PACIFIC_RESET_PROVIDERS = {"gemini"}


@dataclass(frozen=True)
class BuildRequest:
    character_name: str
    concept: str
    phrases: list[str]
    base_color: str
    accent_color: str
    character_style: str = "soft_bear"
    workflow_mode: str = "prototype_only"
    product_mode: str = "standard_static"
    human_origin_note: str = ""
    sketch_image: Image.Image | None = None
    sketch_filename: str = ""
    research_urls: list[str] | None = None
    research_notes: str = ""
    research_keywords: list[str] | None = None
    auto_collect_research: bool = True


def safe_slug(value: str, fallback: str = "emoticon") -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]+", "_", value.strip())
    cleaned = re.sub(r"\s+", "_", cleaned)
    cleaned = cleaned.strip("._")
    return cleaned or fallback


def parse_phrases(raw: str) -> list[str]:
    phrases = [line.strip() for line in raw.splitlines() if line.strip()]
    return phrases or DEFAULT_PHRASES


def normalize_phrase(phrase: str) -> str:
    return re.sub(r"\s+", " ", phrase.strip())


def emotion_for_key(emotion_key: str) -> dict[str, object]:
    for emotion in EMOTION_PRESETS:
        if str(emotion["key"]) == emotion_key:
            return emotion
    return EMOTION_PRESETS[0]


def match_phrase_emotion(phrase: str, fallback_index: int = 0) -> tuple[str, str]:
    normalized = normalize_phrase(phrase).lower()
    best_key = str(emotion_for_index(fallback_index)["key"])
    best_reason = "fallback_sequence"
    best_score = 0
    for emotion_key, keywords in PHRASE_EMOTION_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword.lower() in normalized)
        if score > best_score:
            best_key = emotion_key
            best_score = score
            best_reason = "keyword:" + ",".join(keyword for keyword in keywords if keyword.lower() in normalized)
    return best_key, best_reason


def phrase_for_slot(user_phrases: list[str], emotion_key: str, slot_index: int) -> tuple[str, str]:
    cleaned_user_phrases = [normalize_phrase(phrase) for phrase in user_phrases if normalize_phrase(phrase)]
    if slot_index < len(cleaned_user_phrases):
        return cleaned_user_phrases[slot_index], "user"
    bank = PHRASE_BANK.get(emotion_key, DEFAULT_PHRASES)
    bank_index = (slot_index - len(cleaned_user_phrases)) % len(bank)
    return bank[bank_index], "auto"


def increment_weight_map(memory: dict[str, object], key: str, values: list[str]) -> None:
    weights = memory.get(key, {})
    if not isinstance(weights, dict):
        weights = {}
    for value in values:
        clean = normalize_phrase(str(value))
        if not clean:
            continue
        weights[clean] = int(weights.get(clean, 0)) + 1
    memory[key] = dict(sorted(weights.items(), key=lambda item: (-int(item[1]), item[0]))[:160])


def weighted_values(memory: dict[str, object], key: str, fallback_key: str) -> list[str]:
    weights = memory.get(key, {})
    if isinstance(weights, dict) and weights:
        return [
            str(value)
            for value, _score in sorted(weights.items(), key=lambda item: (-int(item[1]), item[0]))
        ]
    return [str(item) for item in memory.get(fallback_key, [])]


def top_weight_items(weights: object, limit: int = 20) -> list[dict[str, object]]:
    if not isinstance(weights, dict):
        return []
    return [
        {"value": str(value), "score": int(score)}
        for value, score in sorted(weights.items(), key=lambda item: (-int(item[1]), item[0]))[:limit]
    ]


def phrase_emotion_summary(phrase_plan: list[dict[str, str]]) -> dict[str, object]:
    counts: dict[str, int] = {}
    keyword_matches = 0
    for item in phrase_plan:
        emotion_key = str(item.get("emotion_key", "unknown"))
        counts[emotion_key] = counts.get(emotion_key, 0) + 1
        if str(item.get("emotion_match_reason", "")).startswith("keyword:"):
            keyword_matches += 1
    return {
        "enabled": True,
        "keyword_match_count": keyword_matches,
        "fallback_sequence_count": len(phrase_plan) - keyword_matches,
        "emotion_counts": counts,
        "report_file": "phrase_plan.json",
    }


def compact_phrase_key(phrase: str) -> str:
    cleaned = normalize_phrase(phrase).lower()
    cleaned = re.sub(r"[!?.~ㅋㅎㅠㅜ♡♥\s]+", "", cleaned)
    cleaned = re.sub(r"\d+$", "", cleaned)
    return cleaned


def suggest_shorter_phrase(phrase: str) -> str:
    phrase = normalize_phrase(phrase)
    if len(phrase) <= 10:
        return phrase
    replacements = [
        ("정말 ", ""),
        ("진짜 ", ""),
        ("완전 ", ""),
        ("너무 ", ""),
        ("오늘도 ", ""),
    ]
    shortened = phrase
    for before, after in replacements:
        shortened = shortened.replace(before, after)
    if len(shortened) > 10:
        shortened = shortened[:9] + "…"
    return shortened


def safe_phrase_candidates(emotion_key: str, used_phrases: set[str], limit: int = 3) -> list[str]:
    bank = PHRASE_BANK.get(emotion_key, DEFAULT_PHRASES)
    candidates: list[str] = []
    for phrase in bank:
        if compact_phrase_key(phrase) in used_phrases:
            continue
        if any(keyword.lower() in phrase.lower() for keyword in PHRASE_RISK_KEYWORDS):
            continue
        candidates.append(phrase)
        if len(candidates) >= limit:
            break
    if len(candidates) < limit:
        for phrase in DEFAULT_PHRASES:
            if compact_phrase_key(phrase) not in used_phrases and phrase not in candidates:
                candidates.append(phrase)
            if len(candidates) >= limit:
                break
    return candidates


def build_phrase_replacement_suggestions(
    phrase_plan: list[dict[str, str]],
    phrase_quality: dict[str, object],
) -> dict[str, object]:
    used = {compact_phrase_key(str(item.get("phrase", ""))) for item in phrase_plan}
    suggestions: list[dict[str, object]] = []
    seen_slots: set[str] = set()
    for issue in phrase_quality.get("issues", []):
        if not isinstance(issue, dict):
            continue
        slot = str(issue.get("slot", ""))
        if slot == "-" or slot in seen_slots:
            continue
        seen_slots.add(slot)
        matching_slot = next((item for item in phrase_plan if str(item.get("slot")) == slot), {})
        phrase = str(issue.get("phrase", ""))
        emotion_key = str(matching_slot.get("emotion_key", match_phrase_emotion(phrase)[0]))
        category = str(issue.get("category", ""))
        candidates: list[str] = []
        if category == "readability":
            short = suggest_shorter_phrase(phrase)
            if short and short != phrase:
                candidates.append(short)
        if category in {"risk_keyword", "duplication", "emotion_unclear", "readability"}:
            candidates.extend(safe_phrase_candidates(emotion_key, used | {compact_phrase_key(item) for item in candidates}, 4))
        candidates = unique_keep_order([candidate for candidate in candidates if candidate and candidate != phrase])[:4]
        suggestions.append(
            {
                "slot": slot,
                "original": phrase,
                "emotion_key": emotion_key,
                "emotion": str(emotion_for_key(emotion_key)["label"]),
                "issue_category": category,
                "issue_level": issue.get("level", ""),
                "reason": issue.get("message", ""),
                "candidates": candidates,
                "recommended": candidates[0] if candidates else "",
                "note": "후보는 안전한 참고 문구입니다. 최종 제출 전 캐릭터 말투에 맞게 직접 다듬으세요.",
            }
        )

    auto_ratio_issue = any(
        isinstance(issue, dict) and issue.get("category") == "auto_ratio"
        for issue in phrase_quality.get("issues", [])
    )
    extra_user_phrase_ideas = []
    if auto_ratio_issue:
        for emotion_key in ["thanks", "cheer", "sorry", "love", "surprise", "rest", "party", "happy"]:
            extra_user_phrase_ideas.extend(safe_phrase_candidates(emotion_key, used, 1))
    return {
        "enabled": True,
        "suggestion_count": len(suggestions),
        "suggestions": suggestions,
        "extra_user_phrase_ideas": unique_keep_order(extra_user_phrase_ideas)[:12],
        "rules": {
            "no_api_required": True,
            "risk_keywords_removed": True,
            "final_manual_edit_required": True,
        },
    }


def apply_phrase_replacements(
    phrase_plan: list[dict[str, str]],
    phrase_replacements: dict[str, object],
) -> tuple[list[dict[str, str]], dict[str, object]]:
    replacement_by_slot = {
        str(item.get("slot")): item
        for item in phrase_replacements.get("suggestions", [])
        if isinstance(item, dict) and item.get("recommended")
    }
    revised_plan: list[dict[str, str]] = []
    applied: list[dict[str, object]] = []
    for item in phrase_plan:
        revised = dict(item)
        slot = str(item.get("slot", ""))
        replacement = replacement_by_slot.get(slot)
        if replacement:
            original = str(item.get("phrase", ""))
            recommended = str(replacement.get("recommended", ""))
            emotion_key, match_reason = match_phrase_emotion(recommended, int(slot) - 1 if slot.isdigit() else 0)
            emotion = emotion_for_key(emotion_key)
            revised["original_phrase"] = original
            revised["phrase"] = recommended
            revised["source"] = "auto_replacement"
            revised["emotion_key"] = str(emotion["key"])
            revised["emotion"] = str(emotion["label"])
            revised["emotion_match_reason"] = match_reason
            revised["replacement_reason"] = str(replacement.get("reason", ""))
            applied.append(
                {
                    "slot": slot,
                    "original": original,
                    "replacement": recommended,
                    "emotion_key": str(emotion["key"]),
                    "reason": replacement.get("reason", ""),
                }
            )
        revised_plan.append(revised)
    return revised_plan, {
        "enabled": True,
        "applied_count": len(applied),
        "applied": applied,
        "policy": "원본 세트는 보존하고, 수정판은 revised_phrase_variant 폴더에 별도 생성합니다.",
    }


def phrase_counts_for_plan(phrase_plan: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in phrase_plan:
        key = compact_phrase_key(str(item.get("phrase", "")))
        if key:
            counts[key] = counts.get(key, 0) + 1
    return counts


def improve_revised_phrase_plan(
    revised_plan: list[dict[str, str]],
    user_phrase_count: int,
    max_rounds: int = 3,
) -> tuple[list[dict[str, str]], dict[str, object], dict[str, object]]:
    current_plan = [dict(item) for item in revised_plan]
    current_quality = analyze_phrase_quality(current_plan, user_phrase_count)
    rounds: list[dict[str, object]] = []
    applied_total: list[dict[str, object]] = []
    for round_index in range(1, max_rounds + 1):
        if current_quality.get("status") == "pass":
            break
        counts = phrase_counts_for_plan(current_plan)
        changes: list[dict[str, object]] = []
        used = set(counts.keys())
        for issue in current_quality.get("issues", []):
            if not isinstance(issue, dict) or issue.get("category") != "duplication":
                continue
            slot = str(issue.get("slot", ""))
            if not slot.isdigit():
                continue
            plan_index = int(slot) - 1
            if plan_index < 0 or plan_index >= len(current_plan):
                continue
            item = dict(current_plan[plan_index])
            original_phrase = str(item.get("phrase", ""))
            original_key = compact_phrase_key(original_phrase)
            if counts.get(original_key, 0) < 2:
                continue
            available_used = {compact_phrase_key(str(plan_item.get("phrase", ""))) for plan_item in current_plan}
            candidates = safe_phrase_candidates(str(item.get("emotion_key", "happy")), available_used, 8)
            replacement = next((candidate for candidate in candidates if compact_phrase_key(candidate) != original_key), "")
            if not replacement:
                continue
            emotion_key, match_reason = match_phrase_emotion(replacement, plan_index)
            emotion = emotion_for_key(emotion_key)
            item["original_phrase"] = item.get("original_phrase", original_phrase)
            item["phrase"] = replacement
            item["source"] = "auto_replacement_refined"
            item["emotion_key"] = str(emotion["key"])
            item["emotion"] = str(emotion["label"])
            item["emotion_match_reason"] = match_reason
            item["replacement_reason"] = f"refinement_round_{round_index}: duplicate cleanup"
            current_plan[plan_index] = item
            used.add(compact_phrase_key(replacement))
            changes.append({"slot": slot, "from": original_phrase, "to": replacement, "reason": "duplicate cleanup"})
        next_quality = analyze_phrase_quality(current_plan, user_phrase_count)
        rounds.append(
            {
                "round": round_index,
                "changes": changes,
                "quality_before": {
                    "status": current_quality.get("status"),
                    "score": current_quality.get("score"),
                    "warn_count": current_quality.get("warn_count"),
                    "fail_count": current_quality.get("fail_count"),
                },
                "quality_after": {
                    "status": next_quality.get("status"),
                    "score": next_quality.get("score"),
                    "warn_count": next_quality.get("warn_count"),
                    "fail_count": next_quality.get("fail_count"),
                },
            }
        )
        applied_total.extend(changes)
        if not changes or int(next_quality.get("score", 0)) <= int(current_quality.get("score", 0)):
            current_quality = next_quality
            break
        current_quality = next_quality
    return current_plan, current_quality, {
        "enabled": True,
        "max_rounds": max_rounds,
        "rounds": rounds,
        "total_changes": len(applied_total),
        "changes": applied_total,
    }


def build_revised_phrase_variant(
    output_dir: Path,
    request: BuildRequest,
    spec: dict[str, object],
    phrase_plan: list[dict[str, str]],
    phrase_replacements: dict[str, object],
    static_count: int,
    animated_count: int,
) -> dict[str, object]:
    revised_plan, apply_report = apply_phrase_replacements(phrase_plan, phrase_replacements)
    revised_plan, refined_quality, refinement_report = improve_revised_phrase_plan(
        revised_plan,
        len(request.phrases),
        max_rounds=3,
    )
    variant_dir = output_dir / "revised_phrase_variant"
    static_dir = variant_dir / "static_png_submit"
    animated_dir = variant_dir / "animated_gif_submit"
    preview_dir = variant_dir / "preview_jpg"
    static_dir.mkdir(parents=True, exist_ok=True)
    animated_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)

    static_files: list[Path] = []
    animated_files: list[Path] = []
    preview_files: list[Path] = []
    optimization_records: list[dict[str, object]] = []
    expression_plan: list[dict[str, str]] = []

    for i in range(static_count):
        phrase_slot = revised_plan[i]
        phrase = phrase_slot["phrase"]
        emotion = emotion_for_key(str(phrase_slot["emotion_key"]))
        image, expression_variant = make_static_image(request, phrase, i, str(phrase_slot["emotion_key"]))
        png_path = static_dir / f"static_{i + 1:02d}.png"
        jpg_path = preview_dir / f"preview_static_{i + 1:02d}.jpg"
        optimization_records.append(save_optimized_png(image, png_path, int(spec["static_target_bytes"])))
        image.save(jpg_path, "JPEG", quality=92)
        static_files.append(png_path)
        preview_files.append(jpg_path)
        expression_plan.append(
            {
                "file": str(png_path.relative_to(variant_dir)),
                "type": "static_png",
                "phrase": phrase,
                "original_phrase": phrase_slot.get("original_phrase", ""),
                "phrase_source": phrase_slot["source"],
                "emotion": str(emotion["label"]),
                "emotion_key": str(emotion["key"]),
                "emotion_match_reason": phrase_slot.get("emotion_match_reason", ""),
                "effect": str(emotion["effect"]),
                "expression_variant": json.dumps(expression_variant, ensure_ascii=False),
            }
        )

    for i in range(animated_count):
        phrase_slot = revised_plan[i + static_count]
        phrase = phrase_slot["phrase"]
        emotion = emotion_for_key(str(phrase_slot["emotion_key"]))
        frames, expression_variant = make_animated_frames(request, phrase, i, static_count, str(phrase_slot["emotion_key"]))
        gif_path = animated_dir / f"animated_{i + 1:02d}.gif"
        preview_path = preview_dir / f"preview_animated_{i + 1:02d}.jpg"
        optimization_records.append(save_optimized_gif(frames, gif_path, int(spec["animated_target_bytes"])))
        frames[0].save(preview_path, "JPEG", quality=92)
        animated_files.append(gif_path)
        preview_files.append(preview_path)
        expression_plan.append(
            {
                "file": str(gif_path.relative_to(variant_dir)),
                "type": "animated_gif",
                "phrase": phrase,
                "original_phrase": phrase_slot.get("original_phrase", ""),
                "phrase_source": phrase_slot["source"],
                "emotion": str(emotion["label"]),
                "emotion_key": str(emotion["key"]),
                "emotion_match_reason": phrase_slot.get("emotion_match_reason", ""),
                "effect": str(emotion["effect"]),
                "motion": ",".join(str(value) for value in emotion["motion"]),
                "expression_variant": json.dumps(expression_variant, ensure_ascii=False),
            }
        )

    zip_name = "revised_phrase_reference_png_gif.zip"
    zip_path = variant_dir / zip_name
    write_zip(zip_path, [*static_files, *animated_files], variant_dir)
    validation = validate_output_package(variant_dir, request.product_mode, zip_path)
    optimization = optimization_summary(optimization_records)
    revised_quality = refined_quality
    (variant_dir / "revised_phrase_plan.json").write_text(
        json.dumps(revised_plan, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (variant_dir / "revised_expression_plan.json").write_text(
        json.dumps(expression_plan, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (variant_dir / "revised_phrase_apply_report.json").write_text(
        json.dumps(apply_report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (variant_dir / "revised_phrase_refinement_report.json").write_text(
        json.dumps(refinement_report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (variant_dir / "revised_phrase_quality_report.json").write_text(
        json.dumps(revised_quality, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (variant_dir / "revised_validation_report.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "enabled": True,
        "directory": str(variant_dir),
        "zip": str(zip_path),
        "applied_count": apply_report["applied_count"],
        "refinement_change_count": refinement_report["total_changes"],
        "validation_status": validation["status"],
        "quality_status": revised_quality["status"],
        "quality_score": revised_quality["score"],
        "static_png_count": len(static_files),
        "animated_gif_count": len(animated_files),
        "report_files": [
            "revised_phrase_plan.json",
            "revised_expression_plan.json",
            "revised_phrase_apply_report.json",
            "revised_phrase_refinement_report.json",
            "revised_phrase_quality_report.json",
            "revised_validation_report.json",
        ],
    }


def analyze_phrase_quality(phrase_plan: list[dict[str, str]], user_phrase_count: int) -> dict[str, object]:
    score = 100
    issues: list[dict[str, object]] = []
    normalized_counts: dict[str, int] = {}
    for item in phrase_plan:
        key = compact_phrase_key(str(item.get("phrase", "")))
        if key:
            normalized_counts[key] = normalized_counts.get(key, 0) + 1

    def add_issue(slot: str, phrase: str, level: str, points: int, category: str, message: str, suggestion: str) -> None:
        nonlocal score
        score -= points
        issues.append(
            {
                "slot": slot,
                "phrase": phrase,
                "level": level,
                "points": points,
                "category": category,
                "message": message,
                "suggestion": suggestion,
            }
        )

    for item in phrase_plan:
        phrase = str(item.get("phrase", ""))
        slot = str(item.get("slot", ""))
        compact = compact_phrase_key(phrase)
        if len(phrase) > 12:
            add_issue(
                slot,
                phrase,
                "warn",
                3,
                "readability",
                "문구가 길어 작은 이모티콘 화면에서 가독성이 낮을 수 있습니다.",
                f"'{suggest_shorter_phrase(phrase)}'처럼 10자 안팎으로 줄여보세요.",
            )
        if normalized_counts.get(compact, 0) >= 3 and str(item.get("source")) != "user":
            add_issue(
                slot,
                phrase,
                "warn",
                2,
                "duplication",
                "비슷한 문구가 여러 번 반복됩니다.",
                "감사/응원/놀람/휴식 등 다른 상황 문구로 교체해 다양성을 늘리세요.",
            )
        matched_risks = [keyword for keyword in PHRASE_RISK_KEYWORDS if keyword.lower() in phrase.lower()]
        if matched_risks:
            add_issue(
                slot,
                phrase,
                "fail",
                12,
                "risk_keyword",
                f"주의 키워드가 포함되어 있습니다: {', '.join(matched_risks)}",
                "혐오, 차별, 욕설, 정치/종교 공격, 브랜드/유명인 연상 표현은 제거하세요.",
            )
        if str(item.get("emotion_match_reason", "")) == "fallback_sequence" and str(item.get("source")) == "user":
            add_issue(
                slot,
                phrase,
                "info",
                1,
                "emotion_unclear",
                "문구 의미만으로 감정을 확정하기 어렵습니다.",
                "감정이 드러나도록 감사/응원/놀람/휴식 키워드를 조금 더 분명히 넣어보세요.",
            )

    auto_count = sum(1 for item in phrase_plan if str(item.get("source")) == "auto")
    if phrase_plan and auto_count / len(phrase_plan) > 0.7:
        add_issue(
            "-",
            "",
            "warn",
            8,
            "auto_ratio",
            "자동 보충 문구 비율이 높습니다.",
            "캐릭터 말투가 드러나는 직접 작성 문구를 더 추가하세요.",
        )
    if user_phrase_count < 4:
        add_issue(
            "-",
            "",
            "warn",
            6,
            "user_phrase_count",
            "사용자 직접 입력 문구가 적습니다.",
            "최소 8개 이상 직접 작성하면 캐릭터성이 더 안정됩니다.",
        )

    fail_count = sum(1 for issue in issues if issue["level"] == "fail")
    warn_count = sum(1 for issue in issues if issue["level"] == "warn")
    info_count = sum(1 for issue in issues if issue["level"] == "info")
    score = max(0, min(100, score))
    if fail_count:
        status = "fail"
    elif warn_count:
        status = "warn"
    else:
        status = "pass"
    return {
        "enabled": True,
        "status": status,
        "score": score,
        "fail_count": fail_count,
        "warn_count": warn_count,
        "info_count": info_count,
        "auto_phrase_count": auto_count,
        "user_phrase_count": user_phrase_count,
        "duplicate_groups": [
            {"key": key, "count": count}
            for key, count in sorted(normalized_counts.items(), key=lambda item: (-item[1], item[0]))
            if count >= 2
        ][:20],
        "issues": issues[:80],
        "rules": {
            "recommended_max_chars": 12,
            "minimum_user_phrases": 8,
            "risk_keywords": PHRASE_RISK_KEYWORDS,
        },
    }


def build_phrase_plan(
    user_phrases: list[str],
    total_count: int,
    learned_phrases: list[str] | None = None,
    phrase_weights: dict[str, int] | None = None,
) -> list[dict[str, str]]:
    plan: list[dict[str, str]] = []
    seen: dict[str, int] = {}
    if phrase_weights:
        learned_phrases = [
            str(value)
            for value, _score in sorted(phrase_weights.items(), key=lambda item: (-int(item[1]), item[0]))
        ]
    else:
        learned_phrases = learned_phrases or []
    for slot_index in range(total_count):
        sequence_emotion = emotion_for_index(slot_index)
        phrase, source = phrase_for_slot(user_phrases, str(sequence_emotion["key"]), slot_index)
        if source == "auto" and learned_phrases and slot_index % 5 == 0:
            phrase = learned_phrases[(slot_index // 5) % len(learned_phrases)]
            source = "research_memory"
        matched_emotion_key, match_reason = match_phrase_emotion(phrase, slot_index)
        if source == "auto" and match_reason == "fallback_sequence":
            matched_emotion_key = str(sequence_emotion["key"])
        emotion = emotion_for_key(matched_emotion_key)
        normalized = normalize_phrase(phrase)
        seen[normalized] = seen.get(normalized, 0) + 1
        if seen[normalized] > 1 and source == "auto":
            phrase = f"{phrase} {seen[normalized]}"
            matched_emotion_key, match_reason = match_phrase_emotion(phrase, slot_index)
            if match_reason == "fallback_sequence":
                matched_emotion_key = str(sequence_emotion["key"])
            emotion = emotion_for_key(matched_emotion_key)
        plan.append(
            {
                "slot": str(slot_index + 1),
                "phrase": phrase,
                "source": source,
                "emotion_key": str(emotion["key"]),
                "emotion": str(emotion["label"]),
                "emotion_match_reason": match_reason,
                "sequence_emotion_key": str(sequence_emotion["key"]),
            }
        )
    return plan


def parse_research_urls(raw: str) -> list[str]:
    urls = []
    for line in raw.splitlines():
        value = line.strip()
        if not value:
            continue
        parsed = urlparse(value)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            urls.append(value)
    return urls[:12]


def parse_research_keywords(raw: str) -> list[str]:
    keywords: list[str] = []
    for part in re.split(r"[\n,]+", raw):
        value = normalize_phrase(part)
        if value:
            keywords.append(value)
    return unique_keep_order(keywords)[:10]


def keywords_from_notes(notes: str) -> list[str]:
    base_keywords = []
    for category, words in TREND_KEYWORDS.items():
        if any(word.lower() in notes.lower() for word in words):
            base_keywords.append(f"카카오 이모티콘 {category}")
    if "저작권" in notes or "법" in notes:
        base_keywords.append("카카오 이모티콘 저작권 가이드")
    if "미니" in notes:
        base_keywords.append("카카오 미니 이모티콘 제작 가이드")
    return unique_keep_order(base_keywords)[:6]


def host_matches(host: str, patterns: list[str]) -> bool:
    host = host.lower()
    return any(host == pattern or host.endswith(f".{pattern}") or pattern in host for pattern in patterns)


def classify_source_quality(url: str, title: str = "", status: str = "") -> dict[str, object]:
    host = urlparse(url).netloc.lower()
    text = f"{title}\n{url}\n{status}".lower()
    score = 50
    tier = "general_web"
    purpose = "background_reference"
    reasons: list[str] = []
    use_limits = [
        "추상 경향만 참고하고 캐릭터, 구도, 문구, 썸네일은 복제하지 않습니다.",
    ]

    if host_matches(host, PLATFORM_OFFICIAL_HOSTS):
        score += 35
        tier = "platform_official"
        purpose = "platform_policy"
        reasons.append("카카오/플랫폼 공식 출처로 규격과 운영정책 판단에 우선 사용합니다.")
    elif host_matches(host, LEGAL_OFFICIAL_HOSTS):
        score += 35
        tier = "legal_official"
        purpose = "legal_guardrail"
        reasons.append("정부/저작권 관련 공식 출처로 법적 가드레일 판단에 우선 사용합니다.")
    elif host_matches(host, TREND_REFERENCE_HOSTS):
        score -= 5
        tier = "trend_reference"
        purpose = "trend_only"
        reasons.append("영상/크리에이터 자료는 트렌드 참고용이며 표현 복제 금지 대상으로 다룹니다.")
    elif host_matches(host, USER_GENERATED_HOST_HINTS):
        score -= 15
        tier = "user_generated"
        purpose = "trend_only"
        reasons.append("블로그/커뮤니티성 자료는 2차 해석일 수 있어 낮은 신뢰도로 참고합니다.")
    else:
        reasons.append("일반 웹 자료로 분류되어 공식 자료와 교차 확인이 필요합니다.")

    if any(keyword in text for keyword in ["저작권", "copyright", "상표", "trademark", "초상권", "법", "약관", "정책"]):
        score += 5
        if purpose == "background_reference":
            purpose = "legal_guardrail"
        reasons.append("법률/정책 키워드가 있어 생성 규칙보다 안전 가드레일에 우선 반영합니다.")
    if any(keyword in text for keyword in ["생성형 ai", "ai 생성", "ai-generated", "aigc"]):
        reasons.append("AI 정책 관련 키워드가 있어 사람 제작 증빙 체크에 반영합니다.")
    if "fetch_failed" in status or "api_failed" in status:
        score -= 10
        reasons.append("본문/제목 수집이 실패했으므로 URL 도메인 수준으로만 참고합니다.")

    score = max(0, min(100, score))
    if score >= 80:
        confidence = "high"
    elif score >= 55:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "score": score,
        "confidence": confidence,
        "tier": tier,
        "purpose": purpose,
        "reasons": reasons,
        "use_limits": use_limits,
    }


def summarize_source_quality(sources: list[dict[str, object]]) -> dict[str, object]:
    if not sources:
        return {
            "average_score": 0,
            "platform_official_count": 0,
            "legal_official_count": 0,
            "trend_reference_count": 0,
            "user_generated_count": 0,
            "low_confidence_count": 0,
            "recommended_sources": [],
            "caution_sources": [],
        }

    tier_counts: dict[str, int] = {}
    scores: list[int] = []
    for source in sources:
        quality = source.get("source_quality", {})
        if not isinstance(quality, dict):
            continue
        tier = str(quality.get("tier", "unknown"))
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        scores.append(int(quality.get("score", 0)))

    sorted_sources = sorted(
        sources,
        key=lambda item: int(item.get("source_quality", {}).get("score", 0)) if isinstance(item.get("source_quality", {}), dict) else 0,
        reverse=True,
    )
    recommended_sources = [
        {
            "url": source.get("url", ""),
            "title": source.get("title", ""),
            "score": source.get("source_quality", {}).get("score", 0) if isinstance(source.get("source_quality", {}), dict) else 0,
            "tier": source.get("source_quality", {}).get("tier", "") if isinstance(source.get("source_quality", {}), dict) else "",
        }
        for source in sorted_sources[:8]
    ]
    caution_sources = [
        {
            "url": source.get("url", ""),
            "title": source.get("title", ""),
            "score": source.get("source_quality", {}).get("score", 0) if isinstance(source.get("source_quality", {}), dict) else 0,
            "tier": source.get("source_quality", {}).get("tier", "") if isinstance(source.get("source_quality", {}), dict) else "",
        }
        for source in sorted_sources
        if isinstance(source.get("source_quality", {}), dict)
        and str(source.get("source_quality", {}).get("confidence", "")) == "low"
    ][:8]

    return {
        "average_score": round(sum(scores) / len(scores), 1) if scores else 0,
        "platform_official_count": tier_counts.get("platform_official", 0),
        "legal_official_count": tier_counts.get("legal_official", 0),
        "trend_reference_count": tier_counts.get("trend_reference", 0),
        "user_generated_count": tier_counts.get("user_generated", 0),
        "low_confidence_count": sum(
            1
            for source in sources
            if isinstance(source.get("source_quality", {}), dict)
            and str(source.get("source_quality", {}).get("confidence", "")) == "low"
        ),
        "tier_counts": tier_counts,
        "recommended_sources": recommended_sources,
        "caution_sources": caution_sources,
        "rule": "공식/법률 출처는 정책 판단에 우선 사용하고, 영상/블로그/일반 웹은 추상 트렌드 참고용으로만 사용합니다.",
    }


def mask_secret(value: str) -> str:
    if not value:
        return "not set"
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def kst_now() -> datetime:
    return datetime.now(KST)


def pacific_tz_for_date(now: datetime) -> timezone:
    # Simple US DST approximation: March-November uses PDT, otherwise PST.
    return PACIFIC_DAYLIGHT if 3 <= now.month <= 11 else PACIFIC_STANDARD


def api_usage_window(provider: str) -> dict[str, object]:
    now = kst_now()
    if provider in DAILY_RESET_PROVIDERS:
        if provider in PACIFIC_RESET_PROVIDERS:
            pacific_tz = pacific_tz_for_date(now)
            pacific_now = now.astimezone(pacific_tz)
            pacific_midnight = pacific_now.replace(hour=0, minute=0, second=0, microsecond=0)
            next_pacific_midnight = pacific_midnight + timedelta(days=1)
            return {
                "window": "daily_pacific_midnight",
                "window_days": 1,
                "window_start_kst": pacific_midnight.astimezone(KST),
                "next_reset_at_kst": next_pacific_midnight.astimezone(KST),
            }
        kst_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return {
            "window": "daily_kst_midnight",
            "window_days": 1,
            "window_start_kst": kst_midnight,
            "next_reset_at_kst": kst_midnight + timedelta(days=1),
        }
    window_start = now - timedelta(days=API_SAFETY_WINDOW_DAYS)
    return {
        "window": f"rolling_{API_SAFETY_WINDOW_DAYS}_days_kst",
        "window_days": API_SAFETY_WINDOW_DAYS,
        "window_start_kst": window_start,
        "next_reset_at_kst": now,
    }


def load_api_usage_ledger() -> dict[str, object]:
    if not API_USAGE_LEDGER_PATH.exists():
        return {"version": 1, "events": []}
    try:
        return json.loads(API_USAGE_LEDGER_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "events": []}


def write_api_usage_ledger(ledger: dict[str, object]) -> None:
    MEMORY_ROOT.mkdir(exist_ok=True)
    API_USAGE_LEDGER_PATH.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")


def api_call_limit(provider: str) -> int:
    if provider in DAILY_RESET_PROVIDERS:
        daily_env_name = API_DAILY_LIMIT_ENV_VARS.get(provider, "")
        raw = os.environ.get(daily_env_name, "") if daily_env_name else ""
        if raw == "":
            legacy_31d_name = API_31D_LIMIT_ENV_VARS.get(provider, "")
            raw = os.environ.get(legacy_31d_name, "") if legacy_31d_name else ""
        if raw == "":
            legacy_30d_name = API_LEGACY_30D_LIMIT_ENV_VARS.get(provider, "")
            raw = os.environ.get(legacy_30d_name, "") if legacy_30d_name else ""
        if raw == "":
            raw = "0"
        try:
            return max(0, int(raw))
        except ValueError:
            return 0
    env_name = API_31D_LIMIT_ENV_VARS.get(provider, "")
    legacy_env_name = API_LEGACY_30D_LIMIT_ENV_VARS.get(provider, "")
    raw = os.environ.get(env_name, "") if env_name else ""
    if raw == "" and legacy_env_name:
        raw = os.environ.get(legacy_env_name, "")
    if raw == "":
        raw = "0"
    try:
        return max(0, int(raw))
    except ValueError:
        return 0


def api_usage_summary(provider: str) -> dict[str, object]:
    now = kst_now()
    window = api_usage_window(provider)
    window_start = window["window_start_kst"]
    next_reset_at = window["next_reset_at_kst"]
    ledger = load_api_usage_ledger()
    events = ledger.get("events", [])
    recent_events = []
    used_units = 0
    for event in events if isinstance(events, list) else []:
        if not isinstance(event, dict) or event.get("provider") != provider:
            continue
        try:
            event_time = datetime.fromisoformat(str(event.get("created_at_kst")))
        except ValueError:
            continue
        if event_time >= window_start:
            units = int(event.get("units", 1))
            used_units += units
            recent_events.append(event)
    limit = api_call_limit(provider)
    remaining = max(0, limit - used_units) if limit else 0
    return {
        "provider": provider,
        "window": str(window["window"]),
        "window_days": int(window["window_days"]),
        "now_kst": now.isoformat(),
        "window_start_kst": window_start.isoformat(),
        "next_reset_at_kst": next_reset_at.isoformat(),
        "limit": limit,
        "used": used_units,
        "remaining": remaining,
        "enabled": bool(os.environ.get(API_KEY_ENV_VARS.get(provider, ""), "")) and limit > 0,
        "events": recent_events[-20:],
    }


def reserve_api_usage(provider: str, units: int, purpose: str) -> tuple[bool, str]:
    units = max(1, units)
    summary = api_usage_summary(provider)
    if not os.environ.get(API_KEY_ENV_VARS.get(provider, ""), ""):
        return False, f"{provider} API key is not set."
    if int(summary["limit"]) <= 0:
        limit_env = API_DAILY_LIMIT_ENV_VARS.get(provider, API_31D_LIMIT_ENV_VARS.get(provider, ""))
        return False, f"{provider} {summary['window']} limit is not set. Set {limit_env} to allow usage."
    if int(summary["remaining"]) < units:
        return False, f"{provider} {summary['window']} limit exceeded: used {summary['used']} / limit {summary['limit']}. Next reset KST: {summary['next_reset_at_kst']}."
    ledger = load_api_usage_ledger()
    events = ledger.get("events", [])
    if not isinstance(events, list):
        events = []
    events.append(
        {
            "created_at_kst": kst_now().isoformat(),
            "provider": provider,
            "units": units,
            "purpose": purpose,
        }
    )
    cutoff = kst_now() - timedelta(days=45)
    kept_events = []
    for event in events:
        if not isinstance(event, dict):
            continue
        try:
            event_time = datetime.fromisoformat(str(event.get("created_at_kst")))
        except ValueError:
            continue
        if event_time >= cutoff:
            kept_events.append(event)
    ledger["events"] = kept_events
    write_api_usage_ledger(ledger)
    return True, "reserved"


def api_key_status() -> dict[str, dict[str, str]]:
    status: dict[str, dict[str, str]] = {}
    for provider, env_name in API_KEY_ENV_VARS.items():
        value = os.environ.get(env_name, "")
        usage = api_usage_summary(provider)
        status[provider] = {
            "env_var": env_name,
            "limit_env_var": API_DAILY_LIMIT_ENV_VARS.get(provider, API_31D_LIMIT_ENV_VARS.get(provider, "")),
            "legacy_limit_env_var": API_LEGACY_30D_LIMIT_ENV_VARS.get(provider, ""),
            "available": "yes" if bool(value) else "no",
            "masked": mask_secret(value),
            "limit": str(usage["limit"]),
            "used": str(usage["used"]),
            "remaining": str(usage["remaining"]),
            "next_reset_at_kst": str(usage["next_reset_at_kst"]),
            "window": str(usage["window"]),
            "enabled": "yes" if usage["enabled"] else "no",
        }
    return status


def youtube_video_id(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if "youtu.be" in host:
        return parsed.path.strip("/").split("/")[0]
    if "youtube.com" in host:
        query = parse_qs(parsed.query)
        if query.get("v"):
            return query["v"][0]
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live"}:
            return parts[1]
    return ""


def fetch_youtube_metadata(url: str) -> tuple[str, str, str]:
    api_key = os.environ.get(API_KEY_ENV_VARS["youtube"], "")
    video_id = youtube_video_id(url)
    if not api_key or not video_id:
        return "", "", "youtube_api_unavailable"
    allowed, reason = reserve_api_usage("youtube", 1, f"fetch_youtube_metadata:{video_id}")
    if not allowed:
        return "", "", f"youtube_api_blocked:{reason}"
    api_url = (
        "https://www.googleapis.com/youtube/v3/videos"
        f"?part=snippet&id={quote(video_id)}&key={quote(api_key)}"
    )
    try:
        request = Request(api_url, headers={"User-Agent": "KakaoEmoticonV100Research/1.0"})
        with urlopen(request, timeout=6) as response:
            payload = json.loads(response.read(500_000).decode("utf-8", errors="replace"))
        items = payload.get("items", [])
        if not items:
            return "", "", "youtube_api_no_items"
        snippet = items[0].get("snippet", {})
        title = str(snippet.get("title", "")).strip()
        description = str(snippet.get("description", "")).strip()
        return title, description[:2000], "youtube_api_fetched"
    except Exception as exc:
        return "", "", f"youtube_api_failed:{type(exc).__name__}"


def fetch_search_results(keyword: str) -> tuple[list[str], str]:
    api_key = os.environ.get(API_KEY_ENV_VARS["search"], "")
    search_engine_id = os.environ.get("GOOGLE_CSE_ID", "")
    if not api_key or not search_engine_id:
        return [], "search_api_unavailable"
    allowed, reason = reserve_api_usage("search", 1, f"custom_search:{keyword}")
    if not allowed:
        return [], f"search_api_blocked:{reason}"
    api_url = (
        "https://www.googleapis.com/customsearch/v1"
        f"?key={quote(api_key)}&cx={quote(search_engine_id)}&q={quote(keyword)}&num=5"
    )
    try:
        request = Request(api_url, headers={"User-Agent": "KakaoEmoticonV100Research/1.0"})
        with urlopen(request, timeout=8) as response:
            payload = json.loads(response.read(700_000).decode("utf-8", errors="replace"))
        urls = [
            str(item.get("link", "")).strip()
            for item in payload.get("items", [])
            if isinstance(item, dict) and item.get("link")
        ]
        return unique_keep_order([url for url in urls if url.startswith(("http://", "https://"))]), "search_api_fetched"
    except Exception as exc:
        return [], f"search_api_failed:{type(exc).__name__}"


def collect_search_urls(keywords: list[str]) -> tuple[list[str], list[dict[str, object]]]:
    collected_urls: list[str] = []
    reports: list[dict[str, object]] = []
    for keyword in keywords[:8]:
        urls, status = fetch_search_results(keyword)
        collected_urls.extend(urls)
        reports.append(
            {
                "keyword": keyword,
                "status": status,
                "url_count": len(urls),
                "urls": urls,
                "fallback": not bool(urls),
            }
        )
    return unique_keep_order(collected_urls)[:30], reports


def provider_for_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    return ""


def extract_json_object(text: str) -> dict[str, object]:
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        pass
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def gemini_analyze_research_text(text: str) -> tuple[dict[str, object], str]:
    api_key = os.environ.get(API_KEY_ENV_VARS["gemini"], "")
    if not api_key:
        return {}, "gemini_api_unavailable"
    allowed, reason = reserve_api_usage("gemini", 1, "gemini_analyze_research_text")
    if not allowed:
        return {}, f"gemini_api_blocked:{reason}"
    prompt = (
        "Analyze the following Korean/English emoticon research notes for a safe original Kakao emoticon workflow. "
        "Do not copy any source. Return JSON only with keys: "
        "top_categories (array using cute,daily,reaction,comfort,funny,simple,motion), "
        "phrase_additions (array of short Korean phrases), visual_notes (array), tone_notes (array), "
        "legal_risk_flags (array), summary (string). Text:\n"
        + text[:6000]
    )
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }
    api_url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-1.5-flash:generateContent?key={quote(api_key)}"
    )
    try:
        request = Request(
            api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "KakaoEmoticonV100Research/1.0"},
            method="POST",
        )
        with urlopen(request, timeout=12) as response:
            data = json.loads(response.read(1_000_000).decode("utf-8", errors="replace"))
        candidates = data.get("candidates", [])
        if not candidates:
            return {}, "gemini_api_no_candidates"
        parts = candidates[0].get("content", {}).get("parts", [])
        text_parts = [str(part.get("text", "")) for part in parts if isinstance(part, dict)]
        parsed = extract_json_object("\n".join(text_parts))
        if not parsed:
            return {}, "gemini_api_empty_json"
        return parsed, "gemini_api_fetched"
    except Exception as exc:
        return {}, f"gemini_api_failed:{type(exc).__name__}"


def fetch_page_title(url: str) -> tuple[str, str]:
    try:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0 KakaoEmoticonV100Research/1.0"})
        with urlopen(request, timeout=5) as response:
            content_type = response.headers.get("Content-Type", "")
            data = response.read(300_000)
        if "html" not in content_type.lower():
            return "", "non_html"
        text = data.decode("utf-8", errors="replace")
        og_match = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', text, re.I)
        if og_match:
            return html.unescape(og_match.group(1)).strip(), "fetched"
        title_match = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
        if title_match:
            return html.unescape(re.sub(r"\s+", " ", title_match.group(1))).strip(), "fetched"
        return "", "no_title"
    except Exception as exc:
        return "", f"fetch_failed:{type(exc).__name__}"


def keyword_counts(text: str) -> dict[str, int]:
    lowered = text.lower()
    counts: dict[str, int] = {}
    for category, keywords in TREND_KEYWORDS.items():
        counts[category] = sum(lowered.count(keyword.lower()) for keyword in keywords)
    return counts


def legal_keyword_counts(text: str) -> dict[str, int]:
    lowered = text.lower()
    counts: dict[str, int] = {}
    for category, keywords in LEGAL_KEYWORDS.items():
        counts[category] = sum(lowered.count(keyword.lower()) for keyword in keywords)
    return counts


def legal_guardrail_report(text: str, top_categories: list[str], legal_counts: dict[str, int]) -> dict[str, object]:
    risk_flags: list[str] = []
    if legal_counts.get("copyright", 0) > 0:
        risk_flags.append("저작권/표절 관련 표현이 감지되었습니다. 특정 작품, 캐릭터, 문구를 복제하지 마세요.")
    if legal_counts.get("trademark", 0) > 0:
        risk_flags.append("상표/브랜드 관련 표현이 감지되었습니다. 로고, 브랜드명, 공식 캐릭터를 피하세요.")
    if legal_counts.get("portrait", 0) > 0:
        risk_flags.append("초상권/유명인 관련 표현이 감지되었습니다. 특정 인물이 연상되지 않게 하세요.")
    if legal_counts.get("ai_policy", 0) > 0:
        risk_flags.append("생성형 AI 정책 관련 표현이 감지되었습니다. 최종 제출은 사람의 직접 제작 증빙이 필요합니다.")
    if legal_counts.get("harmful_expression", 0) > 0:
        risk_flags.append("유해 표현 관련 키워드가 감지되었습니다. 혐오/차별/선정/폭력/정치·종교 공격 표현을 피하세요.")
    if "funny" in top_categories:
        risk_flags.append("개그/밈 방향은 유행어의 비하·혐오 의미를 별도 검수해야 합니다.")
    risk_level = "low"
    if len(risk_flags) >= 3:
        risk_level = "high"
    elif risk_flags:
        risk_level = "medium"
    return {
        "risk_level": risk_level,
        "risk_flags": risk_flags,
        "must_not_copy": [
            "existing emoticon characters",
            "specific poses or compositions from one source",
            "video thumbnails or captured frames",
            "brand logos, trademarks, celebrity likenesses",
            "distinctive phrases from another creator",
        ],
        "safe_use": [
            "abstract emotion categories",
            "general size and readability principles",
            "broad tone patterns such as short, friendly, daily-use phrases",
            "legal and platform policy constraints",
        ],
    }


def analyze_research_sources(
    urls: list[str],
    notes: str,
    search_keywords: list[str] | None = None,
) -> dict[str, object]:
    search_keywords = unique_keep_order([*(search_keywords or []), *keywords_from_notes(notes)])[:10]
    search_urls, search_reports = collect_search_urls(search_keywords) if search_keywords else ([], [])
    urls = unique_keep_order([*urls, *search_urls])
    sources: list[dict[str, object]] = []
    combined_parts = [notes]
    api_used_count = 0
    api_fallback_count = 0
    free_collection_count = 0
    for url in urls:
        api_provider = provider_for_url(url)
        api_before = api_usage_summary(api_provider) if api_provider else None
        youtube_title, youtube_description, youtube_status = fetch_youtube_metadata(url)
        if youtube_status == "youtube_api_fetched":
            title = youtube_title
            status = youtube_status
            collection_mode = "api"
            fallback_reason = ""
            api_used_count += 1
            combined_parts.append(youtube_description)
        else:
            title, status = fetch_page_title(url)
            collection_mode = "free_fallback" if api_provider else "free"
            fallback_reason = youtube_status if api_provider else ""
            if api_provider:
                api_fallback_count += 1
            else:
                free_collection_count += 1
            if "youtube" in urlparse(url).netloc.lower() or "youtu.be" in urlparse(url).netloc.lower():
                status = f"{status};{youtube_status}"
        source_quality = classify_source_quality(url, title, status)
        source = {
            "url": url,
            "domain": urlparse(url).netloc,
            "title": title,
            "status": status,
            "api_provider": api_provider,
            "collection_mode": collection_mode,
            "fallback_reason": fallback_reason,
            "source_quality": source_quality,
        }
        if api_before:
            source["api_remaining_before"] = str(api_before["remaining"])
            source["api_next_reset_at_kst"] = str(api_before["next_reset_at_kst"])
        sources.append(source)
        combined_parts.extend([title, urlparse(url).netloc])
    combined_text = "\n".join(combined_parts)
    source_quality_summary = summarize_source_quality(sources)
    counts = keyword_counts(combined_text)
    legal_counts = legal_keyword_counts(combined_text)
    top_categories = [
        category
        for category, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)
        if count > 0
    ][:5]
    if not top_categories:
        top_categories = ["cute", "daily", "reaction"]
    suggestions = trend_suggestions(top_categories)
    guardrails = legal_guardrail_report(combined_text, top_categories, legal_counts)
    gemini_result, gemini_status = gemini_analyze_research_text(combined_text)
    if gemini_result:
        gemini_categories = [
            str(category)
            for category in gemini_result.get("top_categories", [])
            if str(category) in TREND_KEYWORDS
        ]
        if gemini_categories:
            top_categories = unique_keep_order([*gemini_categories, *top_categories])[:5]
        suggestions["phrase_additions"] = unique_keep_order(
            [*suggestions.get("phrase_additions", []), *[str(item) for item in gemini_result.get("phrase_additions", [])]]
        )[:16]
        suggestions["visual_notes"] = unique_keep_order(
            [*suggestions.get("visual_notes", []), *[str(item) for item in gemini_result.get("visual_notes", [])]]
        )[:16]
        suggestions["tone_notes"] = unique_keep_order(
            [*suggestions.get("tone_notes", []), *[str(item) for item in gemini_result.get("tone_notes", [])]]
        )[:16]
        gemini_risk_flags = [str(item) for item in gemini_result.get("legal_risk_flags", [])]
        if gemini_risk_flags:
            guardrails["risk_flags"] = unique_keep_order([*guardrails.get("risk_flags", []), *gemini_risk_flags])[:16]
            guardrails["risk_level"] = "high" if len(guardrails["risk_flags"]) >= 3 else "medium"
    return {
        "created_at": time.strftime("%Y%m%d_%H%M%S"),
        "source_count": len(sources),
        "search_keywords": search_keywords,
        "search_reports": search_reports,
        "search_url_count": len(search_urls),
        "api_used_count": api_used_count,
        "api_fallback_count": api_fallback_count,
        "free_collection_count": free_collection_count,
        "source_quality_summary": source_quality_summary,
        "fallback_policy": "When API key, 31-day KST limit, or remaining quota is unavailable, v100 automatically skips API calls and uses free URL/title/domain plus user-note analysis.",
        "sources": sources,
        "notes": notes,
        "keyword_counts": counts,
        "legal_keyword_counts": legal_counts,
        "top_categories": top_categories,
        "suggestions": suggestions,
        "legal_guardrails": guardrails,
        "gemini_status": gemini_status,
        "gemini_used": bool(gemini_result),
        "gemini_summary": str(gemini_result.get("summary", "")) if gemini_result else "",
        "gemini_fallback_policy": "If Gemini key, daily limit, quota, or network is unavailable, v100 keeps using local keyword/legal analysis.",
        "safety_rule": "Use sources for abstract trend learning only. Do not copy characters, compositions, phrases, thumbnails, or brand assets.",
    }


def trend_suggestions(categories: list[str]) -> dict[str, object]:
    phrase_additions: list[str] = []
    visual_notes: list[str] = []
    tone_notes: list[str] = []
    if "cute" in categories:
        phrase_additions.extend(["귀여워", "말랑해", "히히"])
        visual_notes.append("둥근 얼굴, 큰 여백, 작은 손발을 우선합니다.")
    if "daily" in categories:
        phrase_additions.extend(["출근 완료", "집 가자", "밥 먹자"])
        tone_notes.append("매일 쓰기 쉬운 짧은 생활 문구를 늘립니다.")
    if "reaction" in categories:
        phrase_additions.extend(["헉", "오잉?", "그렇구나"])
        visual_notes.append("표정 차이를 크게 만들고 상황 반응형 문구를 늘립니다.")
    if "comfort" in categories:
        phrase_additions.extend(["토닥토닥", "괜찮아", "수고했어"])
        tone_notes.append("위로형 말투와 낮은 자극의 색감을 사용합니다.")
    if "funny" in categories:
        phrase_additions.extend(["킹받네", "빵터짐", "어쩔티비"])
        tone_notes.append("유행어는 혐오/비하 의미가 없는지 반드시 검수합니다.")
    if "simple" in categories:
        visual_notes.append("작은 화면에서 보이도록 선을 굵게, 장식을 줄입니다.")
    if "motion" in categories:
        visual_notes.append("움직임은 3단계 이상 차이가 보이되 프레임 수와 용량을 줄입니다.")
    return {
        "phrase_additions": unique_keep_order(phrase_additions)[:12],
        "visual_notes": unique_keep_order(visual_notes),
        "tone_notes": unique_keep_order(tone_notes),
    }


def unique_keep_order(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result


def load_evolution_memory() -> dict[str, object]:
    if not EVOLUTION_MEMORY_PATH.exists():
        return {
            "version": 1,
            "research_runs": [],
            "learned_phrase_additions": [],
            "learned_notes": [],
            "legal_guardrail_notes": [],
            "phrase_weights": {},
            "note_weights": {},
            "category_weights": {},
            "legal_guardrail_weights": {},
        }
    try:
        return json.loads(EVOLUTION_MEMORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {
            "version": 1,
            "research_runs": [],
            "learned_phrase_additions": [],
            "learned_notes": [],
            "legal_guardrail_notes": [],
            "phrase_weights": {},
            "note_weights": {},
            "category_weights": {},
            "legal_guardrail_weights": {},
        }


def write_evolution_memory(memory: dict[str, object]) -> None:
    MEMORY_ROOT.mkdir(exist_ok=True)
    EVOLUTION_MEMORY_PATH.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")


def compact_evolution_memory() -> dict[str, object]:
    memory = load_evolution_memory()
    memory["research_runs"] = list(memory.get("research_runs", []))[-50:]
    memory["learned_phrase_additions"] = unique_keep_order([str(item) for item in memory.get("learned_phrase_additions", [])])[-80:]
    memory["learned_notes"] = unique_keep_order([str(item) for item in memory.get("learned_notes", [])])[-80:]
    memory["legal_guardrail_notes"] = unique_keep_order([str(item) for item in memory.get("legal_guardrail_notes", [])])[-120:]
    for key in ["phrase_weights", "note_weights", "category_weights", "legal_guardrail_weights"]:
        weights = memory.get(key, {})
        if isinstance(weights, dict):
            memory[key] = dict(sorted(weights.items(), key=lambda item: (-int(item[1]), item[0]))[:160])
        else:
            memory[key] = {}
    memory["last_compacted_at"] = time.strftime("%Y%m%d_%H%M%S")
    write_evolution_memory(memory)
    return memory


def reset_evolution_memory() -> dict[str, object]:
    memory = {
        "version": 1,
        "research_runs": [],
        "learned_phrase_additions": [],
        "learned_notes": [],
        "legal_guardrail_notes": [],
        "phrase_weights": {},
        "note_weights": {},
        "category_weights": {},
        "legal_guardrail_weights": {},
        "reset_at": time.strftime("%Y%m%d_%H%M%S"),
    }
    write_evolution_memory(memory)
    return memory


def reset_api_usage_ledger() -> dict[str, object]:
    ledger = {"version": 1, "events": [], "reset_at_kst": kst_now().isoformat()}
    write_api_usage_ledger(ledger)
    return ledger


def save_evolution_memory(analysis: dict[str, object]) -> dict[str, object]:
    MEMORY_ROOT.mkdir(exist_ok=True)
    memory = load_evolution_memory()
    runs = list(memory.get("research_runs", []))
    runs.append(
        {
            "created_at": analysis.get("created_at"),
            "source_count": analysis.get("source_count"),
            "top_categories": analysis.get("top_categories"),
            "source_quality_summary": analysis.get("source_quality_summary"),
        }
    )
    memory["research_runs"] = runs[-50:]
    suggestions = analysis.get("suggestions", {})
    if isinstance(suggestions, dict):
        learned_phrases = list(memory.get("learned_phrase_additions", []))
        learned_phrases.extend(str(item) for item in suggestions.get("phrase_additions", []) if item)
        memory["learned_phrase_additions"] = unique_keep_order(learned_phrases)[-80:]
        increment_weight_map(memory, "phrase_weights", [str(item) for item in suggestions.get("phrase_additions", []) if item])
        learned_notes = list(memory.get("learned_notes", []))
        learned_notes.extend(str(item) for item in suggestions.get("visual_notes", []) if item)
        learned_notes.extend(str(item) for item in suggestions.get("tone_notes", []) if item)
        memory["learned_notes"] = unique_keep_order(learned_notes)[-80:]
        increment_weight_map(
            memory,
            "note_weights",
            [str(item) for item in suggestions.get("visual_notes", []) if item]
            + [str(item) for item in suggestions.get("tone_notes", []) if item],
        )
    increment_weight_map(memory, "category_weights", [str(item) for item in analysis.get("top_categories", [])])
    guardrails = analysis.get("legal_guardrails", {})
    if isinstance(guardrails, dict):
        legal_notes = list(memory.get("legal_guardrail_notes", []))
        legal_notes.extend(str(item) for item in guardrails.get("risk_flags", []) if item)
        memory["legal_guardrail_notes"] = unique_keep_order(legal_notes)[-120:]
        increment_weight_map(memory, "legal_guardrail_weights", [str(item) for item in guardrails.get("risk_flags", []) if item])
    EVOLUTION_MEMORY_PATH.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")
    return memory


def run_research_only(
    urls: list[str],
    notes: str,
    auto_collect: bool = True,
    search_keywords: list[str] | None = None,
) -> dict[str, object]:
    research_urls = list(urls)
    if auto_collect:
        research_urls = unique_keep_order([*AUTO_RESEARCH_SEEDS, *research_urls])
    analysis = analyze_research_sources(research_urls, notes, search_keywords)
    memory = save_evolution_memory(analysis)
    timestamp = str(analysis["created_at"])
    output_dir = OUTPUT_ROOT / f"{timestamp}_research_only"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "research_insights.json").write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "evolution_memory_snapshot.json").write_text(
        json.dumps(memory, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "output_dir": str(output_dir),
        "analysis": analysis,
        "memory": memory,
    }


def clamp_int(value: str, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except ValueError:
        return default
    return max(minimum, min(maximum, parsed))


def run_learning_cycle(
    urls: list[str],
    notes: str,
    auto_collect: bool = True,
    rounds: int = 3,
    search_keywords: list[str] | None = None,
) -> dict[str, object]:
    rounds = max(1, min(10, rounds))
    analyses: list[dict[str, object]] = []
    for round_index in range(rounds):
        round_notes = notes
        if round_index:
            round_notes = f"{notes}\n반복 학습 라운드 {round_index + 1}: 같은 자료를 다른 관점으로 재점검"
        research_urls = list(urls)
        if auto_collect:
            research_urls = unique_keep_order([*AUTO_RESEARCH_SEEDS, *research_urls])
        analysis = analyze_research_sources(research_urls, round_notes, search_keywords)
        analyses.append(analysis)
        save_evolution_memory(analysis)

    memory = load_evolution_memory()
    category_counts: dict[str, int] = {}
    legal_risk_counts: dict[str, int] = {}
    for analysis in analyses:
        for category in analysis.get("top_categories", []):
            category_counts[str(category)] = category_counts.get(str(category), 0) + 1
        guardrails = analysis.get("legal_guardrails", {})
        if isinstance(guardrails, dict):
            risk = str(guardrails.get("risk_level", "unknown"))
            legal_risk_counts[risk] = legal_risk_counts.get(risk, 0) + 1
    source_quality_summaries = [
        analysis.get("source_quality_summary", {})
        for analysis in analyses
        if isinstance(analysis.get("source_quality_summary", {}), dict)
    ]
    official_source_total = sum(
        int(summary.get("platform_official_count", 0)) + int(summary.get("legal_official_count", 0))
        for summary in source_quality_summaries
    )
    low_confidence_source_total = sum(int(summary.get("low_confidence_count", 0)) for summary in source_quality_summaries)
    source_quality_average = round(
        sum(float(summary.get("average_score", 0)) for summary in source_quality_summaries) / len(source_quality_summaries),
        1,
    ) if source_quality_summaries else 0

    top_categories = [
        category
        for category, _count in sorted(category_counts.items(), key=lambda item: item[1], reverse=True)
    ]
    learned_phrases = [str(item) for item in memory.get("learned_phrase_additions", [])]
    learned_notes = [str(item) for item in memory.get("learned_notes", [])]
    legal_notes = [str(item) for item in memory.get("legal_guardrail_notes", [])]
    phrase_weights = memory.get("phrase_weights", {})
    note_weights = memory.get("note_weights", {})
    category_weights = memory.get("category_weights", {})
    legal_guardrail_weights = memory.get("legal_guardrail_weights", {})
    daily_report = {
        "created_at": time.strftime("%Y%m%d_%H%M%S"),
        "rounds": rounds,
        "source_count_per_round": [analysis.get("source_count", 0) for analysis in analyses],
        "api_used_total": sum(int(analysis.get("api_used_count", 0)) for analysis in analyses),
        "api_fallback_total": sum(int(analysis.get("api_fallback_count", 0)) for analysis in analyses),
        "free_collection_total": sum(int(analysis.get("free_collection_count", 0)) for analysis in analyses),
        "search_url_total": sum(int(analysis.get("search_url_count", 0)) for analysis in analyses),
        "gemini_used_total": sum(1 for analysis in analyses if analysis.get("gemini_used")),
        "official_source_total": official_source_total,
        "low_confidence_source_total": low_confidence_source_total,
        "source_quality_average": source_quality_average,
        "top_categories": top_categories,
        "category_counts": category_counts,
        "legal_risk_counts": legal_risk_counts,
        "learned_phrase_preview": learned_phrases[-20:],
        "learned_note_preview": learned_notes[-20:],
        "legal_guardrail_preview": legal_notes[-20:],
        "top_phrase_weights": top_weight_items(phrase_weights, 20),
        "top_note_weights": top_weight_items(note_weights, 20),
        "top_category_weights": top_weight_items(category_weights, 20),
        "top_legal_guardrail_weights": top_weight_items(legal_guardrail_weights, 20),
        "next_generation_advice": build_next_generation_advice(top_categories, legal_notes),
    }
    output_dir = OUTPUT_ROOT / f"{daily_report['created_at']}_learning_cycle"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "daily_learning_report.json").write_text(
        json.dumps(daily_report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "round_analyses.json").write_text(
        json.dumps(analyses, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "evolution_memory_snapshot.json").write_text(
        json.dumps(memory, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "output_dir": str(output_dir),
        "daily_report": daily_report,
        "analyses": analyses,
        "memory": memory,
    }


def build_next_generation_advice(top_categories: list[str], legal_notes: list[str]) -> list[str]:
    advice: list[str] = []
    if "simple" in top_categories:
        advice.append("작은 화면 가독성을 위해 선을 굵게 하고 장식을 줄이세요.")
    if "cute" in top_categories:
        advice.append("둥근 실루엣, 큰 여백, 작은 손발 비율을 우선하세요.")
    if "daily" in top_categories:
        advice.append("출근, 퇴근, 밥, 잠, 감사 같은 매일 쓰는 상황을 늘리세요.")
    if "reaction" in top_categories:
        advice.append("놀람, 공감, 거절, 확인 같은 짧은 반응형 문구를 강화하세요.")
    if "motion" in top_categories:
        advice.append("움직임은 짧고 반복이 자연스럽게, 프레임과 용량을 보수적으로 관리하세요.")
    if legal_notes:
        advice.append("생성 전 법적 가드레일을 다시 확인하고 특정 작가/IP/문구를 복제하지 마세요.")
    return advice or ["스케치 기반 원본성을 유지하고, 문구와 표정의 실사용성을 먼저 점검하세요."]


def memory_page(message: str = "") -> str:
    memory = load_evolution_memory()
    runs = list(memory.get("research_runs", []))
    phrases = [str(item) for item in memory.get("learned_phrase_additions", [])]
    notes = [str(item) for item in memory.get("learned_notes", [])]
    legal_notes = [str(item) for item in memory.get("legal_guardrail_notes", [])]
    phrase_weight_items = top_weight_items(memory.get("phrase_weights", {}), 20)
    category_weight_items = top_weight_items(memory.get("category_weights", {}), 20)

    def list_items(items: list[str], empty: str) -> str:
        if not items:
            return f"<p>{html.escape(empty)}</p>"
        return "<ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in items[-40:]) + "</ul>"

    def weight_items(items: list[dict[str, object]], empty: str) -> str:
        if not items:
            return f"<p>{html.escape(empty)}</p>"
        return "<ul>" + "".join(
            f"<li><strong>{html.escape(str(item['value']))}</strong> 점수 {html.escape(str(item['score']))}</li>"
            for item in items
        ) + "</ul>"

    run_rows = ""
    for run in runs[-20:]:
        if not isinstance(run, dict):
            continue
        created_at = html.escape(str(run.get("created_at", "")))
        source_count = html.escape(str(run.get("source_count", "")))
        categories = html.escape(", ".join(str(item) for item in run.get("top_categories", [])))
        run_rows += f"<tr><td>{created_at}</td><td>{source_count}</td><td>{categories}</td></tr>"
    if not run_rows:
        run_rows = '<tr><td colspan="3">아직 학습 기록이 없습니다.</td></tr>'

    message_html = f'<section class="notice">{html.escape(message)}</section>' if message else ""
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>v100 Memory</title>
  <style>
    body {{
      margin: 0;
      color: #2d2424;
      font-family: "Malgun Gothic", "Apple SD Gothic Neo", sans-serif;
      background: linear-gradient(135deg, #fffaf0, #eef8ef);
    }}
    main {{ width: min(1100px, calc(100% - 32px)); margin: 0 auto; padding: 42px 0; }}
    .panel {{
      margin-bottom: 18px;
      border: 2px solid #ead8bc;
      border-radius: 28px;
      background: rgba(255,255,255,.82);
      padding: 26px;
      box-shadow: 0 18px 50px rgba(96, 69, 45, .11);
    }}
    h1 {{ margin: 0 0 10px; font-size: clamp(32px, 5vw, 56px); letter-spacing: -0.05em; }}
    h2 {{ margin-top: 0; }}
    p, li, td, th {{ line-height: 1.65; color: #6f625f; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }}
    table {{ width: 100%; border-collapse: collapse; overflow: hidden; border-radius: 16px; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #ead8bc; text-align: left; }}
    th {{ color: #2d2424; background: #fff3d8; }}
    button, a.button {{
      display: inline-block;
      border: 0;
      border-radius: 999px;
      padding: 12px 16px;
      background: #7fd8be;
      color: #2d2424;
      font-weight: 900;
      text-decoration: none;
      cursor: pointer;
      margin-right: 8px;
    }}
    .danger {{ background: #ffb1a1; }}
    .notice {{ margin-bottom: 18px; padding: 14px 16px; border-radius: 18px; background: #e9fff4; border: 1px solid #9be2c7; }}
    @media (max-width: 820px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <main>
    <section class="panel">
      <h1>진화 메모리</h1>
      <p>자료 수집과 반복 학습으로 누적된 문구, 제작 노트, 법적 가드레일을 확인합니다.</p>
      <p>
        <a class="button" href="/">제작 화면으로</a>
      </p>
      <form method="post" action="/memory/compact" style="display:inline">
        <button type="submit">중복 정리</button>
      </form>
      <form method="post" action="/memory/reset" style="display:inline">
        <button class="danger" type="submit">전체 초기화</button>
      </form>
    </section>
    {message_html}
    <section class="panel">
      <h2>요약</h2>
      <p>학습 기록 {len(runs)}개 / 문구 {len(phrases)}개 / 제작 노트 {len(notes)}개 / 법적 가드레일 {len(legal_notes)}개</p>
    </section>
    <section class="grid">
      <div class="panel">
        <h2>상위 문구 점수</h2>
        {weight_items(phrase_weight_items, "아직 문구 점수가 없습니다.")}
      </div>
      <div class="panel">
        <h2>상위 카테고리 점수</h2>
        {weight_items(category_weight_items, "아직 카테고리 점수가 없습니다.")}
      </div>
    </section>
    <section class="panel">
      <h2>최근 학습 기록</h2>
      <table>
        <thead><tr><th>시간</th><th>소스 수</th><th>카테고리</th></tr></thead>
        <tbody>{run_rows}</tbody>
      </table>
    </section>
    <section class="grid">
      <div class="panel">
        <h2>학습 문구</h2>
        {list_items(phrases, "아직 학습된 문구가 없습니다.")}
      </div>
      <div class="panel">
        <h2>제작 노트</h2>
        {list_items(notes, "아직 학습된 제작 노트가 없습니다.")}
      </div>
    </section>
    <section class="panel">
      <h2>법적 가드레일</h2>
      {list_items(legal_notes, "아직 법적 가드레일 메모가 없습니다.")}
    </section>
  </main>
</body>
</html>"""


def system_status_page() -> str:
    dependency_status = {}
    try:
        dependency_status["Pillow"] = Image.__version__
    except Exception:
        dependency_status["Pillow"] = "unknown"
    memory = load_evolution_memory()
    key_status = api_key_status()
    key_rows = "".join(
        f"<li>{html.escape(provider)}: <code>{html.escape(info['env_var'])}</code> "
        f"사용 가능 {html.escape(info['available'])} / 정책 {html.escape(info['window'])} / 한도 {html.escape(info['limit'])} / "
        f"사용 {html.escape(info['used'])} / 남음 {html.escape(info['remaining'])} / "
        f"다음 회복 {html.escape(info['next_reset_at_kst'])}</li>"
        for provider, info in key_status.items()
    )
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>v100 System Status</title>
  <style>
    body {{
      margin: 0;
      color: #2d2424;
      font-family: "Malgun Gothic", "Apple SD Gothic Neo", sans-serif;
      background: linear-gradient(135deg, #fffaf0, #f2fbff);
    }}
    main {{ width: min(920px, calc(100% - 32px)); margin: 0 auto; padding: 42px 0; }}
    .panel {{
      margin-bottom: 18px;
      border: 2px solid #ead8bc;
      border-radius: 28px;
      background: rgba(255,255,255,.84);
      padding: 26px;
      box-shadow: 0 18px 50px rgba(96, 69, 45, .11);
    }}
    h1 {{ margin: 0 0 10px; font-size: clamp(32px, 5vw, 54px); letter-spacing: -0.05em; }}
    p, li {{ line-height: 1.7; color: #6f625f; }}
    code {{ background: #fff3d8; padding: 2px 6px; border-radius: 8px; }}
    a.button {{
      display: inline-block;
      border-radius: 999px;
      padding: 12px 16px;
      background: #7fd8be;
      color: #2d2424;
      font-weight: 900;
      text-decoration: none;
      margin-right: 8px;
    }}
  </style>
</head>
<body>
  <main>
    <section class="panel">
      <h1>실행 상태</h1>
      <p><a class="button" href="/">제작 화면으로</a><a class="button" href="/results">최근 결과물</a><a class="button" href="/memory">진화 메모리</a><a class="button" href="/api-settings">API 키 안내</a><a class="button" href="/release-check">배포 점검</a></p>
    </section>
    <section class="panel">
      <h2>웹서버 비용</h2>
      <p>현재 v100은 <strong>무료 로컬 웹서버</strong>로 실행됩니다. 외부 호스팅, 클라우드 서버, 도메인 연결이 필요 없습니다.</p>
      <ul>
        <li>주소: <code>http://{HOST}:{PORT}</code></li>
        <li>접속 범위: 내 컴퓨터 전용</li>
        <li>서버 비용: 없음</li>
        <li>필수 API 키: 없음</li>
        <li>API 사용 안전장치: Google 계열은 일일 한도, OpenAI는 31일 한도</li>
      </ul>
    </section>
    <section class="panel">
      <h2>API 키 상태</h2>
      <p>키는 앱 파일에 저장하지 않고 환경변수에서만 읽습니다.</p>
      <ul>{key_rows}</ul>
    </section>
    <section class="panel">
      <h2>로컬 데이터</h2>
      <ul>
        <li>출력 폴더: <code>{html.escape(str(OUTPUT_ROOT))}</code></li>
        <li>메모리 파일: <code>{html.escape(str(EVOLUTION_MEMORY_PATH))}</code></li>
        <li>학습 기록: {len(list(memory.get("research_runs", [])))}개</li>
        <li>학습 문구: {len(list(memory.get("learned_phrase_additions", [])))}개</li>
      </ul>
    </section>
    <section class="panel">
      <h2>의존성</h2>
      <ul>
        <li>Python: <code>{html.escape(sys.version.split()[0])}</code></li>
        <li>Pillow: <code>{html.escape(str(dependency_status["Pillow"]))}</code></li>
      </ul>
    </section>
  </main>
</body>
</html>"""


def api_settings_page(message: str = "") -> str:
    key_status = api_key_status()
    rows = "".join(
        f"<tr><td>{html.escape(provider)}</td><td><code>{html.escape(info['env_var'])}</code></td>"
        f"<td><code>{html.escape(info['limit_env_var'])}</code></td>"
        f"<td>{html.escape(info['available'])}</td><td>{html.escape(info['enabled'])}</td>"
        f"<td>{html.escape(info['window'])}</td>"
        f"<td>{html.escape(info['limit'])}</td><td>{html.escape(info['used'])}</td><td>{html.escape(info['remaining'])}</td>"
        f"<td>{html.escape(info['next_reset_at_kst'])}</td><td>{html.escape(info['masked'])}</td></tr>"
        for provider, info in key_status.items()
    )
    cse_id = os.environ.get("GOOGLE_CSE_ID", "")
    message_html = f'<section class="notice">{html.escape(message)}</section>' if message else ""
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>v100 API Settings</title>
  <style>
    body {{ margin: 0; color: #2d2424; font-family: "Malgun Gothic", sans-serif; background: linear-gradient(135deg, #fffaf0, #f8f2ff); }}
    main {{ width: min(920px, calc(100% - 32px)); margin: 0 auto; padding: 42px 0; }}
    .panel {{ margin-bottom: 18px; border: 2px solid #ead8bc; border-radius: 28px; background: rgba(255,255,255,.86); padding: 26px; box-shadow: 0 18px 50px rgba(96,69,45,.11); }}
    h1 {{ margin: 0 0 10px; font-size: clamp(32px, 5vw, 54px); letter-spacing: -0.05em; }}
    p, li, td, th {{ line-height: 1.65; color: #6f625f; }}
    code {{ background: #fff3d8; padding: 2px 6px; border-radius: 8px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #ead8bc; text-align: left; }}
    th {{ color: #2d2424; background: #fff3d8; }}
    a.button, button {{ display: inline-block; border: 0; border-radius: 999px; padding: 12px 16px; background: #7fd8be; color: #2d2424; font-weight: 900; text-decoration: none; margin-right: 8px; cursor: pointer; }}
    .notice {{ margin-bottom: 18px; padding: 14px 16px; border-radius: 18px; background: #e9fff4; border: 1px solid #9be2c7; }}
  </style>
</head>
<body>
  <main>
    <section class="panel">
      <h1>API 키 안내</h1>
      <p><a class="button" href="/">제작 화면으로</a><a class="button" href="/status">실행 상태</a><a class="button" href="/release-check">배포 점검</a></p>
      <form method="post" action="/api-usage/reset">
        <button type="submit">API 사용량 원장 초기화</button>
      </form>
    </section>
    {message_html}
    <section class="panel">
      <h2>현재 상태</h2>
      <table>
        <thead><tr><th>Provider</th><th>키 환경변수</th><th>한도 환경변수</th><th>키 있음</th><th>사용 허용</th><th>리셋 정책</th><th>한도</th><th>사용</th><th>남음</th><th>다음 회복(KST)</th><th>표시</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </section>
    <section class="panel">
      <h2>키 사용 방식</h2>
      <p>v100은 API 키를 코드나 리포트에 저장하지 않습니다. Windows 환경변수에 넣으면 앱 실행 시 읽습니다.</p>
      <ul>
        <li><code>YOUTUBE_API_KEY</code>: 유튜브 영상 제목/설명 수집 고도화</li>
        <li><code>SEARCH_API_KEY</code>: 향후 검색 API 연동용 자리</li>
        <li><code>GEMINI_API_KEY</code>: 향후 구글 Gemini 분석 고도화용 자리</li>
        <li><code>OPENAI_API_KEY</code>: 향후 문구/분석 고도화용 자리</li>
      </ul>
      <p>비용 방지를 위해 키가 있어도 한도 환경변수가 0이면 API 호출을 막습니다.</p>
      <ul>
        <li><code>YOUTUBE_API_DAILY_CALL_LIMIT</code>: 하루 유튜브 API 호출 허용 횟수</li>
        <li><code>SEARCH_API_DAILY_CALL_LIMIT</code>: 하루 검색 API 호출 허용 횟수</li>
        <li><code>GOOGLE_CSE_ID</code>: Google Custom Search 검색 엔진 ID, 현재 {'설정됨' if cse_id else '미설정'}</li>
        <li><code>GEMINI_API_DAILY_CALL_LIMIT</code>: 하루 Gemini API 호출 허용 횟수, Pacific 자정 리셋</li>
        <li><code>OPENAI_API_31D_CALL_LIMIT</code>: 최근 31일 OpenAI API 호출 허용 횟수</li>
      </ul>
      <p>현재 필수 키는 없습니다. 키가 없으면 URL 제목 수집과 조사 메모 분석으로 동작합니다.</p>
    </section>
  </main>
</body>
</html>"""


def load_recent_results(limit: int = 30) -> list[dict[str, object]]:
    if not OUTPUT_ROOT.exists():
        return []
    rows: list[dict[str, object]] = []
    for output_dir in sorted(OUTPUT_ROOT.iterdir(), key=lambda path: path.stat().st_mtime, reverse=True):
        if not output_dir.is_dir():
            continue
        report_path = output_dir / "build_report.json"
        if not report_path.exists():
            continue
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(report, dict):
            continue
        gallery = report.get("preview_gallery", {}) if isinstance(report.get("preview_gallery", {}), dict) else {}
        evidence = report.get("creator_evidence_package", {}) if isinstance(report.get("creator_evidence_package", {}), dict) else {}
        revised = report.get("revised_phrase_variant", {}) if isinstance(report.get("revised_phrase_variant", {}), dict) else {}
        readiness = report.get("submission_readiness", {}) if isinstance(report.get("submission_readiness", {}), dict) else {}
        phrase_quality = report.get("phrase_quality", {}) if isinstance(report.get("phrase_quality", {}), dict) else {}
        rows.append(
            {
                "folder": str(output_dir),
                "name": output_dir.name,
                "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(output_dir.stat().st_mtime)),
                "character_name": report.get("character_name", ""),
                "product_label": report.get("product_label", ""),
                "workflow_label": report.get("workflow_label", ""),
                "validation_status": report.get("validation_status", ""),
                "readiness_score": readiness.get("score", ""),
                "readiness_label": readiness.get("decision_label", ""),
                "phrase_quality_status": phrase_quality.get("status", ""),
                "phrase_quality_score": phrase_quality.get("score", ""),
                "zip": report.get("zip", ""),
                "gallery": gallery.get("html", ""),
                "revised_zip": revised.get("zip", ""),
                "evidence_zip": evidence.get("zip", ""),
                "build_report": str(report_path),
            }
        )
        if len(rows) >= limit:
            break
    return rows


def safe_output_dir_by_name(name: str) -> Path | None:
    safe_name = Path(name).name
    candidate = OUTPUT_ROOT / safe_name
    try:
        resolved = candidate.resolve()
        output_root = OUTPUT_ROOT.resolve()
    except Exception:
        return None
    if not str(resolved).startswith(str(output_root)) or not resolved.is_dir():
        return None
    return candidate


def read_json_file(path: Path, fallback: object) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def bytes_label(size: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(max(size, 0))
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def directory_size(path: Path) -> int:
    total = 0
    if not path.exists():
        return total
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                continue
    return total


def release_exclusion_reason(path: Path) -> str | None:
    rel = path.relative_to(Path("."))
    parts = rel.parts
    excluded_dirs = {
        ".git",
        ".vscode",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        "outputs",
        "output",
        "release",
        "github_backup",
        "_github_upload",
        "_review_extract",
        "_review_v92",
        "_final_zip_recheck",
        "_deliverables_v90",
    }
    excluded_prefixes = ("_test_localappdata",)
    excluded_suffixes = (
        ".pyc",
        ".pyo",
        ".pyd",
        ".log",
        ".tmp",
        ".bak",
        ".zip",
        ".exe",
        ".sha256.txt",
    )
    secret_patterns = ("api_key", "apikey", "secret", "token", ".env")
    for part in parts:
        lowered = part.lower()
        if lowered in excluded_dirs:
            return f"{part} 폴더 제외"
        if any(lowered.startswith(prefix) for prefix in excluded_prefixes):
            return f"{part} 임시 폴더 제외"
    lowered_name = path.name.lower()
    if lowered_name in {"thumbs.db", ".ds_store"}:
        return "OS 캐시 파일 제외"
    if lowered_name.endswith(excluded_suffixes):
        return "빌드/캐시 산출물 제외"
    if any(pattern in lowered_name for pattern in secret_patterns):
        return "키/비밀값 가능성 파일 제외"
    return None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def release_allowlist_files() -> list[Path]:
    candidates = [
        Path("app.py"),
        Path("README.md"),
        Path("QUICK_START_OTHER_PC_KO.txt"),
        Path("DOWNLOAD_LATEST_FROM_GITHUB_KO.md"),
        Path("RELEASE_NOTES_KO.md"),
        Path("TROUBLESHOOTING_KO.md"),
        Path("SYNC_STATE_GUIDE_KO.md"),
        Path("requirements.txt"),
        Path("DOWNLOAD_LATEST_RELEASE.bat"),
        Path("EXPORT_SYNC_STATE.bat"),
        Path("IMPORT_SYNC_STATE.bat"),
        Path("START_HERE.bat"),
        Path("START_WINDOWS.bat"),
        Path("RUN_SERVER_NO_BROWSER.bat"),
        Path("VERIFY_PACKAGE.bat"),
        Path("START_MAC_LINUX.sh"),
        Path("KAKAO_SAFE_WORKFLOW.md"),
        Path("RESEARCH_SOURCES.md"),
        Path("memory/evolution_memory.json"),
        Path("memory/api_usage_ledger.json"),
        Path("scripts/stop_port.py"),
        Path("scripts/wait_for_port.py"),
        Path("scripts/verify_package.py"),
        Path("scripts/export_sync_state.py"),
        Path("scripts/import_sync_state.py"),
    ]
    return [path for path in candidates if path.exists() and path.is_file()]


def release_excluded_summary(included_files: list[Path]) -> dict[str, int]:
    included = {path.resolve() for path in included_files}
    summary: dict[str, int] = {}
    for item in Path(".").rglob("*"):
        if not item.is_file() or item.resolve() in included:
            continue
        reason = release_exclusion_reason(item) or "v100 portable 핵심 구성 외 파일 제외"
        summary[reason] = summary.get(reason, 0) + 1
    return summary


def build_release_package() -> dict[str, object]:
    RELEASE_ROOT.mkdir(exist_ok=True)
    timestamp = kst_now().strftime("%Y%m%d_%H%M%S")
    package_stem = f"kakao_emoticon_v100_clean_portable_{timestamp}"
    zip_path = RELEASE_ROOT / f"{package_stem}.zip"
    checksum_path = RELEASE_ROOT / f"{package_stem}.sha256.txt"
    report_path = RELEASE_ROOT / f"{package_stem}_report.json"
    latest_zip_path = RELEASE_ROOT / "kakao_emoticon_v100_clean_latest.zip"
    latest_checksum_path = RELEASE_ROOT / "kakao_emoticon_v100_clean_latest.sha256.txt"
    latest_report_path = RELEASE_ROOT / "kakao_emoticon_v100_clean_latest_report.json"
    package_root_name = "kakao_emoticon_v100_clean"

    included_files = release_allowlist_files()
    excluded_summary = release_excluded_summary(included_files)

    manifest = {
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "created_at_kst": kst_now().isoformat(),
        "package_type": "portable_standard_zip",
        "included_file_count": len(included_files),
        "included_files": [path.as_posix() for path in included_files],
        "excluded_summary": excluded_summary,
        "run_after_extract": "START_HERE.bat",
        "direct_start": "START_WINDOWS.bat",
        "verify_after_extract": "VERIFY_PACKAGE.bat",
        "no_browser_server": "RUN_SERVER_NO_BROWSER.bat",
        "local_url": f"http://{HOST}:{PORT}",
        "notes": [
            "표준 .zip 형식입니다. 알집에서도 열 수 있지만 .alz 전용 형식은 사용하지 않습니다.",
            "outputs 폴더는 용량이 커서 기본 제외했습니다. 결과물은 필요할 때 별도로 보관하세요.",
            "API 키, .env, 로그, 캐시, Git 폴더는 기본 제외했습니다.",
            "압축 해제 후 VERIFY_PACKAGE.bat로 실행 전 검증을 할 수 있습니다.",
        ],
    }

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            f"{package_root_name}/RELEASE_MANIFEST.json",
            json.dumps(manifest, ensure_ascii=False, indent=2),
        )
        for file_path in included_files:
            archive.write(file_path, Path(package_root_name) / file_path)

    checksum = sha256_file(zip_path)
    checksum_path.write_text(f"{checksum}  {zip_path.name}\n", encoding="utf-8")
    report = {
        **manifest,
        "zip_path": str(zip_path),
        "zip_name": zip_path.name,
        "latest_zip_path": str(latest_zip_path),
        "latest_zip_name": latest_zip_path.name,
        "latest_checksum_path": str(latest_checksum_path),
        "latest_report_path": str(latest_report_path),
        "zip_size_bytes": zip_path.stat().st_size,
        "zip_size_label": bytes_label(zip_path.stat().st_size),
        "sha256": checksum,
        "checksum_path": str(checksum_path),
        "report_path": str(report_path),
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copy2(zip_path, latest_zip_path)
    latest_checksum_path.write_text(f"{checksum}  {latest_zip_path.name}\n", encoding="utf-8")
    latest_report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def release_result_page(report: dict[str, object]) -> str:
    zip_path = Path(str(report.get("zip_path", "")))
    checksum_path = Path(str(report.get("checksum_path", "")))
    report_path = Path(str(report.get("report_path", "")))
    latest_zip_path = Path(str(report.get("latest_zip_path", "")))
    latest_checksum_path = Path(str(report.get("latest_checksum_path", "")))
    latest_report_path = Path(str(report.get("latest_report_path", "")))
    zip_href = "/" + zip_path.as_posix() if zip_path.exists() else ""
    checksum_href = "/" + checksum_path.as_posix() if checksum_path.exists() else ""
    report_href = "/" + report_path.as_posix() if report_path.exists() else ""
    latest_zip_href = "/" + latest_zip_path.as_posix() if latest_zip_path.exists() else ""
    latest_checksum_href = "/" + latest_checksum_path.as_posix() if latest_checksum_path.exists() else ""
    latest_report_href = "/" + latest_report_path.as_posix() if latest_report_path.exists() else ""
    excluded = report.get("excluded_summary", {})
    excluded_rows = ""
    if isinstance(excluded, dict):
        excluded_rows = "".join(
            f"<tr><td>{html.escape(str(reason))}</td><td>{html.escape(str(count))}</td></tr>"
            for reason, count in sorted(excluded.items())
        )
    if not excluded_rows:
        excluded_rows = "<tr><td colspan='2'>제외 항목 없음</td></tr>"
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>v100 Release Package Created</title>
  <style>
    body {{ margin:0; color:#2d2424; font-family:"Malgun Gothic", sans-serif; background:linear-gradient(135deg,#fffaf0,#eef8ef); }}
    main {{ width:min(980px, calc(100% - 32px)); margin:0 auto; padding:42px 0; }}
    .panel {{ border:2px solid #ead8bc; border-radius:28px; background:rgba(255,255,255,.88); padding:24px; box-shadow:0 18px 50px rgba(96,69,45,.11); margin-bottom:18px; }}
    h1 {{ margin:0 0 10px; font-size:clamp(32px,5vw,54px); letter-spacing:-.05em; }}
    p, li, td, th {{ line-height:1.65; color:#6f625f; }}
    code {{ background:#fff3d8; padding:2px 7px; border-radius:8px; }}
    a.button {{ display:inline-block; border-radius:999px; padding:12px 16px; background:#7fd8be; color:#2d2424; font-weight:900; text-decoration:none; margin:4px 6px 4px 0; }}
    table {{ width:100%; border-collapse:collapse; }}
    th, td {{ text-align:left; padding:10px 12px; border-bottom:1px solid #ead8bc; }}
    th {{ color:#2d2424; background:#fff3d8; }}
  </style>
</head>
<body>
  <main>
    <section class="panel">
      <h1>표준 ZIP 생성 완료</h1>
      <p>다른 PC에서 압축을 풀고 <code>START_WINDOWS.bat</code>을 실행하면 이어서 사용할 수 있습니다.</p>
      <p>
        <a class="button" href="{html.escape(zip_href)}">ZIP 다운로드</a>
        <a class="button" href="{html.escape(latest_zip_href)}">최신 ZIP 고정 링크</a>
        <a class="button" href="{html.escape(checksum_href)}">SHA256 보기</a>
        <a class="button" href="{html.escape(latest_checksum_href)}">최신 SHA256</a>
        <a class="button" href="{html.escape(report_href)}">패키지 리포트</a>
        <a class="button" href="{html.escape(latest_report_href)}">최신 리포트</a>
        <a class="button" href="/release-check">배포 점검으로</a>
      </p>
    </section>
    <section class="panel">
      <h2>패키지 정보</h2>
      <ul>
        <li>파일명: <code>{html.escape(str(report.get("zip_name", "")))}</code></li>
        <li>최신 고정 파일명: <code>{html.escape(str(report.get("latest_zip_name", "")))}</code></li>
        <li>크기: <strong>{html.escape(str(report.get("zip_size_label", "")))}</strong></li>
        <li>포함 파일 수: {html.escape(str(report.get("included_file_count", "")))}</li>
        <li>SHA256: <code>{html.escape(str(report.get("sha256", "")))}</code></li>
      </ul>
    </section>
    <section class="panel">
      <h2>자동 제외된 항목</h2>
      <table>
        <thead><tr><th>이유</th><th>파일 수</th></tr></thead>
        <tbody>{excluded_rows}</tbody>
      </table>
    </section>
  </main>
</body>
</html>"""


def release_check_page() -> str:
    required_files = [
        ("앱 본체", Path("app.py")),
        ("실행 안내", Path("README.md")),
        ("Windows 실행", Path("START_WINDOWS.bat")),
        ("브라우저 미실행 서버", Path("RUN_SERVER_NO_BROWSER.bat")),
        ("의존성 목록", Path("requirements.txt")),
        ("카카오 안전 워크플로우", Path("KAKAO_SAFE_WORKFLOW.md")),
        ("조사 출처 메모", Path("RESEARCH_SOURCES.md")),
        ("진화 메모리", EVOLUTION_MEMORY_PATH),
        ("API 사용량 원장", API_USAGE_LEDGER_PATH),
    ]
    exclude_targets = ["outputs/", "__pycache__/", ".venv/", "github_backup/", "_github_upload/"]
    gitignore_text = Path(".gitignore").read_text(encoding="utf-8") if Path(".gitignore").exists() else ""

    checks: list[dict[str, str]] = []
    for label, path in required_files:
        exists = path.exists()
        checks.append(
            {
                "label": label,
                "status": "pass" if exists else "fail",
                "message": f"{path.as_posix()} 확인됨" if exists else f"{path.as_posix()} 없음",
            }
        )

    for target in exclude_targets:
        normalized = target.rstrip("/")
        ignored = target in gitignore_text or normalized in gitignore_text
        checks.append(
            {
                "label": f"배포 제외: {target}",
                "status": "pass" if ignored else "warn",
                "message": ".gitignore에 등록됨" if ignored else "최종 ZIP 만들 때 직접 제외 필요",
            }
        )

    results = load_recent_results(limit=200)
    output_size = directory_size(OUTPUT_ROOT)
    output_message = f"결과 폴더 {len(results)}개, 전체 {bytes_label(output_size)}"
    checks.append(
        {
            "label": "결과물 폴더",
            "status": "pass" if results else "warn",
            "message": output_message if results else "아직 생성 결과 없음. 앱 배포는 가능하지만 샘플 검수는 부족합니다.",
        }
    )
    checks.append(
        {
            "label": "GitHub 연결",
            "status": "pass" if Path(".git").exists() else "warn",
            "message": "Git 저장소 확인됨" if Path(".git").exists() else "Git 저장소 정보가 없습니다.",
        }
    )

    fail_count = sum(1 for item in checks if item["status"] == "fail")
    warn_count = sum(1 for item in checks if item["status"] == "warn")
    if fail_count:
        readiness = "수정 필요"
        readiness_class = "fail"
        readiness_text = "필수 파일이 빠져 있어 최종 ZIP 전에 보완이 필요합니다."
    elif warn_count:
        readiness = "거의 준비됨"
        readiness_class = "warn"
        readiness_text = "실행은 가능하지만, ZIP 구성과 샘플 결과물은 한 번 더 확인하면 좋습니다."
    else:
        readiness = "준비 양호"
        readiness_class = "pass"
        readiness_text = "다른 PC에서 이어 쓰기 위한 기본 구성이 잘 갖춰져 있습니다."

    rows = "".join(
        f"""
        <tr>
          <td><span class="pill {html.escape(item["status"])}">{html.escape(item["status"].upper())}</span></td>
          <td>{html.escape(item["label"])}</td>
          <td>{html.escape(item["message"])}</td>
        </tr>
        """
        for item in checks
    )
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>v100 Release Check</title>
  <style>
    body {{ margin:0; color:#2d2424; font-family:"Malgun Gothic", sans-serif; background:linear-gradient(135deg,#fffaf0,#eef8ef 55%,#f6efe1); }}
    main {{ width:min(1080px, calc(100% - 32px)); margin:0 auto; padding:42px 0; }}
    .panel {{ border:2px solid #ead8bc; border-radius:28px; background:rgba(255,255,255,.88); padding:24px; box-shadow:0 18px 50px rgba(96,69,45,.11); margin-bottom:18px; }}
    h1 {{ margin:0 0 10px; font-size:clamp(32px,5vw,54px); letter-spacing:-.05em; }}
    h2 {{ margin:0 0 10px; }}
    p, li, td, th {{ line-height:1.65; color:#6f625f; }}
    table {{ width:100%; border-collapse:collapse; overflow:hidden; border-radius:18px; }}
    th, td {{ text-align:left; padding:12px; border-bottom:1px solid #ead8bc; vertical-align:top; }}
    th {{ color:#2d2424; background:#fff3d8; }}
    code {{ background:#fff3d8; padding:2px 7px; border-radius:8px; }}
    a.button {{ display:inline-block; border-radius:999px; padding:10px 14px; background:#7fd8be; color:#2d2424; font-weight:900; text-decoration:none; margin:4px 6px 4px 0; }}
    button {{ border:0; border-radius:999px; padding:12px 16px; background:#2d2424; color:white; font-weight:900; cursor:pointer; margin-top:8px; }}
    .hero {{ display:grid; grid-template-columns:1.2fr .8fr; gap:18px; align-items:stretch; }}
    .score {{ display:flex; flex-direction:column; justify-content:center; min-height:180px; }}
    .score strong {{ font-size:clamp(34px,6vw,62px); letter-spacing:-.06em; }}
    .pill {{ display:inline-block; border-radius:999px; padding:6px 10px; font-weight:900; font-size:12px; }}
    .pass {{ background:#e9fff4; color:#22725b; border:1px solid #9be2c7; }}
    .warn {{ background:#fff3d8; color:#8a5a00; border:1px solid #f2cc80; }}
    .fail {{ background:#ffe9e5; color:#9f3729; border:1px solid #f0a096; }}
    .pack {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; }}
    @media (max-width:820px) {{ .hero, .pack {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div class="panel">
        <h1>최종 배포 점검</h1>
        <p>다른 PC에서도 이어서 쓸 수 있도록 ZIP 만들기 전에 필수 파일, 제외 폴더, 결과물 상태를 확인합니다.</p>
        <p><a class="button" href="/">제작 화면</a><a class="button" href="/results">최근 결과물</a><a class="button" href="/status">실행 상태</a><a class="button" href="/api-settings">API 키 안내</a></p>
        <form method="post" action="/package-release">
          <button type="submit">다른 PC 이동용 표준 ZIP 만들기</button>
        </form>
      </div>
      <div class="panel score">
        <span class="pill {readiness_class}">RELEASE</span>
        <strong>{html.escape(readiness)}</strong>
        <p>{html.escape(readiness_text)}</p>
      </div>
    </section>
    <section class="panel">
      <h2>점검 결과</h2>
      <table>
        <thead><tr><th>상태</th><th>항목</th><th>내용</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </section>
    <section class="pack">
      <div class="panel">
        <h2>최종 ZIP에 넣을 것</h2>
        <ul>
          <li><code>app.py</code>, <code>README.md</code>, <code>QUICK_START_OTHER_PC_KO.txt</code>, <code>DOWNLOAD_LATEST_FROM_GITHUB_KO.md</code>, <code>RELEASE_NOTES_KO.md</code>, <code>TROUBLESHOOTING_KO.md</code>, <code>SYNC_STATE_GUIDE_KO.md</code>, <code>requirements.txt</code></li>
          <li><code>DOWNLOAD_LATEST_RELEASE.bat</code>, <code>EXPORT_SYNC_STATE.bat</code>, <code>IMPORT_SYNC_STATE.bat</code>, <code>START_HERE.bat</code>, <code>START_WINDOWS.bat</code>, <code>RUN_SERVER_NO_BROWSER.bat</code>, <code>VERIFY_PACKAGE.bat</code></li>
          <li><code>KAKAO_SAFE_WORKFLOW.md</code>, <code>RESEARCH_SOURCES.md</code></li>
          <li><code>memory/*.json</code> 기본 메모리와 API 사용량 원장</li>
          <li><code>scripts/stop_port.py</code>, <code>scripts/wait_for_port.py</code>, <code>scripts/verify_package.py</code>, <code>scripts/export_sync_state.py</code>, <code>scripts/import_sync_state.py</code> 실행 보조 스크립트</li>
        </ul>
      </div>
      <div class="panel">
        <h2>기본 제외할 것</h2>
        <ul>
          <li><code>outputs/</code>: 생성 결과물은 용량이 커서 기본 배포 ZIP에서 제외</li>
          <li><code>.venv/</code>, <code>__pycache__/</code>: PC마다 다시 만들 수 있는 실행 캐시</li>
          <li><code>.git/</code>, <code>github_backup/</code>, <code>_github_upload/</code>: 개발/백업용 폴더</li>
          <li>v90 레거시 배치/설치/검사 스크립트와 개발 도구 폴더</li>
          <li>완성 배포는 알집 전용 형식보다 표준 <code>.zip</code> 권장</li>
        </ul>
      </div>
    </section>
  </main>
</body>
</html>"""


def results_page() -> str:
    rows = load_recent_results()
    row_html = ""
    for row in rows:
        links = []
        for label, key in [
            ("상세", "detail"),
            ("갤러리", "gallery"),
            ("원본 ZIP", "zip"),
            ("수정판 ZIP", "revised_zip"),
            ("증빙 ZIP", "evidence_zip"),
            ("리포트", "build_report"),
        ]:
            value = str(row.get(key, ""))
            if key == "detail":
                value = f"/result?name={quote(str(row.get('name', '')))}"
            if value:
                href = value if value.startswith("/") else "/" + value.replace("\\", "/")
                links.append(f"<a href='{html.escape(href)}'>{label}</a>")
        row_html += f"""
        <tr>
          <td>{html.escape(str(row.get("mtime", "")))}</td>
          <td><strong>{html.escape(str(row.get("character_name", "")))}</strong><br><small>{html.escape(str(row.get("name", "")))}</small></td>
          <td>{html.escape(str(row.get("product_label", "")))}</td>
          <td>{html.escape(str(row.get("validation_status", "")))}</td>
          <td>{html.escape(str(row.get("readiness_score", "")))} / {html.escape(str(row.get("readiness_label", "")))}</td>
          <td>{html.escape(str(row.get("phrase_quality_status", "")))} / {html.escape(str(row.get("phrase_quality_score", "")))}</td>
          <td>{" ".join(links)}</td>
        </tr>
        """
    if not row_html:
        row_html = "<tr><td colspan='7'>아직 생성 결과가 없습니다.</td></tr>"
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>v100 Results</title>
  <style>
    body {{ margin:0; color:#2d2424; font-family:"Malgun Gothic", sans-serif; background:linear-gradient(135deg,#fffaf0,#eef8ef); }}
    main {{ width:min(1180px, calc(100% - 32px)); margin:0 auto; padding:42px 0; }}
    .panel {{ border:2px solid #ead8bc; border-radius:28px; background:rgba(255,255,255,.86); padding:24px; box-shadow:0 18px 50px rgba(96,69,45,.11); margin-bottom:18px; }}
    h1 {{ margin:0 0 10px; font-size:clamp(32px,5vw,54px); letter-spacing:-.05em; }}
    p, td, th, small {{ line-height:1.6; color:#6f625f; }}
    table {{ width:100%; border-collapse:collapse; overflow:hidden; border-radius:18px; }}
    th, td {{ text-align:left; padding:12px; border-bottom:1px solid #ead8bc; vertical-align:top; }}
    th {{ color:#2d2424; background:#fff3d8; }}
    a {{ display:inline-block; margin:2px 4px 2px 0; color:#2d2424; font-weight:900; text-decoration:none; background:#e9fff4; border:1px solid #9be2c7; border-radius:999px; padding:6px 10px; }}
    a.nav {{ background:#7fd8be; border-color:#7fd8be; }}
    @media (max-width: 860px) {{ table {{ font-size:13px; }} th:nth-child(3), td:nth-child(3) {{ display:none; }} }}
  </style>
</head>
<body>
<main>
  <section class="panel">
    <h1>최근 결과물</h1>
    <p>최근 생성한 결과 폴더와 갤러리, ZIP, 리포트를 바로 확인합니다.</p>
    <p><a class="nav" href="/">제작 화면</a><a class="nav" href="/memory">진화 메모리</a><a class="nav" href="/status">실행 상태</a><a class="nav" href="/release-check">배포 점검</a></p>
  </section>
  <section class="panel">
    <table>
      <thead>
        <tr><th>시간</th><th>캐릭터</th><th>상품</th><th>검사</th><th>준비 점수</th><th>문구 품질</th><th>바로가기</th></tr>
      </thead>
      <tbody>{row_html}</tbody>
    </table>
  </section>
</main>
</body>
</html>"""


def result_detail_page(name: str) -> str:
    output_dir = safe_output_dir_by_name(name)
    if output_dir is None:
        return page(error="결과 폴더를 찾을 수 없습니다.")
    report = read_json_file(output_dir / "build_report.json", {})
    if not isinstance(report, dict):
        return page(error="build_report.json을 읽을 수 없습니다.")
    readiness = read_json_file(output_dir / "submission_readiness_report.json", {})
    validation = read_json_file(output_dir / "validation_report.json", {})
    phrase_quality = read_json_file(output_dir / "phrase_quality_report.json", {})
    replacements = read_json_file(output_dir / "phrase_replacement_suggestions.json", {})
    revised_apply = read_json_file(output_dir / "revised_phrase_variant" / "revised_phrase_apply_report.json", {})
    revised_refine = read_json_file(output_dir / "revised_phrase_variant" / "revised_phrase_refinement_report.json", {})
    evidence = report.get("creator_evidence_package", {}) if isinstance(report.get("creator_evidence_package", {}), dict) else {}
    gallery = report.get("preview_gallery", {}) if isinstance(report.get("preview_gallery", {}), dict) else {}
    revised = report.get("revised_phrase_variant", {}) if isinstance(report.get("revised_phrase_variant", {}), dict) else {}

    def link(label: str, path_value: object) -> str:
        value = str(path_value or "")
        if not value:
            return ""
        href = "/" + value.replace("\\", "/")
        return f"<a href='{html.escape(href)}'>{html.escape(label)}</a>"

    def tone(value: object) -> str:
        text = str(value or "").lower()
        if any(word in text for word in ["fail", "blocked", "reject", "위험", "반려"]):
            return "danger"
        if any(word in text for word in ["warn", "manual", "missing", "수정", "주의", "권장"]):
            return "warn"
        if any(word in text for word in ["pass", "ready", "가능", "완료"]):
            return "good"
        return "neutral"

    def badge(label: str, value: object) -> str:
        text = str(value or "미확인")
        return f"<span class='badge {tone(text)}'>{html.escape(label)}: {html.escape(text)}</span>"

    submission = report.get("submission_readiness", {})
    if not isinstance(submission, dict):
        submission = {}
    phrase_summary = report.get("phrase_quality", {})
    if not isinstance(phrase_summary, dict):
        phrase_summary = {}
    validation_status = report.get("validation_status", "")
    validation_fail_count = report.get("validation_fail_count", "")
    validation_warn_count = report.get("validation_warn_count", "")
    zip_purpose_label = report.get("zip_purpose_label", "ZIP 목적 미확인")
    zip_decision = report.get("zip_decision", "")
    zip_next_action = report.get("zip_next_action", "")
    readiness_score = submission.get("score", "")
    readiness_label = submission.get("decision_label", "")
    phrase_status = phrase_summary.get("status", "")
    phrase_score = phrase_summary.get("score", "")
    revised_status = revised.get("quality_status", "")
    revised_score = revised.get("quality_score", "")

    def file_href(path: Path) -> str:
        return "/" + str(path).replace("\\", "/")

    def preview_pair_html(limit: int = 8) -> str:
        original_files = sorted((output_dir / "preview_jpg").glob("*.jpg"))[:limit]
        revised_files = sorted((output_dir / "revised_phrase_variant" / "preview_jpg").glob("*.jpg"))[:limit]
        if not original_files and not revised_files:
            return "<p>아직 표시할 미리보기 이미지가 없습니다.</p>"
        cards: list[str] = []
        max_count = max(len(original_files), len(revised_files))
        for index in range(max_count):
            original = original_files[index] if index < len(original_files) else None
            revised_preview = revised_files[index] if index < len(revised_files) else None
            original_img = (
                f"<a href='{html.escape(file_href(original))}'><img src='{html.escape(file_href(original))}' alt='원본 {index + 1}'></a>"
                if original
                else "<div class='missing-preview'>원본 없음</div>"
            )
            revised_img = (
                f"<a href='{html.escape(file_href(revised_preview))}'><img src='{html.escape(file_href(revised_preview))}' alt='수정본 {index + 1}'></a>"
                if revised_preview
                else "<div class='missing-preview'>수정본 없음</div>"
            )
            cards.append(
                f"""
                <div class="thumb-card">
                  <div class="thumb-title">#{index + 1:02d}</div>
                  <div class="thumb-pair">
                    <div><span>원본</span>{original_img}</div>
                    <div><span>수정본</span>{revised_img}</div>
                  </div>
                </div>
                """
            )
        return "".join(cards)

    preview_pairs_html = preview_pair_html()

    validation_issues = validation.get("issues", []) if isinstance(validation, dict) else []
    validation_rules = validation.get("rules", {}) if isinstance(validation, dict) else {}
    validation_html = html_list(
        [
            f"{issue.get('level', '')}: {issue.get('file', '')} / {issue.get('message', '')}"
            for issue in validation_issues[:12]
            if isinstance(issue, dict)
        ],
        "제출 ZIP/이미지 규격 이슈가 없습니다.",
    )
    validation_rule_html = html_list(
        [
            f"상품: {validation_rules.get('product_label', '')}",
            f"캔버스: {validation_rules.get('canvas_px', '')}",
            f"필요 PNG: {validation_rules.get('static_png_count', '')}",
            f"필요 GIF: {validation_rules.get('animated_gif_count', '')}",
            f"허용 확장자: {', '.join(str(ext) for ext in validation_rules.get('submit_zip_allows', []))}",
        ]
        if isinstance(validation_rules, dict)
        else [],
        "검증 규칙 정보가 없습니다.",
    )
    top_risks = readiness.get("top_risks", []) if isinstance(readiness, dict) else []
    readiness_checks = readiness.get("checks", []) if isinstance(readiness, dict) else []
    checks_html = html_list(
        [
            f"{check.get('name', 'check')}: {check.get('status', '')} / {check.get('message', '')}"
            for check in readiness_checks[:10]
            if isinstance(check, dict)
        ],
        "세부 제출 준비 체크 항목이 없습니다.",
    )
    risk_html = html_list(
        [
            f"{risk.get('name', '점검')}: {risk.get('message', '')} / {risk.get('recommended_action', '')}"
            for risk in top_risks[:8]
            if isinstance(risk, dict)
        ],
        "큰 주의 항목은 감지되지 않았습니다.",
    )
    quality_issues = phrase_quality.get("issues", []) if isinstance(phrase_quality, dict) else []
    quality_html = html_list(
        [
            f"#{issue.get('slot', '')} {issue.get('phrase', '')}: {issue.get('message', '')} -> {issue.get('suggestion', '')}"
            for issue in quality_issues[:10]
            if isinstance(issue, dict)
        ],
        "문구 품질 이슈가 없습니다.",
    )
    replacement_items = replacements.get("suggestions", []) if isinstance(replacements, dict) else []
    replacement_html = html_list(
        [
            f"#{item.get('slot', '')} {item.get('original', '')} -> {item.get('recommended', '')} ({', '.join(str(c) for c in item.get('candidates', [])[:4])})"
            for item in replacement_items[:10]
            if isinstance(item, dict)
        ],
        "대체 문구 제안이 없습니다.",
    )
    apply_items = revised_apply.get("applied", []) if isinstance(revised_apply, dict) else []
    apply_html = html_list(
        [
            f"#{item.get('slot', '')} {item.get('original', '')} -> {item.get('replacement', '')}"
            for item in apply_items[:12]
            if isinstance(item, dict)
        ],
        "수정판에 적용된 대체 문구가 없습니다.",
    )
    refine_items = revised_refine.get("changes", []) if isinstance(revised_refine, dict) else []
    refine_html = html_list(
        [
            f"#{item.get('slot', '')} {item.get('from', '')} -> {item.get('to', '')}"
            for item in refine_items[:12]
            if isinstance(item, dict)
        ],
        "추가 재개선 변경은 없습니다.",
    )
    quick_links = " ".join(
        item
        for item in [
            link("갤러리", gallery.get("html", "")),
            link("원본 ZIP", report.get("zip", "")),
            link("수정판 ZIP", revised.get("zip", "")),
            link("증빙 ZIP", evidence.get("zip", "")),
            link("빌드 리포트", output_dir / "build_report.json"),
        ]
        if item
    )
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Result Detail</title>
  <style>
    body {{ margin:0; color:#2d2424; font-family:"Malgun Gothic", sans-serif; background:linear-gradient(135deg,#fffaf0,#eef8ef); }}
    main {{ width:min(1120px, calc(100% - 32px)); margin:0 auto; padding:42px 0; }}
    .panel {{ border:2px solid #ead8bc; border-radius:28px; background:rgba(255,255,255,.88); padding:24px; box-shadow:0 18px 50px rgba(96,69,45,.11); margin-bottom:18px; }}
    .hero {{ background:linear-gradient(135deg,#fff9e8,#e9fff4 64%,#fff0ea); position:relative; overflow:hidden; }}
    .hero:after {{ content:""; position:absolute; right:-70px; top:-70px; width:210px; height:210px; border-radius:999px; background:rgba(127,216,190,.28); }}
    h1 {{ margin:0 0 10px; font-size:clamp(32px,5vw,54px); letter-spacing:-.05em; }}
    h2 {{ margin:0 0 8px; }}
    p, li {{ line-height:1.65; color:#6f625f; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:16px; }}
    .metric {{ background:#fffaf0; border:1px solid #ead8bc; border-radius:18px; padding:14px; }}
    .metric strong {{ display:block; color:#2d2424; font-size:24px; }}
    .metric.good {{ background:#edfff6; border-color:#8eddbf; }}
    .metric.warn {{ background:#fff8df; border-color:#e9c961; }}
    .metric.danger {{ background:#fff0ec; border-color:#e49a83; }}
    .metric.neutral {{ background:#f7f4ef; }}
    .badge {{ display:inline-block; margin:4px 6px 4px 0; padding:7px 10px; border-radius:999px; font-weight:900; font-size:13px; border:1px solid transparent; }}
    .badge.good {{ background:#dff8eb; border-color:#83d7b6; color:#245d46; }}
    .badge.warn {{ background:#fff1bd; border-color:#e3bd42; color:#6c5311; }}
    .badge.danger {{ background:#ffe0d8; border-color:#df8d75; color:#7a2d1c; }}
    .badge.neutral {{ background:#f0ece5; border-color:#d8ccbc; color:#5d534e; }}
    .verdict {{ border-left:8px solid #d8ccbc; }}
    .verdict.good {{ border-left-color:#6fc49f; }}
    .verdict.warn {{ border-left-color:#e3bd42; }}
    .verdict.danger {{ border-left-color:#df8d75; }}
    .legacy-metrics {{ display:none; }}
    .verdict + .grid + .grid {{ display:none; }}
    .thumb-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:14px; }}
    .thumb-card {{ background:#fffaf0; border:1px solid #ead8bc; border-radius:20px; padding:12px; }}
    .thumb-title {{ font-weight:900; color:#2d2424; margin-bottom:8px; }}
    .thumb-pair {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; }}
    .thumb-pair span {{ display:block; font-weight:900; font-size:12px; color:#6f625f; margin-bottom:6px; }}
    .thumb-pair img {{ width:100%; border-radius:14px; background:#fff; border:1px solid #ead8bc; box-shadow:0 8px 18px rgba(96,69,45,.08); }}
    .missing-preview {{ min-height:112px; display:grid; place-items:center; border:1px dashed #d8ccbc; border-radius:14px; color:#8a7b70; background:#f7f4ef; }}
    a {{ display:inline-block; margin:3px 5px 3px 0; color:#2d2424; font-weight:900; text-decoration:none; background:#e9fff4; border:1px solid #9be2c7; border-radius:999px; padding:7px 11px; }}
    a.nav {{ background:#7fd8be; border-color:#7fd8be; }}
    ul {{ padding-left:20px; }}
  </style>
</head>
<body>
<main>
  <section class="panel hero">
    <h1>{html.escape(str(report.get("character_name", output_dir.name)))}</h1>
    <p>{html.escape(str(report.get("concept", "")))}</p>
    <p>
      {badge("검증", validation_status)}
      {badge("ZIP", zip_purpose_label)}
      {badge("판정", zip_decision)}
      {badge("제출 준비", readiness_label)}
      {badge("문구 품질", phrase_status)}
      {badge("수정본", revised_status)}
    </p>
    <p><a class="nav" href="/results">최근 결과물</a><a class="nav" href="/">제작 화면</a></p>
    <p>{quick_links}</p>
  </section>
  <section class="panel verdict {tone(readiness_label)}">
    <h2>최종 판단</h2>
    <p><strong>{html.escape(str(readiness_label or "아직 판단 정보가 없습니다."))}</strong></p>
    <p><strong>{html.escape(str(zip_purpose_label))}</strong>: {html.escape(str(zip_decision))}</p>
    <p>{html.escape(str(zip_next_action))}</p>
    <p>이 화면은 자동 사전 점검용입니다. 실제 카카오 제출 전에는 사람 창작 원본, 직접 수정 기록, 권리 메모를 반드시 함께 확인해야 합니다.</p>
  </section>
  <section class="grid">
    <div class="metric {tone(validation_status)}"><span>자동 검증</span><strong>{html.escape(str(validation_status))}</strong><p>실패 {html.escape(str(validation_fail_count))} / 경고 {html.escape(str(validation_warn_count))}</p>{badge("상태", validation_status)}</div>
    <div class="metric {tone(readiness_label)}"><span>제출 준비 점수</span><strong>{html.escape(str(readiness_score))}</strong><p>{html.escape(str(readiness_label))}</p></div>
    <div class="metric {tone(phrase_status)}"><span>문구 품질</span><strong>{html.escape(str(phrase_status))}</strong><p>{html.escape(str(phrase_score))}점</p></div>
    <div class="metric {tone(revised_status)}"><span>수정본 품질</span><strong>{html.escape(str(revised_status))}</strong><p>{html.escape(str(revised_score))}점 / 변경 {html.escape(str(revised.get("refinement_change_count", 0)))}개</p></div>
  </section>
  <section class="grid">
    <div class="metric"><span>자동 검사</span><strong>{html.escape(str(report.get("validation_status", "")))}</strong></div>
    <div class="metric"><span>준비 점수</span><strong>{html.escape(str(report.get("submission_readiness", {}).get("score", "")))}</strong><p>{html.escape(str(report.get("submission_readiness", {}).get("decision_label", "")))}</p></div>
    <div class="metric"><span>문구 품질</span><strong>{html.escape(str(report.get("phrase_quality", {}).get("status", "")))}</strong><p>{html.escape(str(report.get("phrase_quality", {}).get("score", "")))}점</p></div>
    <div class="metric"><span>수정판</span><strong>{html.escape(str(revised.get("quality_status", "")))}</strong><p>{html.escape(str(revised.get("quality_score", "")))}점 / 변경 {html.escape(str(revised.get("refinement_change_count", 0)))}개</p></div>
  </section>
  <section class="panel">
    <h2>제출 ZIP/이미지 자동 검사</h2>
    <p>ZIP 무결성, 내부 경로, 중복 파일명, JPG 포함 여부, PNG/GIF 개수와 형식을 확인합니다.</p>
    <div class="grid">
      <div>
        <h2>검사 이슈</h2>
        {validation_html}
      </div>
      <div>
        <h2>적용 규칙</h2>
        {validation_rule_html}
      </div>
    </div>
  </section>
  <section class="panel">
    <h2>반려 가능성 체크</h2>
    {risk_html}
  </section>
  <section class="panel">
    <h2>원본 vs 수정본 빠른 미리보기</h2>
    <p>상세 갤러리를 열기 전에 대표 컷을 바로 비교합니다. 이미지를 누르면 크게 열 수 있습니다.</p>
    <div class="thumb-grid">
      {preview_pairs_html}
    </div>
  </section>
  <section class="panel">
    <h2>제출 준비 세부 체크</h2>
    {checks_html}
  </section>
  <section class="panel">
    <h2>문구 품질 이슈</h2>
    {quality_html}
  </section>
  <section class="grid">
    <div class="panel">
      <h2>대체 문구 후보</h2>
      {replacement_html}
    </div>
    <div class="panel">
      <h2>수정판 적용</h2>
      {apply_html}
      <h2>재개선</h2>
      {refine_html}
    </div>
  </section>
  <section class="panel">
    <h2>생성 정보</h2>
    <ul>
      <li>폴더: {html.escape(str(output_dir))}</li>
      <li>상품: {html.escape(str(report.get("product_label", "")))}</li>
      <li>작업 모드: {html.escape(str(report.get("workflow_label", "")))}</li>
      <li>PNG: {html.escape(str(report.get("static_png_count", 0)))} / GIF: {html.escape(str(report.get("animated_gif_count", 0)))}</li>
      <li>문구 변경: {html.escape(str(gallery.get("changed_count", 0)))}</li>
    </ul>
  </section>
</main>
</body>
</html>"""


def color_or_default(value: str, fallback: str) -> str:
    value = value.strip()
    if re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        return value
    return fallback


def find_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_names = ["malgunbd.ttf" if bold else "malgun.ttf", "arial.ttf"]
    font_dirs = [Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"]
    for font_dir in font_dirs:
        for name in font_names:
            candidate = font_dir / name
            if candidate.exists():
                return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def wrap_text(text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    if not text:
        return [""]
    lines: list[str] = []
    current = ""
    for char in text:
        trial = current + char
        if text_width(trial, font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = char
    if current:
        lines.append(current)
    return lines[:3]


def text_width(text: str, font: ImageFont.ImageFont) -> int:
    box = font.getbbox(text)
    return int(box[2] - box[0])


def draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    center_x: int,
    top: int,
    fill: str,
    stroke_fill: str | None = None,
    stroke_width: int = 0,
) -> int:
    lines = wrap_text(text, font, CANVAS_SIZE - 56)
    y = top
    for line in lines:
        box = font.getbbox(line)
        width = box[2] - box[0]
        height = box[3] - box[1]
        draw.text(
            (center_x - width / 2, y),
            line,
            font=font,
            fill=fill,
            stroke_width=stroke_width,
            stroke_fill=stroke_fill,
        )
        y += height + 8
    return y


def fit_caption_font(
    text: str,
    max_width: int,
    max_lines: int,
    max_height: int,
    start_size: int = 34,
    min_size: int = 20,
) -> ImageFont.ImageFont:
    for size in range(start_size, min_size - 1, -2):
        candidate = find_font(size, bold=True)
        lines = wrap_text(text, candidate, max_width)
        line_heights = [candidate.getbbox(line)[3] - candidate.getbbox(line)[1] for line in lines[:max_lines]]
        total_height = sum(line_heights) + max(0, len(line_heights) - 1) * 4
        if len(lines) <= max_lines and total_height <= max_height:
            return candidate
    return find_font(min_size, bold=True)


def draw_caption_panel(
    draw: ImageDraw.ImageDraw,
    text: str,
    top: int = 282,
    bottom: int = 344,
    max_width: int = 268,
) -> None:
    font = fit_caption_font(text, max_width=max_width, max_lines=2, max_height=bottom - top - 12)
    lines = wrap_text(text, font, max_width)[:2]
    line_heights = [font.getbbox(line)[3] - font.getbbox(line)[1] for line in lines]
    total_height = sum(line_heights) + max(0, len(lines) - 1) * 4
    panel_left = 45
    panel_right = CANVAS_SIZE - 45
    draw.rounded_rectangle(
        (panel_left, top, panel_right, bottom),
        radius=20,
        fill="#fffdf7",
        outline="#ead8bc",
        width=2,
    )
    y = top + max(4, (bottom - top - total_height) // 2 - 1)
    for line, height in zip(lines, line_heights):
        box = font.getbbox(line)
        width = box[2] - box[0]
        draw.text(
            (CANVAS_SIZE / 2 - width / 2, y - box[1]),
            line,
            font=font,
            fill="#2d2424",
            stroke_width=2,
            stroke_fill="#ffffff",
        )
        y += height + 4


def make_background(draw: ImageDraw.ImageDraw, base_color: str, accent_color: str, index: int) -> None:
    draw.rounded_rectangle((12, 12, 348, 348), radius=48, fill="#fff8ea", outline=accent_color, width=5)
    for step in range(0, 360, 24):
        offset = (index * 11 + step) % 360
        x = 180 + int(math.cos(math.radians(offset)) * 145)
        y = 180 + int(math.sin(math.radians(offset)) * 145)
        draw.ellipse((x - 8, y - 8, x + 8, y + 8), fill=base_color)


def emotion_for_index(index: int) -> dict[str, object]:
    return EMOTION_PRESETS[index % len(EMOTION_PRESETS)]


def draw_star(draw: ImageDraw.ImageDraw, cx: int, cy: int, radius: int, fill: str) -> None:
    points = []
    for step in range(10):
        angle = math.radians(-90 + step * 36)
        length = radius if step % 2 == 0 else radius * 0.42
        points.append((cx + math.cos(angle) * length, cy + math.sin(angle) * length))
    draw.polygon(points, fill=fill, outline="#3b2f2f")


def draw_emotion_effect(draw: ImageDraw.ImageDraw, emotion: dict[str, object], index: int, frame_index: int = 0) -> None:
    effect = str(emotion["effect"])
    wiggle = int(math.sin((index + frame_index) * 0.9) * 7)
    if effect == "sparkles":
        draw_star(draw, 62 + wiggle, 78, 16, "#ffca72")
        draw_star(draw, 294 - wiggle, 102, 13, "#ffca72")
        draw.ellipse((282, 58, 296, 72), fill="#ffffff", outline="#3b2f2f", width=2)
    elif effect == "hearts":
        draw.text((54 + wiggle, 68), "♥", font=find_font(34, bold=True), fill="#ff7894")
        draw.text((278 - wiggle, 88), "♥", font=find_font(28, bold=True), fill="#ff9fb3")
    elif effect == "bursts":
        for x, y in [(58, 92), (306, 96), (286, 58)]:
            draw.line((x, y, x + wiggle, y - 28), fill="#ff8f4f", width=4)
            draw.line((x - 10, y - 12, x + 12, y - 12), fill="#ff8f4f", width=4)
    elif effect == "sweat":
        draw.ellipse((274 + wiggle, 88, 302 + wiggle, 124), fill="#9ee7ff", outline="#3b2f2f", width=3)
        draw.polygon([(288 + wiggle, 72), (274 + wiggle, 102), (302 + wiggle, 102)], fill="#9ee7ff", outline="#3b2f2f")
    elif effect == "big_heart":
        draw.text((262 - wiggle, 58), "♥", font=find_font(44, bold=True), fill="#ff6f91")
        draw.text((48 + wiggle, 100), "♥", font=find_font(30, bold=True), fill="#ff9fb3")
    elif effect == "marks":
        draw.text((56 + wiggle, 62), "!", font=find_font(46, bold=True), fill="#ff8f4f", stroke_width=2, stroke_fill="#ffffff")
        draw.text((286 - wiggle, 72), "?", font=find_font(38, bold=True), fill="#7ab7ff", stroke_width=2, stroke_fill="#ffffff")
    elif effect == "clouds":
        for x, y in [(52 + wiggle, 86), (280 - wiggle, 78)]:
            draw.ellipse((x, y, x + 26, y + 18), fill="#ffffff", outline="#3b2f2f", width=2)
            draw.ellipse((x + 16, y - 6, x + 46, y + 18), fill="#ffffff", outline="#3b2f2f", width=2)
            draw.line((x + 8, y + 18, x + 38, y + 18), fill="#ffffff", width=4)
    elif effect == "confetti":
        colors = ["#ff6f91", "#ffca72", "#7fd8be", "#7ab7ff"]
        for n in range(10):
            x = 46 + ((n * 31 + index * 9 + frame_index * 7) % 270)
            y = 48 + ((n * 17 + frame_index * 11) % 76)
            draw.rounded_rectangle((x, y, x + 10, y + 16), radius=3, fill=colors[n % len(colors)])


def expression_variant_for_emotion(emotion_key: str) -> dict[str, object]:
    variants = {
        "happy": {
            "eyes": "smile",
            "mouth": "wide_smile",
            "cheeks": "bright",
            "gesture": "tiny_up_hands",
            "description": "웃는 눈, 큰 미소, 밝은 볼",
        },
        "thanks": {
            "eyes": "soft",
            "mouth": "small_smile",
            "cheeks": "heart",
            "gesture": "bow_hands",
            "description": "부드러운 눈, 작은 미소, 감사 하트",
        },
        "cheer": {
            "eyes": "determined",
            "mouth": "open_cheer",
            "cheeks": "energy",
            "gesture": "fists",
            "description": "힘찬 눈썹, 응원 입모양, 주먹 보조선",
        },
        "sorry": {
            "eyes": "downcast",
            "mouth": "worried",
            "cheeks": "pale",
            "gesture": "folded_hands",
            "description": "처진 눈, 미안한 입, 모은 손",
        },
        "love": {
            "eyes": "heart",
            "mouth": "soft_smile",
            "cheeks": "deep_blush",
            "gesture": "hug",
            "description": "하트 눈, 진한 볼, 포옹 보조선",
        },
        "surprise": {
            "eyes": "wide",
            "mouth": "round",
            "cheeks": "none",
            "gesture": "raised_hands",
            "description": "동그란 눈, 놀란 입, 번쩍 손",
        },
        "rest": {
            "eyes": "sleepy",
            "mouth": "calm",
            "cheeks": "soft",
            "gesture": "blanket",
            "description": "졸린 눈, 차분한 입, 휴식 보조선",
        },
        "party": {
            "eyes": "star",
            "mouth": "open_party",
            "cheeks": "bright",
            "gesture": "celebrate",
            "description": "별 눈, 축하 입모양, 만세 보조선",
        },
    }
    return variants.get(emotion_key, variants["happy"])


def draw_expression_overlay(
    draw: ImageDraw.ImageDraw,
    emotion: dict[str, object],
    index: int,
    bounce: int = 0,
    frame_index: int = 0,
) -> dict[str, object]:
    emotion_key = str(emotion.get("key", "happy"))
    variant = expression_variant_for_emotion(emotion_key)
    cx = 180
    eye_y = 142 + bounce
    mouth_y = 184 + bounce
    cheek_y = 178 + bounce
    wiggle = int(math.sin((index + frame_index) * 0.8) * 3)
    ink = "#2d2424"
    blush = "#ff9fb3"
    accent = "#ff8f4f"
    white = "#ffffff"

    def draw_eye_symbol(x: int, mode: str) -> None:
        if mode == "smile":
            draw.arc((x - 14, eye_y - 6, x + 14, eye_y + 16), start=20, end=160, fill=ink, width=5)
        elif mode == "soft":
            draw.arc((x - 12, eye_y - 2, x + 12, eye_y + 12), start=15, end=165, fill=ink, width=4)
        elif mode == "determined":
            draw.line((x - 15, eye_y - 10, x + 12, eye_y - 2), fill=ink, width=5)
            draw.ellipse((x - 7, eye_y + 2, x + 8, eye_y + 17), fill=ink)
        elif mode == "downcast":
            draw.line((x - 14, eye_y + 4, x + 12, eye_y + 12), fill=ink, width=4)
        elif mode == "heart":
            draw.text((x - 15, eye_y - 18), "♥", font=find_font(24, bold=True), fill="#ff6f91")
        elif mode == "wide":
            draw.ellipse((x - 13, eye_y - 12, x + 13, eye_y + 16), fill=white, outline=ink, width=4)
            draw.ellipse((x - 4, eye_y - 1, x + 5, eye_y + 9), fill=ink)
        elif mode == "sleepy":
            draw.arc((x - 14, eye_y - 2, x + 14, eye_y + 10), start=15, end=165, fill=ink, width=4)
            draw.line((x + 18, eye_y - 12, x + 34, eye_y - 12), fill="#7b6258", width=3)
        elif mode == "star":
            draw_star(draw, x, eye_y, 10, "#ffca72")
        else:
            draw.ellipse((x - 9, eye_y - 8, x + 9, eye_y + 12), fill=ink)

    eye_mode = str(variant["eyes"])
    draw_eye_symbol(132 + wiggle, eye_mode)
    draw_eye_symbol(228 - wiggle, eye_mode)

    mouth_mode = str(variant["mouth"])
    if mouth_mode in {"wide_smile", "open_party"}:
        draw.arc((144, mouth_y - 18, 216, mouth_y + 30), start=10, end=170, fill=ink, width=6)
        if mouth_mode == "open_party":
            draw.ellipse((166, mouth_y - 2, 194, mouth_y + 28), fill="#f27f94", outline=ink, width=3)
    elif mouth_mode == "small_smile":
        draw.arc((158, mouth_y - 6, 202, mouth_y + 18), start=20, end=160, fill=ink, width=5)
    elif mouth_mode == "open_cheer":
        draw.rounded_rectangle((158, mouth_y - 8, 202, mouth_y + 28), radius=16, fill="#f27f94", outline=ink, width=4)
        draw.line((162, mouth_y + 2, 198, mouth_y + 2), fill=white, width=3)
    elif mouth_mode == "worried":
        draw.arc((158, mouth_y + 2, 202, mouth_y + 28), start=200, end=340, fill=ink, width=5)
    elif mouth_mode == "soft_smile":
        draw.arc((154, mouth_y - 4, 206, mouth_y + 20), start=20, end=160, fill=ink, width=5)
    elif mouth_mode == "round":
        draw.ellipse((166, mouth_y - 6, 194, mouth_y + 24), fill="#3b2f2f")
        draw.ellipse((173, mouth_y + 1, 187, mouth_y + 16), fill="#f27f94")
    elif mouth_mode == "calm":
        draw.line((160, mouth_y + 8, 200, mouth_y + 8), fill=ink, width=4)

    cheeks = str(variant["cheeks"])
    if cheeks in {"bright", "soft"}:
        draw.ellipse((92, cheek_y, 122, cheek_y + 22), fill=blush)
        draw.ellipse((238, cheek_y, 268, cheek_y + 22), fill=blush)
    elif cheeks == "heart":
        draw.text((94, cheek_y - 10), "♥", font=find_font(18, bold=True), fill="#ff7894")
        draw.text((246, cheek_y - 10), "♥", font=find_font(18, bold=True), fill="#ff7894")
    elif cheeks == "energy":
        draw.line((94, cheek_y + 6, 122, cheek_y - 2), fill=accent, width=4)
        draw.line((238, cheek_y - 2, 266, cheek_y + 6), fill=accent, width=4)
    elif cheeks == "pale":
        draw.ellipse((96, cheek_y + 4, 120, cheek_y + 20), fill="#cfe8ff")
        draw.ellipse((240, cheek_y + 4, 264, cheek_y + 20), fill="#cfe8ff")
    elif cheeks == "deep_blush":
        draw.ellipse((88, cheek_y - 2, 126, cheek_y + 26), fill="#ff7fa1")
        draw.ellipse((234, cheek_y - 2, 272, cheek_y + 26), fill="#ff7fa1")

    gesture = str(variant["gesture"])
    hand_y = 226 + bounce
    if gesture == "tiny_up_hands":
        draw.line((116, hand_y + 4, 92, hand_y - 12), fill=ink, width=5)
        draw.line((244, hand_y + 4, 268, hand_y - 12), fill=ink, width=5)
        draw.ellipse((82, hand_y - 26, 108, hand_y), fill=white, outline=ink, width=4)
        draw.ellipse((252, hand_y - 26, 278, hand_y), fill=white, outline=ink, width=4)
    elif gesture == "bow_hands":
        draw.arc((128, hand_y - 8, 176, hand_y + 28), start=210, end=330, fill=ink, width=5)
        draw.arc((184, hand_y - 8, 232, hand_y + 28), start=210, end=330, fill=ink, width=5)
    elif gesture == "fists":
        draw.ellipse((82, hand_y - 14, 116, hand_y + 20), fill=white, outline=ink, width=5)
        draw.ellipse((244, hand_y - 14, 278, hand_y + 20), fill=white, outline=ink, width=5)
    elif gesture == "folded_hands":
        draw.line((146, hand_y - 4, 178, hand_y + 22), fill=ink, width=5)
        draw.line((214, hand_y - 4, 182, hand_y + 22), fill=ink, width=5)
    elif gesture == "hug":
        draw.arc((84, hand_y - 24, 174, hand_y + 44), start=220, end=350, fill=ink, width=5)
        draw.arc((186, hand_y - 24, 276, hand_y + 44), start=190, end=320, fill=ink, width=5)
    elif gesture == "raised_hands":
        draw.line((108, hand_y, 82, hand_y - 36), fill=ink, width=5)
        draw.line((252, hand_y, 278, hand_y - 36), fill=ink, width=5)
        draw.ellipse((70, hand_y - 50, 96, hand_y - 24), fill=white, outline=ink, width=4)
        draw.ellipse((264, hand_y - 50, 290, hand_y - 24), fill=white, outline=ink, width=4)
    elif gesture == "blanket":
        draw.rounded_rectangle((110, hand_y - 2, 250, hand_y + 44), radius=18, fill="#dff4ff", outline=ink, width=4)
    elif gesture == "celebrate":
        draw.line((108, hand_y, 78, hand_y - 42), fill=ink, width=5)
        draw.line((252, hand_y, 282, hand_y - 42), fill=ink, width=5)
        draw.ellipse((66, hand_y - 56, 92, hand_y - 30), fill=white, outline=ink, width=4)
        draw.ellipse((268, hand_y - 56, 294, hand_y - 30), fill=white, outline=ink, width=4)
        draw_star(draw, 72, hand_y - 58, 9, "#ffca72")
        draw_star(draw, 288, hand_y - 58, 9, "#ffca72")

    return {
        "emotion_key": emotion_key,
        "eyes": variant["eyes"],
        "mouth": variant["mouth"],
        "cheeks": variant["cheeks"],
        "gesture": variant["gesture"],
        "description": variant["description"],
    }


def sketch_alpha_bbox(layer: Image.Image) -> tuple[int, int, int, int] | None:
    alpha = layer.getchannel("A")
    return alpha.getbbox()


def sketch_to_layer(sketch: Image.Image, target_size: int = 220) -> Image.Image:
    layer = sketch.convert("RGBA")
    cleaned = Image.new("RGBA", layer.size, (255, 255, 255, 0))
    pixels = layer.load()
    output = cleaned.load()
    for y in range(layer.height):
        for x in range(layer.width):
            r, g, b, a = pixels[x, y]
            if a == 0:
                continue
            brightness = (r + g + b) / 3
            # Treat paper-white sketch backgrounds as transparent while keeping pencil/ink marks.
            if brightness > 238 and max(r, g, b) - min(r, g, b) < 18:
                continue
            output[x, y] = (r, g, b, min(255, int(a * 1.15)))
    bbox = sketch_alpha_bbox(cleaned)
    if bbox:
        cleaned = cleaned.crop(bbox)
    else:
        cleaned.thumbnail((target_size, target_size), Image.Resampling.LANCZOS)
        return cleaned
    cleaned.thumbnail((target_size, target_size), Image.Resampling.LANCZOS)
    return cleaned


def analyze_sketch_consistency(sketch: Image.Image | None, filename: str = "") -> dict[str, object]:
    if sketch is None:
        return {
            "enabled": False,
            "source": "default_character",
            "message": "러프 스케치가 없어 기본 캐릭터 스타일을 사용했습니다.",
        }
    original = sketch.convert("RGBA")
    cleaned = sketch_to_layer(original, target_size=220)
    bbox = sketch_alpha_bbox(cleaned)
    width, height = cleaned.size
    aspect_ratio = round(width / height, 3) if height else 0
    if width == 0 or height == 0 or bbox is None:
        quality = "low"
        notes = ["스케치에서 유효한 선/형태를 충분히 찾지 못했습니다."]
    elif width < 80 or height < 80:
        quality = "medium"
        notes = ["스케치 형태가 작게 감지되어 확대 배치합니다."]
    else:
        quality = "good"
        notes = ["스케치를 투명 배경으로 정리하고 고정 크롭/고정 앵커로 배치합니다."]
    return {
        "enabled": True,
        "source": "uploaded_sketch",
        "filename": filename,
        "original_size": list(original.size),
        "cleaned_size": [width, height],
        "aspect_ratio": aspect_ratio,
        "anchor": {"center_x": 180, "center_y": 168, "target_size": 218},
        "motion_policy": "표정 효과와 상하 bounce만 적용하고 좌우 크기/중심 흔들림은 최소화합니다.",
        "quality": quality,
        "notes": notes,
    }


def draw_uploaded_sketch_character(
    image: Image.Image,
    sketch: Image.Image,
    accent_color: str,
    index: int,
    bounce: int = 0,
) -> None:
    draw = ImageDraw.Draw(image)
    wobble = int(math.sin(index * 0.7) * 2)
    shadow_box = (86 + wobble, 72 + bounce, 274 + wobble, 270 + bounce)
    draw.ellipse(shadow_box, fill="#ffffff", outline="#3b2f2f", width=4)
    layer = sketch_to_layer(sketch, target_size=218)
    x = 180 - layer.width // 2 + wobble
    y = 168 - layer.height // 2 + bounce
    image.paste(layer, (x, y), layer)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((116, 230 + bounce, 244, 274 + bounce), radius=22, fill=accent_color, outline="#3b2f2f", width=4)
    draw.line((142, 252 + bounce, 218, 252 + bounce), fill="#ffffff", width=4)


def generate_creator_profile(request: BuildRequest) -> dict[str, str]:
    style_profiles = {
        "soft_bear": ("다정한 위로형", "부드럽고 짧은 말투", "따뜻한 공감과 응원"),
        "bounce_rabbit": ("활발한 응원형", "통통 튀는 반말", "기운을 올려주는 표현"),
        "wink_cat": ("새침한 애교형", "살짝 장난스러운 말투", "귀여운 리액션과 센스"),
        "round_blob": ("느긋한 공감형", "말랑하고 담백한 말투", "쉬어가기와 편안함"),
    }
    personality, speech_style, set_direction = style_profiles.get(request.character_style, style_profiles["soft_bear"])
    concept = request.concept.lower()
    if any(word in concept for word in ["응원", "화이팅", "힘"]):
        personality = "힘을 주는 응원형"
        set_direction = "응원, 격려, 다시 시작하는 상황"
    elif any(word in concept for word in ["위로", "힐링", "따뜻"]):
        personality = "따뜻한 위로형"
        set_direction = "위로, 공감, 수고했다는 표현"
    elif any(word in concept for word in ["장난", "개그", "웃"]):
        personality = "장난스러운 리액션형"
        speech_style = "짧고 재치 있는 말투"
        set_direction = "웃긴 반응과 일상 리액션"
    if request.sketch_image is not None:
        source = "사용자 러프 스케치 기반"
    else:
        source = "앱 기본 캐릭터 기반"
    return {
        "source": source,
        "personality": personality,
        "speech_style": speech_style,
        "set_direction": set_direction,
        "creator_note": "자동 생성 결과는 참고용이며, 최종 제출 전 사람이 직접 선화/채색/수정해야 합니다.",
    }


def draw_character(draw: ImageDraw.ImageDraw, base_color: str, accent_color: str, index: int, bounce: int = 0) -> None:
    draw_soft_bear(draw, base_color, accent_color, index, bounce)


def product_mode_spec(product_mode: str) -> dict[str, object]:
    spec = PRODUCT_MODES.get(product_mode, PRODUCT_MODES["standard_static"])
    return dict(spec)


def draw_soft_bear(draw: ImageDraw.ImageDraw, base_color: str, accent_color: str, index: int, bounce: int = 0) -> None:
    cx = 180
    cy = 166 + bounce
    ear_shift = 8 if index % 2 else 0
    draw.ellipse((86, 58 + bounce, 142, 120 + bounce), fill=base_color, outline="#3b2f2f", width=4)
    draw.ellipse((218, 58 + bounce, 274, 120 + bounce), fill=base_color, outline="#3b2f2f", width=4)
    draw.ellipse((103, 76 + bounce, 130, 106 + bounce), fill="#ffe1ea")
    draw.ellipse((230, 76 + bounce, 257, 106 + bounce), fill="#ffe1ea")
    draw.ellipse((78 + ear_shift, 86 + bounce, 282 - ear_shift, 252 + bounce), fill=base_color, outline="#3b2f2f", width=5)
    draw.ellipse((122, 142 + bounce, 142, 166 + bounce), fill="#2f2525")
    draw.ellipse((218, 142 + bounce, 238, 166 + bounce), fill="#2f2525")
    draw.ellipse((128, 147 + bounce, 135, 154 + bounce), fill="#ffffff")
    draw.ellipse((224, 147 + bounce, 231, 154 + bounce), fill="#ffffff")
    draw.rounded_rectangle((158, 164 + bounce, 202, 192 + bounce), radius=14, fill="#ffffff", outline="#3b2f2f", width=3)
    draw.arc((142, 176 + bounce, 180, 214 + bounce), start=10, end=70, fill="#3b2f2f", width=4)
    draw.arc((180, 176 + bounce, 218, 214 + bounce), start=110, end=170, fill="#3b2f2f", width=4)
    draw.ellipse((94, 176 + bounce, 122, 199 + bounce), fill="#ffb7c9")
    draw.ellipse((238, 176 + bounce, 266, 199 + bounce), fill="#ffb7c9")
    draw.rounded_rectangle((116, 228 + bounce, 244, 274 + bounce), radius=22, fill=accent_color, outline="#3b2f2f", width=4)
    draw.line((136, 252 + bounce, 224, 252 + bounce), fill="#ffffff", width=4)
    draw.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), fill="#ffffff")


def draw_bounce_rabbit(draw: ImageDraw.ImageDraw, base_color: str, accent_color: str, index: int, bounce: int = 0) -> None:
    tilt = 8 if index % 2 else -8
    draw.rounded_rectangle((112 + tilt, 38 + bounce, 154 + tilt, 144 + bounce), radius=24, fill=base_color, outline="#3b2f2f", width=4)
    draw.rounded_rectangle((206 + tilt, 38 + bounce, 248 + tilt, 144 + bounce), radius=24, fill=base_color, outline="#3b2f2f", width=4)
    draw.rounded_rectangle((124 + tilt, 58 + bounce, 144 + tilt, 128 + bounce), radius=14, fill="#ffd3df")
    draw.rounded_rectangle((218 + tilt, 58 + bounce, 238 + tilt, 128 + bounce), radius=14, fill="#ffd3df")
    draw.ellipse((72, 106 + bounce, 288, 266 + bounce), fill=base_color, outline="#3b2f2f", width=5)
    draw.ellipse((116, 157 + bounce, 138, 181 + bounce), fill="#2f2525")
    draw.arc((216, 154 + bounce, 242, 178 + bounce), start=20, end=165, fill="#2f2525", width=5)
    draw.polygon([(180, 174 + bounce), (166, 192 + bounce), (194, 192 + bounce)], fill="#f27f94")
    draw.arc((146, 190 + bounce, 184, 226 + bounce), start=10, end=78, fill="#3b2f2f", width=4)
    draw.arc((176, 190 + bounce, 214, 226 + bounce), start=102, end=170, fill="#3b2f2f", width=4)
    draw.ellipse((92, 190 + bounce, 122, 214 + bounce), fill="#ffb7c9")
    draw.ellipse((238, 190 + bounce, 268, 214 + bounce), fill="#ffb7c9")
    draw.rounded_rectangle((116, 230 + bounce, 244, 274 + bounce), radius=22, fill=accent_color, outline="#3b2f2f", width=4)
    draw.line((142, 252 + bounce, 218, 252 + bounce), fill="#ffffff", width=4)


def draw_wink_cat(draw: ImageDraw.ImageDraw, base_color: str, accent_color: str, index: int, bounce: int = 0) -> None:
    ear_wiggle = 5 if index % 2 else 0
    draw.polygon([(96, 132 + bounce), (128, 58 + bounce - ear_wiggle), (158, 130 + bounce)], fill=base_color, outline="#3b2f2f")
    draw.polygon([(202, 130 + bounce), (232, 58 + bounce + ear_wiggle), (264, 132 + bounce)], fill=base_color, outline="#3b2f2f")
    draw.polygon([(116, 119 + bounce), (128, 82 + bounce), (146, 120 + bounce)], fill="#ffd3df")
    draw.polygon([(214, 120 + bounce), (232, 82 + bounce), (244, 119 + bounce)], fill="#ffd3df")
    draw.ellipse((74, 96 + bounce, 286, 260 + bounce), fill=base_color, outline="#3b2f2f", width=5)
    draw.ellipse((118, 151 + bounce, 140, 174 + bounce), fill="#2f2525")
    draw.arc((216, 150 + bounce, 244, 175 + bounce), start=20, end=165, fill="#2f2525", width=5)
    draw.polygon([(180, 172 + bounce), (166, 188 + bounce), (194, 188 + bounce)], fill="#f49bb0")
    draw.line((72, 181 + bounce, 34, 168 + bounce), fill="#3b2f2f", width=3)
    draw.line((72, 198 + bounce, 35, 204 + bounce), fill="#3b2f2f", width=3)
    draw.line((288, 181 + bounce, 326, 168 + bounce), fill="#3b2f2f", width=3)
    draw.line((288, 198 + bounce, 325, 204 + bounce), fill="#3b2f2f", width=3)
    draw.arc((146, 188 + bounce, 184, 222 + bounce), start=10, end=82, fill="#3b2f2f", width=4)
    draw.arc((176, 188 + bounce, 214, 222 + bounce), start=98, end=170, fill="#3b2f2f", width=4)
    draw.rounded_rectangle((116, 228 + bounce, 244, 274 + bounce), radius=20, fill=accent_color, outline="#3b2f2f", width=4)
    draw.ellipse((169, 240 + bounce, 191, 262 + bounce), fill="#ffffff")


def draw_round_blob(draw: ImageDraw.ImageDraw, base_color: str, accent_color: str, index: int, bounce: int = 0) -> None:
    wobble = 8 if index % 2 else -6
    draw.ellipse((76 + wobble, 78 + bounce, 286 - wobble, 270 + bounce), fill=base_color, outline="#3b2f2f", width=5)
    draw.ellipse((114, 146 + bounce, 142, 174 + bounce), fill="#2f2525")
    draw.ellipse((218, 146 + bounce, 246, 174 + bounce), fill="#2f2525")
    draw.ellipse((124, 154 + bounce, 132, 162 + bounce), fill="#ffffff")
    draw.ellipse((228, 154 + bounce, 236, 162 + bounce), fill="#ffffff")
    draw.ellipse((95, 178 + bounce, 130, 206 + bounce), fill="#ffb7c9")
    draw.ellipse((230, 178 + bounce, 265, 206 + bounce), fill="#ffb7c9")
    draw.rounded_rectangle((150, 184 + bounce, 210, 216 + bounce), radius=14, fill="#ffffff", outline="#3b2f2f", width=4)
    draw.rounded_rectangle((112, 230 + bounce, 248, 274 + bounce), radius=24, fill=accent_color, outline="#3b2f2f", width=4)
    draw.arc((134, 229 + bounce, 168, 267 + bounce), start=250, end=35, fill="#ffffff", width=4)
    draw.arc((194, 229 + bounce, 228, 267 + bounce), start=145, end=290, fill="#ffffff", width=4)


def draw_character_style(
    draw: ImageDraw.ImageDraw,
    style: str,
    base_color: str,
    accent_color: str,
    index: int,
    bounce: int = 0,
) -> None:
    drawers = {
        "soft_bear": draw_soft_bear,
        "bounce_rabbit": draw_bounce_rabbit,
        "wink_cat": draw_wink_cat,
        "round_blob": draw_round_blob,
    }
    drawers.get(style, draw_soft_bear)(draw, base_color, accent_color, index, bounce)


def make_static_image(
    request: BuildRequest,
    phrase: str,
    index: int,
    emotion_key: str | None = None,
) -> tuple[Image.Image, dict[str, object]]:
    image = Image.new("RGB", (CANVAS_SIZE, CANVAS_SIZE), "#ffffff")
    draw = ImageDraw.Draw(image)
    emotion = emotion_for_key(emotion_key) if emotion_key else emotion_for_index(index)
    make_background(draw, request.base_color, request.accent_color, index)
    if request.sketch_image is not None:
        draw_uploaded_sketch_character(image, request.sketch_image, request.accent_color, index)
        draw = ImageDraw.Draw(image)
    else:
        draw_character_style(draw, request.character_style, request.base_color, request.accent_color, index)
    expression_variant = draw_expression_overlay(draw, emotion, index)
    draw_emotion_effect(draw, emotion, index)
    draw_caption_panel(draw, phrase)
    return image, expression_variant


def make_animated_frames(
    request: BuildRequest,
    phrase: str,
    index: int,
    emotion_offset: int = STATIC_COUNT,
    emotion_key: str | None = None,
) -> tuple[list[Image.Image], dict[str, object]]:
    frames: list[Image.Image] = []
    emotion = emotion_for_key(emotion_key) if emotion_key else emotion_for_index(index + emotion_offset)
    motion = list(emotion["motion"])
    expression_variant: dict[str, object] = {}
    for frame_index, bounce in enumerate(motion):
        image = Image.new("RGB", (CANVAS_SIZE, CANVAS_SIZE), "#ffffff")
        draw = ImageDraw.Draw(image)
        make_background(draw, request.base_color, request.accent_color, index + frame_index)
        if request.sketch_image is not None:
            draw_uploaded_sketch_character(image, request.sketch_image, request.accent_color, index, int(bounce))
            draw = ImageDraw.Draw(image)
        else:
            draw_character_style(draw, request.character_style, request.base_color, request.accent_color, index, int(bounce))
        expression_variant = draw_expression_overlay(draw, emotion, index, int(bounce), frame_index)
        draw_emotion_effect(draw, emotion, index, frame_index)
        draw_caption_panel(draw, phrase)
        frames.append(image)
    return frames, expression_variant


def file_size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


def save_optimized_png(image: Image.Image, path: Path, target_bytes: int) -> dict[str, object]:
    attempts: list[dict[str, object]] = []
    original = image.convert("RGBA")
    save_variants: list[tuple[str, Image.Image, dict[str, object]]] = [
        ("rgba_optimize", original, {"format": "PNG", "optimize": True, "compress_level": 9}),
        (
            "palette_192",
            original.convert("P", palette=Image.Palette.ADAPTIVE, colors=192),
            {"format": "PNG", "optimize": True, "compress_level": 9},
        ),
        (
            "palette_128",
            original.convert("P", palette=Image.Palette.ADAPTIVE, colors=128),
            {"format": "PNG", "optimize": True, "compress_level": 9},
        ),
        (
            "palette_96",
            original.convert("P", palette=Image.Palette.ADAPTIVE, colors=96),
            {"format": "PNG", "optimize": True, "compress_level": 9},
        ),
    ]
    best_path = path
    best_size = 0
    for attempt_name, candidate, save_kwargs in save_variants:
        candidate.save(path, **save_kwargs)
        size = file_size(path)
        attempts.append({"attempt": attempt_name, "bytes": size})
        if not best_size or size < best_size:
            best_size = size
            best_path = path
        if target_bytes and size <= target_bytes:
            break
    return {
        "file": str(path),
        "kind": "png",
        "target_bytes": target_bytes,
        "final_bytes": file_size(best_path),
        "met_target": bool(target_bytes and file_size(best_path) <= target_bytes),
        "attempts": attempts,
    }


def save_gif_variant(frames: list[Image.Image], path: Path, colors: int, frame_step: int, duration: int) -> None:
    selected_frames = frames[::frame_step]
    if not selected_frames:
        selected_frames = frames[:1]
    palette_frames = [
        frame.convert("P", palette=Image.Palette.ADAPTIVE, colors=colors)
        for frame in selected_frames
    ]
    palette_frames[0].save(
        path,
        save_all=True,
        append_images=palette_frames[1:],
        duration=duration * frame_step,
        loop=0,
        optimize=True,
        disposal=2,
    )


def save_optimized_gif(frames: list[Image.Image], path: Path, target_bytes: int) -> dict[str, object]:
    attempts: list[dict[str, object]] = []
    variants = [
        ("colors_192_full", 192, 1, 90),
        ("colors_128_full", 128, 1, 95),
        ("colors_96_full", 96, 1, 100),
        ("colors_96_half_frames", 96, 2, 110),
        ("colors_64_half_frames", 64, 2, 120),
    ]
    best_bytes = 0
    best_data = b""
    for attempt_name, colors, frame_step, duration in variants:
        save_gif_variant(frames, path, colors, frame_step, duration)
        data = path.read_bytes()
        size = len(data)
        attempts.append(
            {
                "attempt": attempt_name,
                "bytes": size,
                "colors": colors,
                "frame_step": frame_step,
                "frames": max(1, len(frames[::frame_step])),
                "duration_ms": duration * frame_step,
            }
        )
        if not best_bytes or size < best_bytes:
            best_bytes = size
            best_data = data
        if target_bytes and size <= target_bytes:
            best_data = data
            best_bytes = size
            break
    if best_data:
        path.write_bytes(best_data)
    return {
        "file": str(path),
        "kind": "gif",
        "target_bytes": target_bytes,
        "final_bytes": file_size(path),
        "met_target": bool(target_bytes and file_size(path) <= target_bytes),
        "attempts": attempts,
    }


def optimization_summary(records: list[dict[str, object]]) -> dict[str, object]:
    png_records = [record for record in records if record.get("kind") == "png"]
    gif_records = [record for record in records if record.get("kind") == "gif"]
    return {
        "enabled": True,
        "file_count": len(records),
        "png_count": len(png_records),
        "gif_count": len(gif_records),
        "missed_target_count": sum(1 for record in records if not record.get("met_target")),
        "largest_final_bytes": max([int(record.get("final_bytes", 0)) for record in records] or [0]),
        "records": records,
    }


def build_submission_readiness_report(
    request: BuildRequest,
    spec: dict[str, object],
    validation: dict[str, object],
    optimization: dict[str, object],
    research_analysis: dict[str, object],
    human_origin_checklist: dict[str, object],
    phrase_quality: dict[str, object] | None = None,
) -> dict[str, object]:
    score = 100
    checks: list[dict[str, object]] = []

    def add_check(name: str, status: str, points: int, message: str, action: str) -> None:
        nonlocal score
        if status in {"warn", "fail"}:
            score -= points
        checks.append(
            {
                "name": name,
                "status": status,
                "points": points if status in {"warn", "fail"} else 0,
                "message": message,
                "recommended_action": action,
            }
        )

    validation_fail_count = int(validation.get("fail_count", 0))
    validation_warn_count = int(validation.get("warn_count", 0))
    if validation_fail_count:
        add_check(
            "규격 검사",
            "fail",
            min(35, validation_fail_count * 12),
            f"자동 검사 실패가 {validation_fail_count}개 있습니다.",
            "validation_report.json의 실패 항목을 먼저 수정하세요.",
        )
    elif validation_warn_count:
        add_check(
            "규격 검사",
            "warn",
            min(12, validation_warn_count * 3),
            f"자동 검사 주의가 {validation_warn_count}개 있습니다.",
            "주의 항목을 확인하고 실제 카카오 스튜디오 최신 기준과 비교하세요.",
        )
    else:
        add_check("규격 검사", "pass", 0, "모드별 개수, 형식, ZIP 검사가 통과했습니다.", "유지하세요.")

    missed_target_count = int(optimization.get("missed_target_count", 0))
    if missed_target_count:
        add_check(
            "용량 최적화",
            "warn",
            min(18, missed_target_count * 4),
            f"목표 용량을 넘은 파일이 {missed_target_count}개 있습니다.",
            "optimization_report.json을 확인하고 프레임 수, 색상 수, 텍스트 장식을 줄이세요.",
        )
    else:
        add_check("용량 최적화", "pass", 0, "모든 파일이 현재 앱의 보수적 목표 용량 안에 있습니다.", "유지하세요.")

    guardrails = research_analysis.get("legal_guardrails", {})
    legal_risk_level = str(guardrails.get("risk_level", "unknown")) if isinstance(guardrails, dict) else "unknown"
    if legal_risk_level == "high":
        add_check(
            "법적 리스크",
            "fail",
            28,
            "저작권/상표/초상권/AI 정책 등 고위험 키워드가 감지되었습니다.",
            "타 캐릭터, 브랜드, 유명인, 특정 문구/구도 연상 요소를 제거하고 직접 제작 증빙을 강화하세요.",
        )
    elif legal_risk_level == "medium":
        add_check(
            "법적 리스크",
            "warn",
            14,
            "법적 리스크 관련 키워드가 일부 감지되었습니다.",
            "가드레일 항목을 확인하고 권리 출처와 직접 제작 과정을 기록하세요.",
        )
    else:
        add_check("법적 리스크", "pass", 0, "큰 법적 위험 키워드는 감지되지 않았습니다.", "그래도 제출 전 사람 검수는 유지하세요.")

    source_quality = research_analysis.get("source_quality_summary", {})
    official_count = 0
    low_confidence_count = 0
    if isinstance(source_quality, dict):
        official_count = int(source_quality.get("platform_official_count", 0)) + int(source_quality.get("legal_official_count", 0))
        low_confidence_count = int(source_quality.get("low_confidence_count", 0))
    if official_count == 0:
        add_check(
            "출처 신뢰도",
            "warn",
            10,
            "공식/법률 출처가 분석에 포함되지 않았습니다.",
            "카카오 공식 가이드, 약관, 저작권 기관 자료를 자동 수집에 포함하세요.",
        )
    elif low_confidence_count > official_count:
        add_check(
            "출처 신뢰도",
            "warn",
            8,
            "주의 출처가 공식 출처보다 많습니다.",
            "블로그/영상은 트렌드 참고용으로만 쓰고, 정책 판단은 공식 자료를 우선하세요.",
        )
    else:
        add_check("출처 신뢰도", "pass", 0, f"공식/법률 출처 {official_count}개가 포함되었습니다.", "유지하세요.")

    has_sketch = request.sketch_image is not None
    has_origin_note = bool(request.human_origin_note.strip())
    if request.workflow_mode == "prototype_only":
        add_check(
            "AI/프로토타입 제출 주의",
            "warn",
            16,
            "현재 작업 모드는 참고용 프로토타입입니다.",
            "이 결과물을 그대로 제출하지 말고 직접 선화/채색/수정한 원본과 작업 증빙을 보관하세요.",
        )
    elif not has_sketch and not has_origin_note:
        add_check(
            "사람 제작 증빙",
            "warn",
            18,
            "러프 스케치 업로드와 사람 제작 증빙 메모가 모두 비어 있습니다.",
            "스케치, 레이어 원본, 타임랩스, 수정 캡처를 남기고 메모에 기록하세요.",
        )
    elif not has_origin_note:
        add_check(
            "사람 제작 증빙",
            "warn",
            8,
            "사람 제작 증빙 메모가 비어 있습니다.",
            "직접 그린 과정, 사용 도구, 원본 파일 보관 위치를 적어두세요.",
        )
    else:
        add_check("사람 제작 증빙", "pass", 0, "사람 제작 증빙 메모가 포함되었습니다.", "원본 파일과 단계별 캡처를 함께 보관하세요.")

    user_phrase_count = len(request.phrases)
    phrase_quality = phrase_quality or {}
    phrase_quality_status = str(phrase_quality.get("status", "unknown"))
    if phrase_quality_status == "fail":
        add_check(
            "문구 품질",
            "fail",
            18,
            f"문구 품질 검사 실패가 {phrase_quality.get('fail_count', 0)}개 있습니다.",
            "phrase_quality_report.json을 확인하고 위험 표현, 긴 문구, 반복 문구를 수정하세요.",
        )
    elif phrase_quality_status == "warn":
        add_check(
            "문구 품질",
            "warn",
            min(12, int(phrase_quality.get("warn_count", 0)) * 2 or 6),
            f"문구 품질 주의 항목이 {phrase_quality.get('warn_count', 0)}개 있습니다.",
            "긴 문구를 줄이고 직접 작성 문구와 상황 다양성을 늘리세요.",
        )
    elif phrase_quality_status == "pass":
        add_check("문구 품질", "pass", 0, "문구 품질 검사에서 큰 문제가 감지되지 않았습니다.", "유지하세요.")

    if user_phrase_count < 4:
        add_check(
            "문구 다양성",
            "warn",
            6,
            f"사용자 입력 문구가 {user_phrase_count}개라 자동 보충 비중이 높습니다.",
            "실제 제출 전 캐릭터 말투에 맞는 직접 작성 문구를 더 추가하세요.",
        )
    else:
        add_check("문구 다양성", "pass", 0, "사용자 입력 문구가 충분히 포함되었습니다.", "표현 중복과 권리 위험 문구만 추가 검수하세요.")

    score = max(0, min(100, score))
    if validation_fail_count or legal_risk_level == "high":
        decision = "hold"
        label = "제출 보류 권장"
    elif score >= 85:
        decision = "ready_for_human_review"
        label = "사람 최종 검수 가능"
    elif score >= 65:
        decision = "needs_revision"
        label = "수정 후 재검수 권장"
    else:
        decision = "hold"
        label = "제출 보류 권장"

    return {
        "created_at": time.strftime("%Y%m%d_%H%M%S"),
        "score": score,
        "decision": decision,
        "decision_label": label,
        "product_label": spec.get("label", ""),
        "workflow_label": WORKFLOW_MODES.get(request.workflow_mode, WORKFLOW_MODES["prototype_only"]),
        "checks": checks,
        "top_risks": [check for check in checks if check["status"] in {"fail", "warn"}][:8],
        "required_final_human_actions": [
            "카카오 스튜디오 최신 제안 화면에서 개수, 용량, 파일 형식을 재확인하세요.",
            "최종 제출 이미지는 사람이 직접 선화/채색/수정한 원본을 기준으로 준비하세요.",
            "PSD/CLIP/Procreate 원본, 타임랩스, 단계별 캡처, 참고자료 권리 메모를 보관하세요.",
            "타 캐릭터, 브랜드, 유명인, 특정 썸네일/구도/문구가 연상되는 요소를 제거하세요.",
        ],
        "policy_note": "이 점수는 제출 보조용 사전 점검이며, 카카오의 실제 심사 결과를 보장하지 않습니다.",
        "human_origin_checklist": human_origin_checklist,
    }


def html_list(items: list[object], empty: str) -> str:
    if not items:
        return f"<p>{html.escape(empty)}</p>"
    return "<ul>" + "".join(f"<li>{html.escape(str(item))}</li>" for item in items) + "</ul>"


def build_creator_evidence_package(
    output_dir: Path,
    request: BuildRequest,
    spec: dict[str, object],
    report: dict[str, object],
    human_origin_checklist: dict[str, object],
    submission_readiness: dict[str, object],
    research_analysis: dict[str, object],
    phrase_plan: list[dict[str, str]],
    static_files: list[Path],
    animated_files: list[Path],
    preview_files: list[Path],
) -> dict[str, object]:
    evidence_dir = output_dir / "evidence_package"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    source_materials = sorted((output_dir / "source_materials").glob("*"))
    preview_samples = [str(path.relative_to(output_dir)) for path in preview_files[:8]]
    top_risks = submission_readiness.get("top_risks", [])
    recommended_evidence = human_origin_checklist.get("recommended_evidence", [])
    creator_confirmations = human_origin_checklist.get("creator_confirmations", [])
    guardrails = research_analysis.get("legal_guardrails", {})
    risk_flags = guardrails.get("risk_flags", []) if isinstance(guardrails, dict) else []
    phrase_samples = [
        {
            "slot": item.get("slot", ""),
            "phrase": item.get("phrase", ""),
            "source": item.get("source", ""),
            "emotion": item.get("emotion", ""),
        }
        for item in phrase_plan[:12]
    ]
    checklist_items = [
        {"item": "러프 스케치 또는 직접 제작 시작 자료 보관", "status": "ready" if source_materials else "missing"},
        {"item": "사람 제작 증빙 메모 작성", "status": "ready" if request.human_origin_note.strip() else "missing"},
        {"item": "레이어 원본 파일 PSD/CLIP/Procreate 별도 보관", "status": "manual_required"},
        {"item": "타임랩스 또는 단계별 캡처 보관", "status": "manual_required"},
        {"item": "폰트/브러시/참고자료 권리 메모 작성", "status": "manual_required"},
        {"item": "최종 제출 전 카카오 스튜디오 최신 규격 재확인", "status": "manual_required"},
        {"item": "AI 참고 결과물을 그대로 제출하지 않았는지 확인", "status": "manual_required"},
    ]
    evidence_index = {
        "created_at": time.strftime("%Y%m%d_%H%M%S"),
        "character_name": request.character_name,
        "concept": request.concept,
        "product_mode": request.product_mode,
        "product_label": spec.get("label", ""),
        "workflow_mode": request.workflow_mode,
        "workflow_label": WORKFLOW_MODES.get(request.workflow_mode, WORKFLOW_MODES["prototype_only"]),
        "human_origin_note": request.human_origin_note,
        "sketch_filename": request.sketch_filename,
        "source_materials": [str(path.relative_to(output_dir)) for path in source_materials],
        "generated_counts": {
            "static_png": len(static_files),
            "animated_gif": len(animated_files),
            "preview_jpg": len(preview_files),
        },
        "preview_samples": preview_samples,
        "submission_readiness": {
            "score": submission_readiness.get("score"),
            "decision_label": submission_readiness.get("decision_label"),
            "top_risks": top_risks,
        },
        "legal_risk_flags": risk_flags,
        "phrase_samples": phrase_samples,
        "creator_checklist": checklist_items,
        "recommended_evidence": recommended_evidence,
        "creator_confirmations": creator_confirmations,
        "important_note": "이 패키지는 제작 증빙 정리용입니다. 실제 제출 가능 여부나 심사 통과를 보장하지 않습니다.",
    }
    rights_note = {
        "fonts": [],
        "brushes": [],
        "reference_urls": request.research_urls or [],
        "licensed_assets": [],
        "do_not_copy_confirmation": "타 캐릭터, 브랜드, 유명인, 썸네일, 특정 구도/문구를 복제하지 않았는지 최종 확인하세요.",
        "manual_fill_required": True,
    }
    revision_log = {
        "character_name": request.character_name,
        "entries": [
            {
                "step": "rough_sketch",
                "status": "ready" if source_materials else "manual_required",
                "note": "업로드한 러프 스케치가 있으면 source_materials 폴더에 저장됩니다.",
            },
            {
                "step": "manual_line_art",
                "status": "manual_required",
                "note": "최종 제출 전 사람이 직접 선화/수정한 과정을 캡처하거나 원본 파일로 보관하세요.",
            },
            {
                "step": "manual_coloring",
                "status": "manual_required",
                "note": "채색 레이어, 브러시, 색상 변경 이력을 보관하세요.",
            },
            {
                "step": "final_review",
                "status": "manual_required",
                "note": "카카오 최신 규격, 권리관계, AI 정책, 문구 리스크를 최종 확인하세요.",
            },
        ],
    }

    (evidence_dir / "evidence_index.json").write_text(
        json.dumps(evidence_index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (evidence_dir / "rights_note_template.json").write_text(
        json.dumps(rights_note, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (evidence_dir / "revision_log_template.json").write_text(
        json.dumps(revision_log, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    risk_items = ""
    if isinstance(top_risks, list) and top_risks:
        risk_items = "<ul>" + "".join(
            f"<li><strong>{html.escape(str(risk.get('name', '점검')))}</strong>: "
            f"{html.escape(str(risk.get('message', '')))}<br>"
            f"{html.escape(str(risk.get('recommended_action', '')))}</li>"
            for risk in top_risks[:8]
            if isinstance(risk, dict)
        ) + "</ul>"
    else:
        risk_items = "<p>큰 주의 항목은 감지되지 않았습니다. 그래도 최종 제출 전 사람 검수는 필요합니다.</p>"
    checklist_html = "<ul>" + "".join(
        f"<li><strong>{html.escape(item['status'])}</strong> {html.escape(item['item'])}</li>"
        for item in checklist_items
    ) + "</ul>"
    phrase_html = "<ul>" + "".join(
        f"<li>{html.escape(str(item.get('slot', '')))}. {html.escape(str(item.get('phrase', '')))} "
        f"({html.escape(str(item.get('source', '')))}, {html.escape(str(item.get('emotion', '')))})</li>"
        for item in phrase_samples
    ) + "</ul>"
    preview_html = "<ul>" + "".join(f"<li>{html.escape(path)}</li>" for path in preview_samples) + "</ul>"
    summary_html = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Creator Evidence Package</title>
  <style>
    body {{ margin: 0; color: #2d2424; font-family: "Malgun Gothic", sans-serif; background: #fff8ea; }}
    main {{ width: min(920px, calc(100% - 32px)); margin: 0 auto; padding: 36px 0; }}
    section {{ margin-bottom: 16px; padding: 22px; background: #fff; border: 2px solid #ead8bc; border-radius: 22px; }}
    h1 {{ margin: 0 0 8px; font-size: 34px; }}
    h2 {{ margin: 0 0 8px; }}
    p, li {{ line-height: 1.65; color: #6f625f; }}
    code {{ background: #fff3d8; padding: 2px 6px; border-radius: 8px; }}
  </style>
</head>
<body>
<main>
  <section>
    <h1>사람 제작 증빙 패키지</h1>
    <p><strong>캐릭터</strong>: {html.escape(request.character_name)}</p>
    <p><strong>콘셉트</strong>: {html.escape(request.concept)}</p>
    <p><strong>상품 종류</strong>: {html.escape(str(spec.get("label", "")))}</p>
    <p><strong>준비 점수</strong>: {html.escape(str(submission_readiness.get("score", "?")))}점 / {html.escape(str(submission_readiness.get("decision_label", "")))}</p>
  </section>
  <section>
    <h2>제작 증빙 메모</h2>
    <p>{html.escape(request.human_origin_note or "아직 작성된 증빙 메모가 없습니다.")}</p>
  </section>
  <section>
    <h2>필수 보관 체크리스트</h2>
    {checklist_html}
  </section>
  <section>
    <h2>반려 가능성 주의 항목</h2>
    {risk_items}
  </section>
  <section>
    <h2>권장 증빙 자료</h2>
    {html_list([str(item) for item in recommended_evidence], "권장 증빙 자료가 없습니다.")}
  </section>
  <section>
    <h2>문구 샘플</h2>
    {phrase_html}
  </section>
  <section>
    <h2>미리보기 샘플 경로</h2>
    {preview_html}
  </section>
  <section>
    <h2>동봉 파일</h2>
    <ul>
      <li><code>evidence_index.json</code>: 증빙 패키지 인덱스</li>
      <li><code>rights_note_template.json</code>: 폰트/브러시/자료 권리 메모 템플릿</li>
      <li><code>revision_log_template.json</code>: 직접 수정 이력 템플릿</li>
    </ul>
  </section>
</main>
</body>
</html>"""
    (evidence_dir / "evidence_summary.html").write_text(summary_html, encoding="utf-8")

    package_zip = output_dir / "creator_evidence_package.zip"
    evidence_files = [
        evidence_dir / "evidence_index.json",
        evidence_dir / "rights_note_template.json",
        evidence_dir / "revision_log_template.json",
        evidence_dir / "evidence_summary.html",
        output_dir / "human_origin_checklist.json",
        output_dir / "submission_readiness_report.json",
        output_dir / "research_insights.json",
        output_dir / "sketch_consistency_report.json",
        output_dir / "phrase_quality_report.json",
        output_dir / "phrase_replacement_suggestions.json",
        output_dir / "preview_gallery.html",
        output_dir / "revised_phrase_variant" / "revised_phrase_apply_report.json",
        output_dir / "revised_phrase_variant" / "revised_phrase_refinement_report.json",
        output_dir / "revised_phrase_variant" / "revised_phrase_quality_report.json",
    ]
    with zipfile.ZipFile(package_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in evidence_files:
            if file_path.exists():
                archive.write(file_path, file_path.relative_to(output_dir))
        for source_path in source_materials:
            archive.write(source_path, source_path.relative_to(output_dir))

    return {
        "directory": str(evidence_dir),
        "zip": str(package_zip),
        "html": str(evidence_dir / "evidence_summary.html"),
        "index": str(evidence_dir / "evidence_index.json"),
        "file_count": len([path for path in evidence_files if path.exists()]) + len(source_materials),
        "manual_required_count": sum(1 for item in checklist_items if item["status"] == "manual_required"),
        "missing_count": sum(1 for item in checklist_items if item["status"] == "missing"),
    }


def build_preview_gallery(
    output_dir: Path,
    report: dict[str, object],
    phrase_plan: list[dict[str, str]],
) -> dict[str, object]:
    gallery_path = output_dir / "preview_gallery.html"
    revised_dir = output_dir / "revised_phrase_variant"
    revised_plan_path = revised_dir / "revised_phrase_plan.json"
    revised_plan: list[dict[str, str]] = []
    if revised_plan_path.exists():
        try:
            parsed = json.loads(revised_plan_path.read_text(encoding="utf-8"))
            if isinstance(parsed, list):
                revised_plan = [item for item in parsed if isinstance(item, dict)]
        except Exception:
            revised_plan = []

    def preview_path_for(item_type: str, slot_index: int, revised: bool = False) -> str:
        base = Path("revised_phrase_variant") / "preview_jpg" if revised else Path("preview_jpg")
        if item_type == "animated_gif":
            name = f"preview_animated_{slot_index + 1:02d}.jpg"
        else:
            name = f"preview_static_{slot_index + 1:02d}.jpg"
        return str(base / name).replace("\\", "/")

    cards: list[str] = []
    for index, item in enumerate(phrase_plan):
        item_type = "static_png" if index < int(report.get("static_png_count", 0)) else "animated_gif"
        local_index = index if item_type == "static_png" else index - int(report.get("static_png_count", 0))
        revised_item = revised_plan[index] if index < len(revised_plan) else {}
        original_phrase = str(item.get("phrase", ""))
        revised_phrase = str(revised_item.get("phrase", original_phrase)) if revised_item else original_phrase
        changed = revised_phrase != original_phrase
        change_badge = '<span class="badge changed">changed</span>' if changed else '<span class="badge same">same</span>'
        cards.append(
            f"""
            <article class="card {'changed-card' if changed else ''}">
              <div class="slot">#{index + 1:02d} {html.escape(str(item.get('emotion', '')))} {change_badge}</div>
              <div class="compare">
                <figure>
                  <figcaption>원본</figcaption>
                  <img src="{html.escape(preview_path_for(item_type, local_index, False))}" alt="original preview {index + 1}">
                  <p>{html.escape(original_phrase)}</p>
                </figure>
                <figure>
                  <figcaption>수정판</figcaption>
                  <img src="{html.escape(preview_path_for(item_type, local_index, True))}" alt="revised preview {index + 1}">
                  <p>{html.escape(revised_phrase)}</p>
                </figure>
              </div>
              <p class="meta">type {html.escape(item_type)} / source {html.escape(str(item.get('source', '')))}</p>
            </article>
            """
        )
    changed_count = sum(
        1
        for index, item in enumerate(phrase_plan)
        if index < len(revised_plan) and str(revised_plan[index].get("phrase", "")) != str(item.get("phrase", ""))
    )
    gallery_html = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Preview Gallery</title>
  <style>
    :root {{ --ink:#2d2424; --muted:#766969; --paper:#fff8ea; --line:#ead8bc; --mint:#7fd8be; --coral:#ff9f8a; }}
    body {{ margin:0; font-family:"Malgun Gothic", sans-serif; color:var(--ink); background:linear-gradient(135deg,#fff8ea,#eef8ef); }}
    main {{ width:min(1180px, calc(100% - 28px)); margin:0 auto; padding:34px 0; }}
    header {{ background:rgba(255,255,255,.88); border:2px solid var(--line); border-radius:28px; padding:24px; margin-bottom:18px; }}
    h1 {{ margin:0 0 8px; font-size:clamp(30px,5vw,52px); letter-spacing:-.05em; }}
    p {{ color:var(--muted); line-height:1.65; }}
    .summary {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:14px; }}
    .pill {{ padding:8px 12px; border-radius:999px; background:#fff3d8; border:1px solid #f2cc80; font-weight:800; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:16px; }}
    .card {{ background:rgba(255,255,255,.9); border:2px solid var(--line); border-radius:22px; padding:14px; box-shadow:0 14px 34px rgba(96,69,45,.10); }}
    .changed-card {{ border-color:var(--coral); }}
    .slot {{ display:flex; justify-content:space-between; align-items:center; font-weight:900; margin-bottom:10px; }}
    .badge {{ display:inline-block; border-radius:999px; padding:4px 8px; font-size:12px; }}
    .changed {{ background:#ffe1d9; color:#8a2f1d; }}
    .same {{ background:#e9fff4; color:#23624f; }}
    .compare {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; }}
    figure {{ margin:0; background:#fffaf0; border:1px solid var(--line); border-radius:16px; padding:8px; }}
    figcaption {{ font-size:12px; font-weight:900; color:var(--muted); margin-bottom:6px; }}
    img {{ width:100%; display:block; border-radius:12px; background:#fff; }}
    figure p {{ margin:8px 0 0; color:var(--ink); font-weight:900; min-height:2.4em; }}
    .meta {{ font-size:12px; margin:10px 0 0; }}
  </style>
</head>
<body>
<main>
  <header>
    <h1>미리보기 비교 갤러리</h1>
    <p>원본 세트와 대체 문구 적용 수정판을 나란히 비교합니다. 수정판은 참고용이며 최종 제출 전 사람이 직접 문구와 그림을 검수해야 합니다.</p>
    <div class="summary">
      <span class="pill">캐릭터: {html.escape(str(report.get("character_name", "")))}</span>
      <span class="pill">상품: {html.escape(str(report.get("product_label", "")))}</span>
      <span class="pill">총 컷: {len(phrase_plan)}</span>
      <span class="pill">문구 변경: {changed_count}</span>
      <span class="pill">원본 품질: {html.escape(str(report.get("phrase_quality", {}).get("status", "")))}</span>
      <span class="pill">수정판 품질: {html.escape(str(report.get("revised_phrase_variant", {}).get("quality_status", "")))}</span>
    </div>
  </header>
  <section class="grid">
    {''.join(cards)}
  </section>
</main>
</body>
</html>"""
    gallery_path.write_text(gallery_html, encoding="utf-8")
    return {
        "enabled": True,
        "html": str(gallery_path),
        "changed_count": changed_count,
        "card_count": len(phrase_plan),
        "compares_revised_variant": revised_plan_path.exists(),
    }


def write_zip(zip_path: Path, files: Iterable[Path], root: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in files:
            archive.write(file_path, file_path.relative_to(root))


WINDOWS_RESERVED_FILENAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}


def validate_zip_entry_name(entry: str) -> list[str]:
    problems: list[str] = []
    normalized = entry.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    if entry.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", entry):
        problems.append("absolute path")
    if "\\" in entry:
        problems.append("backslash separator")
    if not parts:
        problems.append("empty path")
    if any(part == ".." for part in normalized.split("/")):
        problems.append("parent directory traversal")
    for part in parts:
        stem = part.split(".", 1)[0].upper()
        if stem in WINDOWS_RESERVED_FILENAMES:
            problems.append(f"reserved Windows name: {part}")
        if part not in {".", ".."} and part.endswith((" ", ".")):
            problems.append(f"unsafe trailing character: {part}")
    return problems


def validate_image_file(path: Path, expected_format: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    try:
        with Image.open(path) as image:
            if image.size != (CANVAS_SIZE, CANVAS_SIZE):
                issues.append(
                    {
                        "level": "fail",
                        "file": str(path),
                        "message": f"Image size is {image.size}, expected {CANVAS_SIZE}x{CANVAS_SIZE}.",
                    }
                )
            if image.format != expected_format:
                issues.append(
                    {
                        "level": "fail",
                        "file": str(path),
                        "message": f"Image format is {image.format}, expected {expected_format}.",
                    }
                )
            if image.mode not in {"RGB", "RGBA", "P"}:
                issues.append(
                    {
                        "level": "warn",
                        "file": str(path),
                        "message": f"Image mode is {image.mode}; RGB/RGBA/P is safer for review.",
                    }
                )
    except Exception as exc:
        issues.append({"level": "fail", "file": str(path), "message": f"Cannot open image: {exc}"})
    return issues


def validate_output_package(output_dir: Path, product_mode: str = "standard_static", zip_path: Path | None = None) -> dict[str, object]:
    spec = product_mode_spec(product_mode)
    expected_static_count = int(spec["static_count"])
    expected_animated_count = int(spec["animated_count"])
    allowed_extensions = {str(ext).lower() for ext in spec.get("zip_allows", ["png", "gif"])}
    static_dir = output_dir / "static_png_submit"
    animated_dir = output_dir / "animated_gif_submit"
    preview_dir = output_dir / "preview_jpg"
    zip_candidates = [
        output_dir / "submit_ready_review_png_gif.zip",
        output_dir / "submit_only_png_gif.zip",
        output_dir / "prototype_reference_png_gif.zip",
    ]
    zip_path = zip_path or next((candidate for candidate in zip_candidates if candidate.exists()), zip_candidates[0])
    static_files = sorted(static_dir.glob("*.png"))
    animated_files = sorted(animated_dir.glob("*.gif"))
    preview_files = sorted(preview_dir.glob("*.jpg"))
    issues: list[dict[str, str]] = []

    if len(static_files) != expected_static_count:
        issues.append(
            {
                "level": "fail",
                "file": str(static_dir),
                "message": f"Static PNG count is {len(static_files)}, expected {expected_static_count} for {spec['label']}.",
            }
        )
    if len(animated_files) != expected_animated_count:
        issues.append(
            {
                "level": "fail",
                "file": str(animated_dir),
                "message": f"Animated GIF count is {len(animated_files)}, expected {expected_animated_count} for {spec['label']}.",
            }
        )

    for file_path in static_files:
        issues.extend(validate_image_file(file_path, "PNG"))
        if file_path.stat().st_size > MAX_STATIC_BYTES:
            issues.append(
                {
                    "level": "warn",
                    "file": str(file_path),
                    "message": "PNG file is larger than the conservative 2MB safety limit.",
                }
            )
        if file_path.stat().st_size > STATIC_SUBMISSION_MAX_BYTES:
            issues.append(
                {
                    "level": "warn",
                    "file": str(file_path),
                    "message": "PNG is over 150KB, which is above the conservative static submission target.",
                }
            )

    for file_path in animated_files:
        issues.extend(validate_image_file(file_path, "GIF"))
        if file_path.stat().st_size > MAX_ANIMATED_BYTES:
            issues.append(
                {
                    "level": "warn",
                    "file": str(file_path),
                    "message": "GIF file is larger than the conservative 500KB safety limit.",
                }
            )
        if file_path.stat().st_size > ANIMATED_SUBMISSION_MAX_BYTES:
            issues.append(
                {
                    "level": "warn",
                    "file": str(file_path),
                    "message": "Animated file is over 650KB, which is above the conservative animated submission target.",
                }
            )

    if not zip_path.exists():
        issues.append({"level": "fail", "file": str(zip_path), "message": "Submit ZIP was not created."})
        zip_entries: list[str] = []
    else:
        with zipfile.ZipFile(zip_path) as archive:
            zip_entries = archive.namelist()
            corrupt_entry = archive.testzip()
        if corrupt_entry:
            issues.append(
                {
                    "level": "fail",
                    "file": str(zip_path),
                    "message": f"Submit ZIP integrity check failed at entry: {corrupt_entry}.",
                }
            )
        duplicate_entries = sorted({entry for entry in zip_entries if zip_entries.count(entry) > 1})
        if duplicate_entries:
            issues.append(
                {
                    "level": "fail",
                    "file": str(zip_path),
                    "message": f"Submit ZIP contains duplicate internal paths: {len(duplicate_entries)}.",
                }
            )
        unsafe_entries = {
            entry: validate_zip_entry_name(entry)
            for entry in zip_entries
            if not entry.endswith("/") and validate_zip_entry_name(entry)
        }
        if unsafe_entries:
            sample_entry, sample_reasons = next(iter(unsafe_entries.items()))
            issues.append(
                {
                    "level": "fail",
                    "file": str(zip_path),
                    "message": (
                        f"Submit ZIP contains unsafe internal paths: {len(unsafe_entries)} "
                        f"(example: {sample_entry}; {', '.join(sample_reasons)})."
                    ),
                }
            )
        jpg_entries = [entry for entry in zip_entries if entry.lower().endswith((".jpg", ".jpeg"))]
        png_entries = [entry for entry in zip_entries if entry.lower().endswith(".png")]
        gif_entries = [entry for entry in zip_entries if entry.lower().endswith(".gif")]
        unexpected_entries = [
            entry
            for entry in zip_entries
            if not entry.endswith("/")
            and not any(entry.lower().endswith(f".{ext}") for ext in allowed_extensions)
        ]
        if jpg_entries:
            issues.append(
                {
                    "level": "fail",
                    "file": str(zip_path),
                    "message": f"Submit ZIP contains JPG/JPEG files: {len(jpg_entries)}.",
                }
            )
        if unexpected_entries:
            issues.append(
                {
                    "level": "warn",
                    "file": str(zip_path),
                    "message": f"Submit ZIP contains unexpected files: {len(unexpected_entries)}.",
                }
            )
        if "gif" not in allowed_extensions and gif_entries:
            issues.append(
                {
                    "level": "fail",
                    "file": str(zip_path),
                    "message": f"{spec['label']} ZIP should not contain GIF files.",
                }
            )
        if len(png_entries) != expected_static_count or len(gif_entries) != expected_animated_count:
            issues.append(
                {
                    "level": "fail",
                    "file": str(zip_path),
                    "message": f"ZIP has PNG {len(png_entries)} and GIF {len(gif_entries)}.",
                }
            )

    fail_count = sum(1 for issue in issues if issue["level"] == "fail")
    warn_count = sum(1 for issue in issues if issue["level"] == "warn")
    status = "pass" if fail_count == 0 else "fail"
    return {
        "status": status,
        "fail_count": fail_count,
        "warn_count": warn_count,
        "static_png_count": len(static_files),
        "animated_gif_count": len(animated_files),
        "preview_jpg_count": len(preview_files),
        "zip_entry_count": len(zip_entries),
        "rules": {
            "product_mode": product_mode,
            "product_label": spec["label"],
            "product_note": spec["note"],
            "canvas_px": f"{CANVAS_SIZE}x{CANVAS_SIZE}",
            "static_png_count": expected_static_count,
            "animated_gif_count": expected_animated_count,
            "max_static_bytes": MAX_STATIC_BYTES,
            "max_animated_bytes": MAX_ANIMATED_BYTES,
            "static_submission_target_bytes": spec["static_target_bytes"],
            "animated_submission_target_bytes": spec["animated_target_bytes"],
            "submit_zip_allows": list(allowed_extensions),
        },
        "issues": issues,
    }


def build_package(request: BuildRequest) -> dict[str, object]:
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    slug = safe_slug(request.character_name)
    output_dir = OUTPUT_ROOT / f"{timestamp}_{slug}"
    spec = product_mode_spec(request.product_mode)
    guidance = workflow_guidance(request.workflow_mode)
    static_count = int(spec["static_count"])
    animated_count = int(spec["animated_count"])
    static_dir = output_dir / "static_png_submit"
    animated_dir = output_dir / "animated_gif_submit"
    preview_dir = output_dir / "preview_jpg"
    source_dir = output_dir / "source_materials"
    static_dir.mkdir(parents=True, exist_ok=True)
    animated_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)
    source_dir.mkdir(parents=True, exist_ok=True)
    creator_profile = generate_creator_profile(request)
    research_urls = list(request.research_urls or [])
    if request.auto_collect_research:
        research_urls = unique_keep_order([*AUTO_RESEARCH_SEEDS, *research_urls])
    research_analysis = analyze_research_sources(research_urls, request.research_notes, request.research_keywords)
    evolution_memory = save_evolution_memory(research_analysis)
    learned_phrases = weighted_values(evolution_memory, "phrase_weights", "learned_phrase_additions")
    phrase_weights = evolution_memory.get("phrase_weights", {})
    if not isinstance(phrase_weights, dict):
        phrase_weights = {}
    sketch_consistency = analyze_sketch_consistency(request.sketch_image, request.sketch_filename)
    if request.sketch_image is not None:
        sketch_name = safe_slug(Path(request.sketch_filename).stem, "uploaded_sketch") + ".png"
        request.sketch_image.save(source_dir / sketch_name, "PNG")
        cleaned_sketch = sketch_to_layer(request.sketch_image, target_size=218)
        cleaned_sketch.save(source_dir / "normalized_sketch_layer.png", "PNG", optimize=True)
        sketch_consistency["normalized_layer"] = str((source_dir / "normalized_sketch_layer.png").relative_to(output_dir))

    static_files: list[Path] = []
    animated_files: list[Path] = []
    preview_files: list[Path] = []
    optimization_records: list[dict[str, object]] = []
    expression_plan: list[dict[str, str]] = []
    phrase_plan = build_phrase_plan(request.phrases, static_count + animated_count, learned_phrases, phrase_weights)
    emotion_matching = phrase_emotion_summary(phrase_plan)
    phrase_quality = analyze_phrase_quality(phrase_plan, len(request.phrases))
    phrase_replacements = build_phrase_replacement_suggestions(phrase_plan, phrase_quality)

    for i in range(static_count):
        phrase_slot = phrase_plan[i]
        phrase = phrase_slot["phrase"]
        emotion = emotion_for_key(str(phrase_slot["emotion_key"]))
        image, expression_variant = make_static_image(request, phrase, i, str(phrase_slot["emotion_key"]))
        png_path = static_dir / f"static_{i + 1:02d}.png"
        jpg_path = preview_dir / f"preview_static_{i + 1:02d}.jpg"
        optimization_records.append(save_optimized_png(image, png_path, int(spec["static_target_bytes"])))
        image.save(jpg_path, "JPEG", quality=92)
        static_files.append(png_path)
        preview_files.append(jpg_path)
        expression_plan.append(
            {
                "file": str(png_path.relative_to(output_dir)),
                "type": "static_png",
                "phrase": phrase,
                "phrase_source": phrase_slot["source"],
                "emotion": str(emotion["label"]),
                "emotion_key": str(emotion["key"]),
                "emotion_match_reason": phrase_slot.get("emotion_match_reason", ""),
                "effect": str(emotion["effect"]),
                "expression_variant": json.dumps(expression_variant, ensure_ascii=False),
            }
        )

    for i in range(animated_count):
        phrase_slot = phrase_plan[i + static_count]
        phrase = phrase_slot["phrase"]
        emotion = emotion_for_key(str(phrase_slot["emotion_key"]))
        frames, expression_variant = make_animated_frames(request, phrase, i, static_count, str(phrase_slot["emotion_key"]))
        gif_path = animated_dir / f"animated_{i + 1:02d}.gif"
        preview_path = preview_dir / f"preview_animated_{i + 1:02d}.jpg"
        optimization_records.append(save_optimized_gif(frames, gif_path, int(spec["animated_target_bytes"])))
        frames[0].save(preview_path, "JPEG", quality=92)
        animated_files.append(gif_path)
        preview_files.append(preview_path)
        expression_plan.append(
            {
                "file": str(gif_path.relative_to(output_dir)),
                "type": "animated_gif",
                "phrase": phrase,
                "phrase_source": phrase_slot["source"],
                "emotion": str(emotion["label"]),
                "emotion_key": str(emotion["key"]),
                "emotion_match_reason": phrase_slot.get("emotion_match_reason", ""),
                "effect": str(emotion["effect"]),
                "motion": ",".join(str(value) for value in emotion["motion"]),
                "expression_variant": json.dumps(expression_variant, ensure_ascii=False),
            }
        )

    zip_name = f"{guidance['zip_prefix']}_png_gif.zip"
    zip_path = output_dir / zip_name
    optimization = optimization_summary(optimization_records)
    write_zip(zip_path, [*static_files, *animated_files], output_dir)
    validation = validate_output_package(output_dir, request.product_mode, zip_path)
    human_origin_checklist = {
        "workflow_mode": request.workflow_mode,
        "workflow_label": WORKFLOW_MODES.get(request.workflow_mode, WORKFLOW_MODES["prototype_only"]),
        "workflow_output": guidance,
        "product_mode": request.product_mode,
        "product_label": spec["label"],
        "human_origin_note": request.human_origin_note,
        "submission_warning": (
            "This package is a prototype reference and should not be submitted as final Kakao artwork."
            if request.workflow_mode == "prototype_only"
            else "Final submission should be based on artwork directly created, edited, and approved by the human creator."
        ),
        "recommended_evidence": [
            "rough sketches",
            "layered source files such as PSD, CLIP, or Procreate",
            "manual redraw or correction screenshots",
            "time-lapse or step-by-step work history",
            "rights notes for fonts, brushes, references, and source materials",
        ],
        "creator_confirmations": [
            "No third-party character, trademark, celebrity, or copyrighted work was copied.",
            "Any AI-assisted output was not submitted as-is.",
            "The final submitted artwork was manually reviewed and edited by the creator.",
        ],
    }
    submission_readiness = build_submission_readiness_report(
        request,
        spec,
        validation,
        optimization,
        research_analysis,
        human_origin_checklist,
        phrase_quality,
    )

    report = {
        "app": APP_NAME,
        "version": APP_VERSION,
        "character_name": request.character_name,
        "concept": request.concept,
        "character_style": request.character_style,
        "character_style_label": CHARACTER_STYLES.get(request.character_style, CHARACTER_STYLES["soft_bear"]),
        "workflow_mode": request.workflow_mode,
        "workflow_label": WORKFLOW_MODES.get(request.workflow_mode, WORKFLOW_MODES["prototype_only"]),
        "product_mode": request.product_mode,
        "product_label": spec["label"],
        "product_spec": spec,
        "creator_profile": creator_profile,
        "sketch_consistency": sketch_consistency,
        "expression_variation": {
            "enabled": True,
            "method": "emotion_overlay",
            "applies_to": ["uploaded_sketch", "default_character"],
            "features": ["eyes", "mouth", "cheeks", "gesture", "effect"],
            "report_file": "expression_plan.json",
        },
        "phrase_emotion_matching": emotion_matching,
        "phrase_quality": {
            "status": phrase_quality["status"],
            "score": phrase_quality["score"],
            "fail_count": phrase_quality["fail_count"],
            "warn_count": phrase_quality["warn_count"],
            "report_file": "phrase_quality_report.json",
        },
        "phrase_replacements": {
            "enabled": True,
            "suggestion_count": phrase_replacements["suggestion_count"],
            "report_file": "phrase_replacement_suggestions.json",
        },
        "research_top_categories": research_analysis["top_categories"],
        "research_source_count": research_analysis["source_count"],
        "research_api_used_count": research_analysis.get("api_used_count", 0),
        "research_api_fallback_count": research_analysis.get("api_fallback_count", 0),
        "research_free_collection_count": research_analysis.get("free_collection_count", 0),
        "research_fallback_policy": research_analysis.get("fallback_policy", ""),
        "legal_risk_level": research_analysis["legal_guardrails"]["risk_level"],
        "top_weighted_phrases": learned_phrases[:10],
        "memory_weight_system": {
            "enabled": True,
            "phrase_weight_count": len(phrase_weights),
            "top_phrase_weights": top_weight_items(phrase_weights, 10),
            "applied_to_phrase_plan": True,
        },
        "sketch_filename": request.sketch_filename,
        "created_at": timestamp,
        "user_phrase_count": len(request.phrases),
        "auto_phrase_count": sum(1 for item in phrase_plan if item["source"] == "auto"),
        "static_png_count": len(static_files),
        "animated_gif_count": len(animated_files),
        "preview_jpg_count": len(preview_files),
        "zip": str(zip_path),
        "zip_purpose_label": guidance["purpose_label"],
        "zip_decision": guidance["decision"],
        "zip_next_action": guidance["action"],
        "optimization": {
            "enabled": True,
            "missed_target_count": optimization["missed_target_count"],
            "largest_final_bytes": optimization["largest_final_bytes"],
            "report_file": "optimization_report.json",
        },
        "submission_readiness": {
            "score": submission_readiness["score"],
            "decision": submission_readiness["decision"],
            "decision_label": submission_readiness["decision_label"],
            "top_risk_count": len(submission_readiness["top_risks"]),
            "report_file": "submission_readiness_report.json",
        },
        "validation_status": validation["status"],
        "validation_fail_count": validation["fail_count"],
        "validation_warn_count": validation["warn_count"],
        "notes": [
            "PNG/GIF only ZIP was created.",
            "JPG files are previews only and are not included in the submit ZIP.",
            str(spec["note"]),
            "If API quota is unavailable or exhausted, collection continues with free URL/title/domain and note analysis.",
            "Memory phrase weights are applied before default phrase suggestions.",
            "Prototype-only outputs are reference material and should not be submitted as final Kakao artwork.",
            "Real submissions should be based on human-created source artwork and retained creation evidence.",
        ],
    }
    (output_dir / "build_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "validation_report.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "optimization_report.json").write_text(
        json.dumps(optimization, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "submission_readiness_report.json").write_text(
        json.dumps(submission_readiness, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "expression_plan.json").write_text(
        json.dumps(expression_plan, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "phrase_plan.json").write_text(
        json.dumps(phrase_plan, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "phrase_quality_report.json").write_text(
        json.dumps(phrase_quality, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "phrase_replacement_suggestions.json").write_text(
        json.dumps(phrase_replacements, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "human_origin_checklist.json").write_text(
        json.dumps(human_origin_checklist, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "creator_profile.json").write_text(
        json.dumps(creator_profile, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "sketch_consistency_report.json").write_text(
        json.dumps(sketch_consistency, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "research_insights.json").write_text(
        json.dumps(research_analysis, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    revised_phrase_variant = build_revised_phrase_variant(
        output_dir,
        request,
        spec,
        phrase_plan,
        phrase_replacements,
        static_count,
        animated_count,
    )
    report["revised_phrase_variant"] = revised_phrase_variant
    preview_gallery = build_preview_gallery(output_dir, report, phrase_plan)
    report["preview_gallery"] = preview_gallery
    evidence_package = build_creator_evidence_package(
        output_dir,
        request,
        spec,
        report,
        human_origin_checklist,
        submission_readiness,
        research_analysis,
        phrase_plan,
        static_files,
        animated_files,
        preview_files,
    )
    report["creator_evidence_package"] = evidence_package
    (output_dir / "build_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "output_dir": str(output_dir),
        "zip_path": str(zip_path),
        "report": report,
        "validation": validation,
        "submission_readiness": submission_readiness,
        "evidence_package": evidence_package,
        "phrase_quality": phrase_quality,
        "phrase_replacements": phrase_replacements,
        "revised_phrase_variant": revised_phrase_variant,
        "preview_gallery": preview_gallery,
    }


def page(
    result: dict[str, object] | None = None,
    research_result: dict[str, object] | None = None,
    error: str | None = None,
) -> str:
    phrases = "\n".join(DEFAULT_PHRASES)
    style_options = "\n".join(
        f'<option value="{html.escape(style_key)}">{html.escape(label)}</option>'
        for style_key, label in CHARACTER_STYLES.items()
    )
    workflow_options = "\n".join(
        f'<option value="{html.escape(mode_key)}">{html.escape(label)}</option>'
        for mode_key, label in WORKFLOW_MODES.items()
    )
    product_options = "\n".join(
        f'<option value="{html.escape(mode_key)}">{html.escape(str(spec["label"]))}</option>'
        for mode_key, spec in PRODUCT_MODES.items()
    )
    result_html = ""
    if result:
        output_dir = html.escape(str(result["output_dir"]))
        zip_path = html.escape(str(result["zip_path"]))
        report = result.get("report", {})
        auto_phrase_count = html.escape(str(report.get("auto_phrase_count", "?"))) if isinstance(report, dict) else "?"
        workflow_label = html.escape(str(report.get("workflow_label", "알 수 없음"))) if isinstance(report, dict) else "알 수 없음"
        zip_purpose_label = html.escape(str(report.get("zip_purpose_label", "ZIP 목적 미확인"))) if isinstance(report, dict) else "ZIP 목적 미확인"
        zip_decision = html.escape(str(report.get("zip_decision", ""))) if isinstance(report, dict) else ""
        zip_next_action = html.escape(str(report.get("zip_next_action", ""))) if isinstance(report, dict) else ""
        product_label = html.escape(str(report.get("product_label", "알 수 없음"))) if isinstance(report, dict) else "알 수 없음"
        static_png_count = html.escape(str(report.get("static_png_count", 0))) if isinstance(report, dict) else "0"
        animated_gif_count = html.escape(str(report.get("animated_gif_count", 0))) if isinstance(report, dict) else "0"
        optimization = report.get("optimization", {}) if isinstance(report, dict) else {}
        optimization_missed = html.escape(str(optimization.get("missed_target_count", 0))) if isinstance(optimization, dict) else "0"
        optimization_largest = html.escape(str(optimization.get("largest_final_bytes", 0))) if isinstance(optimization, dict) else "0"
        readiness = result.get("submission_readiness", {})
        readiness_score = html.escape(str(readiness.get("score", "?"))) if isinstance(readiness, dict) else "?"
        readiness_label = html.escape(str(readiness.get("decision_label", "알 수 없음"))) if isinstance(readiness, dict) else "알 수 없음"
        evidence_package = result.get("evidence_package", {})
        evidence_zip = html.escape(str(evidence_package.get("zip", ""))) if isinstance(evidence_package, dict) else ""
        evidence_html = html.escape(str(evidence_package.get("html", ""))) if isinstance(evidence_package, dict) else ""
        evidence_missing = html.escape(str(evidence_package.get("missing_count", 0))) if isinstance(evidence_package, dict) else "0"
        evidence_manual = html.escape(str(evidence_package.get("manual_required_count", 0))) if isinstance(evidence_package, dict) else "0"
        top_risks = readiness.get("top_risks", []) if isinstance(readiness, dict) else []
        if isinstance(top_risks, list) and top_risks:
            risk_items = "<ul>" + "".join(
                f"<li><strong>{html.escape(str(risk.get('name', '점검')))}</strong> "
                f"{html.escape(str(risk.get('message', '')))} "
                f"<br>{html.escape(str(risk.get('recommended_action', '')))}</li>"
                for risk in top_risks[:5]
                if isinstance(risk, dict)
            ) + "</ul>"
        else:
            risk_items = "<p>큰 반려 위험 항목은 감지되지 않았습니다. 그래도 최종 제출 전 사람 검수는 필요합니다.</p>"
        research_api_fallback_count = html.escape(str(report.get("research_api_fallback_count", 0))) if isinstance(report, dict) else "0"
        research_free_collection_count = html.escape(str(report.get("research_free_collection_count", 0))) if isinstance(report, dict) else "0"
        memory_weight_system = report.get("memory_weight_system", {}) if isinstance(report, dict) else {}
        phrase_weight_count = html.escape(str(memory_weight_system.get("phrase_weight_count", 0))) if isinstance(memory_weight_system, dict) else "0"
        sketch_consistency = report.get("sketch_consistency", {}) if isinstance(report, dict) else {}
        sketch_enabled = html.escape(str(sketch_consistency.get("enabled", False))) if isinstance(sketch_consistency, dict) else "False"
        sketch_quality = html.escape(str(sketch_consistency.get("quality", "not_used"))) if isinstance(sketch_consistency, dict) else "not_used"
        sketch_layer = html.escape(str(sketch_consistency.get("normalized_layer", ""))) if isinstance(sketch_consistency, dict) else ""
        expression_variation = report.get("expression_variation", {}) if isinstance(report, dict) else {}
        expression_enabled = html.escape(str(expression_variation.get("enabled", False))) if isinstance(expression_variation, dict) else "False"
        expression_features = html.escape(", ".join(str(item) for item in expression_variation.get("features", []))) if isinstance(expression_variation, dict) else ""
        emotion_matching = report.get("phrase_emotion_matching", {}) if isinstance(report, dict) else {}
        keyword_match_count = html.escape(str(emotion_matching.get("keyword_match_count", 0))) if isinstance(emotion_matching, dict) else "0"
        emotion_counts = html.escape(json.dumps(emotion_matching.get("emotion_counts", {}), ensure_ascii=False)) if isinstance(emotion_matching, dict) else "{}"
        phrase_quality = report.get("phrase_quality", {}) if isinstance(report, dict) else {}
        phrase_quality_status = html.escape(str(phrase_quality.get("status", "unknown"))) if isinstance(phrase_quality, dict) else "unknown"
        phrase_quality_score = html.escape(str(phrase_quality.get("score", "?"))) if isinstance(phrase_quality, dict) else "?"
        phrase_quality_warns = html.escape(str(phrase_quality.get("warn_count", 0))) if isinstance(phrase_quality, dict) else "0"
        phrase_quality_fails = html.escape(str(phrase_quality.get("fail_count", 0))) if isinstance(phrase_quality, dict) else "0"
        phrase_replacements = report.get("phrase_replacements", {}) if isinstance(report, dict) else {}
        phrase_replacement_count = html.escape(str(phrase_replacements.get("suggestion_count", 0))) if isinstance(phrase_replacements, dict) else "0"
        revised_variant = report.get("revised_phrase_variant", {}) if isinstance(report, dict) else {}
        revised_applied = html.escape(str(revised_variant.get("applied_count", 0))) if isinstance(revised_variant, dict) else "0"
        revised_refined = html.escape(str(revised_variant.get("refinement_change_count", 0))) if isinstance(revised_variant, dict) else "0"
        revised_zip = html.escape(str(revised_variant.get("zip", ""))) if isinstance(revised_variant, dict) else ""
        revised_quality = html.escape(str(revised_variant.get("quality_status", "unknown"))) if isinstance(revised_variant, dict) else "unknown"
        revised_validation = html.escape(str(revised_variant.get("validation_status", "unknown"))) if isinstance(revised_variant, dict) else "unknown"
        preview_gallery = report.get("preview_gallery", {}) if isinstance(report, dict) else {}
        gallery_html = html.escape(str(preview_gallery.get("html", ""))) if isinstance(preview_gallery, dict) else ""
        gallery_changed = html.escape(str(preview_gallery.get("changed_count", 0))) if isinstance(preview_gallery, dict) else "0"
        creator_profile = report.get("creator_profile", {}) if isinstance(report, dict) else {}
        personality = html.escape(str(creator_profile.get("personality", "자동 설정 없음"))) if isinstance(creator_profile, dict) else "자동 설정 없음"
        speech_style = html.escape(str(creator_profile.get("speech_style", "자동 설정 없음"))) if isinstance(creator_profile, dict) else "자동 설정 없음"
        set_direction = html.escape(str(creator_profile.get("set_direction", "자동 설정 없음"))) if isinstance(creator_profile, dict) else "자동 설정 없음"
        research_categories = html.escape(", ".join(str(item) for item in report.get("research_top_categories", []))) if isinstance(report, dict) else ""
        research_source_count = html.escape(str(report.get("research_source_count", 0))) if isinstance(report, dict) else "0"
        legal_risk_level = html.escape(str(report.get("legal_risk_level", "unknown"))) if isinstance(report, dict) else "unknown"
        weighted_phrases = html.escape(", ".join(str(item) for item in report.get("top_weighted_phrases", [])[:8])) if isinstance(report, dict) else ""
        validation = result.get("validation", {})
        validation_status = html.escape(str(validation.get("status", "unknown")))
        fail_count = html.escape(str(validation.get("fail_count", "?")))
        warn_count = html.escape(str(validation.get("warn_count", "?")))
        issues = validation.get("issues", [])
        issue_items = ""
        if isinstance(issues, list) and issues:
            issue_items = "<ul>" + "".join(
                f"<li><strong>{html.escape(str(issue.get('level', 'info')).upper())}</strong> "
                f"{html.escape(str(issue.get('message', '')))}</li>"
                for issue in issues[:8]
                if isinstance(issue, dict)
            ) + "</ul>"
        else:
            issue_items = "<p>검사 실패 항목이 없습니다. 그래도 실제 제출 전에는 사람 눈으로 한 번 더 확인해주세요.</p>"
        result_html = f"""
        <section class="result">
          <h2>생성 완료</h2>
          <p><strong>작업 모드</strong><br>{workflow_label}</p>
          <p><strong>ZIP 목적</strong><br>{zip_purpose_label} / {zip_decision}</p>
          <p><strong>다음 조치</strong><br>{zip_next_action}</p>
          <p><strong>상품 종류</strong><br>{product_label}</p>
          <p><strong>자동 성격</strong><br>{personality}</p>
          <p><strong>자동 말투</strong><br>{speech_style}</p>
          <p><strong>세트 방향</strong><br>{set_direction}</p>
          <p><strong>자료 학습</strong><br>{research_source_count}개 소스 / {research_categories}</p>
          <p><strong>API fallback</strong><br>fallback {research_api_fallback_count}회 / 무료 수집 {research_free_collection_count}회</p>
          <p><strong>법적 리스크</strong><br>{legal_risk_level}</p>
          <p><strong>메모리 가중치</strong><br>문구 가중치 {phrase_weight_count}개 적용 / {weighted_phrases}</p>
          <p><strong>스케치 일관성</strong><br>사용 {sketch_enabled} / 품질 {sketch_quality}<br>{sketch_layer}</p>
          <p><strong>표정/감정 변형</strong><br>적용 {expression_enabled} / {expression_features}</p>
          <p><strong>문구-감정 매칭</strong><br>키워드 매칭 {keyword_match_count}개 / 분포 {emotion_counts}</p>
          <p><strong>문구 품질 검사</strong><br>{phrase_quality_status} / {phrase_quality_score}점 / 실패 {phrase_quality_fails}개 / 주의 {phrase_quality_warns}개</p>
          <p><strong>대체 문구 제안</strong><br>{phrase_replacement_count}개 후보 세트 생성 / phrase_replacement_suggestions.json</p>
          <p><strong>대체 문구 적용 수정판</strong><br>1차 적용 {revised_applied}개 / 재개선 {revised_refined}개 / 품질 {revised_quality} / 검사 {revised_validation}<br>{revised_zip}</p>
          <p><strong>미리보기 비교 갤러리</strong><br>문구 변경 {gallery_changed}개 / {gallery_html}</p>
          <p><strong>결과 폴더</strong><br>{output_dir}</p>
          <p><strong>생성 ZIP</strong><br>{zip_path}</p>
          <p>PNG {static_png_count}개, GIF {animated_gif_count}개, JPG 미리보기가 생성되었습니다.</p>
          <p><strong>자동 용량 최적화</strong><br>목표 초과 {optimization_missed}개 / 최대 파일 {optimization_largest} bytes</p>
          <p><strong>제출 전 준비 점수</strong><br>{readiness_score}점 / {readiness_label}</p>
          <p><strong>사람 제작 증빙 패키지</strong><br>ZIP: {evidence_zip}<br>HTML 요약: {evidence_html}<br>누락 {evidence_missing}개 / 수동 보관 필요 {evidence_manual}개</p>
          <p>문구 자동 보충: {auto_phrase_count}개</p>
          <div class="validation">
            <strong>반려 가능성 체크</strong>
            {risk_items}
          </div>
          <div class="validation">
            <strong>자동 검사:</strong> {validation_status}
            <span>실패 {fail_count}개 / 주의 {warn_count}개</span>
            {issue_items}
          </div>
        </section>
        """
    research_html = ""
    if research_result:
        output_dir = html.escape(str(research_result.get("output_dir", "")))
        if "daily_report" in research_result:
            daily_report = research_result.get("daily_report", {})
            rounds = html.escape(str(daily_report.get("rounds", "?"))) if isinstance(daily_report, dict) else "?"
            categories = html.escape(", ".join(str(item) for item in daily_report.get("top_categories", []))) if isinstance(daily_report, dict) else ""
            risk_counts = html.escape(json.dumps(daily_report.get("legal_risk_counts", {}), ensure_ascii=False)) if isinstance(daily_report, dict) else "{}"
            phrase_preview = html.escape(", ".join(str(item) for item in daily_report.get("learned_phrase_preview", [])[-10:])) if isinstance(daily_report, dict) else ""
            api_used_total = html.escape(str(daily_report.get("api_used_total", 0))) if isinstance(daily_report, dict) else "0"
            api_fallback_total = html.escape(str(daily_report.get("api_fallback_total", 0))) if isinstance(daily_report, dict) else "0"
            free_collection_total = html.escape(str(daily_report.get("free_collection_total", 0))) if isinstance(daily_report, dict) else "0"
            search_url_total = html.escape(str(daily_report.get("search_url_total", 0))) if isinstance(daily_report, dict) else "0"
            gemini_used_total = html.escape(str(daily_report.get("gemini_used_total", 0))) if isinstance(daily_report, dict) else "0"
            official_source_total = html.escape(str(daily_report.get("official_source_total", 0))) if isinstance(daily_report, dict) else "0"
            low_confidence_source_total = html.escape(str(daily_report.get("low_confidence_source_total", 0))) if isinstance(daily_report, dict) else "0"
            source_quality_average = html.escape(str(daily_report.get("source_quality_average", 0))) if isinstance(daily_report, dict) else "0"
            advice = daily_report.get("next_generation_advice", []) if isinstance(daily_report, dict) else []
            advice_items = "<ul>" + "".join(f"<li>{html.escape(str(item))}</li>" for item in advice[:8]) + "</ul>"
            research_html = f"""
            <section class="result">
              <h2>반복 학습 완료</h2>
              <p><strong>학습 폴더</strong><br>{output_dir}</p>
              <p><strong>라운드</strong><br>{rounds}회</p>
              <p><strong>누적 핵심 카테고리</strong><br>{categories}</p>
              <p><strong>자동 검색 URL</strong><br>{search_url_total}개</p>
              <p><strong>API/무료 수집</strong><br>API 사용 {api_used_total} / API fallback {api_fallback_total} / 무료 수집 {free_collection_total}</p>
              <p><strong>출처 신뢰도</strong><br>평균 {source_quality_average}점 / 공식·법률 출처 {official_source_total}개 / 주의 출처 {low_confidence_source_total}개</p>
              <p><strong>Gemini 분석</strong><br>{gemini_used_total}회 사용</p>
              <p><strong>법적 리스크 분포</strong><br>{risk_counts}</p>
              <p><strong>학습 문구 후보</strong><br>{phrase_preview}</p>
              <div class="validation">
                <strong>다음 생성 조언</strong>
                {advice_items}
              </div>
            </section>
            """
        else:
            analysis = research_result.get("analysis", {})
            source_count = html.escape(str(analysis.get("source_count", 0))) if isinstance(analysis, dict) else "0"
            api_used_count = html.escape(str(analysis.get("api_used_count", 0))) if isinstance(analysis, dict) else "0"
            api_fallback_count = html.escape(str(analysis.get("api_fallback_count", 0))) if isinstance(analysis, dict) else "0"
            free_collection_count = html.escape(str(analysis.get("free_collection_count", 0))) if isinstance(analysis, dict) else "0"
            search_url_count = html.escape(str(analysis.get("search_url_count", 0))) if isinstance(analysis, dict) else "0"
            search_keywords = html.escape(", ".join(str(item) for item in analysis.get("search_keywords", []))) if isinstance(analysis, dict) else ""
            source_quality = analysis.get("source_quality_summary", {}) if isinstance(analysis, dict) else {}
            source_quality_average = html.escape(str(source_quality.get("average_score", 0))) if isinstance(source_quality, dict) else "0"
            platform_official_count = html.escape(str(source_quality.get("platform_official_count", 0))) if isinstance(source_quality, dict) else "0"
            legal_official_count = html.escape(str(source_quality.get("legal_official_count", 0))) if isinstance(source_quality, dict) else "0"
            low_confidence_count = html.escape(str(source_quality.get("low_confidence_count", 0))) if isinstance(source_quality, dict) else "0"
            gemini_status = html.escape(str(analysis.get("gemini_status", ""))) if isinstance(analysis, dict) else ""
            gemini_used = html.escape(str(analysis.get("gemini_used", False))) if isinstance(analysis, dict) else "False"
            categories = html.escape(", ".join(str(item) for item in analysis.get("top_categories", []))) if isinstance(analysis, dict) else ""
            guardrails = analysis.get("legal_guardrails", {}) if isinstance(analysis, dict) else {}
            risk_level = html.escape(str(guardrails.get("risk_level", "unknown"))) if isinstance(guardrails, dict) else "unknown"
            risk_flags = guardrails.get("risk_flags", []) if isinstance(guardrails, dict) else []
            risk_items = ""
            if isinstance(risk_flags, list) and risk_flags:
                risk_items = "<ul>" + "".join(f"<li>{html.escape(str(flag))}</li>" for flag in risk_flags[:8]) + "</ul>"
            else:
                risk_items = "<p>큰 법적 위험 키워드는 감지되지 않았습니다. 그래도 최종 생성 전 사람 검수는 필요합니다.</p>"
            suggestions = analysis.get("suggestions", {}) if isinstance(analysis, dict) else {}
            phrase_additions = suggestions.get("phrase_additions", []) if isinstance(suggestions, dict) else []
            phrase_preview = html.escape(", ".join(str(item) for item in phrase_additions[:10]))
            research_html = f"""
            <section class="result">
              <h2>자료 수집/분석 완료</h2>
              <p><strong>분석 폴더</strong><br>{output_dir}</p>
              <p><strong>소스 수</strong><br>{source_count}개</p>
              <p><strong>자동 검색</strong><br>키워드: {search_keywords}<br>수집 URL: {search_url_count}개</p>
              <p><strong>API/무료 수집</strong><br>API 사용 {api_used_count} / API fallback {api_fallback_count} / 무료 수집 {free_collection_count}</p>
              <p><strong>출처 신뢰도</strong><br>평균 {source_quality_average}점 / 카카오 공식 {platform_official_count}개 / 법률·정부 공식 {legal_official_count}개 / 주의 출처 {low_confidence_count}개</p>
              <p><strong>Gemini 분석</strong><br>사용 {gemini_used} / 상태 {gemini_status}</p>
              <p><strong>트렌드 카테고리</strong><br>{categories}</p>
              <p><strong>법적 리스크</strong><br>{risk_level}</p>
              <p><strong>추천 문구 후보</strong><br>{phrase_preview}</p>
              <div class="validation">
                <strong>가드레일</strong>
                {risk_items}
              </div>
            </section>
            """
    error_html = f'<section class="error">{html.escape(error)}</section>' if error else ""
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{APP_NAME}</title>
  <style>
    :root {{
      --ink: #2d2424;
      --muted: #766969;
      --paper: #fff8ea;
      --line: #ead8bc;
      --mint: #7fd8be;
      --coral: #ff9f8a;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      font-family: "Malgun Gothic", "Apple SD Gothic Neo", sans-serif;
      background:
        radial-gradient(circle at 15% 20%, rgba(255,159,138,.35), transparent 26rem),
        radial-gradient(circle at 84% 12%, rgba(127,216,190,.45), transparent 25rem),
        linear-gradient(135deg, #fffaf0, #f7efe1);
    }}
    main {{
      width: min(1080px, calc(100% - 32px));
      margin: 0 auto;
      padding: 44px 0;
    }}
    .hero {{
      display: grid;
      grid-template-columns: 1.1fr .9fr;
      gap: 28px;
      align-items: stretch;
    }}
    .panel {{
      border: 2px solid var(--line);
      border-radius: 30px;
      background: rgba(255,255,255,.78);
      box-shadow: 0 24px 70px rgba(96, 69, 45, .13);
      padding: 30px;
      backdrop-filter: blur(10px);
    }}
    h1 {{
      margin: 0 0 12px;
      font-size: clamp(34px, 6vw, 64px);
      line-height: .95;
      letter-spacing: -0.06em;
    }}
    h2 {{ margin-top: 0; }}
    p {{ color: var(--muted); line-height: 1.7; }}
    label {{
      display: block;
      margin: 18px 0 8px;
      font-weight: 800;
    }}
    input, textarea, select {{
      width: 100%;
      border: 2px solid var(--line);
      border-radius: 18px;
      padding: 14px 15px;
      font: inherit;
      background: #fffdf8;
      color: var(--ink);
    }}
    input[type="checkbox"] {{
      width: auto;
      margin-right: 8px;
    }}
    textarea {{ min-height: 190px; resize: vertical; }}
    .colors {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }}
    button {{
      margin-top: 24px;
      width: 100%;
      border: 0;
      border-radius: 20px;
      padding: 17px 20px;
      background: linear-gradient(135deg, var(--coral), #ffca72);
      color: #382626;
      font-size: 18px;
      font-weight: 900;
      cursor: pointer;
      box-shadow: 0 16px 30px rgba(255,159,138,.32);
    }}
    .secondary-button {{
      margin-top: 12px;
      background: linear-gradient(135deg, var(--mint), #b8efd9);
      box-shadow: 0 16px 30px rgba(127,216,190,.24);
    }}
    .card {{
      min-height: 100%;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }}
    .badge {{
      display: inline-flex;
      width: fit-content;
      border: 2px solid var(--ink);
      border-radius: 999px;
      padding: 8px 13px;
      background: var(--mint);
      font-weight: 900;
    }}
    .rules {{
      margin-top: 24px;
      display: grid;
      gap: 12px;
    }}
    .rule {{
      padding: 14px 16px;
      border-radius: 18px;
      background: var(--paper);
      border: 1px solid var(--line);
      font-weight: 700;
    }}
    .result, .error {{
      margin-top: 22px;
      border-radius: 24px;
      padding: 22px;
    }}
    .result {{ background: #e9fff4; border: 2px solid #9be2c7; }}
    .error {{ background: #fff0f0; border: 2px solid #ffb1b1; }}
    .validation {{
      margin-top: 16px;
      padding: 14px;
      border-radius: 18px;
      background: rgba(255,255,255,.66);
      border: 1px solid #bcebd8;
    }}
    .validation span {{
      display: inline-block;
      margin-left: 8px;
      color: var(--muted);
      font-weight: 700;
    }}
    .validation ul {{
      margin: 10px 0 0;
      padding-left: 20px;
      color: var(--muted);
      line-height: 1.6;
    }}
    .hint {{
      margin: 8px 0 0;
      font-size: 14px;
    }}
    .policy-note {{
      margin-top: 16px;
      padding: 14px 16px;
      border-radius: 18px;
      background: #fff3d8;
      border: 1px solid #f2cc80;
      color: #6b4c16;
      font-weight: 700;
      line-height: 1.6;
    }}
    .memory-link {{
      display: inline-block;
      border-radius: 999px;
      padding: 10px 14px;
      background: #fff3d8;
      color: var(--ink);
      font-weight: 900;
      text-decoration: none;
      border: 1px solid #f2cc80;
    }}
    @media (max-width: 820px) {{
      .hero {{ grid-template-columns: 1fr; }}
      .colors {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div class="panel">
        <span class="badge">v100 clean restart</span>
        <h1>작게 만들고<br>확실하게 제출하기</h1>
        <p>
          복잡한 v92를 그대로 끌고 가지 않고, 제출물 생성에 필요한 최소 흐름부터 다시 세웁니다.
          지금 버전은 PNG 32개, GIF 24개, 제출 ZIP을 빠르게 만드는 출발점입니다.
        </p>
        <p><a class="memory-link" href="/results">최근 결과물</a> <a class="memory-link" href="/memory">진화 메모리 보기</a> <a class="memory-link" href="/status">실행 상태 보기</a> <a class="memory-link" href="/api-settings">API 키 안내</a> <a class="memory-link" href="/release-check">배포 점검</a></p>
        {error_html}
        {research_html}
        {result_html}
      </div>
      <form class="panel card" method="post" action="/build" enctype="multipart/form-data">
        <div>
          <h2>새 이모티콘 세트 만들기</h2>
          <label for="character_name">캐릭터 이름</label>
          <input id="character_name" name="character_name" value="몽실이" maxlength="40">
          <label for="concept">콘셉트</label>
          <input id="concept" name="concept" value="따뜻하고 말랑한 응원 캐릭터" maxlength="120">
          <label for="character_style">캐릭터 스타일</label>
          <select id="character_style" name="character_style">
            {style_options}
          </select>
          <label for="workflow_mode">작업 모드</label>
          <select id="workflow_mode" name="workflow_mode">
            {workflow_options}
          </select>
          <label for="product_mode">카카오 이모티콘 종류</label>
          <select id="product_mode" name="product_mode">
            {product_options}
          </select>
          <p class="hint">정지형/움직이는/미니 모드별로 생성 개수와 ZIP 검사를 분리합니다. 실제 제출 전 최신 카카오 스튜디오 화면에서 최종 규격은 다시 확인하세요.</p>
          <label for="sketch_image">내 러프 스케치 업로드</label>
          <input id="sketch_image" name="sketch_image" type="file" accept="image/png,image/jpeg,image/webp">
          <p class="hint">원형 얼굴, 몸통, 팔다리 정도의 대략적인 스케치도 가능합니다. 흰 배경은 자동으로 최대한 제거해서 캐릭터 바탕으로 사용합니다.</p>
          <p class="policy-note">
            카카오 운영 원칙상 생성형 AI를 활용한 제작물 제안은 제한될 수 있습니다.
            이 자동 생성 결과물은 기본적으로 참고용 프로토타입이며, 실제 제출은 직접 제작한 원본과 작업 증빙을 기준으로 준비하세요.
          </p>
          <div class="colors">
            <div>
              <label for="base_color">캐릭터 색</label>
              <input id="base_color" name="base_color" value="#ffd166">
            </div>
            <div>
              <label for="accent_color">포인트 색</label>
              <input id="accent_color" name="accent_color" value="#7fd8be">
            </div>
          </div>
          <label for="phrases">문구 목록</label>
          <textarea id="phrases" name="phrases">{html.escape(phrases)}</textarea>
          <p class="hint">문구를 56개 모두 적지 않아도 됩니다. 부족한 문구는 감정별 추천 문구로 자동 보충됩니다.</p>
          <label for="research_urls">유튜브/인터넷 참고 URL</label>
          <textarea id="research_urls" name="research_urls" placeholder="https://www.youtube.com/watch?v=...\nhttps://example.com/emoticon-guide"></textarea>
          <p class="hint">제목과 도메인 같은 추상 정보만 학습합니다. 캐릭터, 썸네일, 문구를 그대로 복사하지 마세요.</p>
          <label for="research_keywords">자동 검색 키워드</label>
          <textarea id="research_keywords" name="research_keywords" placeholder="카카오 이모티콘 제작 가이드\n미니 이모티콘 저작권\n움직이는 이모티콘 WebP"></textarea>
          <p class="hint">Google Custom Search 키와 검색 엔진 ID가 있으면 검색 결과 URL을 자동 수집합니다. 한도 도달/키 없음/오류 시 비용 없는 조사 메모 기반 분석으로 자동 fallback됩니다.</p>
          <label>
            <input type="checkbox" name="auto_collect_research" value="1" checked>
            카카오/저작권/법적 안전자료 자동 수집 포함
          </label>
          <label for="research_notes">자료 조사 메모</label>
          <textarea id="research_notes" name="research_notes" placeholder="예: 요즘 미니 이모티콘은 단순한 선, 큰 표정, 짧은 리액션 문구가 잘 보임"></textarea>
          <label for="learning_rounds">반복 학습 라운드</label>
          <input id="learning_rounds" name="learning_rounds" type="number" min="1" max="10" value="3">
          <label for="human_origin_note">사람 제작 증빙 메모</label>
          <textarea id="human_origin_note" name="human_origin_note" placeholder="예: 종이에 러프 스케치 후 직접 선화/채색, Procreate 타임랩스 보관, 레이어 원본 보관"></textarea>
          <button type="submit" formaction="/research">자료만 수집/분석하기</button>
          <button type="submit" formaction="/learn">반복 학습 실행하기</button>
          <button class="secondary-button" type="submit" formaction="/build">PNG/GIF/ZIP 생성하기</button>
        </div>
        <div class="rules">
          <div class="rule">일반 정지형: PNG 32개</div>
          <div class="rule">일반 움직임: PNG 21개 + GIF 3개</div>
          <div class="rule">미니 정지형: PNG 24개</div>
          <div class="rule">미니 움직임: PNG 21개 + GIF 3개</div>
          <div class="rule">API 한도 초과 시 무료 분석으로 자동 전환</div>
          <div class="rule">메모리 가중치가 다음 문구 추천에 반영</div>
        </div>
      </form>
    </section>
  </main>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.startswith("/outputs/"):
            self.serve_output_file()
            return
        if self.path.startswith("/release/"):
            self.serve_release_file()
            return
        if self.path == "/memory":
            self.respond(200, memory_page())
            return
        if self.path == "/status":
            self.respond(200, system_status_page())
            return
        if self.path == "/api-settings":
            self.respond(200, api_settings_page())
            return
        if self.path == "/results":
            self.respond(200, results_page())
            return
        if self.path == "/release-check":
            self.respond(200, release_check_page())
            return
        parsed = urlparse(self.path)
        if parsed.path == "/result":
            params = parse_qs(parsed.query)
            self.respond(200, result_detail_page(params.get("name", [""])[0]))
            return
        self.respond(200, page())

    def do_POST(self) -> None:
        if self.path == "/package-release":
            report = build_release_package()
            self.respond(200, release_result_page(report))
            return
        if self.path == "/memory/compact":
            compact_evolution_memory()
            self.respond(200, memory_page("진화 메모리를 중복 정리했습니다."))
            return
        if self.path == "/memory/reset":
            reset_evolution_memory()
            self.respond(200, memory_page("진화 메모리를 초기화했습니다."))
            return
        if self.path == "/api-usage/reset":
            reset_api_usage_ledger()
            self.respond(200, api_settings_page("API 사용량 원장을 초기화했습니다. 키와 환경변수는 변경하지 않았습니다."))
            return
        if self.path not in {"/build", "/research", "/learn"}:
            self.respond(404, page(error="Unknown route."))
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        content_type = self.headers.get("Content-Type", "")
        files: dict[str, tuple[str, bytes]] = {}
        if content_type.startswith("multipart/form-data"):
            form, files = parse_multipart_form(content_type, body)
        else:
            form = parse_qs(body.decode("utf-8", errors="replace"))
        sketch_image, sketch_filename = image_from_upload(files, "sketch_image")
        try:
            research_urls = parse_research_urls(form_value(form, "research_urls", ""))
            research_keywords = parse_research_keywords(form_value(form, "research_keywords", ""))
            research_notes = form_value(form, "research_notes", "")
            auto_collect = bool(form.get("auto_collect_research"))
            if self.path == "/research":
                research_result = run_research_only(research_urls, research_notes, auto_collect, research_keywords)
                self.respond(200, page(research_result=research_result))
                return
            if self.path == "/learn":
                rounds = clamp_int(form_value(form, "learning_rounds", "3"), 3, 1, 10)
                research_result = run_learning_cycle(research_urls, research_notes, auto_collect, rounds, research_keywords)
                self.respond(200, page(research_result=research_result))
                return
            request = BuildRequest(
                character_name=form_value(form, "character_name", "몽실이"),
                concept=form_value(form, "concept", "따뜻하고 말랑한 응원 캐릭터"),
                phrases=parse_phrases(form_value(form, "phrases", "\n".join(DEFAULT_PHRASES))),
                base_color=color_or_default(form_value(form, "base_color", "#ffd166"), "#ffd166"),
                accent_color=color_or_default(form_value(form, "accent_color", "#7fd8be"), "#7fd8be"),
                character_style=form_value(form, "character_style", "soft_bear")
                if form_value(form, "character_style", "soft_bear") in CHARACTER_STYLES
                else "soft_bear",
                workflow_mode=form_value(form, "workflow_mode", "prototype_only")
                if form_value(form, "workflow_mode", "prototype_only") in WORKFLOW_MODES
                else "prototype_only",
                product_mode=form_value(form, "product_mode", "standard_static")
                if form_value(form, "product_mode", "standard_static") in PRODUCT_MODES
                else "standard_static",
                human_origin_note=form_value(form, "human_origin_note", ""),
                sketch_image=sketch_image,
                sketch_filename=sketch_filename,
                research_urls=research_urls,
                research_notes=research_notes,
                research_keywords=research_keywords,
                auto_collect_research=auto_collect,
            )
            result = build_package(request)
            self.respond(200, page(result=result))
        except Exception as exc:
            self.respond(500, page(error=f"생성 중 오류가 발생했습니다: {exc}"))

    def respond(self, status: int, body: str) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def serve_output_file(self) -> None:
        parsed_path = unquote(urlparse(self.path).path).lstrip("/")
        requested = Path(parsed_path)
        try:
            resolved = requested.resolve()
            output_root = OUTPUT_ROOT.resolve()
        except Exception:
            self.respond(400, page(error="잘못된 파일 경로입니다."))
            return
        if not str(resolved).startswith(str(output_root)) or not resolved.is_file():
            self.respond(404, page(error="결과 파일을 찾을 수 없습니다."))
            return
        content_types = {
            ".html": "text/html; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".zip": "application/zip",
        }
        data = resolved.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_types.get(resolved.suffix.lower(), "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def serve_release_file(self) -> None:
        parsed_path = unquote(urlparse(self.path).path).lstrip("/")
        requested = Path(parsed_path)
        try:
            resolved = requested.resolve()
            release_root = RELEASE_ROOT.resolve()
        except Exception:
            self.respond(400, page(error="잘못된 파일 경로입니다."))
            return
        if not str(resolved).startswith(str(release_root)) or not resolved.is_file():
            self.respond(404, page(error="배포 파일을 찾을 수 없습니다."))
            return
        content_types = {
            ".json": "application/json; charset=utf-8",
            ".txt": "text/plain; charset=utf-8",
            ".zip": "application/zip",
        }
        data = resolved.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_types.get(resolved.suffix.lower(), "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: object) -> None:
        print(f"[server] {self.address_string()} - {format % args}")


def form_value(form: dict[str, list[str]], key: str, default: str) -> str:
    values = form.get(key)
    if not values:
        return default
    return values[0].strip() or default


def parse_multipart_form(content_type: str, body: bytes) -> tuple[dict[str, list[str]], dict[str, tuple[str, bytes]]]:
    form: dict[str, list[str]] = {}
    files: dict[str, tuple[str, bytes]] = {}
    boundary_marker = "boundary="
    if boundary_marker not in content_type:
        return form, files
    boundary = content_type.split(boundary_marker, 1)[1].strip().strip('"')
    delimiter = ("--" + boundary).encode("utf-8")
    for part in body.split(delimiter):
        part = part.strip(b"\r\n")
        if not part or part == b"--" or b"\r\n\r\n" not in part:
            continue
        header_bytes, value = part.split(b"\r\n\r\n", 1)
        headers = header_bytes.decode("utf-8", errors="replace")
        name_match = re.search(r'name="([^"]+)"', headers)
        if not name_match:
            continue
        name = name_match.group(1)
        filename_match = re.search(r'filename="([^"]*)"', headers)
        value = value.rstrip(b"\r\n")
        if filename_match and filename_match.group(1):
            files[name] = (filename_match.group(1), value)
        else:
            form.setdefault(name, []).append(value.decode("utf-8", errors="replace"))
    return form, files


def image_from_upload(files: dict[str, tuple[str, bytes]], key: str) -> tuple[Image.Image | None, str]:
    uploaded = files.get(key)
    if not uploaded:
        return None, ""
    filename, data = uploaded
    if not data:
        return None, ""
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
        return image.convert("RGBA"), filename
    except Exception:
        return None, filename


def main() -> None:
    OUTPUT_ROOT.mkdir(exist_ok=True)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer((HOST, PORT), Handler) as httpd:
        url = f"http://{HOST}:{PORT}"
        print(f"{APP_NAME} running at {url}")
        if os.environ.get("KAKAO_NO_BROWSER", "").strip() != "1":
            try:
                webbrowser.open(url)
            except Exception:
                pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")


if __name__ == "__main__":
    main()
