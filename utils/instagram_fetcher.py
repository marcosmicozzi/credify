"""Instagram Graph API integration for fetching and storing Instagram Business metrics.

This module handles mixed metric types (time_series vs total_value) by fetching
them in separate requests, normalizes timestamps, and provides reliable insert verification.
"""
import requests
from typing import Callable, Dict, List, Optional, Tuple
from datetime import datetime, timezone
from supabase import Client
from dataclasses import dataclass

try:
    import streamlit as st  # type: ignore
except ImportError:  # pragma: no cover
    st = None  # type: ignore


# Metric configuration: maps metric name to its type
METRIC_CONFIG = {
    "reach": "time_series",
    "profile_views": "total_value",
    "accounts_engaged": "total_value",
    "follower_count": "time_series",
}


@dataclass
class FetchResult:
    """Result summary for Instagram insights fetch operation."""
    success: bool
    total_inserted: int
    total_errors: int
    metrics_inserted: Dict[str, int]  # metric_name -> count
    errors: List[str]  # Error messages
    account_id: Optional[str] = None
    user_id: Optional[str] = None


def normalize_timestamp(timestamp_str: Optional[str]) -> Optional[str]:
    """Normalize Instagram API timestamp to UTC ISO format.
    
    Instagram API returns timestamps in various formats. This normalizes them
    to a consistent UTC ISO format for database storage and comparison.
    
    Args:
        timestamp_str: Timestamp string from API (may include timezone)
        
    Returns:
        Normalized ISO timestamp string in UTC, or None if invalid
    """
    if not timestamp_str:
        return None
    
    try:
        # Parse the timestamp (handles ISO format with/without timezone)
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        
        # Ensure UTC timezone
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        
        # Return normalized ISO string
        return dt.isoformat()
    except (ValueError, AttributeError) as e:
        print(f"Warning: Could not normalize timestamp '{timestamp_str}': {e}")
        return None


