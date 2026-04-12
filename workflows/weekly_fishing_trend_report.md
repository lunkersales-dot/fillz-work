# Workflow: 주간 루어낚시 트렌드 리포트

## 목표
매주 월요일 20:00 KST에 자동 실행.
한국 + 일본 YouTube에서 루어낚시 트렌드를 수집·분석하고, 브랜드 PDF 리포트를 Gmail로 발송하며, 모든 데이터를 Notion에 누적 저장한다.

---

## 실행 순서

### Step 1 — YouTube 데이터 수집
**Tool:** `tools/youtube_collector.py`
**입력값:** 없음 (`.env`에서 YOUTUBE_API_KEY 자동 로드)
**하는 일:**
- 한국 키워드(`루어낚시`, `배스낚시`, `루어 로드`, `루어 릴`) 검색
- 일본 키워드(`ルアー釣り`, `バス釣り`, `ルアーロッド`) 검색
- 최근 7일 이내 업로드된 영상 수집
- 채널 통계, 영상 통계(조회수·좋아요·댓글수) 수집
**출력물:** `.tmp/raw_data.json`
**에러 처리:**
- API 할당량 초과(403) → 실행 중단, 사장에게 알림
- 결과 0건 → 경고 로그 후 다음 Step 진행

### Step 2 — 트렌드 분석
**Tool:** `tools/trend_analyzer.py`
**입력값:** `.tmp/raw_data.json`
**하는 일:**
- Claude API로 영상 데이터 분석
- 급상승 주제/키워드 클러스터링
- 제품 언급 추출 (로드·릴·루어·라인 등)
- 잘 되는 포맷 분석 (쇼츠 vs 롱폼, 길이, 제목 패턴)
- 콘텐츠 주제 추천 3가지
- 제품 추천 3가지
**출력물:** `.tmp/analysis.json`
**에러 처리:**
- Claude API 에러 → 재시도 1회, 실패 시 중단

### Step 3 — Notion 저장
**Tool:** `tools/notion_writer.py`
**입력값:** `.tmp/raw_data.json`, `.tmp/analysis.json`
**하는 일:**
- Notion Database에 이번 주 항목 생성
- 수집 날짜, 영상 목록, 분석 요약, 추천 키워드 저장
**출력물:** Notion Database 항목 생성
**에러 처리:**
- 인증 실패(401) → `.env`의 NOTION_TOKEN 확인 요청
- Database ID 없음 → NOTION_DATABASE_ID 확인 요청

### Step 4 — PDF 리포트 생성
**Tool:** `tools/pdf_generator.py`
**입력값:** `.tmp/raw_data.json`, `.tmp/analysis.json`
**하는 일:**
- `tools/report_template.html`에 데이터 주입
- matplotlib으로 차트 생성 (인기 채널 TOP10, 조회수 트렌드)
- WeasyPrint로 PDF 변환
**출력물:** `.tmp/weekly_report_YYYY-MM-DD.pdf`
**에러 처리:**
- WeasyPrint 폰트 에러 → Noto Sans CJK 설치 필요

### Step 5 — Gmail 발송
**Tool:** `tools/gmail_sender.py`
**입력값:** `.tmp/weekly_report_YYYY-MM-DD.pdf`
**하는 일:**
- Gmail OAuth 토큰으로 인증
- PDF 첨부해서 GMAIL_RECIPIENT 주소로 발송
- 제목: `[FILLZ] 주간 루어낚시 트렌드 리포트 YYYY-MM-DD`
**출력물:** 이메일 발송 완료
**에러 처리:**
- 토큰 만료 → 자동 갱신 시도
- 최초 실행 시 → `python tools/gmail_sender.py --auth`로 브라우저 인증 필요

---

## 전체 실행 명령어 (수동 테스트용)

```bash
cd "/Users/kimsihyun/FILLZ WORK"

# Step별 개별 실행
python tools/youtube_collector.py
python tools/trend_analyzer.py
python tools/notion_writer.py
python tools/pdf_generator.py
python tools/gmail_sender.py

# 전체 한번에 실행
python tools/youtube_collector.py && \
python tools/trend_analyzer.py && \
python tools/notion_writer.py && \
python tools/pdf_generator.py && \
python tools/gmail_sender.py
```

---

## 필요한 .env 값

```
YOUTUBE_API_KEY=         # Google Cloud Console에서 발급
ANTHROPIC_API_KEY=       # console.anthropic.com
NOTION_TOKEN=            # Notion Integrations에서 발급
NOTION_DATABASE_ID=      # Notion DB URL의 32자리 ID
GMAIL_RECIPIENT=         # 리포트 받을 이메일 주소
```

---

## API 셋업 가이드

### YouTube API 키 발급
1. console.cloud.google.com 접속
2. 프로젝트 생성 → "YouTube Data API v3" 검색 → 사용 설정
3. 사용자 인증 정보 → API 키 만들기
4. 발급된 키를 `.env`의 YOUTUBE_API_KEY에 입력

### Gmail OAuth 설정
1. console.cloud.google.com → Gmail API 사용 설정
2. OAuth 동의 화면 → 외부 → 앱 이름 FILLZ
3. 사용자 인증 정보 → OAuth 클라이언트 ID → 데스크톱 앱
4. JSON 다운로드 → 프로젝트 루트에 `credentials.json`으로 저장
5. 최초 1회: `python tools/gmail_sender.py --auth` 실행 → 브라우저에서 인증

### Notion Integration 설정
1. notion.so → 설정 → 연결 → 새 통합 만들기
2. 이름: FILLZ Trend Report → 제출
3. "내부 통합 시크릿" 복사 → `.env`의 NOTION_TOKEN에 입력
4. Notion에서 새 데이터베이스 페이지 생성
5. 페이지 우측 상단 … → 연결 → FILLZ Trend Report 연결
6. URL에서 ID 복사 (notion.so/xxxxx?v=... 에서 xxxxx 부분) → NOTION_DATABASE_ID에 입력

---

## Notion 데이터베이스 스키마

| 컬럼 | 타입 | 설명 |
|------|------|------|
| 날짜 | Date | 수집 날짜 (Title) |
| 수집 영상수 | Number | 이번 주 수집된 총 영상 수 |
| 상위 채널 | Text | TOP5 채널명 |
| 트렌딩 키워드 | Text | 이번 주 상위 키워드 |
| 추천 제품 | Text | 언급 급증 제품 |
| 추천 콘텐츠 주제 | Text | 주제 추천 3가지 |
| 분석 요약 | Text | Claude 분석 전문 |
| 원본 데이터 | Text | raw_data.json 요약 |

---

## 업데이트 이력

| 날짜 | 변경 내용 |
|------|----------|
| 2026-04-12 | 최초 생성 |
