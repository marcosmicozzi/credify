"""Instagram/Meta OAuth integration for multi-user Instagram account connection."""
import json
from typing import Optional, Dict, Tuple, Callable
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode

import requests
from requests import Response
from supabase import Client


def get_instagram_oauth_url(
    app_id: str,
    redirect_uri: str,
    state: str,
    scopes: Optional[list] = None
) -> str:
    """Generate Instagram OAuth authorization URL.
    
    Instagram OAuth is handled through Facebook/Meta OAuth.
    Requires Facebook App with Instagram Basic Display or Instagram Graph API product.
    
    Args:
        app_id: Facebook App ID
        redirect_uri: OAuth redirect URI (must match Facebook App settings)
        scopes: List of permission scopes (defaults to Instagram Graph API scopes)
        
    Returns:
        OAuth authorization URL
    """
    if scopes is None:
        # Instagram Graph API scopes for Business accounts
        scopes = [
            "instagram_basic",
            "instagram_manage_insights",
            "pages_read_engagement",  # For accessing Instagram Business accounts
            "pages_show_list"  # To list connected pages
        ]
    
    base_url = "https://www.facebook.com/v18.0/dialog/oauth"
    
    # Note: redirect_uri should be base URL only (no query params)
    # Facebook will append the state parameter automatically
    if not state:
        raise ValueError("state parameter is required for Instagram OAuth")

    params = {
        "client_id": app_id,
        "redirect_uri": redirect_uri,
        "scope": ",".join(scopes),
        "response_type": "code",
        "state": state,
    }

    query_string = urlencode(params)
    return f"{base_url}?{query_string}"


def _format_response_error(response: Optional[Response]) -> str:
    if response is None:
        return "No response received from Meta OAuth endpoint."

    try:
        payload = response.json()
        if isinstance(payload, dict):
            error_obj = payload.get("error")
            if isinstance(error_obj, dict):
                message = error_obj.get("message")
                error_code = error_obj.get("code")
                error_type = error_obj.get("type")
                details = " | ".join(
                    str(part)
                    for part in [
                        message,
                        f"type={error_type}" if error_type else None,
                        f"code={error_code}" if error_code else None,
                    ]
                    if part
                )
                if details:
                    return details
            return json.dumps(payload)
        return response.text
    except ValueError:
        return response.text


def exchange_code_for_token(
    app_id: str,
    app_secret: str,
    code: str,
    redirect_uri: str,
    debug_callback: Optional[Callable[[str, object], None]] = None,
) -> Tuple[Optional[Dict], Optional[str]]:
    """Exchange OAuth authorization code for access token.
    
    Args:
        app_id: Facebook App ID
        app_secret: Facebook App Secret
        code: Authorization code from OAuth callback
        redirect_uri: Same redirect URI used in authorization
        
    Returns:
        Dict with access_token, token_type, expires_in, or None if failed
    """
    url = "https://graph.facebook.com/v18.0/oauth/access_token"
    
    params = {
        "client_id": app_id,
        "client_secret": app_secret,
        "code": code,
        "redirect_uri": redirect_uri
    }

    if debug_callback:
        debug_callback("token_exchange_params", params)

    try:
        response = requests.get(url, params=params, timeout=30)

        if debug_callback:
            debug_callback("token_exchange_status", response.status_code)
            debug_callback("token_exchange_text", response.text)

        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and payload.get("error"):
            return None, _format_response_error(response)
        return payload, None
    except requests.exceptions.HTTPError as e:
        return None, _format_response_error(e.response)
    except requests.exceptions.RequestException as e:
        return None, str(e)


def get_long_lived_token(
    short_lived_token: str,
    app_id: str,
    app_secret: str,
    debug_callback: Optional[Callable[[str, object], None]] = None,
) -> Tuple[Optional[Dict], Optional[str]]:
    """Exchange short-lived token for long-lived token (60 days).
    
    Args:
        short_lived_token: Short-lived access token
        app_id: Facebook App ID
        app_secret: Facebook App Secret
        
    Returns:
        Dict with access_token and expires_in (seconds), or None if failed
    """
    url = "https://graph.facebook.com/v18.0/oauth/access_token"
    
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": short_lived_token
    }

    if debug_callback:
        debug_callback("long_token_params", params)

    try:
        response = requests.get(url, params=params, timeout=30)

        if debug_callback:
            debug_callback("long_token_status", response.status_code)
            debug_callback("long_token_text", response.text)

        response.raise_for_status()
        data = response.json()

        if isinstance(data, dict) and data.get("error"):
            return None, _format_response_error(response)

        if isinstance(data, dict) and "access_token" in data:
            return {
                "access_token": data["access_token"],
                "expires_in": data.get("expires_in", 5184000)  # Default 60 days
            }, None
    except requests.exceptions.HTTPError as e:
        return None, _format_response_error(e.response)
    except requests.exceptions.RequestException as e:
        return None, str(e)

    return None, "Unknown error retrieving long-lived token."


