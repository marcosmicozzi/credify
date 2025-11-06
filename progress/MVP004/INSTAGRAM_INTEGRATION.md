# Instagram Graph API Integration

This document describes the Instagram integration for the Credify app.

## Overview

The Instagram integration fetches and displays four key metrics from Instagram Business accounts:
- **reach** (time_series / day)
- **profile_views** (total_value / day)
- **accounts_engaged** (total_value / day)
- **follower_count** (time_series / day)

## Setup

### 1. Database Schema

Run the SQL schema file to create the `instagram_insights` table:

```sql
-- Execute db/sql/instagram_insights.sql in your Supabase SQL editor
```

This creates:
- `instagram_insights` table with RLS policies
- `instagram_latest_metrics` view for quick access to latest metrics
- Appropriate indexes for performance

**Example: `instagram_latest_metrics` view**

The view provides the most recent metric value per user per metric:

```sql
CREATE OR REPLACE VIEW public.instagram_latest_metrics AS
SELECT DISTINCT ON (user_id, metric)
    user_id,
    metric,
    value,
    end_time,
    retrieved_at
FROM public.instagram_insights
WHERE user_id IS NOT NULL
ORDER BY user_id, metric, end_time DESC;
```

This uses PostgreSQL's `DISTINCT ON` to efficiently select the latest record per `(user_id, metric)` combination.

### 2. Configuration

#### Development (Single User)

Add the following to your `.streamlit/secrets.toml`:

```toml
IG_LONG_TOKEN = "your_long_lived_access_token"
IG_ACCOUNT_ID = "your_instagram_business_account_id"
```

