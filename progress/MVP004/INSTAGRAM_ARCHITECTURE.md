# Instagram Integration Architecture Guide

This document addresses the architectural decisions and implementation patterns for the Instagram Graph API integration.

## 1. Design: Mixed Metric Types Handling

### Problem
Instagram API returns mixed `time_series` and `total_value` metrics. Combining them in a single request can fail or return partial results.

### Solution: Separate Fetch by Type

**Approach**: Fetch each metric separately with explicit `metric_type` parameter.

```python
# Metric configuration maps name to type
METRIC_CONFIG = {
    "reach": "time_series",
    "profile_views": "total_value",
    "accounts_engaged": "total_value",
    "follower_count": "time_series",
}

# Fetch each metric individually
for metric in metrics:
    metric_type = METRIC_CONFIG[metric]
    api_response = fetch_instagram_insights_single(
        access_token=token,
        instagram_account_id=account_id,
        metric=metric,
        metric_type=metric_type,  # Explicit type
        period="day"
    )
```

**Benefits**:
- ✅ Reliable: Each metric fetched with correct type
- ✅ Extensible: Easy to add new metrics to `METRIC_CONFIG`
- ✅ Error isolation: One metric failure doesn't break others
- ✅ Retry-friendly: Can retry individual metrics

**Trade-offs**:
- More API calls (4 instead of 1), but still well within rate limits
- Slightly slower, but more reliable

## 2. Timestamp Normalization Strategy

### Problem
Instagram API returns timestamps in various formats, sometimes with timezone info. We need consistent UTC storage.

### Solution: Normalize to UTC ISO

```python
def normalize_timestamp(timestamp_str: Optional[str]) -> Optional[str]:
    """Normalize to UTC ISO format for consistent storage."""
    if not timestamp_str:
        return None
    
    # Parse (handles ISO with/without timezone)
    dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
    
    # Ensure UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    
    return dt.isoformat()
```

**Why this works**:
- ✅ Consistent format: Always UTC ISO string
- ✅ Predictable ordering: `end_time` comparisons work correctly
- ✅ Uniqueness: Normalized timestamps prevent duplicates
- ✅ Database-friendly: PostgreSQL `TIMESTAMPTZ` handles it perfectly

**Database constraint**:
```sql
UNIQUE (u_id, account_id, metric, end_time)
```
This ensures no duplicate metrics for the same normalized timestamp.

## 3. DB Insert Verification Pattern

### Problem
Supabase Python client's `.execute()` can return no `.data` even on successful inserts.

### Solution: Multi-Factor Verification

```python
def verify_insert_success(result) -> Tuple[bool, int]:
    """Reliable insert verification."""
    if not result:
        return False, 0
    
    # 1. Check for explicit error
    if hasattr(result, 'error') and result.error:
        return False, 0
    
    # 2. Check for data (most reliable)
    if hasattr(result, 'data') and result.data:
        return True, len(result.data)
    
    # 3. Check status code
    if hasattr(result, 'status_code'):
        if 200 <= result.status_code < 300:
            return True, 0  # Success but no data returned
    
    return False, 0
```

**Pattern**:
1. Check for explicit errors first
2. Check for returned data (most reliable)
3. Fall back to status code
4. Return both success status and count

**Usage**:
```python
result = supabase.table("instagram_insights").insert(batch).execute()
success, count = verify_insert_success(result)
```

## 4. Result Summary Format

### Problem
UI needs concise summaries, not per-metric tallies.

### Solution: `FetchResult` Dataclass

```python
@dataclass
class FetchResult:
    success: bool                    # Overall success
    total_inserted: int              # Total records inserted
    total_errors: int                # Total errors encountered
    metrics_inserted: Dict[str, int] # Per-metric counts (for debugging)
    errors: List[str]                # Error messages
    account_id: Optional[str]       # Account ID used
    user_id: Optional[str]          # User ID associated
```

**UI Display**:
```python
result = fetch_and_store_instagram_insights(...)

if result.success:
    st.success(f"✅ Fetched {result.total_inserted} metric records")
else:
    st.warning(f"⚠️ Inserted {result.total_inserted} records with {result.total_errors} errors")
    if result.errors:
        st.error("\n".join(result.errors))
```

**Benefits**:
- ✅ Concise: One object with all info
- ✅ Flexible: Can show summary or details
- ✅ Debuggable: Full error list available
- ✅ Extensible: Easy to add fields

## 5. Account ID Handling: Secrets vs DB

### Problem
Dev uses `secrets.toml`, but production needs per-user account IDs.

### Solution: `user_tokens` Table + Helper Function

**Schema** (already in your SQL):
```sql
CREATE TABLE user_tokens (
    token_id UUID PRIMARY KEY,
    u_id UUID REFERENCES users(u_id),
    platform TEXT CHECK (platform IN ('instagram', 'youtube', ...)),
    access_token TEXT NOT NULL,
    account_id TEXT,  -- IG Business Account ID
    expires_at TIMESTAMPTZ,
    ...
);
```

**Helper Function**:
```python
def get_user_instagram_account(supabase: Client, user_id: str) -> Optional[Dict]:
    """Get user's Instagram account from DB."""
    result = supabase.table("user_tokens") \
        .select("account_id, access_token, expires_at") \
        .eq("u_id", user_id) \
        .eq("platform", "instagram") \
        .execute()
    
    if result.data:
        return result.data[0]
    return None
```

