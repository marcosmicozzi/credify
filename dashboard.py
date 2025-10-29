import streamlit as st
from supabase import create_client, Client

# --- Initialize Supabase ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Credify Dashboard", layout="wide")
st.title("🌟 Creator Dashboard")

# --- Theme Switcher ---
theme = st.radio("Display mode:", ["Light", "Dark"], horizontal=True)

if theme == "Light":
    bg_color = "#f9f9f9"
    text_color = "#111111"
    card_color = "#ffffff"
    secondary_text = "#555555"
    accent_color = "#2563eb"
else:
    bg_color = "#0d1117"             # app background
    text_color = "#e2e8f0"           # main text (bright gray)
    card_color = "#161b22"           # cards and inputs
    secondary_text = "#a1a1aa"       # soft gray text
    accent_color = "#10b981"         # teal green accent

# --- Global Theme CSS ---
st.markdown(f"""
    <style>
    html, body, [class*="stApp"] {{
        background-color: {bg_color} !important;
        color: {text_color} !important;
        font-family: 'Inter', sans-serif;
    }}

    /* Force all Streamlit elements to use readable colors */
    h1, h2, h3, h4, h5, h6, p, span, label, div, input, textarea {{
        color: {text_color} !important;
    }}

    /* Inputs */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {{
        background-color: {card_color} !important;
        color: {text_color} !important;
        border: 1px solid #333333 !important;
    }}

    /* Buttons & radio labels */
    .stRadio > div, .stButton button {{
        color: {text_color} !important;
    }}

    /* Main layout container */
    .block-container {{
        background-color: {bg_color} !important;
        color: {text_color} !important;
        padding-top: 2rem !important;
        border-radius: 8px;
    }}

    /* Project cards */
    .project-card {{
        background-color: {card_color};
        border-radius: 14px;
        padding: 14px;
        margin-bottom: 25px;
        box-shadow: 0px 2px 10px rgba(0,0,0,0.25);
        transition: all 0.25s ease-in-out;
    }}
    .project-card:hover {{
        transform: translateY(-4px);
        box-shadow: 0px 4px 18px rgba(0,0,0,0.4);
    }}
    .project-thumb {{
        border-radius: 10px;
    }}

    /* Links */
    a {{
        color: {accent_color} !important;
        text-decoration: none !important;
        font-weight: 500;
    }}
    a:hover {{
        text-decoration: underline !important;
    }}

    /* Metric cards */
    .stMetric {{
        background-color: {card_color} !important;
        border-radius: 12px !important;
        padding: 10px !important;
        text-align: center !important;
        color: {text_color} !important;
    }}
    .stMetric label {{
        color: {secondary_text} !important;
    }}

    /* Info messages */
    .stAlert {{
        background-color: {card_color} !important;
        color: {text_color} !important;
        border-left: 4px solid {accent_color} !important;
    }}
    </style>
""", unsafe_allow_html=True)

# --- User Email Input ---
email = st.text_input("Enter your email to load your dashboard:")

if email:
    # --- Fetch user ---
    user_res = supabase.table("users").select("*").eq("u_email", email).execute()
    if not user_res.data:
        st.error("❌ No user found with this email.")
        st.stop()

    user = user_res.data[0]
    u_id = user["u_id"]

    # --- Fetch metrics summary ---
    metrics_res = supabase.table("user_metrics").select("*").eq("u_id", u_id).execute()
    metrics = metrics_res.data[0] if metrics_res.data else {
        "total_view_count": 0,
        "total_like_count": 0,
        "total_comment_count": 0,
        "total_share_count": 0,
        "avg_engagement_rate": 0
    }

    # --- Profile Header ---
    st.markdown("### 👤 Profile Overview")
    col1, col2 = st.columns([1, 3])
    with col1:
        st.image(f"https://api.dicebear.com/7.x/identicon/svg?seed={user['u_name']}", width=100)
    with col2:
        st.subheader(user["u_name"] or "Unnamed User")
        st.write(f"📧 {user['u_email']}")
        if user.get("u_bio"):
            st.caption(user["u_bio"])

    st.divider()

    # --- Metrics Overview ---
    st.markdown("### 📊 Performance Summary")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Views", f"{metrics['total_view_count']:,}")
    col2.metric("Likes", f"{metrics['total_like_count']:,}")
    col3.metric("Comments", f"{metrics['total_comment_count']:,}")
    col4.metric("Shares", f"{metrics['total_share_count']:,}")
    col5.metric("Engagement Rate", f"{metrics['avg_engagement_rate']:.2f}%")

    st.divider()

    # --- Projects Section ---
    st.markdown("### 🎬 Your Projects")

    query = """
        projects(p_id, p_title, p_link, p_thumbnail_url),
        u_role
    """
    projects_response = supabase.table("user_projects").select(query).eq("u_id", u_id).execute()
    projects_data = {p["projects"]["p_id"]: p for p in projects_response.data}.values()

    # Sort by views
    projects_sorted = []
    for record in projects_data:
        project = record["projects"]
        role = record["u_role"]
        metrics_response = supabase.table("latest_metrics").select("view_count").eq("p_id", project["p_id"]).execute()
        views = metrics_response.data[0]["view_count"] if metrics_response.data else 0
        projects_sorted.append({**project, "role": role, "view_count": views})
    projects_sorted = sorted(projects_sorted, key=lambda x: x["view_count"], reverse=True)

    if not projects_sorted:
        st.info("You haven't been credited on any projects yet.")
    else:
        cols = st.columns(3)
        for i, project in enumerate(projects_sorted):
            with cols[i % 3]:
                st.markdown("<div class='project-card'>", unsafe_allow_html=True)
                st.image(project["p_thumbnail_url"], use_container_width=True)
                st.markdown(
                    f"**[{project['p_title']}]({project['p_link']})**  \n🎭 *{project['role']}*",
                    unsafe_allow_html=True
                )
                st.caption(f"👁️ {project['view_count']:,} views")
                st.markdown("</div>", unsafe_allow_html=True)

else:
    st.info("👆 Enter your email above to view your personalized dashboard.")
