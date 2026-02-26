"""데이터 모델 정의 - 시스템 전반에서 사용되는 데이터 클래스"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ProcessingStatus(Enum):
    """URL 처리 상태"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SourceType(Enum):
    """수집 소스 유형"""

    GMAIL = "gmail"
    WEB = "web"


@dataclass
class CollectedItem:
    """수집된 콘텐츠 항목"""

    url: str
    title: str = ""
    source: SourceType = SourceType.WEB
    source_name: str = ""
    collected_at: datetime = field(default_factory=datetime.now)

    # DB 저장 후 할당되는 필드
    id: int | None = None
    status: ProcessingStatus = ProcessingStatus.PENDING
    error_msg: str | None = None
    audio_path: str | None = None


@dataclass
class TargetSite:
    """웹 수집 대상 사이트 정보"""

    name: str
    url: str
    type: str = "rss"  # "rss" | "html"
    rss_url: str = ""
    selector: str = ""
