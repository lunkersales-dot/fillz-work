"""
Gmail 발송 Tool
최신 weekly_report PDF를 찾아 Gmail로 발송한다.

최초 1회 실행: python tools/gmail_sender.py --auth
이후 자동 실행: python tools/gmail_sender.py
"""

import os
import sys
import base64
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

load_dotenv()

PROJECT_DIR = Path(__file__).parent.parent
TMP_DIR = PROJECT_DIR / ".tmp"
CREDENTIALS_FILE = PROJECT_DIR / "credentials.json"
TOKEN_FILE = PROJECT_DIR / "token.json"

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
GMAIL_RECIPIENT = os.environ["GMAIL_RECIPIENT"]


def get_gmail_service():
    """Gmail API 서비스 객체 반환. 토큰 없으면 --auth 안내."""
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                print("[오류] credentials.json 없음.")
                print("  → Google Cloud Console에서 OAuth 클라이언트 ID(데스크톱 앱) 생성 후")
                print("  → 프로젝트 루트에 credentials.json으로 저장하세요.")
                print("  → 그 다음: python tools/gmail_sender.py --auth")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)

        TOKEN_FILE.write_text(creds.to_json())
        print(f"인증 완료. 토큰 저장: {TOKEN_FILE}")

    return build("gmail", "v1", credentials=creds)


def find_latest_report() -> Path | None:
    """가장 최근 weekly_report PDF 파일 반환"""
    pdfs = sorted(TMP_DIR.glob("weekly_report_*.pdf"), reverse=True)
    return pdfs[0] if pdfs else None


def build_email_body(report_date: str, pdf_path: Path) -> str:
    """발송 이메일 본문 HTML"""
    return f"""
<div style="font-family: 'Apple SD Gothic Neo', 'Noto Sans KR', sans-serif; max-width: 600px; margin: 0 auto;">
  <div style="background: #111111; padding: 24px 32px;">
    <div style="color: white; font-size: 22px; font-weight: 900; letter-spacing: 2px;">FILLZ</div>
    <div style="color: #888; font-size: 10px; letter-spacing: 3px; margin-top: 4px;">FISHING GEAR</div>
  </div>

  <div style="padding: 32px; background: #FAFAFA; border: 1px solid #E0E0E0; border-top: none;">
    <h2 style="font-size: 18px; color: #111; margin: 0 0 8px;">주간 루어낚시 트렌드 리포트</h2>
    <p style="color: #888; font-size: 13px; margin: 0 0 24px;">{report_date} · KR + JP 마켓 분석</p>

    <p style="color: #444; font-size: 14px; line-height: 1.8; margin: 0 0 24px;">
      이번 주 루어낚시 트렌드 리포트가 준비되었습니다.<br>
      첨부된 PDF에서 채널 분석, 급상승 키워드, 콘텐츠 추천, 제품 추천을 확인하세요.
    </p>

    <div style="background: #1B2A4A; color: white; padding: 16px 20px; border-radius: 4px; font-size: 13px; line-height: 1.7;">
      📎 첨부 파일: {pdf_path.name}
    </div>
  </div>

  <div style="padding: 16px 32px; text-align: center;">
    <p style="color: #BBB; font-size: 11px; margin: 0;">
      FILLZ FISHING GEAR · 자동 발송 시스템
    </p>
  </div>
</div>
"""


def send_report(pdf_path: Path):
    """PDF 리포트를 Gmail로 발송"""
    service = get_gmail_service()

    report_date = pdf_path.stem.replace("weekly_report_", "")
    subject = f"[FILLZ] 주간 루어낚시 트렌드 리포트 {report_date}"

    msg = MIMEMultipart("mixed")
    msg["To"] = GMAIL_RECIPIENT
    msg["Subject"] = subject

    # HTML 본문
    html_part = MIMEMultipart("alternative")
    html_part.attach(MIMEText(build_email_body(report_date, pdf_path), "html", "utf-8"))
    msg.attach(html_part)

    # PDF 첨부
    with open(pdf_path, "rb") as f:
        pdf_data = f.read()
    pdf_part = MIMEApplication(pdf_data, _subtype="pdf")
    pdf_part.add_header("Content-Disposition", "attachment", filename=pdf_path.name)
    msg.attach(pdf_part)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()

    print(f"이메일 발송 완료 → {GMAIL_RECIPIENT}")
    print(f"  제목: {subject}")
    print(f"  첨부: {pdf_path.name} ({pdf_path.stat().st_size // 1024} KB)")


def main():
    if "--auth" in sys.argv:
        print("Gmail OAuth 인증을 시작합니다. 브라우저가 열립니다...")
        get_gmail_service()
        print("인증 완료. 다음부터는 자동으로 실행됩니다.")
        return

    pdf_path = find_latest_report()
    if not pdf_path:
        print(f"[오류] {TMP_DIR}에 weekly_report_*.pdf 없음.")
        print("  pdf_generator.py를 먼저 실행하세요.")
        return

    print(f"발송할 리포트: {pdf_path.name}")
    send_report(pdf_path)


if __name__ == "__main__":
    main()
