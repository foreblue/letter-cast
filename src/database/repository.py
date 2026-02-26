"""URL 저장소 - aiosqlite 기반 비동기 CRUD 및 중복 체크"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from pathlib import Path

import aiosqlite

from src.logger import get_logger
from src.models import CollectedItem, ProcessingStatus, SourceType

logger = get_logger("database")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS processed_urls (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    url          TEXT NOT NULL UNIQUE,
    url_hash     TEXT NOT NULL UNIQUE,
    title        TEXT,
    source       TEXT NOT NULL,
    source_name  TEXT,
    status       TEXT DEFAULT 'pending',
    error_msg    TEXT,
    audio_path   TEXT,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_url_hash ON processed_urls(url_hash);
CREATE INDEX IF NOT EXISTS idx_status ON processed_urls(status);
"""


class URLRepository:
    """URL 저장소 - 중복 체크 및 상태 관리"""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """데이터베이스 연결 및 테이블 생성"""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(CREATE_TABLE_SQL)
        await self._db.commit()
        logger.info("데이터베이스 초기화 완료: %s", self.db_path)

    async def close(self) -> None:
        """데이터베이스 연결 종료"""
        if self._db:
            await self._db.close()
            self._db = None

    @staticmethod
    def _hash_url(url: str) -> str:
        """URL의 SHA-256 해시를 생성합니다."""
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    async def is_duplicate(self, url: str) -> bool:
        """URL이 이미 DB에 존재하는지 확인합니다."""
        assert self._db is not None, "DB가 초기화되지 않았습니다."
        url_hash = self._hash_url(url)
        cursor = await self._db.execute(
            "SELECT 1 FROM processed_urls WHERE url_hash = ?",
            (url_hash,),
        )
        row = await cursor.fetchone()
        return row is not None

    async def save(self, item: CollectedItem) -> int:
        """수집된 항목을 DB에 저장하고 ID를 반환합니다."""
        assert self._db is not None, "DB가 초기화되지 않았습니다."
        url_hash = self._hash_url(item.url)
        cursor = await self._db.execute(
            """
            INSERT INTO processed_urls (url, url_hash, title, source, source_name, status, collected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.url,
                url_hash,
                item.title,
                item.source.value,
                item.source_name,
                item.status.value,
                item.collected_at.isoformat(),
            ),
        )
        await self._db.commit()
        item_id = cursor.lastrowid
        logger.info("URL 저장 완료 (id=%d): %s", item_id, item.url)
        return item_id

    async def update_status(
        self,
        url_id: int,
        status: ProcessingStatus,
        error_msg: str | None = None,
        audio_path: str | None = None,
    ) -> None:
        """URL의 처리 상태를 업데이트합니다."""
        assert self._db is not None, "DB가 초기화되지 않았습니다."
        completed_at = (
            datetime.now().isoformat()
            if status == ProcessingStatus.COMPLETED
            else None
        )
        await self._db.execute(
            """
            UPDATE processed_urls
            SET status = ?, error_msg = ?, audio_path = ?, completed_at = ?
            WHERE id = ?
            """,
            (status.value, error_msg, audio_path, completed_at, url_id),
        )
        await self._db.commit()
        logger.info("상태 업데이트 (id=%d): %s", url_id, status.value)

    async def get_pending(self) -> list[CollectedItem]:
        """PENDING 상태의 모든 항목을 반환합니다."""
        assert self._db is not None, "DB가 초기화되지 않았습니다."
        cursor = await self._db.execute(
            "SELECT * FROM processed_urls WHERE status = ? ORDER BY collected_at",
            (ProcessingStatus.PENDING.value,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_item(row) for row in rows]

    async def get_completed_without_delivery(self) -> list[CollectedItem]:
        """COMPLETED 상태이지만 아직 전달되지 않은 항목을 반환합니다."""
        assert self._db is not None, "DB가 초기화되지 않았습니다."
        cursor = await self._db.execute(
            "SELECT * FROM processed_urls WHERE status = ? AND audio_path IS NOT NULL ORDER BY collected_at",
            (ProcessingStatus.COMPLETED.value,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_item(row) for row in rows]

    async def get_recent_count(self, hours: int = 24) -> int:
        """최근 N시간 이내에 수집된 항목 수를 반환합니다."""
        assert self._db is not None, "DB가 초기화되지 않았습니다."
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM processed_urls WHERE collected_at >= ?",
            (since,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    @staticmethod
    def _row_to_item(row: aiosqlite.Row) -> CollectedItem:
        """DB 행을 CollectedItem으로 변환합니다."""
        return CollectedItem(
            id=row["id"],
            url=row["url"],
            title=row["title"] or "",
            source=SourceType(row["source"]),
            source_name=row["source_name"] or "",
            status=ProcessingStatus(row["status"]),
            error_msg=row["error_msg"],
            audio_path=row["audio_path"],
            collected_at=datetime.fromisoformat(row["collected_at"]),
        )
