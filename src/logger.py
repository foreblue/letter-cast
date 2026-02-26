"""구조화된 로깅 설정 모듈"""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def setup_logger(
    name: str = "lettercast",
    level: str = "INFO",
    log_dir: str | None = None,
) -> logging.Logger:
    """구조화된 로거를 설정하고 반환합니다.

    Args:
        name: 로거 이름
        level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR)
        log_dir: 로그 파일 저장 디렉토리 (None이면 콘솔만 출력)

    Returns:
        설정된 Logger 인스턴스
    """
    logger = logging.getLogger(name)

    # 이미 핸들러가 설정되어 있으면 중복 방지
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 포맷터: 2026-02-27 08:00:05 | INFO | module | message
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)-20s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 파일 핸들러 (log_dir이 지정된 경우)
    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(
            log_path / "lettercast.log",
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(module_name: str) -> logging.Logger:
    """모듈별 하위 로거를 반환합니다.

    Args:
        module_name: 모듈 이름 (예: "collector.gmail", "automator")

    Returns:
        하위 Logger 인스턴스
    """
    return logging.getLogger(f"lettercast.{module_name}")
