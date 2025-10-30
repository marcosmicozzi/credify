import streamlit as st
import requests
from supabase import create_client, Client
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import re

# --- Load secrets (Streamlit) ---
SUPABASE_URL = st.secrets.get("SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_ANON_KEY")
YOUTUBE_API_KEY = st.secrets.get("YOUTUBE_API_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Missing Supabase credentials in .streamlit/secrets.toml")
    st.stop()
if not YOUTUBE_API_KEY:
    st.error("Missing YOUTUBE_API_KEY in .streamlit/secrets.toml")
    st.stop()

# --- Init Supabase client ---
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.title("🎬 Add YouTube Project to Supabase")

# --- Helper: Extract video ID from any YouTube link ---
def extract_video_id(url: str):
    u = urlparse(url)
    if u.netloc in ("youtu.be", "www.youtu.be"):
        return u.path.lstrip("/")
    qs = parse_qs(u.query)
    if "v" in qs:
        return qs["v"][0]
    match = re.search(r"/(shorts|embed)/([A-Za-z0-9_-]{6,})", u.path)
    return match.group(2) if match else None

# --- UI ---
url = st.text_input("Paste a YouTube URL")
if st.button("Add to Supabase") and url:
    vid = extract_video_id(url)
    if not vid:
        st.error("Could not extract video ID.")
        st.stop()

    api = "https://www.googleapis.com/youtube/v3/videos"
    params = {"part": "snippet,statistics", "id": vid, "key": YOUTUBE_API_KEY}
    r = requests.get(api, params=params, timeout=15)
    data = r.json()

    if not r.ok or not data.get("items"):
        st.error(f"YouTube API error: {r.status_code} {data}")
        st.stop()

    item = data["items"][0]
    snip = item["snippet"]
    stats = item["statistics"]
    thumb = snip["thumbnails"].get("high") or snip["thumbnails"].get("medium")

    # --- Build project record ---
    project = {
        "p_id": item["id"],
        "p_title": snip["title"],
        "p_description": snip.get("description"),
        "p_link": url,
        "p_platform": "youtube",
        "p_channel": snip.get("channelTitle"),
        "p_posted_at": snip.get("publishedAt"),
        "p_thumbnail_url": thumb["url"] if thumb else None,
    }

    # --- Build metrics record ---
    views = int(stats.get("viewCount", 0))
    likes = int(stats.get("likeCount", 0))
    comments = int(stats.get("commentCount", 0))
    engagement = round(((likes + comments) / views), 4) if views else None

    metric = {
        "p_id": item["id"],
        "platform": "youtube",
        "view_count": views,
        "like_count": likes,
        "comment_count": comments,
        "share_count": None,
        "engagement_rate": engagement,
    }

    # --- Write to Supabase ---
    supabase.table("projects").upsert(project, on_conflict="p_id").execute()
    supabase.table("youtube_metrics").insert(metric).execute()

    st.success(f"✅ Added '{snip['title']}' to Supabase!")
    st.image(project["p_thumbnail_url"])