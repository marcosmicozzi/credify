import streamlit as st
from supabase import create_client, Client
import pandas as pd
import re
import requests
from auth import show_login, logout_button  # 👈 auth.py we built earlier
from dotenv import load_dotenv
load_dotenv()
import os

# -------------------------------
# INITIAL SETUP
# -------------------------------
st.set_page_config(page_title="Credify", layout="wide")

# Remove Streamlit header / padding
st.markdown("""
<style>
[data-testid="stHeader"] {display:none !important;}
.block-container {padding-top:0rem !important;}
.stSidebar > div:first-child {padding-top:0.5rem !important;}
[data-testid="collapsedControl"] {
  display:block !important; visibility:visible !important;
  color:#1DB954 !important; opacity:0.9 !important; z-index:9999 !important;
  transition:opacity .2s ease-in-out;
}
[data-testid="collapsedControl"]:hover {opacity:1 !important; transform:scale(1.1);}
/* Logout button styling */
button[data-testid="stBaseButton-secondary"] {
  background-color: #333 !important;
  color: #E8E8E8 !important;
  border: 1px solid #555 !important;
}
button[data-testid="stBaseButton-secondary"]:hover {
  background-color: #444 !important;
  border-color: #666 !important;
}
</style>
""", unsafe_allow_html=True)

