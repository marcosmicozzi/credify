# Instagram Insights Schema Review & Recommendations

## Schema Review

### ✅ Strengths

1. **Clear separation**: `instagram_metrics` (per-post) vs `instagram_insights` (account-level) is well-defined
2. **Proper constraints**: Unique constraint on `(u_id, account_id, metric, end_time)` prevents duplicates
3. **Good indexing**: Indexes cover common query patterns
4. **RLS enabled**: Security policies in place

### 🔧 Recommended Improvements

#### 1. Composite Index Optimization

The current index `idx_ig_insights_uid` is single-column. For queries filtering by `u_id` and `end_time` range, add a composite index:

```sql
-- More efficient for time-range queries per user
CREATE INDEX IF NOT EXISTS idx_ig_insights_uid_end_time 
ON instagram_insights (u_id, end_time DESC);
```

#### 2. Account ID Index

The `account_id` index exists but consider making it composite with `end_time` for account-specific time queries:

```sql
-- If you query by account_id + time range
CREATE INDEX IF NOT EXISTS idx_ig_insights_account_end_time 
ON instagram_insights (account_id, end_time DESC);
```

#### 3. RLS Policy Enhancement

Current policy allows `user_id IS NULL`. Consider tightening:

```sql
-- More restrictive: only allow NULL user_id for system/admin operations
-- Or remove NULL entirely if all records must be user-linked
DROP POLICY IF EXISTS "Users can read own instagram insights" ON instagram_insights;
CREATE POLICY "Users can read own instagram insights"
    ON instagram_insights
    FOR SELECT
    USING (auth.uid()::text = u_id::text);
```

#### 4. Link to Projects/Entities (Optional)

If you want to associate account-level insights with specific projects:

```sql
-- Add optional project link
ALTER TABLE instagram_insights 
ADD COLUMN IF NOT EXISTS p_id TEXT REFERENCES projects(p_id) ON DELETE SET NULL;

-- Index for project-linked insights
CREATE INDEX IF NOT EXISTS idx_ig_insights_p_id 
ON instagram_insights (p_id) WHERE p_id IS NOT NULL;
```

**Use case**: If a user wants to see account metrics during a specific campaign/project period.

#### 5. Metadata Column (Future-Proofing)

Store additional context that might come from API:

```sql
-- JSONB for flexible metadata storage
ALTER TABLE instagram_insights 
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

-- GIN index for JSONB queries
CREATE INDEX IF NOT EXISTS idx_ig_insights_metadata 
ON instagram_insights USING GIN (metadata);
```

**Use cases**: 
- Breakdown by post type
- Audience demographics
- Geographic data
- Any future API additions

#### 6. Partitioning Consideration

If the table grows large (>1M rows), consider partitioning by date:

```sql
-- Example: Monthly partitioning (PostgreSQL 10+)
-- This would require table recreation, so plan ahead
CREATE TABLE instagram_insights_2024_01 PARTITION OF instagram_insights
FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

**Recommendation**: Monitor table size. Partition when >500K rows or queries slow down.

#### 7. View Optimization

The `instagram_account_latest_metrics` view is good, but consider materializing if queried frequently:

```sql
-- Materialized view for faster reads (refresh periodically)
CREATE MATERIALIZED VIEW IF NOT EXISTS instagram_account_latest_metrics_mv AS
SELECT DISTINCT ON (u_id, metric)
    u_id,
    account_id,
    metric,
    value,
    end_time,
    retrieved_at
FROM instagram_insights
ORDER BY u_id, metric, end_time DESC;

