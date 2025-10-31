-- View: youtube_latest_metrics
-- Provides the most recent snapshot per video (p_id) from youtube_metrics
-- Uses DISTINCT ON to select latest by fetched_at
-- Now includes engagement_rate calculation

CREATE OR REPLACE VIEW public.youtube_latest_metrics AS
SELECT DISTINCT ON (m.p_id)
  m.p_id,
  m.view_count,
  m.like_count,
  m.comment_count,
  NULL::bigint AS share_count,
  m.fetched_at,
  CASE 
    WHEN m.view_count > 0 THEN 
      ((COALESCE(m.like_count, 0) + COALESCE(m.comment_count, 0) + 0)::numeric / m.view_count * 100)::numeric(5,2)
    ELSE 0::numeric(5,2)
  END AS engagement_rate
FROM public.youtube_metrics m
ORDER BY m.p_id, m.fetched_at DESC;

-- Recommended indexes for performance
-- CREATE INDEX IF NOT EXISTS idx_youtube_metrics_pid_fetched_at ON public.youtube_metrics (p_id, fetched_at DESC);


