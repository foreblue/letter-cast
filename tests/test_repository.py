"""URLRepository 테스트 - 인메모리 SQLite 사용"""

import pytest

from src.database.repository import URLRepository
from src.models import CollectedItem, ProcessingStatus, SourceType


@pytest.fixture
async def repo(tmp_path):
    """테스트용 인메모리 DB repository"""
    db_path = str(tmp_path / "test.db")
    repository = URLRepository(db_path)
    await repository.initialize()
    yield repository
    await repository.close()


class TestURLRepository:
    """URLRepository 테스트"""

    @pytest.mark.asyncio
    async def test_save_and_get_pending(self, repo):
        """저장 후 PENDING 항목 조회 테스트"""
        item = CollectedItem(
            url="https://example.com/article1",
            title="테스트 기사 1",
            source=SourceType.WEB,
            source_name="TestBlog",
        )
        item_id = await repo.save(item)
        assert item_id > 0

        pending = await repo.get_pending()
        assert len(pending) == 1
        assert pending[0].url == "https://example.com/article1"
        assert pending[0].status == ProcessingStatus.PENDING

    @pytest.mark.asyncio
    async def test_duplicate_check(self, repo):
        """중복 URL 체크 테스트"""
        item = CollectedItem(
            url="https://example.com/article1",
            title="테스트 기사",
            source=SourceType.GMAIL,
        )
        await repo.save(item)

        assert await repo.is_duplicate("https://example.com/article1") is True
        assert await repo.is_duplicate("https://example.com/article2") is False

    @pytest.mark.asyncio
    async def test_update_status(self, repo):
        """상태 업데이트 테스트"""
        item = CollectedItem(
            url="https://example.com/article1",
            title="테스트 기사",
            source=SourceType.WEB,
        )
        item_id = await repo.save(item)

        # PENDING → PROCESSING
        await repo.update_status(item_id, ProcessingStatus.PROCESSING)
        pending = await repo.get_pending()
        assert len(pending) == 0  # 더 이상 PENDING이 아님

        # PROCESSING → COMPLETED
        await repo.update_status(
            item_id,
            ProcessingStatus.COMPLETED,
            audio_path="/tmp/audio.mp3",
        )

    @pytest.mark.asyncio
    async def test_update_status_failed(self, repo):
        """실패 상태 업데이트 테스트"""
        item = CollectedItem(
            url="https://example.com/fail",
            title="실패 테스트",
            source=SourceType.WEB,
        )
        item_id = await repo.save(item)

        await repo.update_status(
            item_id,
            ProcessingStatus.FAILED,
            error_msg="타임아웃 발생",
        )
        pending = await repo.get_pending()
        assert len(pending) == 0

    @pytest.mark.asyncio
    async def test_duplicate_url_rejected(self, repo):
        """동일 URL 중복 저장 거부 테스트"""
        item = CollectedItem(
            url="https://example.com/same-url",
            title="원본",
            source=SourceType.WEB,
        )
        await repo.save(item)

        # 동일 URL 재저장 시 에러
        with pytest.raises(Exception):
            await repo.save(item)

    @pytest.mark.asyncio
    async def test_multiple_items(self, repo):
        """다수 항목 저장 및 조회 테스트"""
        for i in range(5):
            item = CollectedItem(
                url=f"https://example.com/article{i}",
                title=f"기사 {i}",
                source=SourceType.WEB,
            )
            await repo.save(item)

        pending = await repo.get_pending()
        assert len(pending) == 5

    @pytest.mark.asyncio
    async def test_recent_count(self, repo):
        """최근 수집 항목 수 조회 테스트"""
        for i in range(3):
            item = CollectedItem(
                url=f"https://example.com/recent{i}",
                title=f"최근 기사 {i}",
                source=SourceType.GMAIL,
            )
            await repo.save(item)

        count = await repo.get_recent_count(hours=24)
        assert count == 3