-- Refresh strategy: daily via cron or trigger
CREATE UNIQUE INDEX ON instagram_account_latest_metrics_mv (u_id, metric);
```

#### 8. Sync Logging Table

Track sync operations for debugging and monitoring:

```sql
CREATE TABLE IF NOT EXISTS instagram_sync_logs (
    id BIGSERIAL PRIMARY KEY,
    u_id UUID REFERENCES users(u_id) ON DELETE CASCADE,
    account_id TEXT,
    sync_started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sync_completed_at TIMESTAMPTZ,
    records_inserted INT DEFAULT 0,
    records_failed INT DEFAULT 0,
    error_message TEXT,
    success BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_sync_logs_uid ON instagram_sync_logs (u_id);
CREATE INDEX IF NOT EXISTS idx_sync_logs_account ON instagram_sync_logs (account_id);
CREATE INDEX IF NOT EXISTS idx_sync_logs_started ON instagram_sync_logs (sync_started_at DESC);
```

## Updated Schema (Recommended)

Here's the complete recommended schema with improvements:

```sql
-- =====================================================
-- INSTAGRAM_INSIGHTS (ACCOUNT-LEVEL DAILY INSIGHTS)
-- =====================================================
CREATE TABLE IF NOT EXISTS instagram_insights (
    id BIGSERIAL PRIMARY KEY,
    u_id UUID REFERENCES users(u_id) ON DELETE CASCADE,
    account_id TEXT NOT NULL,  -- IG Business Account ID
    metric TEXT NOT NULL CHECK (
        metric IN ('reach','profile_views','accounts_engaged','follower_count')
    ),
    value NUMERIC NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,  -- normalized UTC
    retrieved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    p_id TEXT REFERENCES projects(p_id) ON DELETE SET NULL,  -- optional project link
    metadata JSONB DEFAULT '{}'::jsonb,  -- future-proofing
    
    UNIQUE (u_id, account_id, metric, end_time)
);

-- Core indexes
CREATE INDEX IF NOT EXISTS idx_ig_insights_uid ON instagram_insights (u_id);
CREATE INDEX IF NOT EXISTS idx_ig_insights_metric ON instagram_insights (metric);
CREATE INDEX IF NOT EXISTS idx_ig_insights_end_time ON instagram_insights (end_time DESC);
CREATE INDEX IF NOT EXISTS idx_ig_insights_account ON instagram_insights (account_id);

-- Composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_ig_insights_uid_end_time 
ON instagram_insights (u_id, end_time DESC);
CREATE INDEX IF NOT EXISTS idx_ig_insights_account_end_time 
ON instagram_insights (account_id, end_time DESC);
CREATE INDEX IF NOT EXISTS idx_ig_insights_uid_metric_time 
ON instagram_insights (u_id, metric, end_time DESC);

-- Optional indexes
CREATE INDEX IF NOT EXISTS idx_ig_insights_p_id 
ON instagram_insights (p_id) WHERE p_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_ig_insights_metadata 
ON instagram_insights USING GIN (metadata);

-- RLS (tightened - no NULL user_id)
ALTER TABLE instagram_insights ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can read own instagram insights" ON instagram_insights;
CREATE POLICY "Users can read own instagram insights"
    ON instagram_insights
    FOR SELECT
    USING (auth.uid()::text = u_id::text);

DROP POLICY IF EXISTS "Users can insert own instagram insights" ON instagram_insights;
CREATE POLICY "Users can insert own instagram insights"
    ON instagram_insights
    FOR INSERT
    WITH CHECK (auth.uid()::text = u_id::text);

-- View (optimized)
CREATE OR REPLACE VIEW instagram_account_latest_metrics AS
SELECT DISTINCT ON (u_id, metric)
    u_id,
    account_id,
    metric,
    value,
    end_time,
    retrieved_at
FROM instagram_insights
WHERE u_id IS NOT NULL
ORDER BY u_id, metric, end_time DESC;

-- Sync logging table
CREATE TABLE IF NOT EXISTS instagram_sync_logs (
    id BIGSERIAL PRIMARY KEY,
    u_id UUID REFERENCES users(u_id) ON DELETE CASCADE,
    account_id TEXT,
    sync_started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sync_completed_at TIMESTAMPTZ,
    records_inserted INT DEFAULT 0,
    records_failed INT DEFAULT 0,
    error_message TEXT,
    success BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_sync_logs_uid ON instagram_sync_logs (u_id);
CREATE INDEX IF NOT EXISTS idx_sync_logs_account ON instagram_sync_logs (account_id);
CREATE INDEX IF NOT EXISTS idx_sync_logs_started ON instagram_sync_logs (sync_started_at DESC);
```

## Summary

**Priority 1 (Do Now)**:
- Add composite indexes for `(u_id, end_time)` and `(account_id, end_time)`
- Tighten RLS policies (remove NULL user_id allowance if not needed)

**Priority 2 (Soon)**:
- Add `metadata` JSONB column for future API data
- Create `instagram_sync_logs` table for monitoring

**Priority 3 (Later)**:
- Consider materialized view if query performance degrades
- Add `p_id` link if you want project-level association
- Plan partitioning strategy if table grows >500K rows