**Getting your Instagram Business Account ID:**
1. Go to [Facebook Graph API Explorer](https://developers.facebook.com/tools/explorer/)
2. Use your long-lived token
3. Query: `GET /me/accounts` to get your Page ID
4. Query: `GET /{page-id}?fields=instagram_business_account` to get your Instagram Business Account ID

#### Production (Multi-User) ✅ **IMPLEMENTED**

The app now supports **multi-user Instagram authentication** via OAuth. Each user connects their own Instagram Business account through **Settings → Connections**.

**How it works:**
1. Users go to **Settings → Connections**
2. Click **"Connect Instagram"** button
3. Authorize via Facebook OAuth
4. Token stored in `user_tokens` table (per user)
5. Each user sees only their own insights

**Setup required:**
- Create Facebook App with Instagram Graph API product
- Add `FACEBOOK_APP_ID` and `FACEBOOK_APP_SECRET` to secrets
- Configure OAuth redirect URIs in Facebook App settings

See `INSTAGRAM_MULTI_USER_SETUP.md` for detailed setup instructions.

**Legacy secrets** (`IG_LONG_TOKEN`, `IG_ACCOUNT_ID`) are deprecated but kept for backward compatibility during migration.

### 3. Usage

#### Refresh Insights Button

1. Navigate to **Profile** → **Instagram Overview**
2. Click **🔄 Refresh Insights** to fetch the latest metrics from Instagram Graph API
3. Metrics are automatically stored in the `instagram_insights` table

#### Viewing Metrics

**Instagram Overview Page:**
- Displays latest metrics (Reach, Profile Views, Accounts Engaged, Followers)
- Shows recent trends with line charts for each metric
- Refresh button to fetch new data

**Analytics Page:**
- Select "Instagram Analytics" from the platform buttons
- View time-series charts for any of the 4 metrics
- Compare with previous period
- See peak day statistics

## Architecture

### Files Created

1. **`utils/instagram_fetcher.py`**
   - `fetch_instagram_insights()`: Fetches metrics from Graph API
   - `parse_instagram_insights_response()`: Parses API response
   - `fetch_and_store_instagram_insights()`: Main function to fetch and store all 4 metrics
   - `get_latest_instagram_metrics()`: Retrieves latest metrics from Supabase

2. **`db/sql/instagram_insights.sql`**
   - Table schema with RLS policies
   - Indexes for performance
   - View for latest metrics

### Integration Points

- **`credify_app.py`**:
  - `show_instagram_overview()`: Full Instagram metrics dashboard
  - `fetch_instagram_daily_timeseries()`: Helper for analytics charts
  - Updated `show_analytics_page()`: Supports Instagram platform

## Data Model

### `instagram_insights` Table

```sql
- id: UUID (primary key)
- metric: TEXT (e.g., 'reach', 'profile_views')
- value: NUMERIC (metric value)
- end_time: TIMESTAMPTZ (when the metric period ended)
- retrieved_at: TIMESTAMPTZ (when we fetched it)
- user_id: UUID (foreign key to users table)
```

### Unique Constraint

Prevents duplicate entries: `(metric, end_time, user_id)`

## Daily Sync Recommendations

### Option 1: Streamlit Caching (Current Implementation)

The refresh button uses Streamlit's session state. For automated daily syncs:

1. **Supabase Edge Functions** (Recommended):
   - Create a scheduled Edge Function that runs daily
   - Calls `fetch_and_store_instagram_insights()` for all users
   - More reliable and doesn't depend on user activity

2. **Streamlit Scheduled Tasks**:
   - Use `st.cache_data` with `ttl` parameter
   - Less reliable for scheduled tasks
   - Better for on-demand refreshes

### Option 2: External Cron Job

Create a lightweight Python script that:
- Runs daily via cron or GitHub Actions
- Fetches metrics for all users with Instagram accounts
- Stores results in Supabase

Example structure:
```python
# scripts/daily_instagram_sync.py
from utils.instagram_fetcher import fetch_and_store_instagram_insights
from supabase import create_client
import os

# Get all users with Instagram accounts
# Fetch and store metrics for each
```

## API Rate Limits

Instagram Graph API has rate limits:
- **200 calls per hour per user** (for most endpoints)
- **4 metrics per call** (we fetch all 4 in one request)
- **Long-lived tokens** expire after 60 days (unless extended)

Best practice: Fetch once per day per user to stay well within limits.

### Token Refresh Strategy

Long-lived tokens typically last 60 days. To maintain continuous access:

> **Note:** A helper function (`refresh_instagram_token()`) can later be added using the Facebook `fb_exchange_token` endpoint to automatically renew tokens when approaching expiry. This endpoint exchanges a short-lived token for a long-lived one, or extends an existing long-lived token. Consider implementing token expiry tracking and automatic refresh before the 60-day window expires.

## Troubleshooting

### "Instagram integration not configured"
- Ensure `IG_LONG_TOKEN` and `IG_ACCOUNT_ID` are set in `.streamlit/secrets.toml`

### "No Instagram insights data yet"
- Click "Refresh Insights" button to fetch your first metrics
- Verify your token has `instagram_basic` and `instagram_manage_insights` permissions

### "Error fetching Instagram insights"
- Check token validity and permissions
- Verify `IG_ACCOUNT_ID` is correct
- Check Graph API status: https://developers.facebook.com/status/

## Future Enhancements

- [ ] Support multiple Instagram accounts per user
- [ ] Add more metrics (impressions, saves, etc.)
- [ ] Automated daily sync via Supabase Edge Functions
- [ ] Export metrics to CSV/JSON
- [ ] Compare metrics across time periods
- [ ] Integration with TikTok and other platforms

## Developer Notes

### Schema Review

When reviewing `db/sql/instagram_insights.sql`, consider:

- **Missing indexes**: Verify all common query patterns are covered (e.g., filtering by `metric` and `end_time` range)
- **RLS policies**: Ensure policies correctly restrict access to user's own data and handle edge cases (e.g., `user_id IS NULL`)
- **Performance**: Monitor query performance on large datasets; consider partitioning by date if table grows significantly

### Schema Improvements

Potential enhancements to the Supabase schema:

- **Link to projects/entities**: Consider adding an optional `project_id` or `entity_id` column to link Instagram metrics to specific projects or content pieces
- **Metric metadata**: Add a `metadata` JSONB column to store additional context (e.g., breakdown by post type, audience demographics)
- **Aggregation tables**: Create materialized views or tables for pre-computed aggregations (daily/weekly/monthly summaries)

### UI/UX Considerations

- **Async refresh**: Ensure the Streamlit "Refresh Insights" button runs asynchronously to avoid blocking the UI. Consider using `st.spinner()` with background tasks or `st.rerun()` after completion
- **Error handling**: Display user-friendly error messages for API failures, token expiry, or rate limit issues
- **Loading states**: Show clear loading indicators during metric fetches

### Daily Sync Recommendations

For automated daily sync, consider these options in order of preference:

1. **Supabase Edge Functions** (Recommended)
   - Native integration with Supabase
   - Scheduled via Supabase Cron or external scheduler
   - Serverless, scales automatically
   - Easy to monitor and debug via Supabase dashboard

2. **AWS Lambda / Scheduled Function**
   - Good for existing AWS infrastructure
   - Can be triggered by EventBridge (CloudWatch Events)
   - Requires additional setup and monitoring

3. **External Cron Job**
   - Simple for small deployments
   - Requires a persistent server or CI/CD pipeline
   - Less reliable for production workloads

**Implementation tip**: Store sync status in a `sync_logs` table to track last successful sync per user and handle failures gracefully.

