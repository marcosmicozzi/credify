import os
import json
import requests
from datetime import datetime

def lambda_handler(event, context):
    SUPABASE_URL = os.environ['SUPABASE_URL']
    SUPABASE_KEY = os.environ['SUPABASE_KEY']
    YOUTUBE_API_KEY = os.environ['YOUTUBE_API_KEY']
    VIDEO_IDS_ENV = os.environ.get("YOUTUBE_VIDEO_IDS", "")

    # Use environment variable or default to manual example
    video_ids = [v.strip() for v in VIDEO_IDS_ENV.split(",") if v.strip()] or ["3zKwIqxLTd4"]

    print(f"Fetched {len(video_ids)} videos")

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

    for vid in video_ids:
        # Fetch video metrics from YouTube Data API
        yt_response = requests.get(
            f"https://www.googleapis.com/youtube/v3/videos?part=statistics&id={vid}&key={YOUTUBE_API_KEY}"
        )
        yt_response.raise_for_status()
        data = yt_response.json()

        if not data.get("items"):
            print(f"No data found for video {vid}")
            continue

        stats = data["items"][0]["statistics"]
        view_count = int(stats.get("viewCount", 0))
        like_count = int(stats.get("likeCount", 0))
        comment_count = int(stats.get("commentCount", 0))

        # Create payload for Supabase
        payload = {
            "p_id": vid,  # ✅ matches your Supabase schema
            "platform": "youtube",
            "fetched_at": datetime.utcnow().isoformat(),
            "view_count": view_count,
            "like_count": like_count,
            "comment_count": comment_count
        }

        # Deduplicate same-day inserts: skip if a row exists today for this p_id
        try:
            # Compute UTC day start iso
            day_start_iso = payload["fetched_at"][:10] + "T00:00:00Z"
            # Query existing rows for today
            select_url = (
                f"{SUPABASE_URL}/rest/v1/youtube_metrics"
                f"?p_id=eq.{vid}&fetched_at=gte.{day_start_iso}&select=p_id&limit=1"
            )
            sel = requests.get(select_url, headers=headers, timeout=20)
            if sel.ok and sel.json():
                print(f"Skipping insert for {vid} — already have a snapshot today")
                continue
        except Exception as e:
            print(f"Warning: dedupe check failed for {vid}: {e}")

        # Insert into Supabase youtube_metrics
        supabase_response = requests.post(
            f"{SUPABASE_URL}/rest/v1/youtube_metrics",
            headers=headers,
            data=json.dumps(payload)
        )

        print("Supabase response:", supabase_response.status_code, supabase_response.text)

    return {"success": True, "count": len(video_ids)}
