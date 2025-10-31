import streamlit as st
from supabase import create_client, Client
import pandas as pd
import re
import requests
from auth import show_login, logout_button  # logout now handled in topbar menu
import os
from datetime import datetime

# -------------------------------
# INITIAL SETUP
# -------------------------------
st.set_page_config(page_title="Credify", layout="wide", initial_sidebar_state="expanded")

# Remove Streamlit header / padding
st.markdown("""
<style>
[data-testid="stHeader"] {display:none !important;}
.block-container {padding-top:0rem !important;}
.stSidebar > div:first-child {margin-top: var(--topbar-h); padding-top: 20px !important;}
[data-testid="collapsedControl"] {display:none !important;}
/* Hide any Streamlit-provided sidebar collapse/expand controls (compat with multiple versions) */
button[title*="Hide sidebar"],
button[title*="Show sidebar"],
[data-testid="stSidebarNavCollapse"],
[data-testid="stSidebarCollapseControl"],
[data-testid="stSidebarCollapseButton"] { display:none !important; }
/* Force sidebar to remain visible and fixed width */
[data-testid="stSidebar"] { 
  visibility: visible !important; 
  transform: translateX(0) !important; 
  width: 240px !important; 
}
[data-testid="stSidebar"] > div:first-child { width: 240px !important; }
/* Ensure main content accounts for fixed sidebar width */
[data-testid="stAppViewContainer"] > .main { margin-left: 0 !important; }
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
# SUPABASE CLIENT (via Streamlit secrets)
# -------------------------------
SUPABASE_URL = st.secrets.get("SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_ANON_KEY")
YOUTUBE_API_KEY = st.secrets.get("YOUTUBE_API_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Missing Supabase credentials. Please set SUPABASE_URL and SUPABASE_ANON_KEY in .streamlit/secrets.toml")
    st.stop()

if not YOUTUBE_API_KEY:
    st.error("Missing YOUTUBE_API_KEY in .streamlit/secrets.toml")
    st.stop()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# -------------------------------
# AUTHENTICATION GATE
# -------------------------------
if "user" not in st.session_state:
    show_login()
    st.stop()

user_email = st.session_state["user"].email
normalized_email = user_email.lower()
# Logout and login notice now live under the avatar menu in the topbar

# -------------------------------
# THEME SETTINGS — single light monochrome palette
# -------------------------------
def apply_theme(_: str | None = None):
    # Fixed monochrome palette
    primary = "#2E2E2E"
    background = "#FFFFFF"
    secondary_bg = "#F4F4F4"
    text = "#111111"
    border = "#E0E0E0"
    border2 = "#C8C8C8"

    css_vars = {
        "--bg": background,
        "--text": text,
        "--sidebar": secondary_bg,
        "--card": secondary_bg,
        "--border": border,
        "--border-2": border2,
        "--input": "#FFFFFF",
        "--muted": secondary_bg,
        "--primary": primary,
        "--link": primary
    }

    vars_css = ":root{" + ";".join([f"{k}:{v}" for k, v in css_vars.items()]) + "}"

    st.markdown(f"""
        <style>
        {vars_css}
        body,.stApp{{background-color:var(--bg) !important;color:var(--text) !important;}}
        .stSidebar{{background-color:var(--sidebar) !important;color:var(--text) !important;border-right:1px solid var(--border);box-shadow: 2px 0 6px rgba(0,0,0,.06);}}
        .block-container{{max-width:1100px !important;margin:0 auto !important;padding:48px 32px !important;}}
        section {{padding: 0 !important;}}
        h1,h2,h3,h4,h5,h6,p,span,div{{color:var(--text) !important;}}
        a{{color:var(--link) !important;text-decoration:none;}}
        *{{font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif !important;}}

        /* Typography hierarchy */
        h1{{font-size:40px !important;font-weight:800 !important;margin-bottom:16px !important;}}
        h2{{font-size:22px !important;font-weight:700 !important;margin-top:8px !important;}}
        p{{font-size:16px !important;font-weight:400 !important;}}

        /* Inputs */
        .stTextInput>div>div>input,
        .stTextArea>div>div>textarea,
        .stSelectbox>div>div>select{{
            background-color:var(--input) !important;color:var(--text) !important;
            border:1px solid var(--border) !important;
        }}
        /* Baseweb Select dropdown */
        div[data-baseweb="select"]>div{{background-color:var(--input) !important;color:var(--text) !important;border-color:var(--border) !important;}}
        div[data-baseweb="select"] [role="listbox"]{{background-color:var(--input) !important;color:var(--text) !important;border:1px solid var(--border) !important;}}
        div[data-baseweb="select"] [role="option"]{{color:var(--text) !important;background-color:var(--input) !important;}}
        div[data-baseweb="select"] [aria-selected="true"]{{background-color:var(--card) !important;}}

        /* Buttons (monochrome) */
        .stButton>button{{background-color:var(--input) !important;color:var(--text) !important;border:1px solid var(--border) !important;}}
        .stButton>button:hover{{filter:brightness(0.97);border-color:var(--border-2) !important;}}
        /* Primary buttons */
        .stButton>button[kind="primary"],
        button[data-testid="baseButton-primary"]{{background-color:var(--primary) !important;color:#FFFFFF !important;border:1px solid var(--primary) !important;}}
        .stButton>button[kind="primary"]:hover,
        button[data-testid="baseButton-primary"]:hover{{filter:brightness(0.95);}}

        /* Radios/checkboxes accent to match primary */
        div[data-baseweb="radio"] svg{{fill:var(--primary) !important;}}
        div[role="radio"][aria-checked="true"]>div{{border-color:var(--primary) !important;}}

        /* Popovers */
        div[data-testid="stPopover"],
        div[data-testid="stPopoverBody"]{{background-color:var(--input) !important;color:var(--text) !important;border:1px solid var(--border) !important;}}
        div[data-testid="stPopover" ] *,
        div[data-testid="stPopoverBody"] *{{color:var(--text) !important;}}
        div[data-testid="stPopover"] .stButton>button,
        div[data-testid="stPopoverBody"] .stButton>button{{background-color:var(--input) !important;color:var(--text) !important;border:1px solid var(--border) !important;}}
        div[data-testid="stPopover"] .stButton>button:hover,
        div[data-testid="stPopoverBody"] .stButton>button:hover{{filter:brightness(0.97);border-color:var(--border-2) !important;}}

        /* Cards */
        .card, .project-card{{
            background-color:#FFFFFF;border-radius:12px;padding:16px;margin-bottom:16px;
            border:1px solid #E6E6E6; box-shadow:0 2px 6px rgba(0,0,0,0.08);
            transition:transform .15s ease, box-shadow .15s ease;
        }}
        .card:hover, .project-card:hover{{
            transform:translateY(-2px);
            box-shadow:0 4px 12px rgba(0,0,0,0.10);
        }}
        .card-title{{font-weight:700;margin-bottom:8px;}}
        .page-section{{margin: 24px 0 32px 0;}}

        /* Fixed Top Navigation */
        :root{{--topbar-h:56px;}}
        .topnav{{position:fixed;top:0;left:0;right:0;height:var(--topbar-h);display:flex;align-items:center;justify-content:space-between;gap:16px;padding:12px 24px;background:#FFFFFF;border-bottom:1px solid #E6E6E6;box-shadow:0 1px 2px rgba(0,0,0,.04);z-index:1000;}}
        .topnav .brand{{font-weight:800;font-size:18px;}}
        .topnav .actions{{display:flex;align-items:center;gap:12px;}}
        .topnav .avatar{{width:28px;height:28px;border-radius:50%;background:#E6E6E6;display:inline-block;}}
        /* Offset main container below fixed topbar */
        [data-testid="stAppViewContainer"] > .main {{padding-top: calc(var(--topbar-h) + 8px) !important;}}

        /* Sidebar navigation styling */
        [data-testid="stSidebar"] [role="radiogroup"] label p{{font-size:15px !important;font-weight:600 !important;}}
        [data-testid="stSidebar"] [role="radio"][aria-checked="true"]{{background:#FFFFFF;border:1px solid #E6E6E6;border-radius:999px;padding:6px 10px;}}
        [data-testid="stSidebar"] [role="radio"]{{border-radius:999px;padding:6px 10px;}}
        [data-testid="stSidebar"] [role="radio"]:hover{{background:#FFFFFFaa}}
        .sb-brand{{font-weight:800;font-size:18px;margin:0 0 12px 0;}}
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
    res = requests.get(url, timeout=15)
    if not res.ok:
        return None
    try:
        data = res.json()
    except Exception:
        return None
    if "items" not in data or not data.get("items"):
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
# PAGE 1 — PROFILE (replaces Dashboard)
# -------------------------------
def show_profile():
    st.title("Profile")

    # Get user info
    user_res = supabase.table("users").select("*").eq("u_email", normalized_email).execute()
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

    # Profile header spacing retained, label removed per request
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
    st.markdown("### Performance Summary")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Views", f"{metrics['total_view_count']:,}")
    col2.metric("Likes", f"{metrics['total_like_count']:,}")
    col3.metric("Comments", f"{metrics['total_comment_count']:,}")
    col4.metric("Shares", f"{metrics['total_share_count']:,}")
    col5.metric("Engagement Rate", f"{metrics['avg_engagement_rate']:.2f}%")

    st.divider()

    # Add Credit entry point (opens inline section)
    if "show_add_credit" not in st.session_state:
        st.session_state.show_add_credit = False

    with st.container():
        cols_ac = st.columns([1, 5])
        with cols_ac[0]:
            if st.button("Add Credits"):
                st.session_state.show_add_credit = not st.session_state.show_add_credit
        with cols_ac[1]:
            st.caption("Claim credits by pasting a YouTube URL and selecting roles.")

    if st.session_state.show_add_credit:
        st.markdown("#### Add New Credit")
        render_add_credit_form()
        st.divider()

    # Projects
    st.markdown("### Your Credits")
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

    # Sort by views (batch metrics fetch to avoid N+1)
    pids = list(unique_projects.keys())
    metrics_map = {}
    if pids:
        metrics_resp = supabase.table("youtube_latest_metrics").select("p_id, view_count, like_count, comment_count").in_("p_id", pids).execute()
        for m in (metrics_resp.data or []):
            metrics_map[m["p_id"]] = {
                "view_count": m.get("view_count", 0) or 0,
                "like_count": m.get("like_count", 0) or 0,
                "comment_count": m.get("comment_count", 0) or 0,
            }

    sorted_projects = []
    for pid, rec in unique_projects.items():
        rec_metrics = metrics_map.get(pid, {"view_count": 0, "like_count": 0, "comment_count": 0})
        rec["views"] = rec_metrics["view_count"]
        rec["metrics"] = rec_metrics
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
            m = rec.get("metrics", {"view_count": 0, "like_count": 0, "comment_count": 0})
            st.caption(f"Views: {m['view_count']} | Likes: {m['like_count']} | Comments: {m['comment_count']}")
            st.markdown("</div>", unsafe_allow_html=True)

def render_add_credit_form():
    """Inline claim form reused inside Profile."""
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

            # Upsert to avoid duplicate metrics entries
            supabase.table("youtube_metrics").upsert({
                "p_id": video_data["p_id"],
                "platform": "youtube",
                "fetched_at": datetime.utcnow().isoformat(),
                "view_count": video_data["view_count"],
                "like_count": video_data["like_count"],
                "comment_count": video_data["comment_count"]
            }, on_conflict=["p_id", "fetched_at"]).execute()

            st.success(f"✅ Added new project: {video_data['p_title']}")

        # Ensure user exists / update
        supabase.table("users").upsert({
            "u_email": normalized_email,
            "u_name": name,
            "u_bio": bio
        }, on_conflict=["u_email"]).execute()

        user_record = supabase.table("users").select("u_id").eq("u_email", normalized_email).execute()
        u_id = user_record.data[0]["u_id"]

        for role_entry in st.session_state.selected_roles:
            _, role_name = role_entry.split(" - ")
            # Upsert to prevent duplicate role assignments
            supabase.table("user_projects").upsert({
                "u_id": u_id,
                "p_id": video_id,
                "u_role": role_name
            }, on_conflict=["u_id", "p_id", "u_role"]).execute()

        st.success(f"🎉 {name} is now credited for: {', '.join(st.session_state.selected_roles)}!")
        st.balloons()
        st.session_state.selected_roles = []

# -------------------------------
# PAGE 3 — EXPLORE
# -------------------------------
def show_home_page():
    st.title("Home")
    left, right = st.columns([2,1])
    with left:
        st.markdown("<div class='page-section card'><div class='card-title'>For You</div><p>Your personalized feed will appear here.</p></div>", unsafe_allow_html=True)
        st.markdown("<div class='card'><div class='card-title'>Recent Highlights</div><p>Coming soon: recent credits and updates.</p></div>", unsafe_allow_html=True)
    with right:
        st.markdown("<div class='card'><div class='card-title'>Right Panel</div><p>Placeholder for charts or top creators.</p></div>", unsafe_allow_html=True)


def show_notifications_page():
    st.title("Notifications")
    # Basic recent credit events inferred from user_projects
    user_res = supabase.table("users").select("u_id").eq("u_email", normalized_email).execute()
    if not user_res.data:
        st.info("No notifications yet.")
        return
    u_id = user_res.data[0]["u_id"]

    results = supabase.table("user_projects").select("u_role, projects(p_title)").eq("u_id", u_id).order("created_at", desc=True).limit(25).execute()
    items = results.data or []
    if not items:
        st.info("No recent activity.")
        return
    for it in items:
        title = it.get("projects", {}).get("p_title", "Project")
        role = it.get("u_role", "Role")
        st.write(f"✅ Credit accepted: {role} on {title}")

# -------------------------------
# PAGE 4 — SETTINGS
# -------------------------------
def show_analytics_page():
    st.title("Analytics")
    st.markdown("<div class='card page-section'><div class='card-title'>YouTube Performance</div><p>Summary of your credited projects.</p></div>", unsafe_allow_html=True)


def show_settings_page():
    st.title("Settings")
    st.info("Profile editing and preferences coming soon.")


# -------------------------------
# TOP BAR (avatar + notifications)
# -------------------------------
def show_topbar():
    # Simple fixed top navigation with placeholders
    st.markdown(
        """
        <div class='topnav'>
          <div class='brand'>Credify</div>
          <div class='actions'>
            <span>💬</span>
            <span>🔔</span>
            <span class='avatar'></span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# -------------------------------
# SIDEBAR NAVIGATION
# -------------------------------
with st.sidebar:
    st.markdown("<div class='sb-brand'>Credify</div>", unsafe_allow_html=True)
    page = st.radio("Navigate to:", ["Home", "Profile", "Analytics", "Settings"], index=1)

apply_theme()

# Render top bar with avatar and bell
show_topbar()

# -------------------------------
# PAGE ROUTING
# -------------------------------
override = st.session_state.get("page_override")
if override:
    page = override
    st.session_state["page_override"] = None

if page == "Home":
    show_home_page()
elif page == "Profile":
    show_profile()
elif page == "Analytics":
    show_analytics_page()
elif page == "Notifications":
    show_notifications_page()
else:
    show_settings_page()
