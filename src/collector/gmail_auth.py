"""Gmail OAuth 2.0 최초 인증 헬퍼 스크립트

사용법:
    poetry run python -m src.collector.gmail_auth

최초 실행 시 브라우저가 열리며 구글 계정 인증을 진행합니다.
인증 완료 후 config/token.json 파일이 자동 생성됩니다.
"""

from __future__ import annotations

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Gmail API 읽기 전용 스코프
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def authenticate(
    credentials_path: str = "config/credentials.json",
    token_path: str = "config/token.json",
) -> Credentials:
    """Gmail API 인증을 수행하고 Credentials를 반환합니다.

    토큰이 이미 존재하면 로드하고, 만료되었으면 갱신합니다.
    토큰이 없으면 브라우저를 통해 OAuth 인증을 진행합니다.

    Args:
        credentials_path: OAuth 클라이언트 시크릿 파일 경로
        token_path: 저장/로드할 토큰 파일 경로

    Returns:
        유효한 Credentials 인스턴스
    """
    creds: Credentials | None = None
    token_file = Path(token_path)

    # 기존 토큰 로드
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    # 토큰이 없거나 만료된 경우
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("토큰 갱신 중...")
            creds.refresh(Request())
        else:
            credentials_file = Path(credentials_path)
            if not credentials_file.exists():
                raise FileNotFoundError(
                    f"OAuth 클라이언트 시크릿 파일이 없습니다: {credentials_path}\n"
                    f"Google Cloud Console에서 다운로드 후 해당 경로에 저장해 주세요."
                )
            print("브라우저에서 구글 계정 인증을 진행합니다...")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_file), SCOPES
            )
            creds = flow.run_local_server(port=0)

        # 토큰 저장
        token_file.parent.mkdir(parents=True, exist_ok=True)
        with open(token_file, "w") as f:
            f.write(creds.to_json())
        print(f"토큰 저장 완료: {token_path}")

    return creds


if __name__ == "__main__":
    creds = authenticate()
    print("✅ Gmail 인증 성공!")
    print(f"   토큰 유효: {creds.valid}")
    print(f"   만료 시간: {creds.expiry}")
