import streamlit as st
from supabase import create_client, Client
import re
import requests
import os

# --- Setup Supabase client ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

st.title("🎬 Claim Your Role on a Project via YouTube URL")

# --- Helper to extract YouTube video ID ---
def extract_video_id(url):
    pattern = r"(?:v=|youtu\.be/|embed/)([a-zA-Z0-9_-]{11})"
    match = re.search(pattern, url)
    return match.group(1) if match else None

# --- Helper to fetch video data ---
def fetch_youtube_data(video_id):
    url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics&id={video_id}&key={YOUTUBE_API_KEY}"
    res = requests.get(url)
    data = res.json()

    if "items" not in data or not data["items"]:
        return None

    item = data["items"][0]
    snippet = item["snippet"]
    stats = item.get("statistics", {})

    return {
        "p_id": video_id,
        "p_title": snippet.get("title"),
        "p_description": snippet.get("description"),
        "p_link": f"https://www.youtube.com/watch?v={video_id}",
        "p_channel": snippet.get("channelTitle"),
        "p_posted_at": snippet.get("publishedAt"),
        "p_thumbnail_url": snippet["thumbnails"]["high"]["url"],
        "view_count": int(stats.get("viewCount", 0)),
        "like_count": int(stats.get("likeCount", 0)),
        "comment_count": int(stats.get("commentCount", 0))
    }

# --- Fetch dynamic roles from Supabase ---
roles_response = supabase.table("roles").select("role_name, category").execute()
categories = {}
if roles_response.data:
    for r in roles_response.data:
        cat = r["category"] if r["category"] else "Misc"
        categories.setdefault(cat, []).append(r["role_name"])
else:
    categories = {"Misc": ["Other"]}

# --- UI ---
url_input = st.text_input("Paste a YouTube URL")
name = st.text_input("Full name")
email = st.text_input("Email")
bio = st.text_area("Short bio (optional)")

st.markdown("### 🎭 Select your roles")

# Initialize session state to store multiple roles
if "selected_roles" not in st.session_state:
    st.session_state.selected_roles = []

category = st.selectbox("Select category", list(categories.keys()), key="category_select")
role = st.selectbox("Select role", categories[category], key="role_select")

if st.button("➕ Add Role"):
    role_entry = f"{category} - {role}"
    if role_entry not in st.session_state.selected_roles:
        st.session_state.selected_roles.append(role_entry)
    else:
        st.warning("You’ve already added this role.")

# Display added roles
if st.session_state.selected_roles:
    st.markdown("**Added roles:**")
    for r in st.session_state.selected_roles:
        st.write(f"• {r}")
else:
    st.info("No roles added yet. Add at least one before claiming.")

# Claim Role button
if st.button("Claim Role"):
    if not url_input or not email or not name:
        st.error("Please fill in all required fields.")
    elif not st.session_state.selected_roles:
        st.error("Please add at least one role.")
    else:
        video_id = extract_video_id(url_input)
        if not video_id:
            st.error("❌ Invalid YouTube URL.")
            st.stop()

        # 1️⃣ Check if project exists
        existing = supabase.table("projects").select("*").eq("p_id", video_id).execute().data
        if existing:
            project = existing[0]
            st.info(f"📽 Project already exists: {project['p_title']}")
        else:
            # 2️⃣ Fetch from YouTube and insert new project
            video_data = fetch_youtube_data(video_id)
            if not video_data:
                st.error("❌ Could not fetch video info from YouTube API.")
                st.stop()

            supabase.table("projects").insert({
                "p_id": video_data["p_id"],
                "p_title": video_data["p_title"],
                "p_description": video_data["p_description"],
                "p_link": video_data["p_link"],
                "p_platform": "youtube",
                "p_channel": video_data["p_channel"],
                "p_posted_at": video_data["p_posted_at"],
                "p_thumbnail_url": video_data["p_thumbnail_url"]
            }).execute()

            supabase.table("metrics").insert({
                "p_id": video_data["p_id"],
                "view_count": video_data["view_count"],
                "like_count": video_data["like_count"],
                "comment_count": video_data["comment_count"]
            }).execute()

            st.success(f"✅ Added new project: {video_data['p_title']}")

        # 3️⃣ Ensure user exists
        user = supabase.table("users").upsert({
        "u_email": email,
        "u_name": name,
        "u_bio": bio
        }, on_conflict=["u_email"]).execute()

# Fetch correct user ID (works for both new + existing users)
        user_record = supabase.table("users").select("u_id").eq("u_email", email).execute()
        u_id = user_record.data[0]["u_id"]
        u_id = user.data[0]["u_id"]

        # 4️⃣ Add all roles
        for role_entry in st.session_state.selected_roles:
            category, role_name = role_entry.split(" - ")
            supabase.table("user_projects").insert({
                "u_id": u_id,
                "p_id": video_id,
                "u_role": role_name
            }).execute()

        st.success(f"🎉 {name} is now credited for: {', '.join(st.session_state.selected_roles)}!")
        st.balloons()

        # Reset roles after submission
        st.session_state.selected_roles = []