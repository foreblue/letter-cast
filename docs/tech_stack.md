# 기술 스택 정의서 (Tech Stack Definition) - LetterCast Pro

본 프로젝트는 고도의 웹 자동화와 데이터 수집이 핵심이므로, 생태계가 풍부하고 자동화 라이브러리가 강력한 **Python**을 주력 언어로 채택합니다.

## 1. 코어 기술 (Core Stack)

*   **언어 (Language):** `Python 3.11+`
    *   비동기 처리(`asyncio`)를 통해 다중 작업(수집, 자동화, 전송)을 효율적으로 수행합니다.
*   **UI 자동화 (Automation):** `Playwright (Python)`
    *   Google NotebookLM의 동적 UI 제어 및 실제 브라우저 프로필(`User Data Directory`) 연동에 최적화되어 있습니다.
*   **패키지 관리 (Dependency Management):** `Poetry` 또는 `venv` + `pip`
    *   의존성 충돌 방지 및 환경 격리를 위해 사용합니다.

## 2. 모듈별 상세 기술 (Module Details)

### 2.1 멀티 채널 수집 (Collector)
*   **Gmail 연동:** `google-api-python-client`, `google-auth-oauthlib`
    *   OAuth 2.0을 통한 안전한 메일 접근 및 필터링.
*   **웹 수집:** `feedparser` (RSS), `BeautifulSoup4` (HTML 파싱)
    *   RSS 피드가 없는 사이트는 Playwright를 통해 동적 렌더링 후 추출합니다.

### 2.2 데이터 관리 (Aggregator)
*   **데이터베이스:** `SQLite`
    *   URL 중복 방지(`deduplication`) 및 처리 상태(Pending, Completed, Failed)를 관리하기 위한 경량 파일 DB.

### 2.3 오디오 생성 및 전달 (Automator & Delivery)
*   **NotebookLM 자동화:** Playwright의 `persistent_context` 기능을 활용하여 기존 구글 로그인 세션을 유지합니다.
*   **텔레그램 전송:** `python-telegram-bot`
    *   생성된 MP3 파일 및 메타데이터(제목, 원문 링크)를 채널로 전송합니다.

## 3. 프로젝트 구조 (Proposed Structure)

```text
letter-cast/
├── src/
│   ├── collector/      # Gmail & Web Crawling
│   ├── automator/      # NotebookLM UI Logic
│   ├── delivery/       # Telegram Bot Logic
│   ├── database/       # DB Schema & Queries
│   └── main.py         # App Entry Point
├── data/               # SQLite DB & Temp MP3 Storage
├── config/             # YAML Configs & .env
├── tests/              # Unit & Integration Tests
└── pyproject.toml      # Dependency Config
```

---
*본 문서는 **Gemini 2.0 Flash** 모델에 의해 작성되었습니다.*
