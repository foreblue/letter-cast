"""웹 수집기 - RSS 피드 및 HTML 파싱을 통한 최신 게시글 URL 추출"""

from __future__ import annotations

from datetime import datetime

import feedparser
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from src.logger import get_logger
from src.models import CollectedItem, SourceType, TargetSite

logger = get_logger("collector.web")


class WebCollector:
    """대상 웹사이트에서 최신 게시글 URL을 수집합니다."""

    def __init__(self, target_sites: list[TargetSite] | None = None) -> None:
        self.target_sites = target_sites or []

    async def fetch_latest_urls(self) -> list[CollectedItem]:
        """모든 대상 사이트에서 최신 URL을 수집합니다."""
        items: list[CollectedItem] = []

        for site in self.target_sites:
            try:
                if site.type == "rss":
                    site_items = await self._fetch_from_rss(site)
                else:
                    site_items = await self._fetch_from_html(site)
                items.extend(site_items)
                logger.info("%s에서 %d개 URL 수집", site.name, len(site_items))
            except Exception as e:
                logger.error("%s 수집 실패: %s", site.name, e)

        logger.info("웹 총 %d개 URL 수집 완료", len(items))
        return items

    async def _fetch_from_rss(self, site: TargetSite) -> list[CollectedItem]:
        """RSS 피드에서 최신 게시글을 수집합니다."""
        rss_url = site.rss_url or site.url
        feed = feedparser.parse(rss_url)

        if feed.bozo and not feed.entries:
            logger.warning("%s: RSS 파싱 실패 - %s", site.name, feed.bozo_exception)
            return []

        items = []
        # 최신 게시글 1건만 수집
        for entry in feed.entries[:1]:
            url = entry.get("link", "")
            title = entry.get("title", "제목 없음")

            if url:
                items.append(
                    CollectedItem(
                        url=url,
                        title=title,
                        source=SourceType.WEB,
                        source_name=site.name,
                        collected_at=datetime.now(),
                    )
                )

        return items

    async def _fetch_from_html(self, site: TargetSite) -> list[CollectedItem]:
        """Playwright로 HTML 페이지에서 최신 게시글 링크를 추출합니다."""
        if not site.selector:
            logger.warning("%s: CSS 선택자가 설정되지 않았습니다.", site.name)
            return []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                await page.goto(site.url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_selector(site.selector, timeout=10000)

                # 선택자로 첫 번째 링크 추출
                element = await page.query_selector(site.selector)
                if not element:
                    logger.warning("%s: 선택자에 매칭되는 요소 없음", site.name)
                    return []

                href = await element.get_attribute("href")
                title = (await element.inner_text()).strip() or "제목 없음"

                if not href:
                    logger.warning("%s: href 속성이 없습니다.", site.name)
                    return []

                # 상대 URL → 절대 URL 변환
                if href.startswith("/"):
                    from urllib.parse import urljoin

                    href = urljoin(site.url, href)

                return [
                    CollectedItem(
                        url=href,
                        title=title,
                        source=SourceType.WEB,
                        source_name=site.name,
                        collected_at=datetime.now(),
                    )
                ]

            except Exception as e:
                logger.error("%s 페이지 로드 실패: %s", site.name, e)
                return []
            finally:
                await browser.close()
