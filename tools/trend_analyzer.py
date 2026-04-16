"""
트렌드 분석 Tool
raw_data.json을 Claude API로 분석해 트렌드 인사이트를 생성한다.
입력: .tmp/raw_data.json
출력: .tmp/analysis.json
"""

import os
import json
import datetime
from pathlib import Path
from collections import Counter
from dotenv import load_dotenv
import anthropic

load_dotenv()

TMP_DIR = Path(__file__).parent.parent / ".tmp"
INPUT_FILE = TMP_DIR / "raw_data.json"
OUTPUT_FILE = TMP_DIR / "analysis.json"

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def extract_top_channels(videos: list[dict], top_n: int = 10) -> list[dict]:
    """채널별 집계해서 상위 채널 반환"""
    channel_data = {}
    for v in videos:
        cid = v["channel_id"]
        if cid not in channel_data:
            channel_data[cid] = {
                "channel_id": cid,
                "channel_title": v["channel_title"],
                "channel_country": v.get("channel_country", ""),
                "subscriber_count": v.get("channel_subscriber_count", 0),
                "total_views": v.get("channel_total_views", 0),
                "video_count_this_week": 0,
                "total_views_this_week": 0,
                "videos": [],
            }
        channel_data[cid]["video_count_this_week"] += 1
        channel_data[cid]["total_views_this_week"] += v.get("view_count", 0)
        channel_data[cid]["videos"].append({
            "title": v["title"],
            "view_count": v.get("view_count", 0),
            "engagement_rate": v.get("engagement_rate", 0),
        })

    sorted_channels = sorted(
        channel_data.values(),
        key=lambda x: x["total_views_this_week"],
        reverse=True,
    )
    return sorted_channels[:top_n]


def extract_keywords(videos: list[dict], top_n: int = 20) -> list[dict]:
    """태그와 제목에서 키워드 빈도 추출"""
    tag_counter = Counter()
    for v in videos:
        tags = v.get("tags", [])
        for tag in tags:
            tag_lower = tag.lower().strip()
            if len(tag_lower) >= 2:
                tag_counter[tag_lower] += 1

    return [{"keyword": k, "count": c} for k, c in tag_counter.most_common(top_n)]


