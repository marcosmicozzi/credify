# Code Review: Metrics Handling in Credify

**Date:** 2025-10-31  
**Focus:** Architecture and implementation of `youtube_metrics` and `youtube_latest_metrics` usage

---

## Executive Summary

The metrics system follows a reasonable two-tier architecture (historical + latest), but there are **critical inconsistencies** and **missing automation** that could lead to stale data and performance issues. Key concerns:

1. **Table naming inconsistency** between code paths
2. **No automatic triggers** - `user_metrics` updates are manual
3. **Inefficient fallback logic** that queries entire history
4. **Potential race conditions** on profile page reloads
5. **No database view/trigger** documented for `youtube_latest_metrics`

---

## 1. Metrics Flow & Architecture

### Current Implementation

**`youtube_metrics` (Historical Table)**
- ✅ Acts as full historical dataset (every daily snapshot per video)
- ✅ Stores `p_id`, `fetched_at`, `view_count`, `like_count`, `comment_count`, `platform`
- ✅ Populated by AWS Lambda daily job (one row per `p_id` per day)
- ✅ Used for analytics time-series queries (`fetch_user_daily_timeseries`)

**`youtube_latest_metrics` (Latest Snapshot View)**
- ⚠️ **ISSUE**: Table name inconsistency in codebase
  - Code references: `latest_youtube_metrics` (lines 287, 522, 787)
  - Script references: `youtube_latest_metrics` (`scripts/update_user_metrics.py:31`)
  - Readme references: `latest_metrics` (generic, unclear)
- ❓ **UNKNOWN**: Implementation details not visible in codebase
  - Assumed to be a PostgreSQL view or materialized view using `DISTINCT ON (p_id) ORDER BY fetched_at DESC`
  - **No schema definition found** in codebase
  - **No SQL migration files** or documentation

### Assessment

```266:347:credify_app.py
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
```

**Findings:**
- ✅ Correct preference for `latest_youtube_metrics` when available
- ✅ Fallback logic handles missing view gracefully
- ❌ **Inconsistent table name**: Should standardize on either `latest_youtube_metrics` or `youtube_latest_metrics`
- ⚠️ **Performance concern**: Fallback queries entire `youtube_metrics` table with `ORDER BY fetched_at DESC`, then filters client-side. This could be slow for users with many videos.

### Recommendations

1. **Standardize table name** - Choose one naming convention and use it everywhere
2. **Document expected schema** - Create a SQL migration file or schema documentation
3. **Validate view exists** - Add a check/validation that `youtube_latest_metrics` is properly configured
4. **Improve fallback query** - Use a more efficient pattern:
   ```sql
   SELECT DISTINCT ON (p_id) p_id, view_count, like_count, comment_count
   FROM youtube_metrics
   WHERE p_id = ANY($1::text[])
   ORDER BY p_id, fetched_at DESC
   ```

---

## 2. Data Retrieval & Update Logic

### Profile Page Reload Flow

```432:475:credify_app.py
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
```

**Findings:**
- ✅ Profile page correctly queries `user_metrics` (aggregated totals)
- ✅ Calls `update_user_metrics()` on every page load to ensure freshness
- ⚠️ **Performance concern**: Recalculating on every page load is expensive
- ❌ **No automatic sync**: No database trigger to update `user_metrics` when `youtube_metrics` changes

### Project Cards Metrics Display

```516:542:credify_app.py
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
```

**Findings:**
- ✅ Correctly uses `latest_youtube_metrics` for per-video metrics
- ✅ Batch fetching (no N+1 queries)
- ✅ Same fallback pattern (with same performance concerns)

### Home Feed Metrics

```784:799:credify_app.py
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
```

**Findings:**
- ✅ Consistent pattern across all pages
- ⚠️ Only fetches `view_count` for feed (could add likes/comments later)

### Update Mechanism Analysis

