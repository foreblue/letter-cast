# LetterCast Pro

개인용 멀티 채널 팟캐스트 자동화 시스템

Gmail과 웹사이트에서 최신 콘텐츠를 수집하고, Google NotebookLM을 통해 오디오로 변환하여 텔레그램 채널로 자동 전달합니다.

## 설치

```bash
poetry install
poetry run playwright install chromium
cp config/.env.example config/.env
cp config/settings.example.yaml config/settings.yaml
```

## 실행

```bash
poetry run python -m src.main
```
