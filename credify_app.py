import streamlit as st
from supabase import create_client, Client
import pandas as pd
import re
import requests
import json
import plotly.graph_objects as go
import plotly.express as px
from auth import show_login, logout_button  # logout now handled in topbar menu
from supabase_utils import get_following, is_following, follow_user, unfollow_user, search_users
import os
from datetime import datetime, timedelta, timezone

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
        
        /* Search dropdown */
        .search-container{{position:relative;flex:1;max-width:400px;margin:0 16px;}}
        .search-dropdown{{
            position:absolute;top:100%;left:0;right:0;background:#FFFFFF;border:1px solid #E6E6E6;
            border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,0.15);z-index:1001;max-height:400px;
            overflow-y:auto;margin-top:4px;
        }}
        .search-result-item{{
            padding:12px 16px;border-bottom:1px solid #F0F0F0;cursor:pointer;display:flex;
            align-items:center;gap:12px;transition:background-color 0.15s;
        }}
        .search-result-item:hover{{background-color:#F8F8F8;}}
        .search-result-item:last-child{{border-bottom:none;}}
        .search-result-avatar{{width:40px;height:40px;border-radius:50%;flex-shrink:0;}}
        .search-result-content{{flex:1;min-width:0;}}
        .search-result-name{{font-weight:600;font-size:14px;margin-bottom:2px;}}
        .search-result-meta{{font-size:12px;color:#666;}}
        .search-result-action{{flex-shrink:0;}}

        /* Fixed Top Navigation */
        :root{{--topbar-h:56px;}}
        .topnav{{position:fixed;top:0;left:0;right:0;height:var(--topbar-h);display:flex;align-items:center;justify-content:space-between;gap:16px;padding:12px 24px;background:#FFFFFF;border-bottom:1px solid #E6E6E6;box-shadow:0 1px 2px rgba(0,0,0,.04);z-index:1000;}}
        .topnav .brand{{font-weight:800;font-size:18px;}}
        .topnav .actions{{display:flex;align-items:center;gap:12px;}}
        .topnav .avatar{{width:28px;height:28px;border-radius:50%;background:#E6E6E6;display:inline-block;}}
        /* Search positioning - below topbar */
        .search-wrapper{{position:fixed;top:var(--topbar-h);left:0;right:0;background:#FFFFFF;border-bottom:1px solid #E6E6E6;padding:8px 24px;z-index:999;display:flex;justify-content:center;}}
        /* Offset main container below topbar and search */
        [data-testid="stAppViewContainer"] > .main {{padding-top: calc(var(--topbar-h) + 56px) !important;}}

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
# ANALYTICS HELPERS (daily time series)
# -------------------------------
@st.cache_data(show_spinner=False)
def get_user_id_by_email_cached(email: str) -> str | None:
    res = supabase.table("users").select("u_id").eq("u_email", email).execute()
    if not res.data:
        return None
    return res.data[0]["u_id"]


def get_current_user_id() -> str | None:
    """Get current logged-in user's ID from session state."""
    return get_user_id_by_email_cached(normalized_email)


def update_user_metrics(u_id: str):
    """Recalculate and update user_metrics for a given user based on their projects."""
    # 1. Find all project IDs for this user
    projects_resp = supabase.table("user_projects").select("p_id").eq("u_id", u_id).execute()
    project_ids = [p["p_id"] for p in projects_resp.data]
    if not project_ids:
        # No projects, set all to zero
        supabase.table("user_metrics").upsert({
            "u_id": u_id,
            "total_view_count": 0,
            "total_like_count": 0,
            "total_comment_count": 0,
            "total_share_count": 0,
            "avg_engagement_rate": 0,
            "updated_at": datetime.utcnow().isoformat()
        }).execute()
        return

    # 2. Get latest metrics for each project
    # Try latest_youtube_metrics first (preferred for real-time), fall back to youtube_metrics if table doesn't exist
    try:
        metrics_resp = supabase.table("latest_youtube_metrics").select("p_id, view_count, like_count, comment_count, share_count").in_("p_id", project_ids).execute()
        latest_metrics = list(metrics_resp.data or [])
    except Exception:
        # Fallback: query youtube_metrics and get the latest entry per project
        metrics_resp = supabase.table("youtube_metrics").select("p_id, view_count, like_count, comment_count, fetched_at").in_("p_id", project_ids).order("fetched_at", desc=True).execute()
        # Group by p_id and take the first (most recent) entry for each
        seen_pids = set()
        latest_metrics = []
        for m in (metrics_resp.data or []):
            pid = m["p_id"]
            if pid not in seen_pids:
                latest_metrics.append({
                    "p_id": pid,
                    "view_count": m.get("view_count", 0) or 0,
                    "like_count": m.get("like_count", 0) or 0,
                    "comment_count": m.get("comment_count", 0) or 0,
                    "share_count": m.get("share_count", 0) or 0,  # May not exist in youtube_metrics
                })
                seen_pids.add(pid)
    
    if not latest_metrics:
        # No metrics found, set all to zero
        supabase.table("user_metrics").upsert({
            "u_id": u_id,
            "total_view_count": 0,
            "total_like_count": 0,
            "total_comment_count": 0,
            "total_share_count": 0,
            "avg_engagement_rate": 0,
            "updated_at": datetime.utcnow().isoformat()
        }).execute()
        return

    # 3. Aggregate totals
    total_views = sum(m.get("view_count", 0) or 0 for m in latest_metrics)
    total_likes = sum(m.get("like_count", 0) or 0 for m in latest_metrics)
    total_comments = sum(m.get("comment_count", 0) or 0 for m in latest_metrics)
    total_shares = sum(m.get("share_count", 0) or 0 for m in latest_metrics)
    
    # Calculate engagement rate (likes + comments + shares) / views * 100
    engagement_rates = []
    for m in latest_metrics:
        views = m.get("view_count", 0) or 0
        if views > 0:
            likes = m.get("like_count", 0) or 0
            comments = m.get("comment_count", 0) or 0
            shares = m.get("share_count", 0) or 0
            engagement = ((likes + comments + shares) / views) * 100
            engagement_rates.append(engagement)
    avg_engagement = sum(engagement_rates) / len(engagement_rates) if engagement_rates else 0

    # 4. Upsert into user_metrics
    supabase.table("user_metrics").upsert({
        "u_id": u_id,
        "total_view_count": total_views,
        "total_like_count": total_likes,
        "total_comment_count": total_comments,
        "total_share_count": total_shares,
        "avg_engagement_rate": avg_engagement,
        "updated_at": datetime.utcnow().isoformat()
    }).execute()


@st.cache_data(show_spinner=False)
def fetch_user_daily_timeseries(u_id: str, start_date_iso: str, end_date_iso: str) -> pd.DataFrame:
    """Return daily increments (not lifetime) aggregated across all user's videos.

    Works with either data shape in youtube_metrics:
    - cumulative per-day snapshots (typical API snapshots) → use positive day-over-day diff
    - daily increments already stored → use values directly
    """
    # Fetch project ids for user
    up_resp = supabase.table("user_projects").select("p_id").eq("u_id", u_id).execute()
    pids = [row["p_id"] for row in (up_resp.data or [])]
    if not pids:
        return pd.DataFrame(columns=["date", "views", "likes", "comments"]).astype({"date": "datetime64[ns]"})

    # Pull snapshots within window for these pids
    # Note: Supabase range filters are inclusive
    ym = supabase.table("youtube_metrics") \
        .select("p_id, fetched_at, view_count, like_count, comment_count") \
        .in_("p_id", pids) \
        .gte("fetched_at", start_date_iso) \
        .lte("fetched_at", end_date_iso) \
        .execute()
    rows = ym.data or []
    if not rows:
        return pd.DataFrame(columns=["date", "views", "likes", "comments"]).astype({"date": "datetime64[ns]"})

    df = pd.DataFrame(rows)
    # Normalize timestamps to date (UTC)
    df["fetched_at"] = pd.to_datetime(df["fetched_at"], utc=True, errors="coerce")
    df["date"] = df["fetched_at"].dt.tz_convert("UTC").dt.date

    # Keep last snapshot per video per day
    df_sorted = df.sort_values(["p_id", "date", "fetched_at"])  # ascending so last per group is last row
    last_per_day = df_sorted.groupby(["p_id", "date"], as_index=False).tail(1)

    # Compute per-video daily increments; detect whether values are cumulative or already daily
    last_per_day = last_per_day.sort_values(["p_id", "date"])  # ensure order
    increments = []
    for pid, group in last_per_day.groupby("p_id", as_index=False):
        g = group.copy()
        for col in ["view_count", "like_count", "comment_count"]:
            diff = g[col].diff().fillna(0)
            # Heuristic: if values are mostly non-decreasing across the period, treat as cumulative
            non_decreasing_ratio = (diff >= 0).mean()
            if non_decreasing_ratio >= 0.8:
                vals = diff
            else:
                # already daily values
                vals = g[col]
            vals = vals.clip(lower=0)
            g[col + "_inc"] = vals
        increments.append(g[["p_id", "date", "view_count_inc", "like_count_inc", "comment_count_inc"]])
    if not increments:
        return pd.DataFrame(columns=["date", "views", "likes", "comments"]).astype({"date": "datetime64[ns]"})
    inc_df = pd.concat(increments, ignore_index=True)

    # Aggregate across videos per day — daily increments
    agg = inc_df.groupby("date", as_index=False).agg({
        "view_count_inc": "sum",
        "like_count_inc": "sum",
        "comment_count_inc": "sum",
    }).rename(columns={
        "view_count_inc": "views",
        "like_count_inc": "likes",
        "comment_count_inc": "comments",
    })

    # Ensure full date index for selected range (fill missing days with zeros)
    start_dt = pd.to_datetime(start_date_iso).date()
    end_dt = pd.to_datetime(end_date_iso).date()
    all_days = pd.date_range(start=start_dt, end=end_dt, freq="D").date
    full = pd.DataFrame({"date": all_days})
    out = full.merge(agg, on="date", how="left")
    out = out.fillna({"views": 0, "likes": 0, "comments": 0})
    out["date"] = pd.to_datetime(out["date"])  # for chart x-axis
    return out



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

    # Always recalculate metrics on page load to ensure fresh data
    update_user_metrics(u_id)

    # Fetch updated metrics
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
        # Try latest_youtube_metrics first (preferred for real-time), fall back to youtube_metrics if table doesn't exist
        try:
            metrics_resp = supabase.table("latest_youtube_metrics").select("p_id, view_count, like_count, comment_count").in_("p_id", pids).execute()
            for m in (metrics_resp.data or []):
                pid = m["p_id"]
                metrics_map[pid] = {
                    "view_count": m.get("view_count", 0) or 0,
                    "like_count": m.get("like_count", 0) or 0,
                    "comment_count": m.get("comment_count", 0) or 0,
                }
        except Exception:
            # Fallback: query youtube_metrics and get the latest entry per project
            metrics_resp = supabase.table("youtube_metrics").select("p_id, view_count, like_count, comment_count, fetched_at").in_("p_id", pids).order("fetched_at", desc=True).execute()
            seen_pids = set()
            for m in (metrics_resp.data or []):
                pid = m["p_id"]
                if pid not in seen_pids:
                    metrics_map[pid] = {
                        "view_count": m.get("view_count", 0) or 0,
                        "like_count": m.get("like_count", 0) or 0,
                        "comment_count": m.get("comment_count", 0) or 0,
                    }
                    seen_pids.add(pid)

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

            # Insert metrics entry (fetched_at is timestamp, so duplicates unlikely, but check to be safe)
            fetched_at = datetime.utcnow().isoformat()
            existing_metrics = supabase.table("youtube_metrics").select("p_id").eq("p_id", video_data["p_id"]).eq("fetched_at", fetched_at).execute()
            if not existing_metrics.data:
                supabase.table("youtube_metrics").insert({
                    "p_id": video_data["p_id"],
                    "platform": "youtube",
                    "fetched_at": fetched_at,
                    "view_count": video_data["view_count"],
                    "like_count": video_data["like_count"],
                    "comment_count": video_data["comment_count"]
                }).execute()

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
            # Check if this role assignment already exists to prevent duplicates
            existing = supabase.table("user_projects").select("u_id").eq("u_id", u_id).eq("p_id", video_id).eq("u_role", role_name).execute()
            if not existing.data:
                # Insert only if it doesn't exist
                supabase.table("user_projects").insert({
                    "u_id": u_id,
                    "p_id": video_id,
                    "u_role": role_name
                }).execute()

        # Update user metrics after credits are added
        update_user_metrics(u_id)
        
        st.success(f"🎉 {name} is now credited for: {', '.join(st.session_state.selected_roles)}!")
        st.balloons()
        st.session_state.selected_roles = []
        st.rerun()  # Refresh page to show updated metrics

# -------------------------------
# PAGE 3 — HOME FEED
# -------------------------------
def show_home_page():
    st.title("Home")
    
    current_u_id = get_current_user_id()
    if not current_u_id:
        st.info("Please complete your profile to see your feed.")
        return
    
    # Get list of followed users
    followed_ids = get_following(supabase, current_u_id)
    
    if not followed_ids:
        st.info("Follow creators to see their updates here. Use the search bar above to discover and follow others!")
        return
    
    # Fetch recent activities from followed users
    # 1. Get recent projects from followed users (via user_projects)
    projects_res = supabase.table("user_projects").select(
        "p_id, u_id, created_at, projects(p_id, p_title, p_link, p_thumbnail_url, p_created_at)"
    ).in_("u_id", followed_ids).order("created_at", desc=True).limit(50).execute()
    
    # 2. Get recent metric updates (youtube_metrics for projects from followed users)
    # First get project IDs from followed users
    user_projects_res = supabase.table("user_projects").select("p_id, u_id").in_("u_id", followed_ids).execute()
    followed_project_ids = [up["p_id"] for up in (user_projects_res.data or [])]
    # Map project IDs to user IDs for metrics
    project_to_user = {up["p_id"]: up["u_id"] for up in (user_projects_res.data or [])}
    
    metric_updates = []
    if followed_project_ids:
        metrics_res = supabase.table("youtube_metrics").select(
            "p_id, fetched_at, projects(p_id, p_title, p_link, p_thumbnail_url, p_created_at)"
        ).in_("p_id", followed_project_ids).order("fetched_at", desc=True).limit(50).execute()
        
        # Process metrics: use project_to_user map to get u_id
        for m in (metrics_res.data or []):
            project = m.get("projects", {})
            p_id = m.get("p_id")
            if project and p_id and p_id in project_to_user:
                metric_updates.append({
                    "type": "metric_update",
                    "u_id": project_to_user[p_id],
                    "p_id": project.get("p_id"),
                    "p_title": project.get("p_title"),
                    "p_link": project.get("p_link"),
                    "p_thumbnail_url": project.get("p_thumbnail_url"),
                    "timestamp": m.get("fetched_at"),
                })
    
    # 3. Combine and format project activities
    project_activities = []
    for up in (projects_res.data or []):
        project = up.get("projects", {})
        if project:
            project_activities.append({
                "type": "new_project",
                "u_id": up.get("u_id"),
                "p_id": project.get("p_id"),
                "p_title": project.get("p_title"),
                "p_link": project.get("p_link"),
                "p_thumbnail_url": project.get("p_thumbnail_url"),
                "timestamp": project.get("p_created_at") or up.get("created_at"),
            })
    
    # 4. Combine all activities and deduplicate by project ID (keep most recent)
    all_activities = project_activities + metric_updates
    # Deduplicate: if same project appears multiple times, keep only the most recent entry
    activities_by_project = {}
    for activity in all_activities:
        p_id = activity.get("p_id")
        if p_id:
            # If we haven't seen this project, or this activity is more recent, keep it
            if p_id not in activities_by_project:
                activities_by_project[p_id] = activity
            else:
                # Compare timestamps - keep the more recent one
                existing_timestamp = activities_by_project[p_id].get("timestamp", "")
                current_timestamp = activity.get("timestamp", "")
                if current_timestamp > existing_timestamp:
                    activities_by_project[p_id] = activity
    
    # Convert back to list and sort by timestamp
    deduplicated_activities = list(activities_by_project.values())
    deduplicated_activities.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    
    # Limit to 10 most recent
    feed_items = deduplicated_activities[:10]
    
    if not feed_items:
        st.info("No recent activity from creators you follow.")
        return
    
    # Get user info for display (batch fetch)
    feed_user_ids = list(set(item["u_id"] for item in feed_items))
    users_res = supabase.table("users").select("u_id, u_name, u_email").in_("u_id", feed_user_ids).execute()
    users_map = {u["u_id"]: u for u in (users_res.data or [])}
    
    # Get project-specific metrics for each feed item (not user totals)
    feed_project_ids = [item["p_id"] for item in feed_items if item.get("p_id")]
    project_metrics_map = {}
    if feed_project_ids:
        # Try latest_youtube_metrics first (preferred for real-time), fall back to youtube_metrics if table doesn't exist
        try:
            metrics_res = supabase.table("latest_youtube_metrics").select("p_id, view_count").in_("p_id", feed_project_ids).execute()
            for m in (metrics_res.data or []):
                pid = m["p_id"]
                project_metrics_map[pid] = m.get("view_count", 0) or 0
        except Exception:
            # Fallback: query youtube_metrics and get the latest entry per project
            metrics_res = supabase.table("youtube_metrics").select("p_id, view_count, fetched_at").in_("p_id", feed_project_ids).order("fetched_at", desc=True).execute()
            seen_pids = set()
            for m in (metrics_res.data or []):
                pid = m["p_id"]
                if pid not in seen_pids:
                    project_metrics_map[pid] = m.get("view_count", 0) or 0
                    seen_pids.add(pid)
    
    # Display feed
    st.markdown("### Your Feed")
    st.caption(f"Recent activity from {len(followed_ids)} creator{'s' if len(followed_ids) != 1 else ''} you follow")
    
    for item in feed_items:
        user = users_map.get(item["u_id"], {})
        user_name = user.get("u_name", "Unknown Creator")
        avatar_url = f"https://api.dicebear.com/7.x/identicon/svg?seed={user_name}"
        # Get project-specific view count for this feed item
        project_views = project_metrics_map.get(item.get("p_id"), 0)
        activity_type = "New project" if item["type"] == "new_project" else "Metrics updated"
        timestamp = item.get("timestamp", "")
        
        # Parse and format timestamp
        try:
            if timestamp:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                time_ago = datetime.now(timezone.utc) - dt.replace(tzinfo=timezone.utc)
                if time_ago.days > 0:
                    time_str = f"{time_ago.days} day{'s' if time_ago.days != 1 else ''} ago"
                elif time_ago.seconds > 3600:
                    hours = time_ago.seconds // 3600
                    time_str = f"{hours} hour{'s' if hours != 1 else ''} ago"
                else:
                    mins = time_ago.seconds // 60
                    time_str = f"{mins} minute{'s' if mins != 1 else ''} ago" if mins > 0 else "Just now"
            else:
                time_str = "Recently"
        except:
            time_str = "Recently"
        
        # Feed card
        with st.container():
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            col1, col2 = st.columns([1, 5])
            with col1:
                st.image(avatar_url, width=50)
            with col2:
                st.markdown(f"**{user_name}** · {activity_type} · {time_str}")
                if item.get("p_title"):
                    st.markdown(f"[{item['p_title']}]({item.get('p_link', '#')})")
                if project_views > 0:
                    st.caption(f"Views: {project_views:,}")
            st.markdown("</div>", unsafe_allow_html=True)


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
    st.caption("Daily totals across all your credited videos (views, likes, comments).")

    # Identify user id
    user_res = supabase.table("users").select("u_id").eq("u_email", normalized_email).execute()
    if not user_res.data:
        st.info("No user record found. Add a credit to get started.")
        return
    u_id = user_res.data[0]["u_id"]

    # Controls: range only (daily metrics)
    col_a, col_b = st.columns([1, 2])
    with col_a:
        preset = st.radio("Range", ["Last 7 days", "Last 28 days", "Last 12 months", "Custom"], index=1)
    with col_b:
        today = datetime.now(timezone.utc).date()
        if preset == "Last 7 days":
            start_date = today - timedelta(days=6)
            end_date = today
        elif preset == "Last 28 days":
            start_date = today - timedelta(days=27)
            end_date = today
        elif preset == "Last 12 months":
            start_date = today - timedelta(days=364)
            end_date = today
        else:
            dates = st.date_input("Custom range", value=(today - timedelta(days=29), today))
            if isinstance(dates, tuple) and len(dates) == 2:
                start_date, end_date = dates
            else:
                st.warning("Select a start and end date.")
                return

    # Fetch data
    start_iso = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc).isoformat()
    end_iso = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc).isoformat()
    with st.spinner("Loading analytics..."):
        ts_df = fetch_user_daily_timeseries(u_id, start_iso, end_iso)
        # Fallback: if no rows (e.g., no snapshot today yet), try ending yesterday
        if ts_df.empty:
            end_date_fallback = end_date - timedelta(days=1)
            if end_date_fallback >= start_date:
                end_iso_fb = datetime.combine(end_date_fallback, datetime.max.time(), tzinfo=timezone.utc).isoformat()
                ts_df = fetch_user_daily_timeseries(u_id, start_iso, end_iso_fb)

    if ts_df.empty:
        st.info("No metrics yet. Once your AWS job runs, data will appear here.")
        return

    # Inform when data appears too sparse
    num_days = (end_date - start_date).days + 1
    if num_days >= 7 and (ts_df[["views", "likes", "comments"]].sum().sum() == 0):
        st.warning("We have a limited dataset right now; charts may look flat until more days pass.")

    # Metric definitions
    metric_options = ["Views", "Likes", "Comments"]
    metric_map = {
        "Views": "views",
        "Likes": "likes",
        "Comments": "comments",
    }
    
    # Track selected metric in session state
    if "selected_analytics_metric" not in st.session_state:
        st.session_state.selected_analytics_metric = "Views"
    
    # Calculate totals for all metrics
    metric_totals = {m: int(ts_df[metric_map[m]].sum()) for m in metric_options}
    
    # Row of metric cards (Spotify-style)
    metric_cols = st.columns(len(metric_options))
    button_keys = []
    
    for idx, metric in enumerate(metric_options):
        with metric_cols[idx]:
            is_selected = st.session_state.selected_analytics_metric == metric
            total = metric_totals[metric]
            button_key = f"metric_btn_{metric}"
            button_keys.append(button_key)
            
            # Card styling based on selection - lighter palette for readability
            if is_selected:
                card_bg = "#E0E0E0"  # Selected: darker grey but readable
                card_color = "#000000"  # Black text for contrast
                card_border = "2px solid #000000"
            else:
                card_bg = "#F5F5F5"  # Unselected: light grey
                card_color = "#000000"  # Black text
                card_border = "1px solid #E0E0E0"
            
            # Container with card and button
            card_id = f"metric_card_{metric.replace(' ', '_')}"
            st.markdown(f"""
            <div style="position: relative; margin-bottom: 8px;">
                <div id="{card_id}" style="
                    background-color: {card_bg};
                    color: {card_color};
                    border: {card_border};
                    border-radius: 8px;
                    padding: 16px 12px;
                    text-align: center;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                    transition: all 0.2s ease;
                    pointer-events: none;
                ">
                    <div style="font-size: 14px; font-weight: 600; margin-bottom: 4px; opacity: 0.9;">
                        {metric}
                    </div>
                    <div style="font-size: 20px; font-weight: 700;">
                        {total:,}
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Clickable button positioned over card
            if st.button(
                "",
                key=button_key,
                use_container_width=True,
            ):
                st.session_state.selected_analytics_metric = metric
                st.rerun()
    
    # Style all metric buttons to overlay their cards + add hover effects
    if button_keys:
        keys_str = ", ".join([f'button[key="{k}"]' for k in button_keys])
        # Collect unselected card IDs for hover
        unselected_cards = [
            f'#metric_card_{m.replace(" ", "_")}' 
            for m in metric_options 
            if m != st.session_state.selected_analytics_metric
        ]
        unselected_selector = ", ".join(unselected_cards) if unselected_cards else ""
        
        hover_css = f"""
        /* Hover effect for unselected metric cards */
        {unselected_selector} {{
            transition: background-color 0.2s ease !important;
        }}
        """ if unselected_selector else ""
        
        st.markdown(f"""
        <style>
        {keys_str} {{
            position: absolute !important;
            top: 0 !important;
            left: 0 !important;
            width: 100% !important;
            height: 80px !important;
            opacity: 0 !important;
            cursor: pointer !important;
            z-index: 10 !important;
        }}
        {hover_css}
        </style>
        <script>
        (function() {{
            const metrics = {json.dumps([m for m in metric_options if m != st.session_state.selected_analytics_metric])};
            metrics.forEach(metric => {{
                const metricKey = metric.replace(/ /g, '_');
                const btn = document.querySelector('button[key="metric_btn_' + metric + '"]');
                const card = document.getElementById('metric_card_' + metricKey);
                if (btn && card) {{
                    btn.addEventListener('mouseenter', () => {{
                        card.style.backgroundColor = '#EBEBEB';
                    }});
                    btn.addEventListener('mouseleave', () => {{
                        card.style.backgroundColor = '#F5F5F5';
                    }});
                }}
            }});
        }})();
        </script>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Get selected metric
    selected_metric = st.session_state.selected_analytics_metric
    metric_col = metric_map[selected_metric]
    metric_sum = metric_totals[selected_metric]

    # Chart: Spotify-style area chart with smooth line
    chart_df = ts_df.set_index("date")[[metric_col]].rename(columns={metric_col: selected_metric.lower()})
    
    # Apply smooth interpolation using rolling average for Spotify-like curves
    # Use a small window (3 days) to smooth without losing detail
    smoothed_values = chart_df[selected_metric.lower()].rolling(
        window=min(3, len(chart_df)), 
        min_periods=1,
        center=True
    ).mean()
    
    # Create Plotly area chart
    fig = go.Figure()
    
    # Add filled area trace with smoothed data
    fig.add_trace(go.Scatter(
        x=chart_df.index,
        y=smoothed_values,
        mode='lines',
        name=selected_metric,
        fill='tozeroy',
        fillcolor='rgba(66,133,244,0.2)',  # Soft translucent blue
        line=dict(
            color='rgba(66,133,244,1)',  # Solid blue line
            width=2.5
        ),
        hovertemplate='<b>%{fullData.name}</b><br>' +
                      '%{x|%b %d, %Y}<br>' +
                      '%{y:,.0f}<extra></extra>'
    ))
    
    # Update layout for Spotify-style aesthetics
    fig.update_layout(
        height=320,
        showlegend=False,
        margin=dict(l=0, r=0, t=0, b=0),
        hovermode='x unified',
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(
            showgrid=True,
            gridcolor='rgba(0,0,0,0.1)',
            showline=False,
            zeroline=False
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(0,0,0,0.1)',
            showline=False,
            zeroline=False
        ),
        font=dict(
            family='-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif',
            size=12,
            color='#111111'
        )
    )
    
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # Previous period comparison for selected metric
    period_days = (end_date - start_date).days + 1
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=period_days - 1)
    prev_start_iso = datetime.combine(prev_start, datetime.min.time(), tzinfo=timezone.utc).isoformat()
    prev_end_iso = datetime.combine(prev_end, datetime.max.time(), tzinfo=timezone.utc).isoformat()
    prev_df = fetch_user_daily_timeseries(u_id, prev_start_iso, prev_end_iso)
    prev_sum = int(prev_df[metric_col].sum()) if not prev_df.empty else 0
    
    def pct(curr: int, prev: int) -> str:
        if prev == 0:
            return "–"
        return f"{((curr - prev)/prev)*100:.1f}%"
    
    delta = metric_sum - prev_sum
    delta_pct = pct(metric_sum, prev_sum)
    delta_color = "green" if delta >= 0 else "red"
    
    st.caption(
        f"**{selected_metric}** — Δ vs previous {period_days}d: <span style='color: {delta_color}; font-weight: 600;'>{delta:+,} ({delta_pct})</span>",
        unsafe_allow_html=True
    )

    # Peak day for selected metric
    if not ts_df.empty and ts_df[metric_col].max() > 0:
        peak_row = ts_df.loc[ts_df[metric_col].idxmax()]
        peak_date = peak_row["date"].date()
        peak_value = int(peak_row[metric_col])
        st.caption(f"Peak day: **{peak_date}** with **{peak_value:,} {selected_metric.lower()}**")


def show_settings_page():
    st.title("Settings")
    st.info("Profile editing and preferences coming soon.")


# -------------------------------
# SEARCH COMPONENTS
# -------------------------------
def render_search_result_item(user: dict, current_u_id: str):
    """Render a single search result item in the dropdown."""
    avatar_url = f"https://api.dicebear.com/7.x/identicon/svg?seed={user.get('u_name', 'user')}"
    is_following_user = user.get("is_following", False)
    total_views = user.get("total_views", 0)
    bio = user.get("u_bio", "")
    
    # Determine meta text (bio or views)
    meta_text = bio if bio else f"{total_views:,} views" if total_views > 0 else "No metrics yet"
    if len(meta_text) > 60:
        meta_text = meta_text[:57] + "..."
    
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown(f"""
            <div class='search-result-item'>
                <img src='{avatar_url}' class='search-result-avatar' />
                <div class='search-result-content'>
                    <div class='search-result-name'>{user.get('u_name', 'Unknown')}</div>
                    <div class='search-result-meta'>{meta_text}</div>
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        button_label = "Unfollow" if is_following_user else "Follow"
        button_kind = "secondary" if is_following_user else "primary"
        if st.button(button_label, key=f"search_follow_{user['u_id']}", use_container_width=True):
            try:
                if is_following_user:
                    unfollow_user(supabase, current_u_id, user["u_id"])
                    st.success(f"Unfollowed {user.get('u_name', 'user')}")
                else:
                    follow_user(supabase, current_u_id, user["u_id"])
                    st.success(f"Following {user.get('u_name', 'user')}")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {str(e)}")


def render_search_dropdown(search_query: str, current_u_id: str):
    """Render search dropdown with results."""
    if not search_query or len(search_query.strip()) < 1:
        return
    
    users = search_users(supabase, search_query, current_u_id)
    
    if not users:
        st.markdown("""
            <div class='search-dropdown'>
                <div style='padding:16px;text-align:center;color:#666;'>No users found</div>
            </div>
        """, unsafe_allow_html=True)
        return
    
    # Render dropdown with results
    st.markdown('<div class="search-dropdown">', unsafe_allow_html=True)
    for user in users:
        render_search_result_item(user, current_u_id)
    st.markdown('</div>', unsafe_allow_html=True)


# -------------------------------
# TOP BAR (avatar + notifications + search)
# -------------------------------
def show_topbar():
    """Render top navigation bar with integrated search."""
    current_u_id = get_current_user_id()
    
    # Initialize search query in session state if not present
    if "search_query" not in st.session_state:
        st.session_state.search_query = ""
    
    # Topbar HTML with search integrated
    st.markdown("""
        <div class='topnav'>
          <div class='brand'>Credify</div>
          <div class='actions'>
            <span>💬</span>
            <span>🔔</span>
            <span class='avatar'></span>
          </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Search container positioned below topbar (in fixed wrapper)
    if current_u_id:
        st.markdown('<div class="search-wrapper">', unsafe_allow_html=True)
        st.markdown('<div class="search-container">', unsafe_allow_html=True)
        search_input = st.text_input(
            "Search users",
            value=st.session_state.search_query,
            key="topbar_search",
            placeholder="Search by name or email...",
            label_visibility="collapsed"
        )
        
        # Update session state on input change
        if search_input != st.session_state.search_query:
            st.session_state.search_query = search_input
        
        # Show dropdown if there's a query
        if st.session_state.search_query:
            render_search_dropdown(st.session_state.search_query, current_u_id)
        
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

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
