"""환경 설정 검증 스크립트

Usage:
    poetry run python -m src.check_setup
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path


def check_python_version() -> bool:
    """Python 버전 확인"""
    version = sys.version_info
    ok = version >= (3, 11)
    status = "✅" if ok else "❌"
    print(f"{status} Python {version.major}.{version.minor}.{version.micro} ... {'OK' if ok else 'Python 3.11+ 필요'}")
    return ok


def check_gmail_credentials(config_path: str) -> bool:
    """Gmail 인증 파일 확인"""
    exists = Path(config_path).exists()
    status = "✅" if exists else "⚠️"
    msg = "OK" if exists else f"파일 없음 ({config_path})"
    print(f"{status} Gmail credentials ... {msg}")
    return exists


def check_gmail_token(token_path: str) -> bool:
    """Gmail 토큰 파일 확인"""
    exists = Path(token_path).exists()
    status = "✅" if exists else "⚠️"
    msg = "OK" if exists else f"최초 인증 필요 (poetry run python -m src.collector.gmail_auth)"
    print(f"{status} Gmail token ... {msg}")
    return exists


async def check_telegram_bot(bot_token: str) -> bool:
    """텔레그램 봇 연결 확인"""
    if not bot_token:
        print("⚠️  Telegram bot connection ... 봇 토큰 미설정")
        return False

    try:
        from telegram import Bot

        bot = Bot(token=bot_token)
        me = await bot.get_me()
        print(f"✅ Telegram bot connection ... OK (@{me.username})")
        return True
    except Exception as e:
        print(f"❌ Telegram bot connection ... 실패 ({e})")
        return False


def check_chrome_profile(user_data_dir: str, profile: str) -> bool:
    """크롬 프로필 확인"""
    profile_path = Path(user_data_dir).expanduser() / profile
    exists = profile_path.exists()
    status = "✅" if exists else "❌"
    msg = "OK" if exists else f"프로필 없음 ({profile_path})"
    print(f"{status} Chrome profile found ... {msg}")
    return exists


def check_sqlite() -> bool:
    """SQLite 사용 가능 확인"""
    try:
        import sqlite3

        print(f"✅ SQLite database ... OK (v{sqlite3.sqlite_version})")
        return True
    except ImportError:
        print("❌ SQLite database ... sqlite3 모듈 없음")
        return False


def check_playwright() -> bool:
    """Playwright 설치 확인"""
    try:
        from playwright.sync_api import sync_playwright

        print("✅ Playwright ... OK")
        return True
    except ImportError:
        print("❌ Playwright ... 미설치 (poetry run playwright install chromium)")
        return False


def check_config_files() -> bool:
    """설정 파일 존재 확인"""
    settings_exists = Path("config/settings.yaml").exists()
    env_exists = Path("config/.env").exists()

    if settings_exists:
        print("✅ config/settings.yaml ... OK")
    else:
        print("⚠️  config/settings.yaml ... 없음 (cp config/settings.example.yaml config/settings.yaml)")

    if env_exists:
        print("✅ config/.env ... OK")
    else:
        print("⚠️  config/.env ... 없음 (cp config/.env.example config/.env)")

    return settings_exists and env_exists


async def main() -> None:
    """모든 설정 항목을 검증합니다."""
    print("=" * 50)
    print("  LetterCast Pro - 환경 설정 검증")
    print("=" * 50)
    print()

    results = []

    # 기본 확인
    results.append(check_python_version())
    results.append(check_sqlite())
    results.append(check_playwright())
    print()

    # 설정 파일 확인
    results.append(check_config_files())
    print()

    # 설정 기반 확인
    try:
        from src.config import Settings

        settings = Settings.load()

        results.append(check_gmail_credentials(settings.gmail.credentials_path))
        results.append(check_gmail_token(settings.gmail.token_path))
        results.append(
            check_chrome_profile(
                settings.notebooklm.chrome_user_data_dir,
                settings.notebooklm.chrome_profile,
            )
        )
        results.append(await check_telegram_bot(settings.telegram.bot_token))
    except FileNotFoundError:
        print("⚠️  설정 파일 없음 - 세부 검증 스킵")
        print("   config/settings.example.yaml을 복사하여 config/settings.yaml을 생성하세요.")

    print()
    print("=" * 50)

    if all(results):
        print("✅ All checks passed!")
    else:
        failed = results.count(False)
        print(f"⚠️  {failed}개 항목에 주의가 필요합니다.")

    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
