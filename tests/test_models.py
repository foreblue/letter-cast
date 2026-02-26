"""데이터 모델 테스트"""

from datetime import datetime

import pytest

from src.models import CollectedItem, ProcessingStatus, SourceType, TargetSite


class TestCollectedItem:
    """CollectedItem 데이터 클래스 테스트"""

    def test_default_creation(self):
        """기본값으로 생성 테스트"""
        item = CollectedItem(url="https://example.com/article")
        assert item.url == "https://example.com/article"
        assert item.title == ""
        assert item.source == SourceType.WEB
        assert item.status == ProcessingStatus.PENDING
        assert item.id is None
        assert item.error_msg is None
        assert item.audio_path is None

    def test_full_creation(self):
        """모든 필드를 지정하여 생성 테스트"""
        now = datetime.now()
        item = CollectedItem(
            url="https://example.com/article",
            title="테스트 기사",
            source=SourceType.GMAIL,
            source_name="newsletter@test.com",
            collected_at=now,
            id=1,
            status=ProcessingStatus.COMPLETED,
        )
        assert item.source == SourceType.GMAIL
        assert item.source_name == "newsletter@test.com"
        assert item.id == 1
        assert item.status == ProcessingStatus.COMPLETED
        assert item.collected_at == now


class TestProcessingStatus:
    """ProcessingStatus Enum 테스트"""

    def test_values(self):
        """모든 상태 값 테스트"""
        assert ProcessingStatus.PENDING.value == "pending"
        assert ProcessingStatus.PROCESSING.value == "processing"
        assert ProcessingStatus.COMPLETED.value == "completed"
        assert ProcessingStatus.FAILED.value == "failed"

    def test_from_string(self):
        """문자열에서 Enum 변환 테스트"""
        assert ProcessingStatus("pending") == ProcessingStatus.PENDING
        assert ProcessingStatus("completed") == ProcessingStatus.COMPLETED


class TestTargetSite:
    """TargetSite 데이터 클래스 테스트"""

    def test_rss_site(self):
        """RSS 사이트 생성 테스트"""
        site = TargetSite(
            name="TechBlog",
            url="https://techblog.com",
            type="rss",
            rss_url="https://techblog.com/feed",
        )
        assert site.type == "rss"
        assert site.rss_url == "https://techblog.com/feed"

    def test_html_site(self):
        """HTML 사이트 생성 테스트"""
        site = TargetSite(
            name="NewsSite",
            url="https://news.example.com",
            type="html",
            selector="article a:first-of-type",
        )
        assert site.type == "html"
        assert site.selector == "article a:first-of-type"
