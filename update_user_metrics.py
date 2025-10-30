import streamlit as st
from supabase import create_client
from datetime import datetime
import os

# --- Read secrets from .streamlit/secrets.toml ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Helper Function ---
def update_user_metrics(u_email: str):
    """Recalculate total metrics for a given user based on all their projects."""
    # 1. Find the user
    user_resp = supabase.table("users").select("u_id").eq("u_email", u_email).execute()
    if not user_resp.data:
        print(f"❌ No user found for {u_email}")
        return
    u_id = user_resp.data[0]["u_id"]

    # 2. Find all project IDs for this user
    projects_resp = supabase.table("user_projects").select("p_id").eq("u_id", u_id).execute()
    project_ids = [p["p_id"] for p in projects_resp.data]
    if not project_ids:
        print(f"⚠️ No projects linked to user {u_email}")
        return

    # 3. Get latest metrics for each project
    metrics_resp = supabase.table("latest_metrics").select("*").in_("p_id", project_ids).execute()
    if not metrics_resp.data:
        print(f"⚠️ No metrics found for user's projects")
        return

    # 4. Aggregate totals
    total_views = sum(m.get("view_count", 0) or 0 for m in metrics_resp.data)
    total_likes = sum(m.get("like_count", 0) or 0 for m in metrics_resp.data)
    total_comments = sum(m.get("comment_count", 0) or 0 for m in metrics_resp.data)
    total_shares = sum(m.get("share_count", 0) or 0 for m in metrics_resp.data)
    engagement_rates = [m.get("engagement_rate", 0) or 0 for m in metrics_resp.data]
    avg_engagement = sum(engagement_rates) / len(engagement_rates) if engagement_rates else 0

    # 5. Upsert into user_metrics
    supabase.table("user_metrics").upsert({
        "u_id": u_id,
        "total_view_count": total_views,
        "total_like_count": total_likes,
        "total_comment_count": total_comments,
        "total_share_count": total_shares,
        "avg_engagement_rate": avg_engagement,
        "updated_at": datetime.utcnow().isoformat()
    }).execute()

    print(f"✅ Updated metrics for {u_email}")


# --- TEST CALL ---
if __name__ == "__main__":
    # Replace this with your actual email for testing
    test_email = "micozzimarcos@gmail.com"
    update_user_metrics(test_email)