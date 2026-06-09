from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    INFO = "info"
    WARN = "warn"
    BLOCK = "block"


class GateStatus(str, Enum):
    PASS = "pass"
    REVIEW = "review"
    BLOCK = "block"


@dataclass
class SourceMaterial:
    kind: str
    title: str
    url: str = ""
    rights_note: str = ""
    transformation_note: str = ""
    used_direct_media: bool = False


@dataclass
class AssetNote:
    kind: str
    path_or_url: str
    source: str = ""
    license_note: str = ""
    generated: bool = False


@dataclass
class DraftComplianceInput:
    title: str
    narration: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    sources: list[SourceMaterial] = field(default_factory=list)
    assets: list[AssetNote] = field(default_factory=list)
    uses_realistic_synthetic_media: bool = False
    synthetic_disclosure_acknowledged: bool = False
    made_for_kids: bool = False
    public_upload_requested: bool = False


@dataclass
class RiskFinding:
    code: str
    severity: Severity
    message: str
    recommendation: str


@dataclass
class ComplianceReport:
    status: GateStatus
    findings: list[RiskFinding]
    policy_sources_reviewed: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "findings": [
                {
                    **asdict(finding),
                    "severity": finding.severity.value,
                }
                for finding in self.findings
            ],
            "policy_sources_reviewed": self.policy_sources_reviewed,
        }


POLICY_SOURCE_URLS = [
    "https://support.google.com/youtube/answer/12504220",
    "https://support.google.com/youtube/answer/1311392",
    "https://support.google.com/youtube/answer/14328491",
    "https://support.google.com/youtube/answer/9783148",
    "https://developers.google.com/youtube/terms/developer-policies",
]

PROHIBITED_CLAIM_TERMS = [
    "100% 수익",
    "무조건 수익",
    "반드시 돈",
    "완치",
    "치료 보장",
    "투자 추천",
    "코인 추천",
    "주식 추천",
    "도박",
    "불법",
]

REUSED_CONTENT_HINTS = [
    "무편집",
    "원본 그대로",
    "클립 모음",
    "짤 모음",
    "다른 채널 영상",
    "영화 장면",
    "드라마 장면",
    "방송 캡처",
]


def _combined_text(draft: DraftComplianceInput) -> str:
    return " ".join([draft.title, draft.narration, draft.description, " ".join(draft.tags)]).lower()


def evaluate_compliance(draft: DraftComplianceInput) -> ComplianceReport:
    findings: list[RiskFinding] = []
    text = _combined_text(draft)

    for term in PROHIBITED_CLAIM_TERMS:
        if term.lower() in text:
            findings.append(
                RiskFinding(
                    code="unsafe_claim",
                    severity=Severity.BLOCK,
                    message=f"위험 표현이 포함되어 있습니다: {term}",
                    recommendation="수익, 치료, 투자, 불법 행위처럼 보일 수 있는 보장성 표현을 제거하세요.",
                )
            )

    for hint in REUSED_CONTENT_HINTS:
        if hint.lower() in text:
            findings.append(
                RiskFinding(
                    code="reused_content_hint",
                    severity=Severity.WARN,
                    message=f"재사용 콘텐츠로 오해될 수 있는 표현이 있습니다: {hint}",
                    recommendation="비평, 해설, 교육적 분석, 새 대본, 새 음성, 새 장면 등 실질적 창작 요소를 명확히 기록하세요.",
                )
            )

    for source in draft.sources:
        if source.used_direct_media and not source.rights_note.strip():
            findings.append(
                RiskFinding(
                    code="missing_rights_note",
                    severity=Severity.BLOCK,
                    message=f"직접 사용한 외부 소스에 권리/허가 메모가 없습니다: {source.title}",
                    recommendation="소스 권리, 라이선스, 허가, 공정이용 검토 메모 중 하나를 기록하세요.",
                )
            )
        if source.url and not source.transformation_note.strip():
            findings.append(
                RiskFinding(
                    code="missing_transformation_note",
                    severity=Severity.BLOCK,
                    message=f"외부 참고자료의 창작 변형 메모가 없습니다: {source.title}",
                    recommendation="무엇을 참고했고 무엇을 새로 창작했는지 분리해서 적으세요.",
                )
            )

    for asset in draft.assets:
        if not asset.generated and not asset.license_note.strip():
            findings.append(
                RiskFinding(
                    code="missing_asset_license",
                    severity=Severity.BLOCK,
                    message=f"외부 자산의 라이선스 메모가 없습니다: {asset.path_or_url}",
                    recommendation="직접 촬영, 직접 제작, 무료/유료 라이선스, 허가 여부를 기록하세요.",
                )
            )

    if draft.uses_realistic_synthetic_media and not draft.synthetic_disclosure_acknowledged:
        findings.append(
            RiskFinding(
                code="synthetic_disclosure_needed",
                severity=Severity.BLOCK,
                message="현실적으로 보이는 합성/변조 콘텐츠 공개 확인이 필요합니다.",
                recommendation="YouTube Studio의 altered content 공개 여부를 검토하고 체크하세요.",
            )
        )

    if draft.made_for_kids:
        findings.append(
            RiskFinding(
                code="made_for_kids_review",
                severity=Severity.WARN,
                message="아동용 콘텐츠로 표시되어 별도 검토가 필요합니다.",
                recommendation="아동용 품질 원칙, 타겟팅, 데이터/댓글/광고 제한을 별도로 확인하세요.",
            )
        )

    if draft.public_upload_requested:
        findings.append(
            RiskFinding(
                code="human_upload_approval_required",
                severity=Severity.WARN,
                message="공개 업로드 전 사람의 최종 승인이 필요합니다.",
                recommendation="초기 버전은 공개 업로드 대신 수동 업로드 패키지만 생성하세요.",
            )
        )

    if any(f.severity == Severity.BLOCK for f in findings):
        status = GateStatus.BLOCK
    elif any(f.severity == Severity.WARN for f in findings):
        status = GateStatus.REVIEW
    else:
        status = GateStatus.PASS

    return ComplianceReport(status=status, findings=findings, policy_sources_reviewed=POLICY_SOURCE_URLS)