# -------------------------------
# SUPABASE CLIENT
# -------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
YOUTUBE_API_KEY = st.secrets["YOUTUBE_API_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# -------------------------------
# AUTHENTICATION GATE
# -------------------------------
if "user" not in st.session_state:
    show_login()
    st.stop()

user_email = st.session_state["user"].email
logout_button()
st.sidebar.success(f"Logged in as {user_email}")

# -------------------------------
# THEME SETTINGS
# -------------------------------
def set_app_theme(mode):
    if mode == "Dark":
        st.markdown("""
            <style>
            body,.stApp{background-color:#0B0C10 !important;color:#F2F4F8 !important;}
            .stSidebar{background-color:#111418 !important;color:#E8E8E8 !important;}
            h1,h2,h3,h4,h5,h6,p,span,div{color:#F2F4F8 !important;}
            a{color:#1DB954 !important;text-decoration:none;}
            .stTextInput>div>div>input,
            .stTextArea>div>div>textarea,
            .stSelectbox>div>div>select{
                background-color:#1C1F24 !important;color:#F2F4F8 !important;
                border:1px solid #333 !important;
            }
            .project-card{
                background-color:#181C20;border-radius:10px;padding:10px;margin-bottom:16px;
                box-shadow:0 2px 12px rgba(0,0,0,0.5);
                transition:transform .2s ease, box-shadow .2s ease;
            }
            .project-card:hover{
                transform:translateY(-3px);
                box-shadow:0 4px 16px rgba(0,0,0,0.6);
            }
            </style>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
            <style>
            body,.stApp{background-color:#FFFFFF !important;color:#222 !important;}
            .stSidebar{background-color:#F8F8F8 !important;}
            a{color:#0B5FFF !important;text-decoration:none;}
            .project-card{
                background-color:#F9F9F9;border-radius:10px;padding:10px;
                margin-bottom:16px;box-shadow:0 1px 5px rgba(0,0,0,0.1);
            }
            </style>
        """, unsafe_allow_html=True)

# -------------------------------
# HELPERS
# -------------------------------
def extract_video_id(url):
    pattern = r"(?:v=|youtu\\.be/|embed/)([a-zA-Z0-9_-]{11})"
    match = re.search(pattern, url)
    return match.group(1) if match else None


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

# -------------------------------
# PAGE 1 — DASHBOARD
# -------------------------------
def show_dashboard():
    st.title("🌟 Creator Dashboard")

    # Get user info
    user_res = supabase.table("users").select("*").eq("u_email", user_email).execute()
    if not user_res.data:
        st.info("No profile found yet — one will be created after your first claim.")
        return

    user = user_res.data[0]
    u_id = user["u_id"]

    # Fetch metrics
    metrics_res = supabase.table("user_metrics").select("*").eq("u_id", u_id).execute()
    metrics = metrics_res.data[0] if metrics_res.data else {
        "total_view_count": 0, "total_like_count": 0,
        "total_comment_count": 0, "total_share_count": 0,
        "avg_engagement_rate": 0
    }

    # Profile
    st.markdown("### 👤 Profile Overview")
    col1, col2 = st.columns([1, 3])
    with col1:
        st.image(f"https://api.dicebear.com/7.x/identicon/svg?seed={user['u_name']}", width=100)
    with col2:
        st.subheader(user["u_name"])
        st.write(user["u_email"])
        if user.get("u_bio"):
            st.caption(user["u_bio"])

    st.divider()

    # Metrics
    st.markdown("### 📊 Performance Summary")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Views", f"{metrics['total_view_count']:,}")
    col2.metric("Likes", f"{metrics['total_like_count']:,}")
    col3.metric("Comments", f"{metrics['total_comment_count']:,}")
    col4.metric("Shares", f"{metrics['total_share_count']:,}")
    col5.metric("Engagement Rate", f"{metrics['avg_engagement_rate']:.2f}%")

    st.divider()

    # Projects
    st.markdown("### 🎬 Your Projects")
    projects_response = supabase.table("user_projects") \
        .select("projects(p_id, p_title, p_link, p_thumbnail_url), u_role") \
        .eq("u_id", u_id).execute()

    data = projects_response.data
    if not data:
        st.info("You haven’t been credited on any projects yet.")
        return

    # Aggregate roles
    unique_projects = {}
    for rec in data:
        pid = rec["projects"]["p_id"]
        role = rec["u_role"]
        if pid not in unique_projects:
            unique_projects[pid] = {"project": rec["projects"], "roles": [role]}
        else:
            unique_projects[pid]["roles"].append(role)

    # Sort by views
    sorted_projects = []
    for pid, rec in unique_projects.items():
        metric_res = supabase.table("latest_metrics").select("view_count").eq("p_id", pid).execute()
        views = metric_res.data[0]["view_count"] if metric_res.data else 0
        rec["views"] = views
        sorted_projects.append(rec)
    sorted_projects = sorted(sorted_projects, key=lambda x: x["views"], reverse=True)

    # Display
    cols = st.columns(3)
    for i, rec in enumerate(sorted_projects):
        proj = rec["project"]
        roles = ", ".join(rec["roles"])
        with cols[i % 3]:
            st.markdown("<div class='project-card'>", unsafe_allow_html=True)
            st.image(proj["p_thumbnail_url"], use_container_width=True)
            st.markdown(f"**[{proj['p_title']}]({proj['p_link']})**  \n🎭 *{roles}*")
            mres = supabase.table("latest_metrics").select("view_count, like_count, comment_count").eq("p_id", proj["p_id"]).execute()
            if mres.data:
                m = mres.data[0]
                st.caption(f"👁️ {m['view_count']} | 👍 {m['like_count']} | 💬 {m['comment_count']}")
            st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------
# PAGE 2 — CLAIM CREDITS
# -------------------------------
def show_claim_page():
    st.title("🎬 Claim Your Role on a Project via YouTube URL")

    url_input = st.text_input("Paste a YouTube URL")
    name = st.text_input("Full name")
    bio = st.text_area("Short bio (optional)")

    # Roles
    roles_response = supabase.table("roles").select("role_name, category").execute()
    categories = {}
    if roles_response.data:
        for r in roles_response.data:
            cat = r["category"] if r["category"] else "Misc"
            categories.setdefault(cat, []).append(r["role_name"])
    else:
        categories = {"Misc": ["Other"]}

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

    if st.session_state.selected_roles:
        st.markdown("**Added roles:**")
        for r in st.session_state.selected_roles:
            st.write(f"• {r}")
    else:
        st.info("No roles added yet. Add at least one before claiming.")

    if st.button("Claim Role"):
        if not url_input or not name:
            st.error("Please fill in all required fields.")
            st.stop()
        elif not st.session_state.selected_roles:
            st.error("Please add at least one role.")
            st.stop()

        video_id = extract_video_id(url_input)
        if not video_id:
            st.error("❌ Invalid YouTube URL.")
            st.stop()

        # Check if project exists
        existing = supabase.table("projects").select("*").eq("p_id", video_id).execute().data
        if existing:
            project = existing[0]
            st.info(f"📽 Project already exists: {project['p_title']}")
        else:
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

        # Ensure user exists / update
        supabase.table("users").upsert({
            "u_email": user_email,
            "u_name": name,
            "u_bio": bio
        }, on_conflict=["u_email"]).execute()

        user_record = supabase.table("users").select("u_id").eq("u_email", user_email).execute()
        u_id = user_record.data[0]["u_id"]

        for role_entry in st.session_state.selected_roles:
            _, role_name = role_entry.split(" - ")
            supabase.table("user_projects").insert({
                "u_id": u_id,
                "p_id": video_id,
                "u_role": role_name
            }).execute()

        st.success(f"🎉 {name} is now credited for: {', '.join(st.session_state.selected_roles)}!")
        st.balloons()
        st.session_state.selected_roles = []

# -------------------------------
# PAGE 3 — EXPLORE
# -------------------------------
def show_explore_page():
    st.title("🔍 Explore Public Projects")
    st.info("This section will display trending creators soon.")

# -------------------------------
# PAGE 4 — SETTINGS
# -------------------------------
def show_settings_page():
    st.title("⚙️ Settings")
    st.info("Profile editing and preferences coming soon.")

# -------------------------------
# SIDEBAR NAVIGATION
# -------------------------------
with st.sidebar:
    st.title("🎧 Credify")
    theme = st.radio("Display mode:", ["Light", "Dark"], index=1)
    page = st.radio("Navigate to:", ["Dashboard", "Claim Credits", "Explore", "Settings"])

set_app_theme(theme)

# -------------------------------
# PAGE ROUTING
# -------------------------------
if page == "Dashboard":
    show_dashboard()
elif page == "Claim Credits":
    show_claim_page()
elif page == "Explore":
    show_explore_page()
else:
    show_settings_page()
