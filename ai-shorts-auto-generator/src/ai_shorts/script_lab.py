from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SceneDraft:
    order: int
    caption: str
    visual_direction: str
    narration: str


@dataclass
class ScriptDraft:
    topic: str
    title: str
    hook: str
    narration: str
    scenes: list[SceneDraft]
    thumbnail_text: str
    description: str
    tags: list[str] = field(default_factory=list)
    pinned_comment: str = ""
    transformation_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "scenes": [asdict(scene) for scene in self.scenes],
        }


def script_draft_from_dict(data: dict[str, Any]) -> ScriptDraft:
    scenes = [
        SceneDraft(
            order=int(scene.get("order", idx + 1)),
            caption=str(scene.get("caption", "")),
            visual_direction=str(scene.get("visual_direction", "")),
            narration=str(scene.get("narration", "")),
        )
        for idx, scene in enumerate(data.get("scenes", []))
    ]
    return ScriptDraft(
        topic=str(data.get("topic", "")),
        title=str(data.get("title", "")),
        hook=str(data.get("hook", "")),
        narration=str(data.get("narration", "")),
        scenes=scenes,
        thumbnail_text=str(data.get("thumbnail_text", "")),
        description=str(data.get("description", "")),
        tags=[str(tag) for tag in data.get("tags", [])],
        pinned_comment=str(data.get("pinned_comment", "")),
        transformation_note=str(data.get("transformation_note", "")),
    )


def _clean_topic(topic: str) -> str:
    cleaned = re.sub(r"\s+", " ", topic.strip())
    return cleaned or "생활에 도움 되는 쇼츠"


def create_local_script_draft(topic: str, source_notes: str = "") -> ScriptDraft:
    clean_topic = _clean_topic(topic)
    title = f"{clean_topic}: 바로 써먹는 3가지 포인트"
    hook = f"{clean_topic}, 대부분 여기서 놓칩니다."
    scenes = [
        SceneDraft(
            order=1,
            caption="문제는 생각보다 가까이에 있습니다",
            visual_direction="vertical clean Korean short intro scene, bold readable title, original abstract background",
            narration=f"{clean_topic}을 볼 때 가장 먼저 확인할 것은 문제의 출처입니다.",
        ),
        SceneDraft(
            order=2,
            caption="핵심 기준을 하나로 줄입니다",
            visual_direction="simple checklist scene with large Korean captions and warm neutral lighting",
            narration="기준을 하나로 줄이면 선택이 빨라지고 실수도 줄어듭니다.",
        ),
        SceneDraft(
            order=3,
            caption="작게 반복할 수 있어야 오래 갑니다",
            visual_direction="daily routine visual, calendar and progress marks, no third party logo",
            narration="처음부터 크게 바꾸기보다 오늘 반복할 수 있는 작은 행동으로 바꿔야 합니다.",
        ),
        SceneDraft(
            order=4,
            caption="오늘 하나만 적용해보세요",
            visual_direction="closing scene, calm call to action, original minimal illustration",
            narration="오늘은 하나만 적용해보세요. 작은 차이가 다음 선택을 바꿉니다.",
        ),
    ]
    narration = " ".join([hook, *[scene.narration for scene in scenes]])
    transformation_note = (
        "외부 콘텐츠를 복제하지 않고, 참고 메모에서 주제 패턴만 추출해 새 대본, 새 장면 구성, 새 음성/자막으로 제작합니다."
    )
    if source_notes.strip():
        transformation_note += f" 참고 메모: {source_notes.strip()[:300]}"
    return ScriptDraft(
        topic=clean_topic,
        title=title,
        hook=hook,
        narration=narration,
        scenes=scenes,
        thumbnail_text="오늘 바로 바꾸는 3가지",
        description=(
            f"{clean_topic}에 대해 직접 구성한 쇼츠 초안입니다.\n\n"
            "이 영상은 참고 콘텐츠를 재업로드하거나 편집 모음으로 사용하지 않고, 새 대본과 새 장면으로 제작하는 것을 목표로 합니다."
        ),
        tags=["쇼츠", "생활팁", "자기관리", "Shorts"],
        pinned_comment="이 주제에서 가장 먼저 바꿔보고 싶은 습관은 무엇인가요?",
        transformation_note=transformation_note,
    )
