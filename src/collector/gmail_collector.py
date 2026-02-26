"""Gmail 수집기 - Gmail API를 사용하여 뉴스레터에서 URL을 추출"""

from __future__ import annotations

import base64
import re
from datetime import datetime

from bs4 import BeautifulSoup
from googleapiclient.discovery import build

from src.collector.gmail_auth import authenticate
from src.logger import get_logger
from src.models import CollectedItem, SourceType

logger = get_logger("collector.gmail")

# URL 추출 정규표현식 (mailto, unsubscribe 등 제외)
URL_PATTERN = re.compile(
    r'https?://(?!.*(?:unsubscribe|mailto|manage|preferences|opt-out))'
    r'[^\s<>"\')\]]+',
    re.IGNORECASE,
)

# 제외할 URL 패턴
EXCLUDED_DOMAINS = {
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "www.w3.org",
    "schemas.microsoft.com",
    "aka.ms",
}


class GmailCollector:
    """Gmail에서 뉴스레터 URL을 수집합니다."""

    def __init__(
        self,
        credentials_path: str = "config/credentials.json",
        token_path: str = "config/token.json",
        allowed_senders: list[str] | None = None,
        max_results: int = 10,
    ) -> None:
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.allowed_senders = allowed_senders or []
        self.max_results = max_results
        self._service = None

    async def _get_service(self):
        """Gmail API 서비스를 초기화합니다."""
        if self._service is None:
            creds = authenticate(self.credentials_path, self.token_path)
            self._service = build("gmail", "v1", credentials=creds)
        return self._service

    async def fetch_unread_urls(self) -> list[CollectedItem]:
        """모든 허용된 발신자의 읽지 않은 메일에서 URL을 추출합니다."""
        items: list[CollectedItem] = []

        for sender in self.allowed_senders:
            try:
                sender_items = await self._fetch_from_sender(sender)
                items.extend(sender_items)
                logger.info("%s로부터 %d개 URL 수집", sender, len(sender_items))
            except Exception as e:
                logger.error("%s 수집 실패: %s", sender, e)

        logger.info("Gmail 총 %d개 URL 수집 완료", len(items))
        return items

    async def _fetch_from_sender(self, sender: str) -> list[CollectedItem]:
        """특정 발신자의 읽지 않은 메일에서 URL을 추출합니다."""
        service = await self._get_service()
        query = f"from:{sender} is:unread"

        results = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=self.max_results)
            .execute()
        )

        messages = results.get("messages", [])
        if not messages:
            logger.debug("%s: 읽지 않은 메일 없음", sender)
            return []

        items = []
        for msg_ref in messages:
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=msg_ref["id"], format="full")
                .execute()
            )

            subject = self._get_header(msg, "Subject") or "제목 없음"
            body_html = self._get_body(msg)
            urls = self._extract_urls(body_html)

            for url in urls:
                items.append(
                    CollectedItem(
                        url=url,
                        title=subject,
                        source=SourceType.GMAIL,
                        source_name=sender,
                        collected_at=datetime.now(),
                    )
                )

        return items

    async def mark_as_read(self, message_id: str) -> None:
        """메일을 읽음으로 표시합니다."""
        service = await self._get_service()
        service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"removeLabelIds": ["UNREAD"]},
        ).execute()
        logger.debug("메일 읽음 처리: %s", message_id)

    @staticmethod
    def _get_header(msg: dict, name: str) -> str | None:
        """메일 헤더에서 특정 값을 추출합니다."""
        headers = msg.get("payload", {}).get("headers", [])
        for header in headers:
            if header["name"].lower() == name.lower():
                return header["value"]
        return None

    @staticmethod
    def _get_body(msg: dict) -> str:
        """메일 본문 HTML을 추출합니다."""
        payload = msg.get("payload", {})

        # 단순 메일 (본문이 바로 있는 경우)
        body_data = payload.get("body", {}).get("data")
        if body_data:
            return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="ignore")

        # 멀티파트 메일
        parts = payload.get("parts", [])
        for part in parts:
            mime_type = part.get("mimeType", "")
            if mime_type == "text/html":
                data = part.get("body", {}).get("data", "")
                if data:
                    return base64.urlsafe_b64decode(data).decode(
                        "utf-8", errors="ignore"
                    )

            # 중첩 멀티파트 처리
            sub_parts = part.get("parts", [])
            for sub in sub_parts:
                if sub.get("mimeType") == "text/html":
                    data = sub.get("body", {}).get("data", "")
                    if data:
                        return base64.urlsafe_b64decode(data).decode(
                            "utf-8", errors="ignore"
                        )

        return ""

    @staticmethod
    def _extract_urls(html: str) -> list[str]:
        """HTML 본문에서 의미 있는 URL을 추출합니다."""
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        urls: list[str] = []
        seen: set[str] = set()

        # <a> 태그의 href에서 추출
        for link in soup.find_all("a", href=True):
            url = link["href"].strip()
            if not url.startswith("http"):
                continue
            # 제외 도메인 필터링
            if any(domain in url for domain in EXCLUDED_DOMAINS):
                continue
            # URL 정리 (트래킹 파라미터 등은 유지 - 원본 보존)
            if url not in seen:
                seen.add(url)
                urls.append(url)

        # 본문 텍스트에서 추가 URL 탐색
        text = soup.get_text()
        for match in URL_PATTERN.finditer(text):
            url = match.group(0).rstrip(".,;:!?)")
            if url not in seen:
                if not any(domain in url for domain in EXCLUDED_DOMAINS):
                    seen.add(url)
                    urls.append(url)

        return urls
