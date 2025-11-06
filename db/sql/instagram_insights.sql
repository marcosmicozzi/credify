-- Table: instagram_insights
-- Stores daily Instagram Business account metrics fetched from Graph API
-- Supports time-series data with end_time for each metric snapshot

CREATE TABLE IF NOT EXISTS public.instagram_insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric TEXT NOT NULL,
    value NUMERIC NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    retrieved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id UUID REFERENCES public.users(u_id) ON DELETE CASCADE,
    
    -- Ensure we don't duplicate the same metric for the same end_time and user
    CONSTRAINT unique_metric_per_time_user UNIQUE (metric, end_time, user_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_instagram_insights_user_id ON public.instagram_insights(user_id);
CREATE INDEX IF NOT EXISTS idx_instagram_insights_metric ON public.instagram_insights(metric);
CREATE INDEX IF NOT EXISTS idx_instagram_insights_end_time ON public.instagram_insights(end_time DESC);
CREATE INDEX IF NOT EXISTS idx_instagram_insights_user_metric_time ON public.instagram_insights(user_id, metric, end_time DESC);

-- Enable Row Level Security
ALTER TABLE public.instagram_insights ENABLE ROW LEVEL SECURITY;

-- RLS Policies
-- Users can read their own Instagram insights
CREATE POLICY "Users can read own instagram insights"
    ON public.instagram_insights
    FOR SELECT
    USING (auth.uid()::text = user_id::text OR user_id IS NULL);

-- Users can insert their own Instagram insights
CREATE POLICY "Users can insert own instagram insights"
    ON public.instagram_insights
    FOR INSERT
    WITH CHECK (auth.uid()::text = user_id::text OR user_id IS NULL);

-- Optional: View for latest metrics per user per metric (similar to youtube_latest_metrics)
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

-- Grant permissions (adjust based on your Supabase setup)
-- GRANT SELECT, INSERT ON public.instagram_insights TO authenticated;
-- GRANT SELECT ON public.instagram_latest_metrics TO authenticated;