def build_analysis_prompt(videos: list[dict], top_channels: list[dict], keywords: list[dict]) -> str:
    """Claude에게 보낼 분석 프롬프트 구성"""
    top_20_videos = videos[:20]
    video_summary = []
    for v in top_20_videos:
        video_summary.append(
            f"- [{v.get('view_count', 0):,}회] {v['title']} "
            f"(채널: {v['channel_title']}, 좋아요율: {v.get('engagement_rate', 0)}%, "
            f"쇼츠여부: {v.get('is_short', False)}, 태그: {', '.join(v.get('tags', [])[:5])})"
        )

    channel_summary = []
    for c in top_channels[:5]:
        channel_summary.append(
            f"- {c['channel_title']} (구독자: {c['subscriber_count']:,}, "
            f"이번 주 조회수: {c['total_views_this_week']:,}, 업로드: {c['video_count_this_week']}편)"
        )

    keyword_str = ", ".join([f"{k['keyword']}({k['count']})" for k in keywords[:15]])

    return f"""당신은 루어낚시 업계 트렌드 분석 전문가입니다.
아래 데이터는 이번 주 한국/일본 YouTube에서 수집한 루어낚시 관련 영상 데이터입니다.

## 이번 주 TOP 20 영상
{chr(10).join(video_summary)}

## 상위 채널 TOP 5
{chr(10).join(channel_summary)}

## 자주 등장한 태그 키워드
{keyword_str}

---

위 데이터를 분석해서 아래 항목을 JSON 형식으로 답해주세요.
반드시 유효한 JSON만 출력하고, 다른 텍스트는 포함하지 마세요.

{{
  "weekly_summary": "이번 주 루어낚시 트렌드 3줄 요약 (한국어)",
  "trending_topics": [
    {{"topic": "주제명", "reason": "왜 뜨는지 설명", "evidence": "관련 영상 제목 예시"}}
  ],
  "trending_products": [
    {{"product": "제품/카테고리명", "type": "로드/릴/루어/라인/기타", "reason": "언급 이유", "mentions": 0}}
  ],
  "format_analysis": {{
    "shorts_vs_longform": "쇼츠 vs 롱폼 비율 분석",
    "best_performing_length": "잘 되는 영상 길이",
    "title_patterns": "잘 되는 제목 패턴 설명",
    "thumbnail_patterns": "썸네일 패턴 추정"
  }},
  "content_recommendations": [
    {{"title": "추천 콘텐츠 주제", "reason": "추천 이유", "target_keyword": "타겟 키워드"}}
  ],
  "product_recommendations": [
    {{"product": "추천 제품/카테고리", "reason": "추천 이유", "opportunity": "기회 요인"}}
  ],
  "market_insight": "한국/일본 시장 차이점 및 인사이트 (2-3문장)",
  "brand_content_strategy": {{
    "summary": "루어낚시 장비 브랜드가 이번 주 트렌드를 활용해 콘텐츠를 만든다면 핵심 방향 한 줄 요약",
    "recommendations": [
      {{
        "content_idea": "콘텐츠 아이디어 제목",
        "approach": "구체적 접근 방식 — 어떻게 기획하고 찍을지, 어떤 메시지를 담을지",
        "format": "추천 포맷 (예: 쇼츠, 롱폼, 시리즈 등)",
        "why_it_works": "이번 주 트렌드에서 왜 브랜드에게 효과적인지"
      }}
    ]
  }},
  "translated_titles": {{
    "일본어 또는 영어 원본 제목": "한국어 번역 제목 (30자 이내로 요약)"
  }}
}}

중요 규칙:
- trending_topics는 최소 3개, trending_products는 최소 3개, content_recommendations는 정확히 3개, product_recommendations는 정확히 3개 포함하세요.
- brand_content_strategy.recommendations는 정확히 3개 포함하세요. 크리에이터가 아닌 브랜드 관점에서, 제품을 자연스럽게 녹일 수 있는 콘텐츠 방향으로 작성하세요.
- translated_titles: TOP 20 영상 중 일본어 또는 영어로 된 제목만 한국어로 번역해주세요. 한국어 제목은 제외. 번역 제목은 핵심만 담아 30자 이내로 작성하세요."""


def analyze_with_claude(prompt: str) -> dict:
    """Claude API로 트렌드 분석"""
    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()

    # JSON 블록 추출
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()

    return json.loads(raw)


def main():
    if not INPUT_FILE.exists():
        print(f"[오류] {INPUT_FILE} 없음. youtube_collector.py를 먼저 실행하세요.")
        return

    raw = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    videos = raw.get("videos", [])

    if not videos:
        print("[경고] 수집된 영상이 없습니다. 분석을 건너뜁니다.")
        OUTPUT_FILE.write_text(json.dumps({"analyzed_at": datetime.datetime.utcnow().isoformat(), "error": "no_data"}, ensure_ascii=False, indent=2))
        return

    print(f"분석 시작 | 영상 {len(videos)}개")

    top_channels = extract_top_channels(videos)
    keywords = extract_keywords(videos)

    print("  Claude API로 트렌드 분석 중...")
    prompt = build_analysis_prompt(videos, top_channels, keywords)

    try:
        analysis = analyze_with_claude(prompt)
    except Exception as e:
        print(f"[오류] Claude 분석 실패: {e}. 재시도 중...")
        analysis = analyze_with_claude(prompt)  # 1회 재시도

    output = {
        "analyzed_at": datetime.datetime.utcnow().isoformat(),
        "collected_at": raw.get("collected_at"),
        "total_videos_analyzed": len(videos),
        "top_channels": top_channels,
        "top_keywords": keywords,
        "analysis": analysis,
    }

    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"\n완료. 저장: {OUTPUT_FILE}")
    print(f"  요약: {analysis.get('weekly_summary', '')[:80]}...")


if __name__ == "__main__":
    main()