**Current Flow:**
1. AWS Lambda inserts into `youtube_metrics` ✅
2. **Missing**: No trigger to update `youtube_latest_metrics` (if it's a materialized view, needs refresh)
3. **Missing**: No trigger to automatically update `user_metrics`
4. Profile page manually calls `update_user_metrics()` on load ⚠️

**Issues:**
- ❌ **No automatic sync**: If a user doesn't visit their profile, `user_metrics` stays stale
- ❌ **Race condition potential**: Multiple profile page loads could trigger concurrent `update_user_metrics()` calls
- ⚠️ **Lambda job doesn't trigger updates**: When Lambda inserts new metrics, `user_metrics` is not automatically updated

### Recommendations

1. **Add database trigger** to update `user_metrics` when `youtube_metrics` is inserted:
   ```sql
   CREATE OR REPLACE FUNCTION update_user_metrics_on_metric_insert()
   RETURNS TRIGGER AS $$
   BEGIN
     -- Recalculate user_metrics for all users who have this p_id
     -- (Call update_user_metrics logic via PL/pgSQL or a stored procedure)
     RETURN NEW;
   END;
   $$ LANGUAGE plpgsql;
   
   CREATE TRIGGER trigger_update_user_metrics
   AFTER INSERT ON youtube_metrics
   FOR EACH ROW
   EXECUTE FUNCTION update_user_metrics_on_metric_insert();
   ```

2. **Cache `user_metrics` updates**: Only recalculate if `youtube_metrics` has been updated since last `user_metrics.updated_at`

3. **Add lock/mutex** to prevent concurrent `update_user_metrics()` calls

4. **Consider background job**: Instead of updating on page load, run a periodic job to refresh `user_metrics`

---

## 3. Automation & Data Freshness

### AWS Lambda Daily Job

```1:59:aws/get_youtube_metrics/get_youtube_metrics.py
import os
import json
import requests
from datetime import datetime

def lambda_handler(event, context):
    SUPABASE_URL = os.environ['SUPABASE_URL']
    SUPABASE_KEY = os.environ['SUPABASE_KEY']
    YOUTUBE_API_KEY = os.environ['YOUTUBE_API_KEY']
    VIDEO_IDS_ENV = os.environ.get("YOUTUBE_VIDEO_IDS", "")

    # Use environment variable or default to manual example
    video_ids = [v.strip() for v in VIDEO_IDS_ENV.split(",") if v.strip()] or ["3zKwIqxLTd4"]

    print(f"Fetched {len(video_ids)} videos")

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

    for vid in video_ids:
        # Fetch video metrics from YouTube Data API
        yt_response = requests.get(
            f"https://www.googleapis.com/youtube/v3/videos?part=statistics&id={vid}&key={YOUTUBE_API_KEY}"
        )
        yt_response.raise_for_status()
        data = yt_response.json()

        if not data.get("items"):
            print(f"No data found for video {vid}")
            continue

        stats = data["items"][0]["statistics"]
        view_count = int(stats.get("viewCount", 0))
        like_count = int(stats.get("likeCount", 0))
        comment_count = int(stats.get("commentCount", 0))

        # Create payload for Supabase
        payload = {
            "p_id": vid,  # ✅ matches your Supabase schema
            "platform": "youtube",
            "fetched_at": datetime.utcnow().isoformat(),
            "view_count": view_count,
            "like_count": like_count,
            "comment_count": comment_count
        }

        # Insert into Supabase youtube_metrics
        supabase_response = requests.post(
            f"{SUPABASE_URL}/rest/v1/youtube_metrics",
            headers=headers,
            data=json.dumps(payload)
        )

        print("Supabase response:", supabase_response.status_code, supabase_response.text)

    return {"success": True, "count": len(video_ids)}
```

**Findings:**
- ✅ Lambda correctly inserts into `youtube_metrics` with `fetched_at` timestamp
- ✅ One row per video per day (assuming daily execution)
- ❌ **Missing**: Does not update `youtube_latest_metrics` (if materialized view, needs `REFRESH`)
- ❌ **Missing**: Does not trigger `user_metrics` updates
- ⚠️ **No deduplication**: If Lambda runs twice in a day, creates duplicate rows (relies on app-level check in claim flow)

### Profile Reload Freshness

**Current Behavior:**
- ✅ Profile page calls `update_user_metrics()` on every load
- ✅ Reads from `user_metrics` after update
- ⚠️ **Inefficient**: Recalculates even if data hasn't changed

**Freshness Guarantee:**
- ✅ Profile page will show fresh data (if user visits after Lambda runs)
- ❌ **Stale until visit**: If Lambda runs at 07:45 UTC and user visits at 08:00 UTC, data is fresh. But if user doesn't visit for days, data stays stale.

### Recommendations

1. **Add trigger to Lambda job**: After inserting metrics, trigger `user_metrics` recalculation for affected users
2. **Materialized view refresh**: If `youtube_latest_metrics` is materialized, add `REFRESH` to Lambda job
3. **Add upsert logic**: Use `ON CONFLICT` in Lambda to prevent duplicate same-day inserts:
   ```sql
   INSERT INTO youtube_metrics (p_id, fetched_at, ...)
   VALUES (...)
   ON CONFLICT (p_id, DATE(fetched_at)) DO UPDATE SET ...
   ```

---

## 4. Performance Considerations

### Query Patterns

**Good Practices Found:**
- ✅ Batch fetching with `in_("p_id", pids)` to avoid N+1 queries
- ✅ Caching with `@st.cache_data` for `get_user_id_by_email_cached()`

**Performance Issues:**

1. **Inefficient Fallback Query**
   ```python
   # Current fallback (line 291):
   metrics_resp = supabase.table("youtube_metrics")
       .select("p_id, view_count, like_count, comment_count, fetched_at")
       .in_("p_id", project_ids)
       .order("fetched_at", desc=True)
       .execute()
   # Then filters client-side with seen_pids set
   ```
   **Problem**: Orders entire result set, then filters client-side. For users with 100 videos and 365 days of history, this fetches 36,500 rows and sorts them.

   **Better approach**: Use PostgreSQL `DISTINCT ON`:
   ```sql
   SELECT DISTINCT ON (p_id) p_id, view_count, like_count, comment_count
   FROM youtube_metrics
   WHERE p_id = ANY($1::text[])
   ORDER BY p_id, fetched_at DESC
   ```

2. **Repeated Profile Page Recalculations**
   ```python
   # Line 445: Called on every profile page load
   update_user_metrics(u_id)
   ```
   **Problem**: For users with many projects, this:
   - Queries `user_projects` (1 query)
   - Queries `latest_youtube_metrics` or `youtube_metrics` (1 query, potentially large)
   - Aggregates in Python (CPU)
   - Upserts `user_metrics` (1 write)
   
   **Impact**: Profile page load time increases with number of projects.

3. **Analytics Time-Series Query**
   ```350:425:credify_app.py
   @st.cache_data(show_spinner=False)
   def fetch_user_daily_timeseries(u_id: str, start_date_iso: str, end_date_iso: str) -> pd.DataFrame:
   ```
   **Assessment**: ✅ Properly cached, but still processes all snapshots in memory. For 12 months × 100 videos = 36,500 rows, this is acceptable but could be optimized with database-side aggregation.

### Recommendations

1. **Optimize fallback query** - Use `DISTINCT ON` in SQL
2. **Add `updated_at` check** - Only recalculate `user_metrics` if `youtube_metrics` has newer data:
   ```python
   last_metric_update = max(m.get("fetched_at") for m in latest_metrics)
   user_metrics = supabase.table("user_metrics").select("updated_at").eq("u_id", u_id).execute()
   if user_metrics.data and user_metrics.data[0]["updated_at"] >= last_metric_update:
       return  # Skip recalculation
   ```

3. **Consider materialized view for `youtube_latest_metrics`** - If refresh cost is acceptable, ensures consistent fast queries

4. **Add indexes** - Ensure `youtube_metrics` has:
   - Index on `(p_id, fetched_at DESC)` for latest queries
   - Index on `fetched_at` for date range queries

---

## 5. Consistency Guarantees

### Duplicate Data Prevention

**Lambda Job:**
- ❌ **No deduplication**: Lambda can insert duplicate rows if run multiple times per day
- ⚠️ **App-level check exists**: Claim flow checks for duplicate `fetched_at` (line 638), but Lambda doesn't

**View Consistency:**
- ❓ **Unknown**: If `youtube_latest_metrics` is a view using `DISTINCT ON`, it should handle duplicates correctly
- ⚠️ **If materialized view**: Needs refresh after each Lambda insert to stay consistent

### Stale Data Risks

**Scenarios:**

1. **User doesn't visit profile after Lambda runs**
   - `user_metrics` stays stale until profile visit
   - **Impact**: Dashboard/feed may show outdated totals

2. **Concurrent profile loads**
   - Multiple `update_user_metrics()` calls could race
   - **Impact**: Last write wins, but wastes database resources

3. **Materialized view not refreshed**
   - If `youtube_latest_metrics` is materialized and not refreshed, shows stale data
   - **Impact**: All pages using `latest_youtube_metrics` show wrong values

### Recommendations

1. **Add unique constraint** to prevent duplicate same-day inserts:
   ```sql
   CREATE UNIQUE INDEX idx_youtube_metrics_pid_date 
   ON youtube_metrics (p_id, DATE(fetched_at));
   ```

2. **Document view refresh strategy** - Clarify whether `youtube_latest_metrics` is:
   - A regular view (always fresh, but query cost)
   - A materialized view (needs refresh, but fast queries)
   - A trigger-maintained table (best of both)

3. **Add version/timestamp tracking** - Include `updated_at` in queries to detect stale data

4. **Implement idempotent updates** - Use `ON CONFLICT` in Lambda to handle retries safely

---

## Summary of Critical Issues

### High Priority

1. **Table name inconsistency** - Standardize `latest_youtube_metrics` vs `youtube_latest_metrics`
2. **Missing automatic sync** - Add trigger or background job to update `user_metrics`
3. **No deduplication in Lambda** - Add unique constraint or upsert logic

### Medium Priority

4. **Inefficient fallback query** - Use `DISTINCT ON` instead of client-side filtering
5. **Profile page performance** - Add caching/timestamp checks to avoid unnecessary recalculations
6. **Missing schema documentation** - Document expected `youtube_latest_metrics` structure

### Low Priority

7. **Race condition handling** - Add locks/mutex for concurrent updates
8. **View refresh strategy** - Clarify and document materialized view refresh approach

---

## Action Items

- [ ] Standardize table name across all code paths
- [ ] Document `youtube_latest_metrics` schema (SQL view definition or table structure)
- [ ] Add database trigger or background job to auto-update `user_metrics`
- [ ] Add unique constraint to `youtube_metrics` for same-day deduplication
- [ ] Optimize fallback query using `DISTINCT ON`
- [ ] Add `updated_at` timestamp check to skip unnecessary recalculations
- [ ] Add indexes on `youtube_metrics` for performance
- [ ] Document refresh strategy for materialized views (if applicable)