def fetch_instagram_insights_single(
    access_token: str,
    instagram_account_id: str,
    metric: str,
    metric_type: str,
    period: str = "day"
) -> Optional[Dict]:
    """Fetch a single Instagram metric with explicit type handling.
    
    Fetches one metric at a time to avoid mixed type issues. The metric_type
    parameter ensures we request the correct format from the API.
    
    Args:
        access_token: Long-lived Instagram access token
        instagram_account_id: Instagram Business Account ID
        metric: Metric name (e.g., 'reach', 'profile_views')
        metric_type: Either 'time_series' or 'total_value'
        period: Time period ('day', 'week', 'days_28')
        
    Returns:
        API response dict or None if fetch fails
    """
    base_url = "https://graph.facebook.com/v18.0"
    url = f"{base_url}/{instagram_account_id}/insights"
    
    params = {
        "metric": metric,
        "period": period,
        "metric_type": metric_type,
        "access_token": access_token
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {metric} ({metric_type}): {e}")
        return None


def parse_metric_response(
    metric_name: str,
    api_response: Dict,
    retrieved_at: str
) -> List[Dict]:
    """Parse a single metric's API response into structured records.
    
    Handles both time_series (array of values) and total_value (single value)
    response formats.
    
    Args:
        metric_name: Name of the metric
        api_response: API response dict
        retrieved_at: ISO timestamp when we fetched this data
        
    Returns:
        List of metric records ready for database insertion
    """
    records = []
    
    if not api_response or "data" not in api_response:
        return records
    
    # API returns data as a list, take first item (should only be one for single metric)
    metric_data = api_response["data"][0] if api_response["data"] else {}
    values = metric_data.get("values", [])
    
    for value_entry in values:
        # Handle time_series format: array of {value, end_time}
        if "value" in value_entry and "end_time" in value_entry:
            metric_value = value_entry.get("value", 0)
            end_time_raw = value_entry.get("end_time")
            
            # Normalize timestamp
            end_time = normalize_timestamp(end_time_raw)
            if not end_time:
                continue  # Skip invalid timestamps
            
            records.append({
                "metric": metric_name,
                "value": float(metric_value) if metric_value is not None else 0.0,
                "end_time": end_time,
                "retrieved_at": retrieved_at
            })
        # Handle total_value format: single value with end_time
        elif "value" in value_entry:
            metric_value = value_entry.get("value", 0)
            end_time_raw = value_entry.get("end_time")
            
            end_time = normalize_timestamp(end_time_raw)
            if not end_time:
                continue
            
            records.append({
                "metric": metric_name,
                "value": float(metric_value) if metric_value is not None else 0.0,
                "end_time": end_time,
                "retrieved_at": retrieved_at
            })
    
    return records


def verify_insert_success(result) -> Tuple[bool, int]:
    """Verify Supabase insert operation success.
    
    The Supabase Python client's .execute() can return no .data on inserts
    even when successful. This function provides reliable success detection.
    
    Args:
        result: Result object from supabase.table().insert().execute()
        
    Returns:
        Tuple of (success: bool, inserted_count: int)
    """
    if not result:
        return False, 0
    
    # Check for explicit error
    if hasattr(result, 'error') and result.error:
        return False, 0
    
    # Check for data in response (most reliable indicator)
    if hasattr(result, 'data') and result.data:
        return True, len(result.data)
    
    # If no data but no error, check status code if available
    if hasattr(result, 'status_code'):
        if 200 <= result.status_code < 300:
            # Success status but no data returned (common with Supabase)
            # We'll assume success but can't count records
            return True, 0
    
    # Default: assume failure if we can't verify
    return False, 0


def fetch_and_store_instagram_insights(
    supabase: Client,
    access_token: str,
    instagram_account_id: str,
    user_id: Optional[str] = None,
    metrics: Optional[List[str]] = None,
    debug_log: Optional[Callable[[str], None]] = None
) -> FetchResult:
    """Fetch Instagram metrics and store them in Supabase.
    
    Fetches metrics separately by type to handle mixed time_series/total_value
    responses reliably. Returns a comprehensive result summary.
    
    Args:
        supabase: Supabase client instance
        access_token: Long-lived Instagram access token
        instagram_account_id: Instagram Business Account ID
        user_id: User ID to associate with metrics
        metrics: Optional list of metrics to fetch (defaults to all 4)
        debug_log: Optional callback for debug logging
        
    Returns:
        FetchResult with success status, counts, and error details
    """
    metrics_list = metrics or list(METRIC_CONFIG.keys())
    
    if debug_log:
        debug_log("Starting Instagram insights fetch")
        debug_log(f"Account ID: {instagram_account_id}")
        if user_id:
            debug_log(f"User ID: {user_id}")
        debug_log(f"Metrics requested: {metrics_list}")
    
    retrieved_at = datetime.now(timezone.utc).isoformat()
    
    try:
        all_records: List[Dict] = []
        errors: List[str] = []
        metrics_inserted = {metric: 0 for metric in metrics_list}
        
        # Fetch each metric separately by type
        for metric in metrics_list:
            metric_type = METRIC_CONFIG.get(metric, "time_series")
            
            if debug_log:
                debug_log(f"Fetching metric '{metric}' ({metric_type})")
            
            api_response = fetch_instagram_insights_single(
                access_token=access_token,
                instagram_account_id=instagram_account_id,
                metric=metric,
                metric_type=metric_type,
                period="day"
            )
            
            if not api_response:
                errors.append(f"Failed to fetch {metric} ({metric_type})")
                if debug_log:
                    debug_log(f"Failed to fetch '{metric}' ({metric_type})")
                continue
            
            records = parse_metric_response(metric, api_response, retrieved_at)
            
            if not records:
                errors.append(f"No data returned for {metric}")
                if debug_log:
                    debug_log(f"No data returned for metric '{metric}'")
                continue
            
            for record in records:
                if user_id:
                    record["u_id"] = user_id
                record["account_id"] = instagram_account_id
            
            all_records.extend(records)
            if debug_log:
                debug_log(f"Prepared {len(records)} record(s) for metric '{metric}'")
        
        total_inserted = 0
        total_errors = len(errors)
        
        if all_records:
            try:
                batch_size = 50
                for i in range(0, len(all_records), batch_size):
                    batch = all_records[i:i + batch_size]
                    if debug_log:
                        debug_log(f"Inserting batch {i // batch_size + 1} with {len(batch)} record(s)")
                    result = supabase.table("instagram_insights").insert(batch).execute()
                    
                    success, inserted_count = verify_insert_success(result)
                    
                    if success:
                        for record in batch:
                            metric_name = record.get("metric")
                            if metric_name in metrics_inserted:
                                metrics_inserted[metric_name] += 1
                        total_inserted += inserted_count if inserted_count > 0 else len(batch)
                        if debug_log:
                            debug_log(f"Batch {i // batch_size + 1} insert succeeded (count={inserted_count or len(batch)})")
                    else:
                        error_msg = f"Insert failed for batch starting at index {i}"
                        if hasattr(result, 'error') and result.error:
                            error_msg += f": {result.error}"
                        if debug_log:
                            debug_log(f"Batch {i // batch_size + 1} insert failed: {error_msg}")
                        errors.append(error_msg)
                        total_errors += 1
                        
            except Exception as insert_error:
                errors.append(f"Database insert exception: {str(insert_error)}")
                total_errors += 1
                if debug_log:
                    debug_log(f"Database insert exception: {insert_error}")
        else:
            if debug_log:
                debug_log("No records prepared for insertion")
        
        if debug_log:
            debug_log(f"Insert summary: inserted={total_inserted}, errors={total_errors}")
            if errors:
                debug_log(f"Errors: {errors}")
        
        return FetchResult(
            success=total_inserted > 0 and total_errors == 0,
            total_inserted=total_inserted,
            total_errors=total_errors,
            metrics_inserted=metrics_inserted,
            errors=errors,
            account_id=instagram_account_id,
            user_id=user_id
        )
    except Exception as e:
        error_msg = f"Insights error: {e}"
        if debug_log:
            debug_log(error_msg)
        if st:
            try:
                st.exception(e)
            except Exception:  # pragma: no cover
                try:
                    st.error(error_msg)  # type: ignore
                except Exception:
                    print(error_msg)
        else:
            print(error_msg)
        metrics_inserted = {metric: 0 for metric in metrics_list}
        return FetchResult(
            success=False,
            total_inserted=0,
            total_errors=1,
            metrics_inserted=metrics_inserted,
            errors=[error_msg],
            account_id=instagram_account_id,
            user_id=user_id
        )


def get_user_instagram_account(
    supabase: Client,
    user_id: str
) -> Optional[Dict]:
    """Get user's Instagram account info from user_tokens table.
    
    For multi-user production, retrieves Instagram account ID and token
    from the user_tokens table instead of secrets.toml.
    
    Args:
        supabase: Supabase client instance
        user_id: User ID to look up
        
    Returns:
        Dict with 'account_id', 'access_token', 'expires_at', 'account_username', or None if not found
    """
    try:
        result = supabase.table("user_tokens") \
            .select("account_id, access_token, expires_at, account_username") \
            .eq("u_id", user_id) \
            .eq("platform", "instagram") \
            .execute()
        
        if result.data and len(result.data) > 0:
            token_data = result.data[0]
            return {
                "account_id": token_data.get("account_id"),
                "access_token": token_data.get("access_token"),
                "expires_at": token_data.get("expires_at"),
                "account_username": token_data.get("account_username")
            }
    except Exception as e:
        print(f"Error fetching user Instagram account: {e}")
    
    return None


def refresh_instagram_token(
    access_token: str,
    app_id: str,
    app_secret: str
) -> Optional[Dict]:
    """Refresh a long-lived Instagram access token.
    
    Uses Facebook's fb_exchange_token endpoint to extend token lifetime.
    Should be called before token expiry (typically 60 days).
    
    Args:
        access_token: Current long-lived access token
        app_id: Facebook App ID
        app_secret: Facebook App Secret
        
    Returns:
        Dict with 'access_token' and 'expires_in' (seconds), or None if failed
    """
    url = "https://graph.facebook.com/v18.0/oauth/access_token"
    
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": access_token
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if "access_token" in data:
            return {
                "access_token": data["access_token"],
                "expires_in": data.get("expires_in", 5184000)  # Default 60 days in seconds
            }
    except requests.exceptions.RequestException as e:
        print(f"Error refreshing Instagram token: {e}")
    
    return None


def get_latest_instagram_metrics(
    supabase: Client,
    user_id: Optional[str] = None,
    account_id: Optional[str] = None
) -> Dict[str, float]:
    """Get the latest Instagram metrics for a user/account.
    
    Uses the instagram_account_latest_metrics view for efficient querying.
    
    Args:
        supabase: Supabase client instance
        user_id: Optional user ID to filter by
        account_id: Optional account ID to filter by
        
    Returns:
        Dictionary mapping metric names to their latest values
    """
    try:
        query = supabase.table("instagram_account_latest_metrics").select("metric, value")
        
        if user_id:
            query = query.eq("u_id", user_id)
        if account_id:
            query = query.eq("account_id", account_id)
        
        result = query.execute()
        
        if not result.data:
            return {}
        
        # Build metric map
        latest_metrics = {}
        for record in result.data:
            metric_name = record.get("metric")
            if metric_name:
                latest_metrics[metric_name] = float(record.get("value", 0))
        
        return latest_metrics
    except Exception as e:
        print(f"Error fetching latest Instagram metrics: {e}")
        return {}
