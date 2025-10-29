# file: test_youtube_fetch.py
import streamlit as st
import re
import requests
from urllib.parse import urlparse, parse_qs

st.title("YouTube Fetch Test")

YOUTUBE_API_KEY = st.secrets["YOUTUBE_API_KEY"]  # set this in .streamlit/secrets.toml

def extract_video_id(url: str) -> str | None:
    # handles https://www.youtube.com/watch?v=ID and youtu.be/ID etc.
    try:
        u = urlparse(url)
        if u.netloc in ("youtu.be", "www.youtu.be"):
            return u.path.lstrip("/")
        qs = parse_qs(u.query)
        if "v" in qs:
            return qs["v"][0]
        # fallback for /shorts/ID, /embed/ID
        m = re.search(r"/(shorts|embed)/([A-Za-z0-9_-]{6,})", u.path)
        if m:
            return m.group(2)
    except Exception:
        return None
    return None

url = st.text_input("Paste a YouTube URL")
if st.button("Fetch") and url:
    vid = extract_video_id(url)
    if not vid:
        st.error("Could not extract video ID from that URL.")
    else:
        api = "https://www.googleapis.com/youtube/v3/videos"
        params = {
            "part": "snippet,statistics",
            "id": vid,
            "key": YOUTUBE_API_KEY
        }
        r = requests.get(api, params=params, timeout=20)
        data = r.json()
        if r.ok and data.get("items"):
            item = data["items"][0]
            snip = item["snippet"]
            stats = item["statistics"]
            thumb = snip["thumbnails"].get("high") or snip["thumbnails"].get("medium") or snip["thumbnails"].get("default")
            st.success("Fetched!")
            st.write({
                "p_id": item["id"],
                "p_title": snip["title"],
                "p_description": snip.get("description"),
                "p_channel": snip.get("channelTitle"),
                "p_posted_at": snip.get("publishedAt"),
                "p_thumbnail_url": thumb["url"] if thumb else None,
                "view_count": int(stats.get("viewCount", 0)),
                "like_count": int(stats.get("likeCount", 0)),
                "comment_count": int(stats.get("commentCount", 0)),
            })
            if thumb:
                st.image(thumb["url"])
        else:
            st.error(f"API error: {r.status_code} {data}")