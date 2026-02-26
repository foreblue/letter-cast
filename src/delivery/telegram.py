"""텔레그램 전달 모듈 - 오디오 파일 및 메타데이터 전송"""

from __future__ import annotations

import asyncio
from pathlib import Path

from telegram import Bot
from telegram.error import RetryAfter, TelegramError

from src.logger import get_logger

logger = get_logger("delivery")


class TelegramDelivery:
    """텔레그램 채널로 오디오 파일을 전송합니다."""

    def __init__(
        self,
        bot_token: str,
        channel_id: str,
        max_retries: int = 3,
    ) -> None:
        self.bot_token = bot_token
        self.channel_id = channel_id
        self.max_retries = max_retries
        self._bot: Bot | None = None

    def _get_bot(self) -> Bot:
        """Bot 인스턴스를 반환합니다."""
        if self._bot is None:
            self._bot = Bot(token=self.bot_token)
        return self._bot

    async def send_audio(
        self,
        file_path: Path,
        title: str,
        source_url: str,
    ) -> bool:
        """오디오 파일을 텔레그램 채널로 전송합니다.

        Args:
            file_path: 오디오 파일 경로
            title: 오디오 제목
            source_url: 원문 URL

        Returns:
            전송 성공 여부
        """
        if not file_path.exists():
            logger.error("오디오 파일을 찾을 수 없습니다: %s", file_path)
            return False

        bot = self._get_bot()
        caption = f"🎧 {title}\n\n📎 원문: {source_url}"

        for attempt in range(self.max_retries):
            try:
                with open(file_path, "rb") as audio_file:
                    await bot.send_audio(
                        chat_id=self.channel_id,
                        audio=audio_file,
                        caption=caption,
                        title=title,
                        read_timeout=60,
                        write_timeout=60,
                    )
                logger.info("텔레그램 전송 완료: %s", title)
                return True

            except RetryAfter as e:
                wait_time = e.retry_after
                logger.warning(
                    "텔레그램 rate limit, %d초 대기 (시도 %d/%d)",
                    wait_time,
                    attempt + 1,
                    self.max_retries,
                )
                await asyncio.sleep(wait_time)

            except TelegramError as e:
                logger.error(
                    "텔레그램 전송 실패 (시도 %d/%d): %s",
                    attempt + 1,
                    self.max_retries,
                    e,
                )
                if attempt < self.max_retries - 1:
                    # 지수 백오프
                    wait_time = 2 ** (attempt + 1)
                    await asyncio.sleep(wait_time)

        logger.error("텔레그램 전송 최종 실패: %s", title)
        return False

    async def send_message(self, text: str) -> bool:
        """텍스트 메시지를 텔레그램 채널로 전송합니다."""
        bot = self._get_bot()
        try:
            await bot.send_message(
                chat_id=self.channel_id,
                text=text,
                parse_mode="HTML",
            )
            return True
        except TelegramError as e:
            logger.error("메시지 전송 실패: %s", e)
            return False

    async def verify_connection(self) -> bool:
        """텔레그램 봇 연결을 확인합니다."""
        try:
            bot = self._get_bot()
            me = await bot.get_me()
            logger.info("텔레그램 봇 연결 확인: @%s", me.username)
            return True
        except TelegramError as e:
            logger.error("텔레그램 봇 연결 실패: %s", e)
            return False
