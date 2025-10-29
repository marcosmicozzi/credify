import streamlit as st
from supabase import create_client, Client

# -----------------------------
# --- Initialize Supabase ---
# -----------------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Credify", layout="wide", initial_sidebar_state="expanded")

# -----------------------------
# --- THEME SETTINGS ---
# -----------------------------
def set_app_theme(mode):
    if mode == "Dark":
        st.markdown("""
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&family=Space+Grotesk:wght@400;600&family=IBM+Plex+Mono&display=swap" rel="stylesheet">
            <style>
            header {visibility: hidden;}
            .block-container {
                padding-top: 1rem;
                padding-bottom: 0rem;
                padding-left: 3rem;
                padding-right: 3rem;
            }
            body, .stApp {
                background-color: #0B0C10 !important;
                color: #F2F4F8 !important;
                font-family: 'Inter', sans-serif;
            }
            h1, h2, h3, h4, h5 {
                font-family: 'Space Grotesk', sans-serif;
                letter-spacing: -0.5px;
                color: #FFFFFF !important;
            }
            .stSidebar {
                background-color: #111418 !important;
                color: #E8E8E8 !important;
            }
            a {
                color: #1DB954 !important;
                text-decoration: none;
            }
            .stTextInput>div>div>input {
                background-color: #1C1F24 !important;
                color: #F2F4F8 !important;
                border: 1px solid #333 !important;
            }
            .project-card {
                background-color: #181C20;
                border-radius: 10px;
                padding: 10px;
                margin-bottom: 16px;
                box-shadow: 0 2px 12px rgba(0,0,0,0.5);
            }
            .project-card:hover {
                transform: translateY(-3px);
                box-shadow: 0 4px 16px rgba(0,0,0,0.6);
            }
            .mono {
                font-family: 'IBM Plex Mono', monospace;
                font-size: 0.9rem;
                color: #9BD4A1 !important;
            }
            </style>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&family=Space+Grotesk:wght@400;600&family=IBM+Plex+Mono&display=swap" rel="stylesheet">
            <style>
            header {visibility: hidden;}
            .block-container {
                padding-top: 1rem;
                padding-bottom: 0rem;
                padding-left: 3rem;
                padding-right: 3rem;
            }
            body, .stApp {
                background-color: #FFFFFF !important;
                color: #222 !important;
                font-family: 'Inter', sans-serif;
            }
            h1, h2, h3, h4, h5 {
                font-family: 'Space Grotesk', sans-serif;
                letter-spacing: -0.5px;
                color: #111 !important;
            }
            .stSidebar {
                background-color: #F8F8F8 !important;
                color: #111 !important;
            }
            a {
                color: #0B5FFF !important;
                text-decoration: none;
            }
            .project-card {
                background-color: #F9F9F9;
                border-radius: 10px;
                padding: 10px;
                margin-bottom: 16px;
                box-shadow: 0 1px 5px rgba(0,0,0,0.1);
            }
            .mono {
                font-family: 'IBM Plex Mono', monospace;
                font-size: 0.9rem;
                color: #333 !important;
            }
            </style>
        """, unsafe_allow_html=True)

# -----------------------------
# --- SIDEBAR LAYOUT ---
# -----------------------------
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/727/727245.png", width=30)
st.sidebar.markdown("## Credify")

menu = st.sidebar.radio(" ", ["Profile", "Claim Credits", "Explore"], label_visibility="collapsed")

# -----------------------------
# --- SETTINGS PANEL ---
# -----------------------------
with st.sidebar.expander("⚙️ Settings"):
    display_mode = st.radio("Display mode:", ["Light", "Dark"], index=1, horizontal=True)
set_app_theme(display_mode)

# -----------------------------
# --- PROFILE PAGE ---
# -----------------------------
if menu == "Profile":
    st.title("👤 Marcos Micozzi")

    # Fetch user from Supabase (temporary until login system)
    user_res = supabase.table("users").select("*").eq("u_email", "micozzimarcos@gmail.com").execute()
    if not user_res.data:
        st.error("User not found in database.")
    else:
        user = user_res.data[0]
        u_id = user["u_id"]

        # Fetch metrics summary
        metrics_res = supabase.table("user_metrics").select("*").eq("u_id", u_id).execute()
        metrics = metrics_res.data[0] if metrics_res.data else {
            "total_view_count": 0,
            "total_like_count": 0,
            "total_comment_count": 0,
            "total_share_count": 0,
            "avg_engagement_rate": 0
        }

        # Profile Header
        col1, col2 = st.columns([1, 3])
        with col1:
            st.image("https://api.dicebear.com/7.x/identicon/svg?seed=" + user["u_name"], width=100)
        with col2:
            st.subheader(user["u_name"])
            st.caption(user["u_email"])

        st.divider()

        # Metrics Summary
        st.markdown("### 📊 Performance Summary")
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Views", f"{metrics['total_view_count']:,}")
        col2.metric("Likes", f"{metrics['total_like_count']:,}")
        col3.metric("Comments", f"{metrics['total_comment_count']:,}")
        col4.metric("Shares", f"{metrics['total_share_count']:,}")
        col5.metric("Engagement Rate", f"{metrics['avg_engagement_rate']:.2f}%")

        st.divider()

        # Projects Section
        st.markdown("### 🎬 Your Projects")
        projects_response = supabase.table("user_projects") \
            .select("projects(p_id, p_title, p_link, p_thumbnail_url), u_role") \
            .eq("u_id", u_id) \
            .execute()

        if not projects_response.data:
            st.info("You haven't been credited on any projects yet.")
        else:
            # Deduplicate projects (some users have multiple roles)
            unique_projects = {}
            for record in projects_response.data:
                project = record["projects"]
                pid = project["p_id"]
                if pid not in unique_projects:
                    unique_projects[pid] = {
                        "p_title": project["p_title"],
                        "p_link": project["p_link"],
                        "p_thumbnail_url": project["p_thumbnail_url"],
                        "roles": [record["u_role"]]
                    }
                else:
                    unique_projects[pid]["roles"].append(record["u_role"])

            # Fetch metrics & sort by most viewed
            enriched_projects = []
            for pid, data in unique_projects.items():
                m = supabase.table("latest_metrics").select("view_count, like_count, comment_count").eq("p_id", pid).execute()
                if m.data:
                    data.update(m.data[0])
                else:
                    data.update({"view_count": 0, "like_count": 0, "comment_count": 0})
                enriched_projects.append(data)

            enriched_projects.sort(key=lambda x: x["view_count"], reverse=True)

            # Display grid
            cols = st.columns(3)
            for i, p in enumerate(enriched_projects):
                with cols[i % 3]:
                    st.markdown("<div class='project-card'>", unsafe_allow_html=True)
                    st.image(p["p_thumbnail_url"], use_container_width=True)
                    st.markdown(f"**[{p['p_title']}]({p['p_link']})**")
                    st.caption("🎭 " + ", ".join(p["roles"]))
                    st.caption(f"👁️ {p['view_count']} | 👍 {p['like_count']} | 💬 {p['comment_count']}")
                    st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------
# --- CLAIM PAGE ---
# -----------------------------
elif menu == "Claim Credits":
    st.title("🎧 Claim Credits")
    st.info("Here you’ll be able to verify and add your roles to existing projects.")

# -----------------------------
# --- EXPLORE PAGE ---
# -----------------------------
elif menu == "Explore":
    st.title("🌍 Explore")
    st.info("Discover trending projects, collaborators, and stats from across the platform.")
