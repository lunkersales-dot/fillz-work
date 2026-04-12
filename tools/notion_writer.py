"""
Notion 저장 Tool
raw_data.json + analysis.json을 Notion Database에 누적 저장한다.
"""

import os
import json
import datetime
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

TMP_DIR = Path(__file__).parent.parent / ".tmp"
RAW_FILE = TMP_DIR / "raw_data.json"
ANALYSIS_FILE = TMP_DIR / "analysis.json"

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
NOTION_VERSION = "2022-06-28"

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
}


def setup_database_schema():
    """필요한 컬럼이 없으면 데이터베이스에 추가"""
    r = requests.get(f"https://api.notion.com/v1/databases/{DATABASE_ID}", headers=HEADERS)
    r.raise_for_status()
    existing = set(r.json().get("properties", {}).keys())

    add_props = {}
    if "수집 영상수" not in existing:
        add_props["수집 영상수"] = {"number": {"format": "number"}}
    for col in ["상위 채널", "트렌딩 키워드", "추천 제품", "추천 콘텐츠 주제", "분석 요약", "시장 인사이트"]:
        if col not in existing:
            add_props[col] = {"rich_text": {}}

    if add_props:
        requests.patch(f"https://api.notion.com/v1/databases/{DATABASE_ID}",
                       headers=HEADERS, json={"properties": add_props}).raise_for_status()
        print(f"  컬럼 추가됨: {', '.join(add_props.keys())}")
    else:
        print("  스키마 확인 완료")


def format_date(iso_str: str) -> str:
    """ISO 8601 → YYYY-MM-DD"""
    return iso_str[:10]


def truncate(text: str, max_len: int = 2000) -> str:
    """Notion 텍스트 속성 길이 제한"""
    return text[:max_len] if len(text) > max_len else text


def build_page_properties(raw: dict, analysis_data: dict) -> dict:
    """Notion Database 페이지 속성 구성"""
    collected_at = raw.get("collected_at", datetime.datetime.utcnow().isoformat())
    date_str = format_date(collected_at)
    analysis = analysis_data.get("analysis", {})
    top_channels = analysis_data.get("top_channels", [])[:5]
    top_keywords = analysis_data.get("top_keywords", [])[:10]

    channel_names = ", ".join([c["channel_title"] for c in top_channels])
    keyword_names = ", ".join([k["keyword"] for k in top_keywords])

    trending_products = analysis.get("trending_products", [])
    product_names = ", ".join([p.get("product", "") for p in trending_products[:3]])

    recommendations = analysis.get("content_recommendations", [])
    rec_text = "\n".join([
        f"{i+1}. {r.get('title', '')} — {r.get('reason', '')}"
        for i, r in enumerate(recommendations)
    ])

    return {
        "날짜": {
            "title": [{"text": {"content": f"Week of {date_str}"}}]
        },
        "수집 영상수": {
            "number": raw.get("total_videos", 0)
        },
        "상위 채널": {
            "rich_text": [{"text": {"content": truncate(channel_names)}}]
        },
        "트렌딩 키워드": {
            "rich_text": [{"text": {"content": truncate(keyword_names)}}]
        },
        "추천 제품": {
            "rich_text": [{"text": {"content": truncate(product_names)}}]
        },
        "추천 콘텐츠 주제": {
            "rich_text": [{"text": {"content": truncate(rec_text)}}]
        },
        "분석 요약": {
            "rich_text": [{"text": {"content": truncate(analysis.get("weekly_summary", ""))}}]
        },
        "시장 인사이트": {
            "rich_text": [{"text": {"content": truncate(analysis.get("market_insight", ""))}}]
        },
    }


def build_page_content(raw: dict, analysis_data: dict) -> list:
    """Notion 페이지 본문 블록 구성"""
    analysis = analysis_data.get("analysis", {})
    videos = raw.get("videos", [])[:20]
    blocks = []

    # 요약 섹션
    blocks.append({
        "object": "block", "type": "heading_2",
        "heading_2": {"rich_text": [{"text": {"content": "이번 주 요약"}}]}
    })
    blocks.append({
        "object": "block", "type": "paragraph",
        "paragraph": {"rich_text": [{"text": {"content": analysis.get("weekly_summary", "")}}]}
    })

    # 트렌딩 주제
    blocks.append({
        "object": "block", "type": "heading_2",
        "heading_2": {"rich_text": [{"text": {"content": "트렌딩 주제"}}]}
    })
    for topic in analysis.get("trending_topics", []):
        blocks.append({
            "object": "block", "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [{"text": {"content": f"{topic.get('topic', '')} — {topic.get('reason', '')}"}}]}
        })

    # 주목 제품
    blocks.append({
        "object": "block", "type": "heading_2",
        "heading_2": {"rich_text": [{"text": {"content": "주목할 제품"}}]}
    })
    for product in analysis.get("trending_products", []):
        blocks.append({
            "object": "block", "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [{"text": {"content": f"[{product.get('type', '')}] {product.get('product', '')} — {product.get('reason', '')}"}}]}
        })

    # 콘텐츠 추천
    blocks.append({
        "object": "block", "type": "heading_2",
        "heading_2": {"rich_text": [{"text": {"content": "콘텐츠 주제 추천"}}]}
    })
    for i, rec in enumerate(analysis.get("content_recommendations", []), 1):
        blocks.append({
            "object": "block", "type": "numbered_list_item",
            "numbered_list_item": {"rich_text": [{"text": {"content": f"{rec.get('title', '')} (키워드: {rec.get('target_keyword', '')})"}}]}
        })

    # 제품 추천
    blocks.append({
        "object": "block", "type": "heading_2",
        "heading_2": {"rich_text": [{"text": {"content": "제품 추천"}}]}
    })
    for rec in analysis.get("product_recommendations", []):
        blocks.append({
            "object": "block", "type": "numbered_list_item",
            "numbered_list_item": {"rich_text": [{"text": {"content": f"{rec.get('product', '')} — {rec.get('reason', '')}"}}]}
        })

    # TOP 20 영상 목록
    blocks.append({
        "object": "block", "type": "heading_2",
        "heading_2": {"rich_text": [{"text": {"content": "이번 주 TOP 20 영상"}}]}
    })
    for v in videos:
        blocks.append({
            "object": "block", "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [{"text": {"content": f"[{v.get('view_count', 0):,}회] {v['title']} ({v['channel_title']})"}}]}
        })

    return blocks


def main():
    if not RAW_FILE.exists():
        print(f"[오류] {RAW_FILE} 없음.")
        return
    if not ANALYSIS_FILE.exists():
        print(f"[오류] {ANALYSIS_FILE} 없음.")
        return

    raw = json.loads(RAW_FILE.read_text(encoding="utf-8"))
    analysis_data = json.loads(ANALYSIS_FILE.read_text(encoding="utf-8"))

    print("Notion Database 스키마 확인 중...")
    setup_database_schema()
    print("Notion Database에 항목 생성 중...")

    properties = build_page_properties(raw, analysis_data)
    content_blocks = build_page_content(raw, analysis_data)

    # 페이지 생성 (블록은 100개 제한이 있어 먼저 페이지 만들고 이후 추가)
    payload = {
        "parent": {"database_id": DATABASE_ID},
        "properties": properties,
        "children": content_blocks[:100],
    }
    r = requests.post("https://api.notion.com/v1/pages", headers=HEADERS, json=payload)
    r.raise_for_status()
    page = r.json()

    page_id = page["id"]
    print(f"완료. Notion 페이지 생성: {page_id}")
    print(f"  URL: https://notion.so/{page_id.replace('-', '')}")


if __name__ == "__main__":
    main()