def get_instagram_business_account_id(
    access_token: str,
    page_id: Optional[str] = None
) -> Optional[Dict]:
    """Get Instagram Business Account ID and username from Facebook Page or user's pages.
    
    Args:
        access_token: Facebook access token with pages_read_engagement permission
        page_id: Optional specific Page ID. If None, gets first available page.
        
    Returns:
        Dict with 'account_id' and 'username', or None if not found
    """
    try:
        if page_id:
            # Get Instagram account for specific page
            url = f"https://graph.facebook.com/v18.0/{page_id}"
            params = {
                "fields": "instagram_business_account{id,username}",
                "access_token": access_token
            }
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if "instagram_business_account" in data:
                ig_account = data["instagram_business_account"]
                if isinstance(ig_account, dict):
                    return {
                        "account_id": ig_account.get("id"),
                        "username": ig_account.get("username")
                    }
                # If just ID string
                return {"account_id": str(ig_account), "username": None}
        else:
            # Get user's pages and find one with Instagram account
            url = "https://graph.facebook.com/v18.0/me/accounts"
            params = {
                "fields": "id,name,instagram_business_account{id,username}",
                "access_token": access_token
            }
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if "data" in data and len(data["data"]) > 0:
                # Find first page with Instagram Business account
                for page in data["data"]:
                    if "instagram_business_account" in page:
                        ig_account = page["instagram_business_account"]
                        if isinstance(ig_account, dict):
                            return {
                                "account_id": ig_account.get("id"),
                                "username": ig_account.get("username")
                            }
                        # If just ID string
                        return {"account_id": str(ig_account), "username": None}
    except requests.exceptions.RequestException as e:
        print(f"Error getting Instagram Business Account ID: {e}")
    
    return None


def store_instagram_token(
    supabase: Client,
    user_id: str,
    access_token: str,
    account_id: str,
    expires_in: Optional[int] = None,
    account_username: Optional[str] = None,
    refresh_token: Optional[str] = None
) -> bool:
    """Store Instagram token in user_tokens table.
    
    Args:
        supabase: Supabase client instance
        user_id: User ID
        access_token: Long-lived access token
        account_id: Instagram Business Account ID
        expires_in: Token expiry in seconds (optional)
        account_username: Instagram username (optional)
        
    Returns:
        True if stored successfully, False otherwise
    """
    try:
        expires_at = None
        if expires_in:
            expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
        
        # Upsert to handle updates
        token_data = {
            "u_id": user_id,
            "platform": "instagram",
            "access_token": access_token,
            "account_id": account_id,
            "account_username": account_username,
            "expires_at": expires_at,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        if refresh_token:
            token_data["refresh_token"] = refresh_token
        
        result = supabase.table("user_tokens").upsert(
            token_data,
            on_conflict="u_id,platform"
        ).execute()
        
        return result.data is not None
    except Exception as e:
        print(f"Error storing Instagram token: {e}")
        return False


def disconnect_instagram_account(
    supabase: Client,
    user_id: str
) -> bool:
    """Remove Instagram token for user.
    
    Args:
        supabase: Supabase client instance
        user_id: User ID
        
    Returns:
        True if removed successfully, False otherwise
    """
    try:
        result = supabase.table("user_tokens") \
            .delete() \
            .eq("u_id", user_id) \
            .eq("platform", "instagram") \
            .execute()
        
        return True
    except Exception as e:
        print(f"Error disconnecting Instagram account: {e}")
        return False


def is_token_expired(expires_at: Optional[str]) -> bool:
    """Check if token is expired or expiring soon (within 7 days).
    
    Args:
        expires_at: ISO timestamp string or None
        
    Returns:
        True if expired or expiring within 7 days, False otherwise
    """
    if not expires_at:
        return False  # No expiry info, assume valid
    
    try:
        expiry = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        else:
            expiry = expiry.astimezone(timezone.utc)
        
        # Check if expired or expiring within 7 days
        threshold = datetime.now(timezone.utc) + timedelta(days=7)
        return expiry <= threshold
    except (ValueError, AttributeError):
        return False  # Can't parse, assume valid

