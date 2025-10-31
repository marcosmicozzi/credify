"""Supabase utility functions for social features (follow/unfollow, search)."""
from typing import List
from supabase import Client


def get_following(supabase: Client, u_id: str) -> List[str]:
    """Get list of user IDs that the given user is following.
    
    Args:
        supabase: Supabase client instance
        u_id: User ID to get following list for
        
    Returns:
        List of followed user IDs
    """
    res = supabase.table("user_follows").select("followed_id").eq("follower_id", u_id).execute()
    return [row["followed_id"] for row in (res.data or [])]


def is_following(supabase: Client, follower_id: str, followed_id: str) -> bool:
    """Check if follower_id is following followed_id.
    
    Args:
        supabase: Supabase client instance
        follower_id: User ID of the follower
        followed_id: User ID of the user being followed
        
    Returns:
        True if following relationship exists, False otherwise
    """
    res = supabase.table("user_follows").select("follower_id").eq("follower_id", follower_id).eq("followed_id", followed_id).execute()
    return len(res.data or []) > 0


def follow_user(supabase: Client, follower_id: str, followed_id: str) -> None:
    """Create a follow relationship.
    
    Args:
        supabase: Supabase client instance
        follower_id: User ID of the follower
        followed_id: User ID of the user to follow
        
    Raises:
        Exception: If follow relationship creation fails (e.g., duplicate, invalid IDs)
    """
    # Check if already following to avoid duplicate key errors
    if is_following(supabase, follower_id, followed_id):
        return
    
    supabase.table("user_follows").insert({
        "follower_id": follower_id,
        "followed_id": followed_id
    }).execute()


def unfollow_user(supabase: Client, follower_id: str, followed_id: str) -> None:
    """Remove a follow relationship.
    
    Args:
        supabase: Supabase client instance
        follower_id: User ID of the follower
        followed_id: User ID of the user to unfollow
    """
    supabase.table("user_follows").delete().eq("follower_id", follower_id).eq("followed_id", followed_id).execute()


def search_users(supabase: Client, query: str, current_u_id: str) -> List[dict]:
    """Search users by name or email (case-insensitive), excluding self.
    
    Args:
        supabase: Supabase client instance
        query: Search query string
        current_u_id: Current user ID to exclude from results
        
    Returns:
        List of user dictionaries with follow status included
    """
    if not query or len(query.strip()) < 1:
        return []
    
    query_clean = query.strip()
    
    # Search by name (ilike for case-insensitive partial match)
    name_results = supabase.table("users").select("u_id, u_name, u_email, u_bio").ilike("u_name", f"%{query_clean}%").neq("u_id", current_u_id).limit(20).execute()
    
    # Search by email (ilike for case-insensitive partial match)
    email_results = supabase.table("users").select("u_id, u_name, u_email, u_bio").ilike("u_email", f"%{query_clean}%").neq("u_id", current_u_id).limit(20).execute()
    
    # Combine and deduplicate by u_id
    seen_ids = set()
    users = []
    for row in (name_results.data or []) + (email_results.data or []):
        uid = row["u_id"]
        if uid not in seen_ids:
            seen_ids.add(uid)
            users.append(row)
    
    # Limit to 20 total results
    users = users[:20]
    
    # Get follow status for each user
    if users:
        user_ids = [u["u_id"] for u in users]
        follow_res = supabase.table("user_follows").select("followed_id").eq("follower_id", current_u_id).in_("followed_id", user_ids).execute()
        followed_ids = {row["followed_id"] for row in (follow_res.data or [])}
        
        # Add follow status to each user dict
        for user in users:
            user["is_following"] = user["u_id"] in followed_ids
        
        # Fetch user_metrics for total views if available
        metrics_res = supabase.table("user_metrics").select("u_id, total_view_count").in_("u_id", user_ids).execute()
        metrics_map = {m["u_id"]: m.get("total_view_count", 0) or 0 for m in (metrics_res.data or [])}
        
        for user in users:
            user["total_views"] = metrics_map.get(user["u_id"], 0)
    
    return users

