"""설정 관리 모듈 - YAML + .env 기반 설정 로드 및 검증"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv


@dataclass
class GmailConfig:
    """Gmail 수집 설정"""

    credentials_path: str = "config/credentials.json"
    token_path: str = "config/token.json"
    allowed_senders: list[str] = field(default_factory=list)
    max_results: int = 10


@dataclass
class WebSource:
    """웹 수집 대상 사이트"""

    name: str = ""
    url: str = ""
    type: str = "rss"  # "rss" | "html"
    rss_url: str = ""
    selector: str = ""


@dataclass
class NotebookLMConfig:
    """NotebookLM 자동화 설정"""

    chrome_user_data_dir: str = "~/Library/Application Support/Google/Chrome"
    chrome_profile: str = "Default"
    timeout_seconds: int = 300
    retry_count: int = 2


@dataclass
class TelegramConfig:
    """텔레그램 봇 설정"""

    bot_token: str = ""
    channel_id: str = ""


@dataclass
class StorageConfig:
    """저장소 설정"""

    db_path: str = "data/lettercast.db"
    temp_audio_dir: str = "data/tmp"
    max_age_hours: int = 24


@dataclass
class Settings:
    """전체 애플리케이션 설정"""

    gmail: GmailConfig = field(default_factory=GmailConfig)
    web_sources: list[WebSource] = field(default_factory=list)
    notebooklm: NotebookLMConfig = field(default_factory=NotebookLMConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)

    @classmethod
    def load(
        cls,
        config_path: str = "config/settings.yaml",
        env_path: str = "config/.env",
    ) -> Settings:
        """설정 파일과 환경 변수를 로드하여 Settings 인스턴스를 생성합니다."""
        # .env 파일 로드
        env_file = Path(env_path)
        if env_file.exists():
            load_dotenv(env_file)

        # YAML 설정 파일 로드
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(
                f"설정 파일을 찾을 수 없습니다: {config_path}\n"
                f"config/settings.example.yaml을 복사하여 생성해 주세요."
            )

        with open(config_file, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        return cls._from_dict(raw)

    @classmethod
    def _from_dict(cls, raw: dict) -> Settings:
        """딕셔너리에서 Settings 인스턴스를 생성합니다."""
        gmail_raw = raw.get("gmail", {})
        gmail = GmailConfig(
            credentials_path=gmail_raw.get(
                "credentials_path", "config/credentials.json"
            ),
            token_path=gmail_raw.get("token_path", "config/token.json"),
            allowed_senders=gmail_raw.get("allowed_senders", []),
            max_results=gmail_raw.get("max_results", 10),
        )

        web_sources = [
            WebSource(
                name=ws.get("name", ""),
                url=ws.get("url", ""),
                type=ws.get("type", "rss"),
                rss_url=ws.get("rss_url", ""),
                selector=ws.get("selector", ""),
            )
            for ws in raw.get("web_sources", [])
        ]

        nlm_raw = raw.get("notebooklm", {})
        notebooklm = NotebookLMConfig(
            chrome_user_data_dir=nlm_raw.get(
                "chrome_user_data_dir",
                "~/Library/Application Support/Google/Chrome",
            ),
            chrome_profile=nlm_raw.get("chrome_profile", "Default"),
            timeout_seconds=nlm_raw.get("timeout_seconds", 300),
            retry_count=nlm_raw.get("retry_count", 2),
        )

        tg_raw = raw.get("telegram", {})
        telegram = TelegramConfig(
            bot_token=cls._resolve_env(tg_raw.get("bot_token", "")),
            channel_id=cls._resolve_env(tg_raw.get("channel_id", "")),
        )

        st_raw = raw.get("storage", {})
        storage = StorageConfig(
            db_path=st_raw.get("db_path", "data/lettercast.db"),
            temp_audio_dir=st_raw.get("temp_audio_dir", "data/tmp"),
            max_age_hours=st_raw.get("max_age_hours", 24),
        )

        return cls(
            gmail=gmail,
            web_sources=web_sources,
            notebooklm=notebooklm,
            telegram=telegram,
            storage=storage,
        )

    @staticmethod
    def _resolve_env(value: str) -> str:
        """${ENV_VAR} 형식의 값을 환경 변수로 치환합니다."""
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_key = value[2:-1]
            return os.getenv(env_key, "")
        return value

    def validate(self) -> list[str]:
        """설정 값의 유효성을 검사하고 경고 메시지 리스트를 반환합니다."""
        warnings = []

        if not self.gmail.allowed_senders:
            warnings.append("Gmail 허용 발신자 리스트가 비어 있습니다.")

        if not self.telegram.bot_token:
            warnings.append("텔레그램 봇 토큰이 설정되지 않았습니다.")

        if not self.telegram.channel_id:
            warnings.append("텔레그램 채널 ID가 설정되지 않았습니다.")

        credentials = Path(self.gmail.credentials_path)
        if not credentials.exists():
            warnings.append(
                f"Gmail 인증 파일을 찾을 수 없습니다: {self.gmail.credentials_path}"
            )

        chrome_dir = Path(self.notebooklm.chrome_user_data_dir).expanduser()
        if not chrome_dir.exists():
            warnings.append(
                f"크롬 User Data Directory를 찾을 수 없습니다: {chrome_dir}"
            )

        return warnings
