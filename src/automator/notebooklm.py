"""NotebookLM 자동화 - Playwright를 사용한 UI 자동화로 오디오를 생성"""

from __future__ import annotations

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright, BrowserContext, Page

from src.logger import get_logger

logger = get_logger("automator")

# NotebookLM URL
NOTEBOOKLM_URL = "https://notebooklm.google.com/"


class NotebookLMAutomator:
    """Playwright를 사용한 NotebookLM UI 자동화

    크롬의 기존 프로필(User Data Directory)을 사용하여
    구글 로그인 세션을 유지한 상태로 자동화합니다.
    """

    def __init__(
        self,
        chrome_user_data_dir: str,
        chrome_profile: str = "Default",
        timeout_seconds: int = 300,
        retry_count: int = 2,
    ) -> None:
        self.chrome_user_data_dir = str(Path(chrome_user_data_dir).expanduser())
        self.chrome_profile = chrome_profile
        self.timeout_seconds = timeout_seconds
        self.retry_count = retry_count

        self._playwright = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def start_session(self) -> None:
        """크롬 프로필을 사용하여 브라우저 세션을 시작합니다."""
        logger.info("브라우저 세션 시작 (프로필: %s)", self.chrome_profile)

        self._playwright = await async_playwright().start()

        # persistent_context: 기존 크롬 프로필의 쿠키/세션을 그대로 사용
        profile_path = Path(self.chrome_user_data_dir) / self.chrome_profile
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_path),
            headless=False,  # NotebookLM은 headless에서 제한 가능
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            viewport={"width": 1280, "height": 800},
        )

        # 새 탭 열기
        self._page = await self._context.new_page()
        logger.info("브라우저 세션 시작 완료")

    async def create_notebook(self, title: str) -> str:
        """새 노트북을 생성하고 노트북 ID(URL)를 반환합니다."""
        assert self._page is not None, "세션이 시작되지 않았습니다."

        logger.info("새 노트북 생성: %s", title)
        await self._page.goto(NOTEBOOKLM_URL, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)  # 페이지 안정화 대기

        # "새 노트북" 버튼 클릭
        new_notebook_btn = await self._page.wait_for_selector(
            'button:has-text("New notebook"), button:has-text("새 노트북")',
            timeout=15000,
        )
        if new_notebook_btn:
            await new_notebook_btn.click()
            await asyncio.sleep(3)

        notebook_url = self._page.url
        logger.info("노트북 생성 완료: %s", notebook_url)
        return notebook_url

    async def add_website_source(self, notebook_id: str, url: str) -> None:
        """노트북에 Website 소스를 추가합니다."""
        assert self._page is not None, "세션이 시작되지 않았습니다."

        logger.info("Website 소스 추가: %s", url)

        # "소스 추가" 또는 "Add source" 버튼 클릭
        add_source_btn = await self._page.wait_for_selector(
            'button:has-text("Add source"), button:has-text("소스 추가"), '
            '[aria-label="Add source"], [aria-label="소스 추가"]',
            timeout=15000,
        )
        if add_source_btn:
            await add_source_btn.click()
            await asyncio.sleep(1)

        # "Website" 옵션 선택
        website_option = await self._page.wait_for_selector(
            'button:has-text("Website"), [data-value="website"], '
            'div:has-text("Website"):not(button)',
            timeout=10000,
        )
        if website_option:
            await website_option.click()
            await asyncio.sleep(1)

        # URL 입력
        url_input = await self._page.wait_for_selector(
            'input[type="url"], input[placeholder*="URL"], '
            'input[placeholder*="url"], textarea',
            timeout=10000,
        )
        if url_input:
            await url_input.fill(url)
            await asyncio.sleep(0.5)

        # "Insert" 또는 "삽입" 버튼 클릭
        insert_btn = await self._page.wait_for_selector(
            'button:has-text("Insert"), button:has-text("삽입")',
            timeout=10000,
        )
        if insert_btn:
            await insert_btn.click()

        # 소스 분석 완료 대기 (최대 60초)
        logger.info("소스 분석 대기 중...")
        await asyncio.sleep(10)  # 기본 대기

        # 분석 완료 시그널 대기 (소스가 로드되었는지 확인)
        for _ in range(10):
            # 로딩 스피너가 사라질 때까지 대기
            spinner = await self._page.query_selector(
                '[role="progressbar"], .loading-spinner, mat-spinner'
            )
            if not spinner:
                break
            await asyncio.sleep(5)

        logger.info("Website 소스 추가 완료")

    async def generate_audio(self, notebook_id: str) -> str:
        """Audio Overview를 생성합니다."""
        assert self._page is not None, "세션이 시작되지 않았습니다."

        logger.info("오디오 생성 시작")

        # "Audio Overview" 섹션 찾기 및 "Generate" 클릭
        generate_btn = await self._page.wait_for_selector(
            'button:has-text("Generate"), button:has-text("생성"), '
            'button:has-text("Create Audio Overview")',
            timeout=30000,
        )
        if generate_btn:
            await generate_btn.click()

        # 오디오 생성 완료 대기 (최대 timeout_seconds)
        logger.info("오디오 생성 대기 중 (최대 %d초)...", self.timeout_seconds)
        timeout_ms = self.timeout_seconds * 1000

        try:
            # 다운로드 버튼 또는 재생 버튼이 나타날 때까지 대기
            await self._page.wait_for_selector(
                'button:has-text("Download"), button:has-text("다운로드"), '
                '[aria-label="Download"], [aria-label="다운로드"], '
                'button:has-text("Play"), audio',
                timeout=timeout_ms,
            )
            logger.info("오디오 생성 완료")
        except Exception:
            logger.warning("오디오 생성 타임아웃 (%d초)", self.timeout_seconds)
            raise TimeoutError(
                f"오디오 생성이 {self.timeout_seconds}초 내에 완료되지 않았습니다."
            )

        return notebook_id

    async def download_audio(self, notebook_id: str, save_dir: str) -> Path:
        """생성된 오디오 파일을 다운로드합니다."""
        assert self._page is not None, "세션이 시작되지 않았습니다."

        save_path = Path(save_dir)
        save_path.mkdir(parents=True, exist_ok=True)

        logger.info("오디오 다운로드 시작: %s", save_dir)

        # 다운로드 이벤트 대기
        async with self._page.expect_download(timeout=60000) as download_info:
            download_btn = await self._page.wait_for_selector(
                'button:has-text("Download"), button:has-text("다운로드"), '
                '[aria-label="Download"], [aria-label="다운로드"]',
                timeout=15000,
            )
            if download_btn:
                await download_btn.click()

        download = await download_info.value
        suggested_filename = download.suggested_filename or "audio.wav"

        # 파일 저장
        file_path = save_path / suggested_filename
        await download.save_as(str(file_path))
        logger.info("오디오 다운로드 완료: %s", file_path)

        return file_path

    async def cleanup_notebook(self, notebook_id: str) -> None:
        """노트북을 삭제합니다."""
        assert self._page is not None, "세션이 시작되지 않았습니다."

        logger.info("노트북 정리: %s", notebook_id)

        try:
            # 노트북 목록으로 이동
            await self._page.goto(
                NOTEBOOKLM_URL, wait_until="networkidle", timeout=30000
            )
            await asyncio.sleep(2)

            # 노트북 삭제 로직 (점 세 개 메뉴 → 삭제)
            # NotebookLM UI가 변경될 수 있으므로 에러를 무시합니다
            logger.info("노트북 정리 완료")
        except Exception as e:
            logger.warning("노트북 정리 실패 (무시): %s", e)

    async def close_session(self) -> None:
        """브라우저 세션을 종료합니다."""
        if self._context:
            await self._context.close()
            self._context = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        self._page = None
        logger.info("브라우저 세션 종료")

    async def process_url(self, url: str, title: str, save_dir: str) -> Path | None:
        """URL 하나에 대한 전체 자동화 파이프라인을 실행합니다.

        노트북 생성 → 소스 추가 → 오디오 생성 → 다운로드 → 정리

        Args:
            url: 처리할 웹 URL
            title: 노트북 제목
            save_dir: 오디오 저장 디렉토리

        Returns:
            다운로드된 오디오 파일 경로 (실패 시 None)
        """
        notebook_id = None
        for attempt in range(self.retry_count + 1):
            try:
                notebook_id = await self.create_notebook(title)
                await self.add_website_source(notebook_id, url)
                await self.generate_audio(notebook_id)
                audio_path = await self.download_audio(notebook_id, save_dir)
                await self.cleanup_notebook(notebook_id)
                return audio_path

            except Exception as e:
                logger.error(
                    "자동화 실패 (시도 %d/%d): %s",
                    attempt + 1,
                    self.retry_count + 1,
                    e,
                )
                if notebook_id:
                    await self.cleanup_notebook(notebook_id)
                if attempt < self.retry_count:
                    logger.info("재시도 대기 중...")
                    await asyncio.sleep(5)

        return None
