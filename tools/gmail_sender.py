"""
Gmail 발송 Tool (SMTP + 앱 비밀번호 방식)
최신 weekly_report PDF를 찾아 Gmail로 발송한다.
"""

import os
import smtplib
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_DIR = Path(__file__).parent.parent
TMP_DIR = PROJECT_DIR / ".tmp"

GMAIL_SENDER   = os.environ["GMAIL_SENDER"]
GMAIL_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
GMAIL_RECIPIENT = os.environ["GMAIL_RECIPIENT"]

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def find_latest_report():
    pdfs = sorted(TMP_DIR.glob("weekly_report_*.pdf"), reverse=True)
    return pdfs[0] if pdfs else None


def build_email_body(report_date: str, pdf_path: Path) -> str:
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
    <div style="background: #1B2A4A; color: white; padding: 16px 20px; border-radius: 4px; font-size: 13px;">
      📎 첨부 파일: {pdf_path.name}
    </div>
  </div>
  <div style="padding: 16px 32px; text-align: center;">
    <p style="color: #BBB; font-size: 11px; margin: 0;">FILLZ FISHING GEAR · 자동 발송 시스템</p>
  </div>
</div>
"""


def send_report(pdf_path: Path):
    report_date = pdf_path.stem.replace("weekly_report_", "")
    subject = f"[FILLZ] 주간 루어낚시 트렌드 리포트 {report_date}"

    msg = MIMEMultipart("mixed")
    msg["From"] = GMAIL_SENDER
    msg["To"] = GMAIL_RECIPIENT
    msg["Subject"] = subject

    html_part = MIMEMultipart("alternative")
    html_part.attach(MIMEText(build_email_body(report_date, pdf_path), "html", "utf-8"))
    msg.attach(html_part)

    with open(pdf_path, "rb") as f:
        pdf_part = MIMEApplication(f.read(), _subtype="pdf")
    pdf_part.add_header("Content-Disposition", "attachment", filename=pdf_path.name)
    msg.attach(pdf_part)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(GMAIL_SENDER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_SENDER, GMAIL_RECIPIENT, msg.as_bytes())

    print(f"이메일 발송 완료 → {GMAIL_RECIPIENT}")
    print(f"  제목: {subject}")
    print(f"  첨부: {pdf_path.name} ({pdf_path.stat().st_size // 1024} KB)")


def main():
    pdf_path = find_latest_report()
    if not pdf_path:
        print(f"[오류] {TMP_DIR}에 weekly_report_*.pdf 없음.")
        print("  pdf_generator.py를 먼저 실행하세요.")
        return

    print(f"발송할 리포트: {pdf_path.name}")
    send_report(pdf_path)


if __name__ == "__main__":
    main()
