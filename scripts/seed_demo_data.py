"""
Seed demo analytics data into Supabase for a given demo user (u_id).

What it does:
- Ensures a few demo projects exist in `projects`
- Links the demo user to those projects in `user_projects`
- Generates 365 days of daily snapshots in `youtube_metrics` (cumulative counters)

Notes:
- Uses environment variables SUPABASE_URL and SUPABASE_ANON_KEY
- Safe re-runs: skips seeding if recent metrics already exist unless --force is used

Usage:
  SUPABASE_URL=... SUPABASE_ANON_KEY=... \
  python scripts/seed_demo_data.py --u-id 8538ed98-b38f-478e-92f7-172512ef6ae5 --days 365
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta, timezone
from random import Random
from typing import List, Dict

from supabase import create_client, Client


def get_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_ANON_KEY")
    if not url or not key:
        raise SystemExit("Missing SUPABASE_URL or SUPABASE_ANON_KEY in environment")
    return create_client(url, key)


def ensure_projects(client: Client, demos: List[Dict[str, str]]) -> None:
    for dv in demos:
        existing = client.table("projects").select("p_id").eq("p_id", dv["p_id"]).execute()
        if existing.data:
            continue
        client.table("projects").insert({
            "p_id": dv["p_id"],
            "p_title": dv["title"],
            "p_description": "Demo project",
            "p_link": f"https://www.youtube.com/watch?v={dv['p_id']}",
            "p_platform": "youtube",
            "p_channel": "Demo Channel",
            "p_posted_at": datetime.utcnow().isoformat(),
            "p_thumbnail_url": "https://picsum.photos/seed/demo/640/360",
        }).execute()


def ensure_user_links(client: Client, u_id: str, demos: List[Dict[str, str]]) -> None:
    for dv in demos:
        exists = client.table("user_projects").select("u_id").eq("u_id", u_id).eq("p_id", dv["p_id"]).limit(1).execute()
        if exists.data:
            continue
        client.table("user_projects").insert({
            "u_id": u_id,
            "p_id": dv["p_id"],
            "u_role": "Demo Role",
        }).execute()


def seed_metrics(client: Client, p_ids: List[str], days: int, force: bool) -> int:
    # If we have any recent rows, skip unless forced
    if not force:
        recent = client.table("youtube_metrics").select("p_id").in_("p_id", p_ids) \
            .gte("fetched_at", (datetime.utcnow() - timedelta(days=30)).isoformat()) \
            .limit(1).execute()
        if recent.data:
            print("Recent metrics already exist; use --force to reseed.")
            return 0

    rng = Random(42)
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=days - 1)

    rows: List[Dict[str, object]] = []
    for pid_idx, pid in enumerate(p_ids):
        cum_v = 0
        cum_l = 0
        cum_c = 0
        
        # Base daily views per video (different per video for variety)
        base_daily_views = [1200, 800, 1500][pid_idx % 3]
        
        for d in range(days):
            day = start + timedelta(days=d)
            day_of_week = day.weekday()  # 0=Monday, 6=Sunday
            
            # Weekend effect: typically lower views on Sat/Sun
            weekend_multiplier = 0.7 if day_of_week >= 5 else 1.0
            
            # Gradual trend: slight growth over time (1% per month ~= 0.033% per day)
            trend_factor = 1.0 + (d * 0.00033)
            
            # Random daily variation: -30% to +50% of base
            daily_variation = rng.uniform(0.7, 1.5)
            
            # Occasional viral spikes (5% chance per day)
            spike_multiplier = 1.0
            if rng.random() < 0.05:
                spike_multiplier = rng.uniform(3.0, 8.0)
            
            # Occasional dips (10% chance per day, less dramatic)
            dip_multiplier = 1.0
            if rng.random() < 0.10 and spike_multiplier == 1.0:
                dip_multiplier = rng.uniform(0.4, 0.8)
            
            # Calculate daily views with all factors
            inc_v = int(base_daily_views * weekend_multiplier * trend_factor * daily_variation * spike_multiplier * dip_multiplier)
            
            # Likes: 2-5% of views, with some variation
            like_rate = rng.uniform(0.02, 0.05)
            inc_l = max(0, int(inc_v * like_rate))
            
            # Comments: 0.5-2% of views, with some variation
            comment_rate = rng.uniform(0.005, 0.02)
            inc_c = max(0, int(inc_v * comment_rate))

            # Accumulate to cumulative totals (as YouTube stores them)
            cum_v += inc_v
            cum_l += inc_l
            cum_c += inc_c

            rows.append({
                "p_id": pid,
                "platform": "youtube",
                "fetched_at": datetime.combine(day, datetime.max.time(), tzinfo=timezone.utc).isoformat(),
                "view_count": cum_v,
                "like_count": cum_l,
                "comment_count": cum_c,
            })

    inserted = 0
    batch_size = 500
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        client.table("youtube_metrics").insert(batch).execute()
        inserted += len(batch)
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--u-id", required=True, help="Demo user's u_id")
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    client = get_client()
    demos = [
        {"p_id": "dEm0V1dE01a", "title": "Demo Video A"},
        {"p_id": "dEm0V1dE01b", "title": "Demo Video B"},
        {"p_id": "dEm0V1dE01c", "title": "Demo Video C"},
    ]

    ensure_projects(client, demos)
    ensure_user_links(client, args.u_id, demos)
    inserted = seed_metrics(client, [d["p_id"] for d in demos], args.days, args.force)

    print(f"✅ Seed complete. Inserted {inserted} youtube_metrics rows.")


if __name__ == "__main__":
    main()