**Usage Pattern**:
```python
# Try DB first (production), fall back to secrets (dev)
account_info = get_user_instagram_account(supabase, user_id)

if account_info:
    account_id = account_info["account_id"]
    access_token = account_info["access_token"]
else:
    # Fall back to secrets for dev
    account_id = st.secrets.get("IG_ACCOUNT_ID")
    access_token = st.secrets.get("IG_LONG_TOKEN")
```

**Benefits**:
- ✅ Multi-user ready: Each user has their own account
- ✅ Dev-friendly: Falls back to secrets
- ✅ Token management: Can store expiry, refresh tokens
- ✅ Extensible: Works for other platforms too

## 6. Token Refresh Helper

### Problem
Long-lived tokens expire after 60 days. Need automatic renewal.

### Solution: `refresh_instagram_token()` Function

**Location**: `utils/instagram_fetcher.py`

```python
def refresh_instagram_token(
    access_token: str,
    app_id: str,
    app_secret: str
) -> Optional[Dict]:
    """Refresh token using fb_exchange_token endpoint."""
    url = "https://graph.facebook.com/v18.0/oauth/access_token"
    
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": access_token
    }
    
    response = requests.get(url, params=params, timeout=30)
    return response.json()  # Returns new token + expires_in
```

**Trigger Strategy**:

1. **Proactive Refresh** (Recommended):
   ```python
   # Check token expiry before each sync
   if token_data["expires_at"] < datetime.now(timezone.utc) + timedelta(days=7):
       new_token = refresh_instagram_token(...)
       # Update user_tokens table
   ```

2. **Scheduled Job**:
   - Run daily cron job
   - Check all tokens expiring in next 7 days
   - Refresh and update DB

3. **On-Demand**:
   - When API returns 401/403 error
   - Attempt refresh and retry request

**Implementation Location**:
- **Helper**: `utils/instagram_fetcher.py` (already added)
- **Scheduler**: Create `scripts/refresh_instagram_tokens.py` for cron job
- **Integration**: Add expiry check in `fetch_and_store_instagram_insights()`

## 7. Daily Sync Mechanism Recommendation

### Recommendation: **Supabase Edge Functions** (Primary) + **GitHub Actions** (Backup)

### Option 1: Supabase Edge Functions ⭐ (Recommended)

**Why**:
- ✅ Native integration with Supabase
- ✅ Serverless, auto-scales
- ✅ Easy monitoring via Supabase dashboard
- ✅ Can use Supabase Cron (pg_cron) for scheduling
- ✅ Direct database access (no API calls needed)

**Implementation**:
```typescript
// supabase/functions/daily-instagram-sync/index.ts
import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

serve(async (req) => {
  const supabase = createClient(...)
  
  // Get all users with Instagram tokens
  const { data: users } = await supabase
    .from('user_tokens')
    .select('u_id, account_id, access_token')
    .eq('platform', 'instagram')
  
  // Fetch and store for each user
  for (const user of users) {
    await fetchAndStore(user)
  }
  
  return new Response(JSON.stringify({ success: true }))
})
```

**Schedule via pg_cron**:
```sql
-- Run daily at 2 AM UTC
SELECT cron.schedule(
  'daily-instagram-sync',
  '0 2 * * *',
  $$
  SELECT net.http_post(
    url := 'https://your-project.supabase.co/functions/v1/daily-instagram-sync',
    headers := '{"Authorization": "Bearer YOUR_ANON_KEY"}'::jsonb
  )
  $$
);
```

### Option 2: GitHub Actions (Backup/Alternative)

**Why**:
- ✅ Free for public repos
- ✅ Easy to set up
- ✅ Good for small-scale deployments
- ✅ Version-controlled

**Implementation**:
```yaml
# .github/workflows/daily-instagram-sync.yml
name: Daily Instagram Sync

on:
  schedule:
    - cron: '0 2 * * *'  # 2 AM UTC daily
  workflow_dispatch:  # Manual trigger

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: |
          pip install -r requirements.txt
          python scripts/daily_instagram_sync.py
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
```

### Option 3: AWS Lambda (If Already Using AWS)

**Why**:
- ✅ Good if you already have AWS infrastructure
- ✅ EventBridge for scheduling
- ✅ Scales automatically

**Trade-off**: More setup complexity

### Recommendation Summary

**For Production**: Use **Supabase Edge Functions** with pg_cron scheduling
- Native integration
- Serverless
- Easy monitoring

**For Development/Backup**: Use **GitHub Actions**
- Simple setup
- Free tier
- Good for testing

**Avoid**: Streamlit on-demand (unreliable for scheduled tasks)

## Implementation Checklist

- [x] Refactored `instagram_fetcher.py` with separate metric fetching
- [x] Timestamp normalization function
- [x] Reliable insert verification
- [x] `FetchResult` dataclass for summaries
- [x] `get_user_instagram_account()` helper
- [x] `refresh_instagram_token()` helper
- [ ] Update `credify_app.py` to use new `FetchResult` format
- [ ] Create Supabase Edge Function for daily sync
- [ ] Set up pg_cron schedule
- [ ] Add token expiry checking
- [ ] Create sync logging integration

## Next Steps

1. **Update Streamlit UI** to use new `FetchResult` format
2. **Create Edge Function** for daily sync
3. **Set up monitoring** via `instagram_sync_logs` table
4. **Test token refresh** flow
5. **Migrate from secrets to DB** for account IDs

