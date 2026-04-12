"""
YouTube Data API v3 수집 Tool
루어낚시 관련 한국/일본 채널의 최근 7일 영상 데이터를 수집한다.
출력: .tmp/raw_data.json
"""

import os
import json
import datetime
from pathlib import Path
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()

API_KEY = os.environ["YOUTUBE_API_KEY"]
TMP_DIR = Path(__file__).parent.parent / ".tmp"
OUTPUT_FILE = TMP_DIR / "raw_data.json"

SEARCH_QUERIES = [
    # 한국어 키워드
    {"q": "루어낚시", "regionCode": "KR", "relevanceLanguage": "ko"},
    {"q": "배스낚시", "regionCode": "KR", "relevanceLanguage": "ko"},
    {"q": "루어 로드 추천", "regionCode": "KR", "relevanceLanguage": "ko"},
    {"q": "루어 릴 추천", "regionCode": "KR", "relevanceLanguage": "ko"},
    # 일본어 키워드
    {"q": "ルアー釣り", "regionCode": "JP", "relevanceLanguage": "ja"},
    {"q": "バス釣り", "regionCode": "JP", "relevanceLanguage": "ja"},
    {"q": "ルアーロッド インプレ", "regionCode": "JP", "relevanceLanguage": "ja"},
]

MAX_RESULTS_PER_QUERY = 20


def get_published_after() -> str:
    """7일 전 날짜를 ISO 8601 형식으로 반환"""
    seven_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=7)
    return seven_days_ago.strftime("%Y-%m-%dT%H:%M:%SZ")


def search_videos(youtube, query_params: dict, published_after: str) -> list[dict]:
    """키워드로 영상 검색, 기본 메타데이터 반환"""
    response = youtube.search().list(
        part="id,snippet",
        type="video",
        order="viewCount",
        publishedAfter=published_after,
        maxResults=MAX_RESULTS_PER_QUERY,
        **query_params,
    ).execute()

    videos = []
    for item in response.get("items", []):
        videos.append({
            "video_id": item["id"]["videoId"],
            "title": item["snippet"]["title"],
            "channel_id": item["snippet"]["channelId"],
            "channel_title": item["snippet"]["channelTitle"],
            "published_at": item["snippet"]["publishedAt"],
            "description": item["snippet"]["description"][:500],
            "thumbnail": item["snippet"]["thumbnails"].get("medium", {}).get("url", ""),
            "query": query_params["q"],
            "region": query_params.get("regionCode", ""),
        })
    return videos


def get_video_statistics(youtube, video_ids: list[str]) -> dict[str, dict]:
    """영상 ID 목록으로 상세 통계 수집 (50개씩 배치)"""
    stats = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        response = youtube.videos().list(
            part="statistics,contentDetails,snippet",
            id=",".join(batch),
        ).execute()
        for item in response.get("items", []):
            vid = item["id"]
            s = item.get("statistics", {})
            snippet = item.get("snippet", {})
            duration = item.get("contentDetails", {}).get("duration", "")
            stats[vid] = {
                "view_count": int(s.get("viewCount", 0)),
                "like_count": int(s.get("likeCount", 0)),
                "comment_count": int(s.get("commentCount", 0)),
                "tags": snippet.get("tags", []),
                "category_id": snippet.get("categoryId", ""),
                "duration": duration,
                "is_short": "PT" in duration and "M" not in duration and int(
                    duration.replace("PT", "").replace("S", "") or 0
                ) <= 60 if duration else False,
            }
    return stats


def get_channel_statistics(youtube, channel_ids: list[str]) -> dict[str, dict]:
    """채널 ID 목록으로 채널 통계 수집 (50개씩 배치)"""
    stats = {}
    unique_ids = list(set(channel_ids))
    for i in range(0, len(unique_ids), 50):
        batch = unique_ids[i:i + 50]
        response = youtube.channels().list(
            part="statistics,snippet",
            id=",".join(batch),
        ).execute()
        for item in response.get("items", []):
            cid = item["id"]
            s = item.get("statistics", {})
            stats[cid] = {
                "subscriber_count": int(s.get("subscriberCount", 0)),
                "total_view_count": int(s.get("viewCount", 0)),
                "video_count": int(s.get("videoCount", 0)),
                "country": item.get("snippet", {}).get("country", ""),
            }
    return stats


def calculate_engagement_rate(view_count: int, like_count: int, comment_count: int) -> float:
    """좋아요 + 댓글 / 조회수 × 100"""
    if view_count == 0:
        return 0.0
    return round((like_count + comment_count) / view_count * 100, 2)


def main():
    TMP_DIR.mkdir(exist_ok=True)
    youtube = build("youtube", "v3", developerKey=API_KEY)
    published_after = get_published_after()

    print(f"수집 시작 | 기준: {published_after} 이후 영상")
    all_videos = []
    seen_ids = set()

    for query_params in SEARCH_QUERIES:
        print(f"  검색 중: {query_params['q']}")
        try:
            videos = search_videos(youtube, query_params, published_after)
            for v in videos:
                if v["video_id"] not in seen_ids:
                    seen_ids.add(v["video_id"])
                    all_videos.append(v)
            print(f"    → {len(videos)}건 수집")
        except HttpError as e:
            if e.resp.status == 403:
                print(f"[오류] API 할당량 초과. 내일 다시 시도하세요.")
                raise
            print(f"[경고] '{query_params['q']}' 검색 실패: {e}")

    if not all_videos:
        print("[경고] 수집된 영상이 없습니다.")
        OUTPUT_FILE.write_text(json.dumps({"collected_at": datetime.datetime.utcnow().isoformat(), "videos": []}, ensure_ascii=False, indent=2))
        return

    print(f"\n총 {len(all_videos)}개 영상 수집. 상세 통계 조회 중...")

    video_ids = [v["video_id"] for v in all_videos]
    video_stats = get_video_statistics(youtube, video_ids)

    channel_ids = [v["channel_id"] for v in all_videos]
    channel_stats = get_channel_statistics(youtube, channel_ids)

    # 데이터 합치기
    for v in all_videos:
        vs = video_stats.get(v["video_id"], {})
        cs = channel_stats.get(v["channel_id"], {})
        v.update(vs)
        v["channel_subscriber_count"] = cs.get("subscriber_count", 0)
        v["channel_total_views"] = cs.get("total_view_count", 0)
        v["channel_video_count"] = cs.get("video_count", 0)
        v["channel_country"] = cs.get("country", "")
        v["engagement_rate"] = calculate_engagement_rate(
            v.get("view_count", 0),
            v.get("like_count", 0),
            v.get("comment_count", 0),
        )

    # 조회수 기준 정렬
    all_videos.sort(key=lambda x: x.get("view_count", 0), reverse=True)

    output = {
        "collected_at": datetime.datetime.utcnow().isoformat(),
        "week_start": published_after,
        "total_videos": len(all_videos),
        "videos": all_videos,
    }

    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"\n완료. 저장: {OUTPUT_FILE}")
    print(f"  TOP 영상: [{all_videos[0]['view_count']:,}회] {all_videos[0]['title']}")


if __name__ == "__main__":
    main()
