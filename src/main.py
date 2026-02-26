"""LetterCast Pro - 메인 오케스트레이터

Usage:
    poetry run python -m src.main           # 전체 파이프라인 실행
    poetry run python -m src.main --collect  # 수집만 실행
    poetry run python -m src.main --dry-run  # 변경 없이 시뮬레이션
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from src.automator.notebooklm import NotebookLMAutomator
from src.collector.gmail_collector import GmailCollector
from src.collector.web_collector import WebCollector
from src.config import Settings
from src.database.repository import URLRepository
from src.delivery.telegram import TelegramDelivery
from src.logger import get_logger, setup_logger
from src.models import CollectedItem, ProcessingStatus, TargetSite

logger = get_logger("main")


class LetterCastPipeline:
    """전체 파이프라인 오케스트레이터"""

    def __init__(self, settings: Settings, dry_run: bool = False) -> None:
        self.settings = settings
        self.dry_run = dry_run
        self.repo: URLRepository | None = None

    async def initialize(self) -> None:
        """리소스 초기화"""
        self.repo = URLRepository(self.settings.storage.db_path)
        await self.repo.initialize()

        # 임시 오디오 디렉토리 생성
        Path(self.settings.storage.temp_audio_dir).mkdir(parents=True, exist_ok=True)

    async def cleanup(self) -> None:
        """리소스 정리"""
        if self.repo:
            await self.repo.close()

    # ──────────────────────────────────────────────
    # Phase 1: 수집
    # ──────────────────────────────────────────────
    async def collect(self) -> list[CollectedItem]:
        """모든 소스에서 URL을 수집합니다."""
        logger.info("═══ Phase 1: 수집 시작 ═══")
        all_items: list[CollectedItem] = []

        # Gmail 수집
        try:
            gmail_collector = GmailCollector(
                credentials_path=self.settings.gmail.credentials_path,
                token_path=self.settings.gmail.token_path,
                allowed_senders=self.settings.gmail.allowed_senders,
                max_results=self.settings.gmail.max_results,
            )
            gmail_items = await gmail_collector.fetch_unread_urls()
            all_items.extend(gmail_items)
        except Exception as e:
            logger.error("Gmail 수집 실패: %s", e)

        # 웹 수집
        try:
            target_sites = [
                TargetSite(
                    name=ws.name,
                    url=ws.url,
                    type=ws.type,
                    rss_url=ws.rss_url,
                    selector=ws.selector,
                )
                for ws in self.settings.web_sources
            ]
            web_collector = WebCollector(target_sites=target_sites)
            web_items = await web_collector.fetch_latest_urls()
            all_items.extend(web_items)
        except Exception as e:
            logger.error("웹 수집 실패: %s", e)

        logger.info("수집 완료: 총 %d개 URL", len(all_items))
        return all_items

    # ──────────────────────────────────────────────
    # Phase 2: 필터링 (중복 제거)
    # ──────────────────────────────────────────────
    async def filter_and_save(
        self, items: list[CollectedItem]
    ) -> list[CollectedItem]:
        """중복을 제거하고 신규 URL만 DB에 저장합니다."""
        assert self.repo is not None

        logger.info("═══ Phase 2: 필터링 시작 ═══")
        new_items: list[CollectedItem] = []

        for item in items:
            if await self.repo.is_duplicate(item.url):
                logger.debug("중복 스킵: %s", item.url)
                continue

            if self.dry_run:
                logger.info("[DRY-RUN] 신규 URL: %s", item.url)
                new_items.append(item)
                continue

            item_id = await self.repo.save(item)
            item.id = item_id
            new_items.append(item)

        logger.info("필터링 완료: %d개 신규 / %d개 전체", len(new_items), len(items))
        return new_items

    # ──────────────────────────────────────────────
    # Phase 3: 오디오 생성
    # ──────────────────────────────────────────────
    async def generate_audio(self, items: list[CollectedItem]) -> list[CollectedItem]:
        """NotebookLM을 통해 오디오를 생성합니다."""
        assert self.repo is not None

        if not items:
            logger.info("생성할 항목이 없습니다.")
            return []

        if self.dry_run:
            logger.info("[DRY-RUN] %d개 URL 오디오 생성 건너뜀", len(items))
            return items

        logger.info("═══ Phase 3: 오디오 생성 시작 (%d건) ═══", len(items))

        automator = NotebookLMAutomator(
            chrome_user_data_dir=self.settings.notebooklm.chrome_user_data_dir,
            chrome_profile=self.settings.notebooklm.chrome_profile,
            timeout_seconds=self.settings.notebooklm.timeout_seconds,
            retry_count=self.settings.notebooklm.retry_count,
        )

        completed: list[CollectedItem] = []

        try:
            await automator.start_session()

            for i, item in enumerate(items, 1):
                logger.info("오디오 생성 (%d/%d): %s", i, len(items), item.title)

                if item.id:
                    await self.repo.update_status(item.id, ProcessingStatus.PROCESSING)

                try:
                    audio_path = await automator.process_url(
                        url=item.url,
                        title=item.title,
                        save_dir=self.settings.storage.temp_audio_dir,
                    )

                    if audio_path and item.id:
                        item.audio_path = str(audio_path)
                        await self.repo.update_status(
                            item.id,
                            ProcessingStatus.COMPLETED,
                            audio_path=str(audio_path),
                        )
                        completed.append(item)
                    elif item.id:
                        await self.repo.update_status(
                            item.id,
                            ProcessingStatus.FAILED,
                            error_msg="오디오 생성 실패",
                        )

                except Exception as e:
                    logger.error("오디오 생성 실패: %s - %s", item.url, e)
                    if item.id:
                        await self.repo.update_status(
                            item.id,
                            ProcessingStatus.FAILED,
                            error_msg=str(e),
                        )

        finally:
            await automator.close_session()

        logger.info("오디오 생성 완료: %d/%d 성공", len(completed), len(items))
        return completed

    # ──────────────────────────────────────────────
    # Phase 4: 전달
    # ──────────────────────────────────────────────
    async def deliver(self, items: list[CollectedItem]) -> int:
        """완료된 오디오를 텔레그램으로 전달합니다."""
        if not items:
            logger.info("전달할 항목이 없습니다.")
            return 0

        if self.dry_run:
            logger.info("[DRY-RUN] %d개 항목 전달 건너뜀", len(items))
            return len(items)

        logger.info("═══ Phase 4: 전달 시작 (%d건) ═══", len(items))

        delivery = TelegramDelivery(
            bot_token=self.settings.telegram.bot_token,
            channel_id=self.settings.telegram.channel_id,
        )

        success_count = 0
        for item in items:
            if not item.audio_path:
                continue

            audio_path = Path(item.audio_path)
            success = await delivery.send_audio(
                file_path=audio_path,
                title=item.title,
                source_url=item.url,
            )

            if success:
                success_count += 1
                # 전송 완료 후 임시 파일 삭제
                try:
                    audio_path.unlink(missing_ok=True)
                except Exception:
                    pass

        logger.info("전달 완료: %d/%d 성공", success_count, len(items))
        return success_count

    # ──────────────────────────────────────────────
    # 전체 파이프라인
    # ──────────────────────────────────────────────
    async def run(self, collect_only: bool = False) -> None:
        """전체 파이프라인을 실행합니다."""
        logger.info("╔══════════════════════════════════════╗")
        logger.info("║   LetterCast Pro 파이프라인 시작     ║")
        logger.info("╚══════════════════════════════════════╝")

        try:
            await self.initialize()

            # Phase 1: 수집
            collected = await self.collect()
            if not collected:
                logger.info("수집된 URL이 없습니다. 종료합니다.")
                return

            # Phase 2: 필터링
            new_items = await self.filter_and_save(collected)
            if not new_items:
                logger.info("신규 URL이 없습니다. 종료합니다.")
                return

            if collect_only:
                logger.info("수집 모드: %d개 신규 URL 저장 완료", len(new_items))
                return

            # Phase 3: 오디오 생성
            completed = await self.generate_audio(new_items)

            # Phase 4: 전달
            await self.deliver(completed)

            logger.info("╔══════════════════════════════════════╗")
            logger.info("║   LetterCast Pro 파이프라인 완료     ║")
            logger.info("╚══════════════════════════════════════╝")

        except KeyboardInterrupt:
            logger.info("사용자에 의해 중단되었습니다.")
        except Exception as e:
            logger.error("파이프라인 오류: %s", e, exc_info=True)
        finally:
            await self.cleanup()


def parse_args() -> argparse.Namespace:
    """CLI 인자를 파싱합니다."""
    parser = argparse.ArgumentParser(
        description="LetterCast Pro - 개인용 멀티 채널 팟캐스트 자동화",
    )
    parser.add_argument(
        "--config",
        default="config/settings.yaml",
        help="설정 파일 경로 (기본: config/settings.yaml)",
    )
    parser.add_argument(
        "--env",
        default="config/.env",
        help="환경 변수 파일 경로 (기본: config/.env)",
    )
    parser.add_argument(
        "--collect",
        action="store_true",
        help="수집만 실행 (오디오 생성/전달 건너뜀)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="변경 없이 시뮬레이션 실행",
    )
    return parser.parse_args()


async def main() -> None:
    """메인 엔트리포인트"""
    args = parse_args()

    # 설정 로드
    settings = Settings.load(config_path=args.config, env_path=args.env)

    # 로거 설정
    import os

    log_level = os.getenv("LOG_LEVEL", "INFO")
    setup_logger(level=log_level, log_dir="data/logs")

    # 설정 검증
    warnings = settings.validate()
    for w in warnings:
        logger.warning("설정 경고: %s", w)

    # 파이프라인 실행
    pipeline = LetterCastPipeline(settings=settings, dry_run=args.dry_run)
    await pipeline.run(collect_only=args.collect)


if __name__ == "__main__":
    asyncio.run(main())
