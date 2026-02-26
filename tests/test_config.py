"""Settings 설정 로드 테스트"""

import pytest
import yaml

from src.config import (
    GmailConfig,
    NotebookLMConfig,
    Settings,
    StorageConfig,
    TelegramConfig,
    WebSource,
)


@pytest.fixture
def sample_config(tmp_path):
    """테스트용 설정 파일 생성"""
    config = {
        "gmail": {
            "credentials_path": "config/credentials.json",
            "token_path": "config/token.json",
            "allowed_senders": ["test@example.com"],
            "max_results": 5,
        },
        "web_sources": [
            {
                "name": "TestBlog",
                "url": "https://test.com",
                "type": "rss",
                "rss_url": "https://test.com/feed",
            }
        ],
        "notebooklm": {
            "chrome_user_data_dir": "/tmp/chrome",
            "chrome_profile": "Test",
            "timeout_seconds": 60,
            "retry_count": 1,
        },
        "telegram": {
            "bot_token": "test-token",
            "channel_id": "-100123456",
        },
        "storage": {
            "db_path": "data/test.db",
            "temp_audio_dir": "data/tmp",
            "max_age_hours": 12,
        },
    }
    config_path = tmp_path / "settings.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)
    return config_path


class TestSettings:
    """Settings 클래스 테스트"""

    def test_load_from_yaml(self, sample_config):
        """YAML 파일에서 설정 로드 테스트"""
        settings = Settings.load(config_path=str(sample_config), env_path="/nonexistent")

        assert settings.gmail.max_results == 5
        assert settings.gmail.allowed_senders == ["test@example.com"]
        assert len(settings.web_sources) == 1
        assert settings.web_sources[0].name == "TestBlog"
        assert settings.notebooklm.timeout_seconds == 60
        assert settings.storage.max_age_hours == 12

    def test_missing_config_file(self):
        """존재하지 않는 설정 파일 로드 시 에러 테스트"""
        with pytest.raises(FileNotFoundError):
            Settings.load(config_path="/nonexistent/settings.yaml")

    def test_env_resolution(self, monkeypatch):
        """환경 변수 치환 테스트"""
        monkeypatch.setenv("TEST_TOKEN", "resolved-token")
        result = Settings._resolve_env("${TEST_TOKEN}")
        assert result == "resolved-token"

    def test_env_resolution_missing(self):
        """존재하지 않는 환경 변수 치환 테스트"""
        result = Settings._resolve_env("${NONEXISTENT_VAR}")
        assert result == ""

    def test_env_resolution_plain_string(self):
        """일반 문자열은 치환하지 않음 테스트"""
        result = Settings._resolve_env("plain-value")
        assert result == "plain-value"

    def test_validate_warnings(self, sample_config):
        """설정 검증 경고 테스트"""
        settings = Settings.load(config_path=str(sample_config), env_path="/nonexistent")
        warnings = settings.validate()
        # credentials 파일이 없으므로 경고 발생
        assert any("Gmail 인증 파일" in w for w in warnings)

    def test_empty_config(self, tmp_path):
        """빈 설정 파일 로드 테스트"""
        config_path = tmp_path / "empty.yaml"
        config_path.write_text("")

        settings = Settings.load(config_path=str(config_path), env_path="/nonexistent")
        assert isinstance(settings.gmail, GmailConfig)
        assert isinstance(settings.telegram, TelegramConfig)
        assert isinstance(settings.storage, StorageConfig)


class TestWebSource:
    """WebSource 데이터 클래스 테스트"""

    def test_default_type(self):
        """기본 타입은 rss"""
        ws = WebSource(name="Test", url="https://test.com")
        assert ws.type == "rss"
