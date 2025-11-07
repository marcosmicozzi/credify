import streamlit as st
from supabase import create_client, Client
import pandas as pd
import re
import requests
import json
import plotly.graph_objects as go
import plotly.express as px
from html import escape
import secrets
from auth import (
    show_login,
    logout_button,
    supabase as auth_supabase,
    get_redirect_url,
    is_localhost,
    get_facebook_app_credentials,
    get_instagram_redirect_url,
)  # logout now handled in topbar menu
from supabase_utils import get_following, is_following, follow_user, unfollow_user, search_users
from utils.instagram_fetcher import (
    fetch_and_store_instagram_insights,
    get_latest_instagram_metrics,
    get_user_instagram_account,
    FetchResult
)
from utils.instagram_oauth import (
    get_instagram_oauth_url,
    exchange_code_for_token,
    get_long_lived_token,
    get_instagram_business_account_id,
    store_instagram_token,
    disconnect_instagram_account,
    is_token_expired
)
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

# -------------------------------
# INITIAL SETUP
# -------------------------------
st.set_page_config(page_title="Credify", layout="wide", initial_sidebar_state="expanded")

# Remove Streamlit header / padding
st.markdown("""
<style>
[data-testid="stHeader"] {display:none !important;}
.block-container {padding-top:0rem !important;}
.stSidebar > div:first-child {margin-top: var(--topbar-h); padding-top: 20px !important;}
[data-testid="collapsedControl"] {display:none !important;}
/* Hide any Streamlit-provided sidebar collapse/expand controls (compat with multiple versions) */
button[title*="Hide sidebar"],
button[title*="Show sidebar"],
[data-testid="stSidebarNavCollapse"],
[data-testid="stSidebarCollapseControl"],
[data-testid="stSidebarCollapseButton"] { display:none !important; }
/* Force sidebar to remain visible and fixed width */
[data-testid="stSidebar"] { 
  visibility: visible !important; 
  transform: translateX(0) !important; 
  width: 240px !important; 
}
[data-testid="stSidebar"] > div:first-child { width: 240px !important; }
/* Ensure main content accounts for fixed sidebar width */
[data-testid="stAppViewContainer"] > .main { margin-left: 0 !important; }
/* Logout button styling */
button[data-testid="stBaseButton-secondary"] {
  background-color: #333 !important;
  color: #E8E8E8 !important;
  border: 1px solid #555 !important;
}
button[data-testid="stBaseButton-secondary"]:hover {
  background-color: #444 !important;
  border-color: #666 !important;
}
</style>
<script>
// Fix accessibility: Add aria-label to Streamlit main menu button
// Enhanced to persist attributes across Streamlit re-renders
(function() {
  const ARIA_LABEL = 'Open main menu';
  const TITLE = 'Open main menu';
  
  function fixMenuButtonAccessibility() {
    const menuButton = document.querySelector('[data-testid="stMainMenu"] button[data-testid="stBaseButton-headerNoPadding"]');
    if (menuButton) {
      const currentAriaLabel = menuButton.getAttribute('aria-label');
      // Fix if aria-label is missing or empty
      if (!currentAriaLabel || currentAriaLabel === '') {
        menuButton.setAttribute('aria-label', ARIA_LABEL);
      }
      // Always set title for tooltip
      const currentTitle = menuButton.getAttribute('title');
      if (!currentTitle || currentTitle === '') {
        menuButton.setAttribute('title', TITLE);
      }
    }
  }
  
  // Run immediately
  fixMenuButtonAccessibility();
  
  // Run after DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', fixMenuButtonAccessibility);
  } else {
    // DOM already loaded, run again after a short delay
    setTimeout(fixMenuButtonAccessibility, 100);
  }
  
  // Enhanced MutationObserver to watch for attribute removal
  const observer = new MutationObserver(function(mutations) {
    let needsFix = false;
    
    mutations.forEach(function(mutation) {
      // Check if aria-label or title was removed
      if (mutation.type === 'attributes') {
        if (mutation.attributeName === 'aria-label' || mutation.attributeName === 'title') {
          const target = mutation.target;
          // Check if it's the menu button
          if (target.matches && target.matches('[data-testid="stBaseButton-headerNoPadding"]')) {
            const ariaLabel = target.getAttribute('aria-label');
            const title = target.getAttribute('title');
            // If attribute was removed or is empty, we need to fix it
            if (!ariaLabel || ariaLabel === '' || !title || title === '') {
              needsFix = true;
            }
          }
        }
      } else if (mutation.type === 'childList') {
        // New elements added - check if menu button was added
        needsFix = true;
      }
    });
    
    // Apply fix if needed
    if (needsFix) {
      fixMenuButtonAccessibility();
    }
  });
  
  // Observe the entire document for changes with enhanced options
  observer.observe(document.body, { 
    childList: true, 
    subtree: true,
    attributes: true,
    attributeFilter: ['aria-label', 'title'],
    attributeOldValue: true  // Track old values to detect removal
  });
  
  // Also observe the menu container specifically if it exists
  const menuContainer = document.querySelector('[data-testid="stMainMenu"]');
  if (menuContainer) {
    observer.observe(menuContainer, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['aria-label', 'title'],
      attributeOldValue: true
    });
    
    // Also observe the button directly if we can find it
    const menuButton = menuContainer.querySelector('button[data-testid="stBaseButton-headerNoPadding"]');
    if (menuButton) {
      observer.observe(menuButton, {
        attributes: true,
        attributeFilter: ['aria-label', 'title'],
        attributeOldValue: true
      });
    }
  }
  
  // Re-check periodically when menu container is added (Streamlit re-renders)
  const containerObserver = new MutationObserver(function(mutations) {
    mutations.forEach(function(mutation) {
      if (mutation.type === 'childList') {
        mutation.addedNodes.forEach(function(node) {
          if (node.nodeType === 1 && node.matches && node.matches('[data-testid="stMainMenu"]')) {
            // Menu container was added, fix accessibility and observe it
            setTimeout(fixMenuButtonAccessibility, 50);
            observer.observe(node, {
              childList: true,
              subtree: true,
              attributes: true,
              attributeFilter: ['aria-label', 'title'],
              attributeOldValue: true
            });
          }
        });
      }
    });
  });
  
  // Watch for menu container being added to the DOM
  containerObserver.observe(document.body, {
    childList: true,
    subtree: true
  });
})();
</script>
""", unsafe_allow_html=True)

# -------------------------------
# SUPABASE CLIENT (via Streamlit secrets)
# -------------------------------
# Use the shared Supabase client from auth.py to ensure PKCE state consistency
SUPABASE_URL = st.secrets.get("SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_ANON_KEY")
YOUTUBE_API_KEY = st.secrets.get("YOUTUBE_API_KEY")
# Instagram tokens are now per-user (stored in user_tokens table)
# Legacy secrets kept for backward compatibility during migration
IG_LONG_TOKEN = st.secrets.get("IG_LONG_TOKEN", None)  # Deprecated: use per-user tokens
IG_ACCOUNT_ID = st.secrets.get("IG_ACCOUNT_ID", None)  # Deprecated: use per-user tokens

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Missing Supabase credentials. Please set SUPABASE_URL and SUPABASE_ANON_KEY in .streamlit/secrets.toml")
    st.stop()

if not YOUTUBE_API_KEY:
    st.error("Missing YOUTUBE_API_KEY in .streamlit/secrets.toml")
    st.stop()

# Use the same Supabase client instance as auth.py to maintain PKCE state
supabase: Client = auth_supabase

# -------------------------------
# AUTHENTICATION GATE
# -------------------------------
# IMPORTANT: Check for OAuth callback BEFORE session validation
# OAuth callbacks need to be processed first, before we validate existing sessions
query_params = st.query_params

# Check if this is an Instagram OAuth callback (has state=instagram_connect)
is_instagram_oauth = (
    "code" in query_params and 
    "state" in query_params and 
    query_params.get("state") == "instagram_connect"
)

# Check if this is a Supabase OAuth callback (code without Instagram state, or error)
is_supabase_oauth = (
    ("code" in query_params or "error" in query_params) and 
    not is_instagram_oauth
)

if is_supabase_oauth:
    # Supabase OAuth callback in progress - let auth.py handle it
    # Clear any stale session state to prevent validation errors
    # The OAuth handler will set the new session after successful exchange
    if "user" in st.session_state:
        # Clear stale user state during OAuth callback
        # This prevents session validation from failing on stale sessions
        del st.session_state["user"]
    if "session" in st.session_state:
        del st.session_state["session"]
    # Show login page which will handle the OAuth callback
    show_login()
    st.stop()

# Instagram OAuth callbacks are handled after authentication (user must be logged in)
# This will be processed later in the Settings page

if "user" not in st.session_state:
    show_login()
    st.stop()

# Validate user session is still valid
user = st.session_state.get("user")
if not user or not hasattr(user, "email"):
    # Session state exists but user object is invalid - clear and show login
    st.session_state.clear()
    show_login()
    st.stop()

# Verify Supabase session is still valid (skip for DemoUser and immediately after OAuth)
user_email = user.email
is_demo_user = user_email == "demo_user@example.com"
oauth_just_completed = st.session_state.get("oauth_just_completed", False)

# On localhost, be more lenient with session validation since cookies don't persist
# We rely on stored tokens instead, which are restored in auth.py
is_localhost_env = is_localhost()

# Skip session validation for DemoUser and immediately after OAuth completion
# OAuth completion flag prevents race condition where validation runs before Supabase session is ready
# On localhost, also skip validation if we have stored tokens (cookies won't work)
has_stored_tokens = "supabase_access_token" in st.session_state and "supabase_refresh_token" in st.session_state

if not is_demo_user and not oauth_just_completed and not (is_localhost_env and has_stored_tokens):
    # For real OAuth users, verify Supabase session is still valid
    try:
        # Try to get current user from Supabase to verify session
        current_user_response = auth_supabase.auth.get_user()
        if not current_user_response:
            # Session expired - clear and show login
            st.session_state.clear()
            auth_supabase.auth.sign_out()
            show_login()
            st.stop()
        
        # Check if we got a user object (different response formats)
        current_user = None
        if hasattr(current_user_response, "user"):
            current_user = current_user_response.user
        elif isinstance(current_user_response, dict) and "user" in current_user_response:
            current_user = current_user_response["user"]
        else:
            current_user = current_user_response
        
        # Verify the session user matches our stored user
        if not current_user or not hasattr(current_user, "email") or current_user.email.lower() != user_email.lower():
            # Session user doesn't match - clear and show login
            st.session_state.clear()
            auth_supabase.auth.sign_out()
            show_login()
            st.stop()
    except Exception as e:
        # Session validation failed - clear and show login
        # This catches expired tokens, network errors, etc.
        st.session_state.clear()
        try:
            auth_supabase.auth.sign_out()
        except Exception:
            pass
        show_login()
        st.stop()
elif oauth_just_completed:
    # OAuth just completed - clear the flag after this rerun
    # On the next rerun, session validation will run normally
    st.session_state["oauth_just_completed"] = False

normalized_email = user_email.lower()

# Handle Instagram OAuth callback if present (must be after authentication)
if is_instagram_oauth:
    # Get user ID for Instagram token storage
    try:
        user_res = supabase.table("users").select("u_id").eq("u_email", normalized_email).execute()
        if user_res.data and len(user_res.data) > 0:
            u_id = user_res.data[0]["u_id"]
            code = query_params.get("code")
            if code:
                handle_instagram_oauth_callback(u_id, code)
                # The callback handler will clear query params and rerun
                # If it doesn't rerun, we'll continue and the Settings page will also handle it
    except Exception as e:
        st.error(f"Error processing Instagram OAuth callback: {str(e)}")
        # Clear the callback params to prevent infinite loops
        st.query_params.clear()
        st.rerun()
# Logout and login notice now live under the avatar menu in the topbar

# -------------------------------
# THEME SETTINGS — single light monochrome palette
# -------------------------------
def apply_theme(_: str | None = None):
    # Fixed monochrome palette
    primary = "#2E2E2E"
    background = "#FFFFFF"
    secondary_bg = "#F4F4F4"
    text = "#111111"
    border = "#E0E0E0"
    border2 = "#C8C8C8"

    css_vars = {
        "--bg": background,
        "--text": text,
        "--sidebar": secondary_bg,
        "--card": secondary_bg,
        "--border": border,
        "--border-2": border2,
        "--input": "#FFFFFF",
        "--muted": secondary_bg,
        "--primary": primary,
        "--link": primary
    }

    vars_css = ":root{" + ";".join([f"{k}:{v}" for k, v in css_vars.items()]) + "}"

    st.markdown(f"""
        <style>
        {vars_css}
        body,.stApp{{background-color:var(--bg) !important;color:var(--text) !important;}}
        .stSidebar{{background-color:var(--sidebar) !important;color:var(--text) !important;border-right:1px solid var(--border);box-shadow: 2px 0 6px rgba(0,0,0,.06);}}
        .block-container{{max-width:1100px !important;margin:0 auto !important;padding:48px 32px !important;}}
        section {{padding: 0 !important;}}
        h1,h2,h3,h4,h5,h6,p,span,div{{color:var(--text) !important;}}
        a{{color:var(--link) !important;text-decoration:none;}}
        *{{font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif !important;}}

        /* Typography hierarchy */
        h1{{font-size:40px !important;font-weight:800 !important;margin-bottom:16px !important;}}
        h2{{font-size:22px !important;font-weight:700 !important;margin-top:8px !important;}}
        p{{font-size:16px !important;font-weight:400 !important;}}

        /* Inputs */
        .stTextInput>div>div>input,
        .stTextArea>div>div>textarea,
        .stSelectbox>div>div>select{{
            background-color:var(--input) !important;color:var(--text) !important;
            border:1px solid var(--border) !important;
        }}
        /* Baseweb Select dropdown */
        div[data-baseweb="select"]>div{{background-color:var(--input) !important;color:var(--text) !important;border-color:var(--border) !important;}}
        div[data-baseweb="select"] [role="listbox"]{{background-color:var(--input) !important;color:var(--text) !important;border:1px solid var(--border) !important;}}
        div[data-baseweb="select"] [role="option"]{{color:var(--text) !important;background-color:var(--input) !important;}}
        div[data-baseweb="select"] [aria-selected="true"]{{background-color:var(--card) !important;}}

        /* Buttons (monochrome) */
        .stButton>button{{background-color:var(--input) !important;color:var(--text) !important;border:1px solid var(--border) !important;}}
        .stButton>button:hover{{filter:brightness(0.97);border-color:var(--border-2) !important;}}
        /* Primary buttons */
        .stButton>button[kind="primary"],
        button[data-testid="baseButton-primary"]{{background-color:var(--primary) !important;color:#FFFFFF !important;border:1px solid var(--primary) !important;}}
        .stButton>button[kind="primary"]:hover,
        button[data-testid="baseButton-primary"]:hover{{filter:brightness(0.95);}}

        /* Radios/checkboxes accent to match primary */
        div[data-baseweb="radio"] svg{{fill:var(--primary) !important;}}
        div[role="radio"][aria-checked="true"]>div{{border-color:var(--primary) !important;}}

        /* Popovers */
        div[data-testid="stPopover"],
        div[data-testid="stPopoverBody"]{{background-color:var(--input) !important;color:var(--text) !important;border:1px solid var(--border) !important;}}
        div[data-testid="stPopover" ] *,
        div[data-testid="stPopoverBody"] *{{color:var(--text) !important;}}
        div[data-testid="stPopover"] .stButton>button,
        div[data-testid="stPopoverBody"] .stButton>button{{background-color:var(--input) !important;color:var(--text) !important;border:1px solid var(--border) !important;}}
        div[data-testid="stPopover"] .stButton>button:hover,
        div[data-testid="stPopoverBody"] .stButton>button:hover{{filter:brightness(0.97);border-color:var(--border-2) !important;}}

        /* Cards */
        .card, .project-card{{
            background-color:#FFFFFF;border-radius:12px;padding:16px;margin-bottom:16px;
            border:1px solid #E6E6E6; box-shadow:0 2px 6px rgba(0,0,0,0.08);
            transition:transform .15s ease, box-shadow .15s ease;
        }}
        .card:hover, .project-card:hover{{
            transform:translateY(-2px);
            box-shadow:0 4px 12px rgba(0,0,0,0.10);
        }}
        /* Project cards - equal height and alignment */
        /* Make Streamlit columns flex containers with equal height */
        div[data-testid="column"] {{
            display: flex !important;
            flex-direction: column !important;
        }}
        /* Make project cards fill column height */
        .project-card {{
            display: flex !important;
            flex-direction: column !important;
            height: 100% !important;
            flex-grow: 1;
        }}
        /* Ensure images have consistent height */
        .project-card img {{
            width: 100% !important;
            height: 200px !important;
            object-fit: cover !important;
            border-radius: 8px;
            margin-bottom: 12px;
            flex-shrink: 0;
        }}
        /* Handle "No thumbnail available" info box */
        .project-card .stAlert {{
            height: 200px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 12px;
            flex-shrink: 0;
        }}
        /* Consistent text spacing in project cards */
        .project-card > p {{
            margin: 0 0 8px 0 !important;
            line-height: 1.4;
        }}
        /* Title with consistent height (2 lines max) */
        .project-card > p:first-of-type {{
            font-weight: 600 !important;
            font-size: 14px !important;
            min-height: 3.2em !important; /* Reserve space for title (2 lines) */
            display: -webkit-box !important;
            -webkit-line-clamp: 2 !important;
            -webkit-box-orient: vertical !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
            flex-shrink: 0;
        }}
        /* Role with consistent height */
        .project-card > p:nth-of-type(2) {{
            font-style: italic !important;
            color: #666 !important;
            font-size: 12px !important;
            min-height: 1.5em !important; /* Reserve space for role */
            margin-bottom: 8px !important;
            flex-shrink: 0;
        }}
        /* Metrics caption - push to bottom */
        .project-card > .stCaption {{
            margin-top: auto !important;
            padding-top: 8px !important;
            border-top: 1px solid #F0F0F0 !important;
            flex-shrink: 0;
        }}
        .card-title{{font-weight:700;margin-bottom:8px;}}
        .page-section{{margin: 24px 0 32px 0;}}
        
        /* Search dropdown */
        .search-container{{position:relative;flex:1;max-width:400px;margin:0 16px;}}
        .search-dropdown{{
            position:absolute;top:100%;left:0;right:0;background:#FFFFFF;border:1px solid #E6E6E6;
            border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,0.15);z-index:1001;max-height:400px;
            overflow-y:auto;margin-top:4px;
        }}
        .search-result-item{{
            padding:12px 16px;border-bottom:1px solid #F0F0F0;cursor:pointer;display:flex;
            align-items:center;gap:12px;transition:background-color 0.15s;
        }}
        .search-result-item:hover{{background-color:#F8F8F8;}}
        .search-result-item:last-child{{border-bottom:none;}}
        .search-result-avatar{{width:40px;height:40px;border-radius:50%;flex-shrink:0;}}
        .search-result-content{{flex:1;min-width:0;}}
        .search-result-name{{font-weight:600;font-size:14px;margin-bottom:2px;}}
        .search-result-meta{{font-size:12px;color:#666;}}
        .search-result-action{{flex-shrink:0;}}

        /* Fixed Top Navigation */
        :root{{--topbar-h:56px;}}
        .topnav{{position:fixed;top:0;left:0;right:0;height:var(--topbar-h);display:flex;align-items:center;justify-content:space-between;gap:16px;padding:12px 24px;background:#FFFFFF;border-bottom:1px solid #E6E6E6;box-shadow:0 1px 2px rgba(0,0,0,.04);z-index:1000;}}
        .topnav .brand{{font-weight:800;font-size:18px;}}
        .topnav .actions{{display:flex;align-items:center;gap:12px;}}
        .topnav .avatar{{width:28px;height:28px;border-radius:50%;background:#E6E6E6;display:inline-block;}}
        /* Search positioning - below topbar */
        .search-wrapper{{position:fixed;top:var(--topbar-h);left:0;right:0;background:#FFFFFF;border-bottom:1px solid #E6E6E6;padding:8px 24px;z-index:999;display:flex;justify-content:center;}}
        /* Offset main container below topbar and search */
        [data-testid="stAppViewContainer"] > .main {{padding-top: calc(var(--topbar-h) + 56px) !important;}}

        /* Sidebar navigation styling */
        [data-testid="stSidebar"] [role="radiogroup"] label p{{font-size:15px !important;font-weight:600 !important;}}
        [data-testid="stSidebar"] [role="radio"][aria-checked="true"]{{background:#FFFFFF;border:1px solid #E6E6E6;border-radius:999px;padding:6px 10px;}}
        [data-testid="stSidebar"] [role="radio"]{{border-radius:999px;padding:6px 10px;}}
        [data-testid="stSidebar"] [role="radio"]:hover{{background:#FFFFFFaa}}
        .sb-brand{{font-weight:800;font-size:18px;margin:0 0 12px 0;}}
        
        /* Metric value font size - smaller to prevent truncation */
        [data-testid="stMetricValue"] {{
            font-size: 20px !important;
            line-height: 1.2 !important;
        }}
        [data-testid="stMetricLabel"] {{
            font-size: 12px !important;
        }}
        
        /* Profile section buttons - light hover styling */
        .add-credits-button-wrapper button {{
            background-color: #FFFFFF !important;
            color: #111111 !important;
            border: 1px solid #E0E0E0 !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            transition: all 0.2s ease-in-out !important;
            width: 100% !important;
        }}
        .add-credits-button-wrapper button:hover {{
            background-color: #F2F2F2 !important;
            border-color: #E0E0E0 !important;
        }}
        /* Refresh button in Profile section - matches sidebar color on hover */
        .profile-refresh-section .stButton > button {{
            transition: all 0.2s ease-in-out !important;
        }}
        .profile-refresh-section .stButton > button:hover {{
            background-color: #F4F4F4 !important;
        }}
        </style>
    """, unsafe_allow_html=True)

# -------------------------------
# HELPERS
# -------------------------------
def sanitize_user_input(text: str) -> str:
    """Sanitize user input by removing HTML tags and dangerous content.
    
    This function strips HTML tags and potentially malicious content from user-generated
    text while preserving legitimate text. The sanitized text is safe to display
    without escaping.
    
    Args:
        text: Input string that may contain HTML or special characters
        
    Returns:
        Sanitized string safe for display
    """
    if not text:
        return ""
    
    # First decode HTML entities (handles legacy escaped data like &lt;script&gt;)
    # Use html.unescape to convert &lt; back to <, &gt; back to >, etc.
    from html import unescape
    text = unescape(text)
    
    # Remove HTML tags using regex (more comprehensive than simple replace)
    # This pattern matches any HTML tag including attributes
    text = re.sub(r'<[^>]+>', '', text)
    
    # Remove any remaining script-like patterns (extra safety)
    text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
    text = re.sub(r'on\w+\s*=', '', text, flags=re.IGNORECASE)
    
    # Strip leading/trailing whitespace and collapse multiple spaces
    text = ' '.join(text.split())
    
    return text


def extract_video_id(url):
    pattern = r"(?:v=|youtu\\.be/|embed/)([a-zA-Z0-9_-]{11})"
    match = re.search(pattern, url)
    return match.group(1) if match else None


def is_valid_image_url(url: str) -> bool:
    """Basic validation for profile image URLs.

    - Requires http/https scheme and a hostname
    - Rejects overly long URLs
    - Attempts a HEAD request to confirm Content-Type is image/*
    - Falls back to file extension heuristics if HEAD fails
    """
    if not url:
        return False
    candidate = url.strip()
    if len(candidate) > 2048:
        return False
    parsed = urlparse(candidate)
    if parsed.scheme not in ("http", "https"):
        return False
    if not parsed.netloc:
        return False
    path_lower = (parsed.path or "").lower()
    has_image_ext = any(path_lower.endswith(ext) for ext in [
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"
    ])
    try:
        head_resp = requests.head(candidate, timeout=5, allow_redirects=True)
        content_type = (head_resp.headers.get("Content-Type") or "").lower()
        if content_type.startswith("image/"):
            return True
    except Exception:
        pass
    return has_image_ext


def fetch_youtube_data(video_id: str) -> dict | None:
    """Fetch YouTube video data from the YouTube Data API.
    
    Args:
        video_id: YouTube video ID (must be exactly 11 characters)
        
    Returns:
        Dictionary with video metadata or None if fetch/validation fails
    """
    # Validate video_id format (YouTube IDs are exactly 11 characters)
    if not video_id or len(video_id) != 11:
        return None
    
    # Additional validation: YouTube IDs contain only alphanumeric, hyphens, and underscores
    if not video_id.replace("-", "").replace("_", "").isalnum():
        return None
    
    url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics&id={video_id}&key={YOUTUBE_API_KEY}"
    res = requests.get(url, timeout=15)
    if not res.ok:
        return None
    try:
        data = res.json()
    except Exception:
        return None
    if "items" not in data or not data.get("items"):
        return None

    item = data["items"][0]
    snippet = item.get("snippet", {})
    stats = item.get("statistics", {})
    
    # Get best available thumbnail (fallback chain: high -> medium -> default)
    thumbnails = snippet.get("thumbnails", {})
    thumbnail_url = None
    for quality in ["high", "medium", "default"]:
        if quality in thumbnails and isinstance(thumbnails[quality], dict) and "url" in thumbnails[quality]:
            thumbnail_url = thumbnails[quality]["url"]
            break
    
    return {
        "p_id": video_id,
        "p_title": snippet.get("title", "Untitled"),
        "p_description": snippet.get("description", ""),
        "p_link": f"https://www.youtube.com/watch?v={video_id}",
        "p_channel": snippet.get("channelTitle", "Unknown"),
        "p_posted_at": snippet.get("publishedAt"),
        "p_thumbnail_url": thumbnail_url,  # Can be None if no thumbnails available
        "view_count": int(stats.get("viewCount", 0) or 0),
        "like_count": int(stats.get("likeCount", 0) or 0),
        "comment_count": int(stats.get("commentCount", 0) or 0)
    }


def fetch_live_metrics_for_user(u_id: str) -> dict[str, dict[str, int]] | None:
    """Fetch live metrics from YouTube API without storing them.
    
    This is for display-only purposes. The live snapshot is NOT persisted to the database.
    Only AWS Lambda should write to youtube_metrics for daily snapshots.
    
    Args:
        u_id: User ID to fetch live metrics for
        
    Returns:
        Dictionary mapping p_id to metrics dict, or None if error
    """
    # 1. Get all project IDs for this user
    projects_resp = supabase.table("user_projects").select("p_id").eq("u_id", u_id).execute()
    project_ids = [p["p_id"] for p in projects_resp.data]
    
    if not project_ids:
        return {}
    
    # 2. Batch fetch from YouTube API (max 50 IDs per request)
    batch_size = 50
    live_metrics = {}
    
    for i in range(0, len(project_ids), batch_size):
        batch_ids = project_ids[i:i + batch_size]
        ids_comma = ",".join(batch_ids)
        
        # Fetch statistics for this batch
        url = f"https://www.googleapis.com/youtube/v3/videos?part=statistics&id={ids_comma}&key={YOUTUBE_API_KEY}"
        try:
            res = requests.get(url, timeout=20)
            if not res.ok:
                continue
            data = res.json()
            if not data.get("items"):
                continue
            
            # Extract metrics without storing
            for item in data["items"]:
                p_id = item["id"]
                stats = item.get("statistics", {})
                live_metrics[p_id] = {
                    "view_count": int(stats.get("viewCount", 0)),
                    "like_count": int(stats.get("likeCount", 0)),
                    "comment_count": int(stats.get("commentCount", 0)),
                    "share_count": 0,  # YouTube API doesn't provide share_count
                }
        except Exception:
            # Skip failed batches, continue with next
            continue
    
    return live_metrics if live_metrics else None


@st.cache_data(show_spinner=False)
def fetch_channels_for_projects(project_ids: list[str]) -> dict[str, dict[str, str]]:
    """Return a map of YouTube channelId -> {title, url} for given video IDs.

    This uses the YouTube Data API to fetch snippet info and extract channel IDs/titles.
    """
    if not project_ids:
        return {}

    channels: dict[str, dict[str, str]] = {}
    batch_size = 50
    for i in range(0, len(project_ids), batch_size):
        batch_ids = project_ids[i:i + batch_size]
        ids_comma = ",".join(batch_ids)
        url = (
            f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={ids_comma}&key={YOUTUBE_API_KEY}"
        )
        try:
            res = requests.get(url, timeout=20)
            if not res.ok:
                continue
            data = res.json()
            for item in (data.get("items") or []):
                snippet = item.get("snippet", {})
                ch_id = snippet.get("channelId")
                ch_title = snippet.get("channelTitle") or "Unknown Channel"
                if ch_id and ch_id not in channels:
                    channels[ch_id] = {
                        "title": ch_title,
                        "url": f"https://www.youtube.com/channel/{ch_id}",
                    }
        except Exception:
            # Skip failures silently to avoid breaking the page
            continue

    return channels

# -------------------------------
# ANALYTICS HELPERS (daily time series)
# -------------------------------
@st.cache_data(show_spinner=False)
def get_user_id_by_email_cached(email: str) -> str | None:
    res = supabase.table("users").select("u_id").eq("u_email", email).execute()
    if not res.data:
        return None
    return res.data[0]["u_id"]


def get_current_user_id() -> str | None:
    """Get current logged-in user's ID from session state."""
    return get_user_id_by_email_cached(normalized_email)


def update_user_metrics(u_id: str):
    """Recalculate and update user_metrics for a given user based on their projects.
    
    This function aggregates stored snapshots from youtube_latest_metrics (which references
    daily snapshots written by AWS Lambda). It does NOT fetch live data from YouTube API.
    For live metrics, use fetch_live_metrics_for_user() instead.
    """
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
    # Try youtube_latest_metrics first (preferred for real-time), fall back to youtube_metrics if table doesn't exist
    try:
        metrics_resp = supabase.table("youtube_latest_metrics").select("p_id, view_count, like_count, comment_count, share_count, fetched_at").in_("p_id", project_ids).execute()
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
                    "fetched_at": m.get("fetched_at"),  # Required for freshness guard
                })
                seen_pids.add(pid)
    
    if not latest_metrics:
        # No metrics found, set all to zero
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

    # 2b. Freshness guard: if user_metrics.updated_at >= max(latest fetched_at), skip recompute
    try:
        # Compute latest fetched_at across this user's projects
        latest_ts_candidates = [m.get("fetched_at") for m in latest_metrics if m.get("fetched_at")]
        if latest_ts_candidates:
            latest_ts = max(latest_ts_candidates)
            um_res = supabase.table("user_metrics").select("updated_at").eq("u_id", u_id).execute()
            if um_res.data and um_res.data[0].get("updated_at") and um_res.data[0]["updated_at"] >= latest_ts:
                return
    except Exception:
        # If anything goes wrong, proceed with recompute to be safe
        pass

    # 3. Aggregate totals
    total_views = sum(m.get("view_count", 0) or 0 for m in latest_metrics)
    total_likes = sum(m.get("like_count", 0) or 0 for m in latest_metrics)
    total_comments = sum(m.get("comment_count", 0) or 0 for m in latest_metrics)
    total_shares = sum(m.get("share_count", 0) or 0 for m in latest_metrics)
    
    # Calculate engagement rate (likes + comments + shares) / views * 100
    engagement_rates = []
    for m in latest_metrics:
        views = m.get("view_count", 0) or 0
        if views > 0:
            likes = m.get("like_count", 0) or 0
            comments = m.get("comment_count", 0) or 0
            shares = m.get("share_count", 0) or 0
            engagement = ((likes + comments + shares) / views) * 100
            engagement_rates.append(engagement)
    avg_engagement = sum(engagement_rates) / len(engagement_rates) if engagement_rates else 0

    # 4. Upsert into user_metrics
    supabase.table("user_metrics").upsert({
        "u_id": u_id,
        "total_view_count": total_views,
        "total_like_count": total_likes,
        "total_comment_count": total_comments,
        "total_share_count": total_shares,
        "avg_engagement_rate": avg_engagement,
        "updated_at": datetime.utcnow().isoformat()
    }).execute()


@st.cache_data(show_spinner=False)
def fetch_user_daily_timeseries(u_id: str, start_date_iso: str, end_date_iso: str) -> pd.DataFrame:
    """Return daily increments (not lifetime) aggregated across all user's videos.

    Works with either data shape in youtube_metrics:
    - cumulative per-day snapshots (typical API snapshots) → use positive day-over-day diff
    - daily increments already stored → use values directly
    """
    # Fetch project ids for user
    up_resp = supabase.table("user_projects").select("p_id").eq("u_id", u_id).execute()
    pids = [row["p_id"] for row in (up_resp.data or [])]
    if not pids:
        return pd.DataFrame(columns=["date", "views", "likes", "comments"]).astype({"date": "datetime64[ns]"})

    # Parse date range in UTC for consistent comparison
    start_dt_utc = pd.to_datetime(start_date_iso, utc=True)
    end_dt_utc = pd.to_datetime(end_date_iso, utc=True)
    
    # Query includes one day BEFORE start_date to get baseline for diff calculation
    # This ensures the first day in the range has a previous value to compare against
    query_start = (start_dt_utc - pd.Timedelta(days=1)).isoformat()
    
    # Check if there's ANY data for these projects (without date filter) for debugging
    all_metrics_check = supabase.table("youtube_metrics") \
        .select("p_id, fetched_at, view_count, like_count, comment_count") \
        .in_("p_id", pids) \
        .order("fetched_at", desc=False) \
        .limit(1) \
        .execute()
    
    # Fetch two sets:
    # 1) Baseline: latest snapshot BEFORE start_dt_utc for each p_id
    baseline_resp = supabase.table("youtube_metrics") \
        .select("p_id, fetched_at, view_count, like_count, comment_count") \
        .in_("p_id", pids) \
        .lt("fetched_at", start_date_iso) \
        .order("fetched_at", desc=True) \
        .limit(10000) \
        .execute()

    # Deduplicate to keep latest-before-start per p_id
    baseline_rows = []
    seen = set()
    for r in (baseline_resp.data or []):
        pid = r.get("p_id")
        if pid and pid not in seen:
            baseline_rows.append(r)
            seen.add(pid)

    # 2) In-range snapshots: start..end (inclusive)
    range_resp = supabase.table("youtube_metrics") \
        .select("p_id, fetched_at, view_count, like_count, comment_count") \
        .in_("p_id", pids) \
        .gte("fetched_at", start_date_iso) \
        .lte("fetched_at", end_date_iso) \
        .execute()

    rows = (baseline_rows or []) + (range_resp.data or [])
    if not rows:
        # If no rows in date range, check if data exists outside the range
        if all_metrics_check.data:
            return pd.DataFrame(columns=["date", "views", "likes", "comments"]).astype({"date": "datetime64[ns]"})
        # No data at all for these projects
        return pd.DataFrame(columns=["date", "views", "likes", "comments"]).astype({"date": "datetime64[ns]"})

    df = pd.DataFrame(rows)
    # Normalize timestamps to UTC and derive date (avoid tz conversion issues)
    df["fetched_at"] = pd.to_datetime(df["fetched_at"], utc=True, errors="coerce")
    df["date"] = df["fetched_at"].dt.date

    # Keep the last snapshot per video per day
    df_sorted = df.sort_values(["p_id", "date", "fetched_at"])  # ascending so last per group is last row
    last_per_day = df_sorted.groupby(["p_id", "date"], as_index=False).tail(1)

    # Compute per‑video daily increments (LAG-style): strictly use day-over-day diffs
    last_per_day = last_per_day.sort_values(["p_id", "date"])  # ensure order
    increments = []
    for pid, group in last_per_day.groupby("p_id", as_index=False):
        g = group.copy()
        for col in ["view_count", "like_count", "comment_count"]:
            vals = g[col].diff().fillna(0).clip(lower=0)
            g[col + "_inc"] = vals
        increments.append(g[["p_id", "date", "view_count_inc", "like_count_inc", "comment_count_inc"]])
    if not increments:
        return pd.DataFrame(columns=["date", "views", "likes", "comments"]).astype({"date": "datetime64[ns]"})
    inc_df = pd.concat(increments, ignore_index=True)

    # Filter increments to only include dates >= start_date (exclude the baseline day)
    start_date_only = start_dt_utc.date()
    inc_df_filtered = inc_df[inc_df["date"] >= start_date_only].copy()
    
    # Aggregate across videos per day — daily increments
    agg = inc_df_filtered.groupby("date", as_index=False).agg({
        "view_count_inc": "sum",
        "like_count_inc": "sum",
        "comment_count_inc": "sum",
    }).rename(columns={
        "view_count_inc": "views",
        "like_count_inc": "likes",
        "comment_count_inc": "comments",
    })

    # Only fill with zeros if we have at least some data in the range
    # This prevents showing zeros when there's no data at all in the selected period
    if len(agg) == 0:
        # No aggregated data means no actual data points in this range
        return pd.DataFrame(columns=["date", "views", "likes", "comments"]).astype({"date": "datetime64[ns]"})
    
    # Ensure full date index for selected range (fill missing days with zeros)
    # But only if we have at least one data point
    start_dt = start_dt_utc.date()
    end_dt = end_dt_utc.date()
    all_days = pd.date_range(start=start_dt, end=end_dt, freq="D").date
    full = pd.DataFrame({"date": all_days})
    out = full.merge(agg, on="date", how="left")
    out = out.fillna({"views": 0, "likes": 0, "comments": 0})
    out["date"] = pd.to_datetime(out["date"])  # for chart x-axis
    return out


@st.cache_data(show_spinner=False)
def fetch_instagram_daily_timeseries(u_id: str, start_date_iso: str, end_date_iso: str, metric_name: str) -> pd.DataFrame:
    """Return daily Instagram metrics for a specific metric.
    
    Instagram metrics are already daily values (not cumulative), so we just aggregate by date.
    
    Args:
        u_id: User ID
        start_date_iso: Start date in ISO format
        end_date_iso: End date in ISO format
        metric_name: Metric name (e.g., 'reach', 'profile_views', 'accounts_engaged', 'follower_count')
        
    Returns:
        DataFrame with columns: date, value
    """
    # Parse date range
    start_dt_utc = pd.to_datetime(start_date_iso, utc=True)
    end_dt_utc = pd.to_datetime(end_date_iso, utc=True)
    
    # Fetch Instagram insights for this user and metric
    insights_resp = supabase.table("instagram_insights") \
        .select("value, end_time") \
        .eq("user_id", u_id) \
        .eq("metric", metric_name) \
        .gte("end_time", start_date_iso) \
        .lte("end_time", end_date_iso) \
        .order("end_time", desc=False) \
        .execute()
    
    if not insights_resp.data:
        return pd.DataFrame(columns=["date", "value"]).astype({"date": "datetime64[ns]"})
    
    # Convert to DataFrame
    df = pd.DataFrame(insights_resp.data)
    df["end_time"] = pd.to_datetime(df["end_time"], utc=True, errors="coerce")
    df["date"] = df["end_time"].dt.date
    
    # Aggregate by date (take latest value per day if multiple)
    df_sorted = df.sort_values(["date", "end_time"])
    daily_agg = df_sorted.groupby("date", as_index=False).last()
    
    # Ensure full date range
    start_dt = start_dt_utc.date()
    end_dt = end_dt_utc.date()
    all_days = pd.date_range(start=start_dt, end=end_dt, freq="D").date
    full = pd.DataFrame({"date": all_days})
    out = full.merge(daily_agg[["date", "value"]], on="date", how="left")
    out = out.fillna({"value": 0})
    out["date"] = pd.to_datetime(out["date"])
    
    return out



# -------------------------------
# PAGE 1 — PROFILE (replaces Dashboard)
# -------------------------------
def show_profile():
    # Get user info
    user_res = supabase.table("users").select("*").eq("u_email", normalized_email).execute()
    if not user_res.data:
        st.info("No profile found yet — one will be created after your first claim.")
        return

    user = user_res.data[0]
    u_id = user["u_id"]

    # Profile header: image centered, name below it (centered)
    # Use saved profile image if available, otherwise fall back to generated avatar
    profile_image_url = user.get("profile_image_url")
    if profile_image_url:
        avatar_url = profile_image_url
    else:
        avatar_url = f"https://api.dicebear.com/7.x/identicon/svg?seed={user['u_name']}"
    st.markdown(f"""
        <div style="text-align: center; margin-bottom: 24px;">
            <img src="{avatar_url}" 
                 style="width: 140px; height: 140px; border-radius: 50%; margin: 0 auto 12px auto; display: block; object-fit: cover; object-position: center; border: 3px solid #E6E6E6; box-shadow: 0 2px 8px rgba(0,0,0,0.1); transform: translateX(-12px);" />
        </div>
    """, unsafe_allow_html=True)
    
    # Metrics - Profile shows live data only
    # Live refresh button with cooldown to protect API limits
    # Store live metrics in session state to persist during user session
    if "live_metrics" not in st.session_state:
        st.session_state.live_metrics = None
    
    # Auto-fetch live metrics on first page load if not in session
    if st.session_state.live_metrics is None:
        with st.spinner("Fetching live metrics..."):
            live_data = fetch_live_metrics_for_user(u_id)
            if live_data:
                st.session_state.live_metrics = live_data
    
    cooldown_seconds = 300  # 5 minutes
    ss_key = "user_refresh_cooldown"
    if ss_key not in st.session_state:
        st.session_state[ss_key] = 0
    last_ts = st.session_state[ss_key]
    now_ts = datetime.now(timezone.utc).timestamp()
    remaining = max(0, int(cooldown_seconds - (now_ts - last_ts)))
    
    # Always display live metrics - Profile is live data only
    if st.session_state.live_metrics:
        # Aggregate live metrics
        live_total_views = sum(m["view_count"] for m in st.session_state.live_metrics.values())
        live_total_likes = sum(m["like_count"] for m in st.session_state.live_metrics.values())
        live_total_comments = sum(m["comment_count"] for m in st.session_state.live_metrics.values())
        live_total_shares = sum(m["share_count"] for m in st.session_state.live_metrics.values())
        live_engagement_rates = []
        for m in st.session_state.live_metrics.values():
            views = m["view_count"]
            if views > 0:
                engagement = ((m["like_count"] + m["comment_count"] + m["share_count"]) / views) * 100
                live_engagement_rates.append(engagement)
        live_avg_engagement = sum(live_engagement_rates) / len(live_engagement_rates) if live_engagement_rates else 0
        display_metrics = {
            "total_view_count": live_total_views,
            "total_like_count": live_total_likes,
            "total_comment_count": live_total_comments,
            "total_share_count": live_total_shares,
            "avg_engagement_rate": live_avg_engagement
        }
    else:
        # No live metrics yet - show zeros while fetching
        display_metrics = {
            "total_view_count": 0,
            "total_like_count": 0,
            "total_comment_count": 0,
            "total_share_count": 0,
            "avg_engagement_rate": 0
        }
    
    # User name centered and bold with balanced spacing
    # Sanitize on display for defense in depth (handles both new and legacy data)
    sanitized_name = sanitize_user_input(user.get('u_name', ''))
    st.markdown(f"<h1 style='text-align: center; margin-bottom: 0px; font-weight: 800;'>{sanitized_name}</h1>", unsafe_allow_html=True)
    
    # Bio centered below name (if exists) with consistent spacing
    bio_spacing = "4px" if user.get("u_bio") else "0px"
    metrics_top_margin = "16px" if user.get("u_bio") else "20px"  # Adjust to maintain 20px total spacing
    if user.get("u_bio"):
        # Sanitize on display for defense in depth (handles both new and legacy data)
        sanitized_bio = sanitize_user_input(user.get('u_bio', ''))
        st.markdown(f"<p style='text-align: center; color: #666; margin-top: {bio_spacing}; margin-bottom: 0px;'>{sanitized_bio}</p>", unsafe_allow_html=True)
    
    # Compact metrics layout: centered stats badge with balanced spacing
    # Calculate spacing for equal name-to-metrics and metrics-to-refresh spacing
    spacing_value = "20px"  # Use consistent 20px spacing for visual balance
    st.markdown(f"""
        <style>
        .profile-metrics-container {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 50px;
            margin: {metrics_top_margin} 0 {spacing_value} 0;
            flex-wrap: wrap;
        }}
        .profile-metric-item {{
            text-align: center;
            min-width: 60px;
        }}
        @media (max-width: 768px) {{
            .profile-metrics-container {{
                gap: 30px;
            }}
        }}
        @media (max-width: 480px) {{
            .profile-metrics-container {{
                gap: 20px;
            }}
        }}
        </style>
    """, unsafe_allow_html=True)
    
    # Metrics displayed in centered compact layout (combined across platforms)
    metric_html = f"""
        <div class="profile-metrics-container">
            <div class="profile-metric-item">
                <div style="font-size: 12px; color: #666; margin-bottom: 4px;">Views</div>
                <div style="font-size: 20px; font-weight: 700;">{display_metrics['total_view_count']:,}</div>
            </div>
            <div class="profile-metric-item">
                <div style="font-size: 12px; color: #666; margin-bottom: 4px;">Likes</div>
                <div style="font-size: 20px; font-weight: 700;">{display_metrics['total_like_count']:,}</div>
            </div>
            <div class="profile-metric-item">
                <div style="font-size: 12px; color: #666; margin-bottom: 4px;">Comments</div>
                <div style="font-size: 20px; font-weight: 700;">{display_metrics['total_comment_count']:,}</div>
            </div>
        </div>
    """
    st.markdown(metric_html, unsafe_allow_html=True)
    
    # Platform sections (YouTube / Instagram / TikTok)
    # Prepare per-platform totals; currently only YouTube live metrics exist
    youtube_totals = {
        "views": display_metrics["total_view_count"],
        "likes": display_metrics["total_like_count"],
        "comments": display_metrics["total_comment_count"],
    }
    instagram_totals = {"views": 0, "likes": 0, "comments": 0}
    tiktok_totals = {"views": 0, "likes": 0, "comments": 0}

    # Refresh button below metrics (perfectly centered using columns)
    disabled = remaining > 0
    label = "Refresh" if not disabled else f"{remaining}s"
    
    # Wrap in a container for styling
    st.markdown('<div class="profile-refresh-section">', unsafe_allow_html=True)
    # Use columns to center the button perfectly
    refresh_col1, refresh_col2, refresh_col3 = st.columns([1, 2, 1])
    with refresh_col2:
        if st.button(label, key="live_refresh_btn", disabled=disabled, use_container_width=True):
            with st.spinner("Fetching latest metrics from YouTube..."):
                live_data = fetch_live_metrics_for_user(u_id)
            if live_data:
                st.session_state.live_metrics = live_data
                st.session_state[ss_key] = datetime.now(timezone.utc).timestamp()
                st.success(f"Fetched latest metrics for {len(live_data)} videos")
                st.rerun()
            else:
                st.warning("Could not fetch live metrics right now.")
    st.markdown('</div>', unsafe_allow_html=True)

    # Platform sections (matching Analytics button style)
    st.markdown("### Platforms")
    btn_cols = st.columns(3)
    with btn_cols[0]:
        st.markdown(f"**YouTube**")
        if st.button("YouTube Overview", key="btn_youtube", use_container_width=True):
            st.session_state["selected_platform"] = "youtube"
            st.session_state["page_override"] = "YouTube"
            st.rerun()
    with btn_cols[1]:
        st.markdown(f"**Instagram**")
        if st.button("Instagram Overview", key="btn_instagram", use_container_width=True):
            st.session_state["selected_platform"] = "instagram"
            st.session_state["page_override"] = "Instagram"
            st.rerun()
    with btn_cols[2]:
        st.markdown(f"**TikTok**")
        if st.button("TikTok Overview", key="btn_tiktok", use_container_width=True):
            st.session_state["selected_platform"] = "tiktok"
            st.session_state["page_override"] = "TikTok"
            st.rerun()
    
    st.divider()

    # Add Credit entry point (opens inline section)
    if "show_add_credit" not in st.session_state:
        st.session_state.show_add_credit = False

    # Full-width Add Credits button matching login button style
    st.markdown('<div class="add-credits-button-wrapper">', unsafe_allow_html=True)
    if st.button("Add Credits", key="add_credits_btn", use_container_width=True):
        st.session_state.show_add_credit = not st.session_state.show_add_credit
    st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.show_add_credit:
        st.markdown("#### Add New Credit")
        render_add_credit_form()
        st.divider()

    # Credits and collaborators have moved to the platform pages

def render_add_credit_form():
    """Inline claim form reused inside Profile."""
    url_input = st.text_input("Paste a YouTube URL")
    name = st.text_input("Full name")
    bio = st.text_area("Short bio (optional)")

    # Roles
    roles_response = supabase.table("roles").select("role_name, category").execute()
    categories = {}
    if roles_response.data:
        for r in roles_response.data:
            cat = r["category"] if r["category"] else "Misc"
            categories.setdefault(cat, []).append(r["role_name"])
    else:
        categories = {"Misc": ["Other"]}

    if "selected_roles" not in st.session_state:
        st.session_state.selected_roles = []

    category = st.selectbox("Select category", list(categories.keys()), key="category_select")
    role = st.selectbox("Select role", categories[category], key="role_select")

    if st.button("➕ Add Role"):
        role_entry = f"{category} - {role}"
        if role_entry not in st.session_state.selected_roles:
            st.session_state.selected_roles.append(role_entry)
        else:
            st.warning("You've already added this role.")

    if st.session_state.selected_roles:
        st.markdown("**Added roles:**")
        for r in st.session_state.selected_roles:
            st.write(f"• {r}")
    else:
        st.info("No roles added yet. Add at least one before claiming.")

    if st.button("Claim Role"):
        if not url_input or not name:
            st.error("Please fill in all required fields.")
            st.stop()
        elif not st.session_state.selected_roles:
            st.error("Please add at least one role.")
            st.stop()

        video_id = extract_video_id(url_input)
        if not video_id:
            st.error("Invalid YouTube URL.")
            st.stop()

        # Check if project exists
        existing = supabase.table("projects").select("*").eq("p_id", video_id).execute().data
        if existing:
            project = existing[0]
            st.info(f"Project already exists: {project['p_title']}")
        else:
            video_data = fetch_youtube_data(video_id)
            if not video_data:
                st.error("Could not fetch video info from YouTube API.")
                st.stop()

            supabase.table("projects").insert({
                "p_id": video_data["p_id"],
                "p_title": video_data["p_title"],
                "p_description": video_data["p_description"],
                "p_link": video_data["p_link"],
                "p_platform": "youtube",
                "p_channel": video_data["p_channel"],
                "p_posted_at": video_data["p_posted_at"],
                "p_thumbnail_url": video_data.get("p_thumbnail_url")  # Can be None if no thumbnail available
            }).execute()

            # Insert metrics entry (fetched_at is timestamp, so duplicates unlikely, but check to be safe)
            fetched_at = datetime.utcnow().isoformat()
            existing_metrics = supabase.table("youtube_metrics").select("p_id").eq("p_id", video_data["p_id"]).eq("fetched_at", fetched_at).execute()
            if not existing_metrics.data:
                supabase.table("youtube_metrics").insert({
                    "p_id": video_data["p_id"],
                    "platform": "youtube",
                    "fetched_at": fetched_at,
                    "view_count": video_data["view_count"],
                    "like_count": video_data["like_count"],
                    "comment_count": video_data["comment_count"]
                }).execute()

            st.success(f"Added new project: {video_data['p_title']}")

        # Ensure user exists / update (sanitize user inputs before saving)
        supabase.table("users").upsert({
            "u_email": normalized_email,
            "u_name": sanitize_user_input(name) if name else "",
            "u_bio": sanitize_user_input(bio) if bio else ""
        }, on_conflict=["u_email"]).execute()

        user_record = supabase.table("users").select("u_id").eq("u_email", normalized_email).execute()
        u_id = user_record.data[0]["u_id"]

        for role_entry in st.session_state.selected_roles:
            _, role_name = role_entry.split(" - ")
            # Check if this role assignment already exists to prevent duplicates
            existing = supabase.table("user_projects").select("u_id").eq("u_id", u_id).eq("p_id", video_id).eq("u_role", role_name).execute()
            if not existing.data:
                # Insert only if it doesn't exist
                supabase.table("user_projects").insert({
                    "u_id": u_id,
                    "p_id": video_id,
                    "u_role": role_name
                }).execute()

        # Update user metrics after credits are added
        update_user_metrics(u_id)
        
        st.success(f"{name} is now credited for: {', '.join(st.session_state.selected_roles)}")
        st.balloons()
        st.session_state.selected_roles = []
        st.rerun()  # Refresh page to show updated metrics

# -------------------------------
# PAGE 3 — HOME FEED
# -------------------------------
def show_home_page():
    st.title("Home")
    
    current_u_id = get_current_user_id()
    if not current_u_id:
        st.info("Please complete your profile to see your feed.")
        return
    
    # Get list of followed users
    followed_ids = get_following(supabase, current_u_id)
    
    if not followed_ids:
        st.info("Follow creators to see their updates here. Use the search bar above to discover and follow others!")
        return
    
    # Fetch recent activities from followed users
    # 1. Get recent projects from followed users (via user_projects)
    projects_res = supabase.table("user_projects").select(
        "p_id, u_id, created_at, projects(p_id, p_title, p_link, p_thumbnail_url, p_created_at)"
    ).in_("u_id", followed_ids).order("created_at", desc=True).limit(50).execute()
    
    # 2. Get recent metric updates (youtube_metrics for projects from followed users)
    # First get project IDs from followed users
    user_projects_res = supabase.table("user_projects").select("p_id, u_id").in_("u_id", followed_ids).execute()
    followed_project_ids = [up["p_id"] for up in (user_projects_res.data or [])]
    # Map project IDs to user IDs for metrics
    project_to_user = {up["p_id"]: up["u_id"] for up in (user_projects_res.data or [])}
    
    metric_updates = []
    if followed_project_ids:
        metrics_res = supabase.table("youtube_metrics").select(
            "p_id, fetched_at, projects(p_id, p_title, p_link, p_thumbnail_url, p_created_at)"
        ).in_("p_id", followed_project_ids).order("fetched_at", desc=True).limit(50).execute()
        
        # Process metrics: use project_to_user map to get u_id
        for m in (metrics_res.data or []):
            project = m.get("projects", {})
            p_id = m.get("p_id")
            if project and p_id and p_id in project_to_user:
                metric_updates.append({
                    "type": "metric_update",
                    "u_id": project_to_user[p_id],
                    "p_id": project.get("p_id"),
                    "p_title": project.get("p_title"),
                    "p_link": project.get("p_link"),
                    "p_thumbnail_url": project.get("p_thumbnail_url"),
                    "timestamp": m.get("fetched_at"),
                })
    
    # 3. Combine and format project activities
    project_activities = []
    for up in (projects_res.data or []):
        project = up.get("projects", {})
        if project:
            project_activities.append({
                "type": "new_project",
                "u_id": up.get("u_id"),
                "p_id": project.get("p_id"),
                "p_title": project.get("p_title"),
                "p_link": project.get("p_link"),
                "p_thumbnail_url": project.get("p_thumbnail_url"),
                "timestamp": project.get("p_created_at") or up.get("created_at"),
            })
    
    # 4. Combine all activities and deduplicate by project ID (keep most recent)
    all_activities = project_activities + metric_updates
    # Deduplicate: if same project appears multiple times, keep only the most recent entry
    activities_by_project = {}
    for activity in all_activities:
        p_id = activity.get("p_id")
        if p_id:
            # If we haven't seen this project, or this activity is more recent, keep it
            if p_id not in activities_by_project:
                activities_by_project[p_id] = activity
            else:
                # Compare timestamps - keep the more recent one
                existing_timestamp = activities_by_project[p_id].get("timestamp", "")
                current_timestamp = activity.get("timestamp", "")
                if current_timestamp > existing_timestamp:
                    activities_by_project[p_id] = activity
    
    # Convert back to list and sort by timestamp
    deduplicated_activities = list(activities_by_project.values())
    deduplicated_activities.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    
    # Limit to 10 most recent
    feed_items = deduplicated_activities[:10]
    
    if not feed_items:
        st.info("No recent activity from creators you follow.")
        return
    
    # Get user info for display (batch fetch)
    feed_user_ids = list(set(item["u_id"] for item in feed_items))
    users_res = supabase.table("users").select("u_id, u_name, u_email, profile_image_url").in_("u_id", feed_user_ids).execute()
    users_map = {u["u_id"]: u for u in (users_res.data or [])}
    
    # Get project-specific metrics for each feed item (not user totals)
    feed_project_ids = [item["p_id"] for item in feed_items if item.get("p_id")]
    project_metrics_map = {}
    if feed_project_ids:
        # Try youtube_latest_metrics first (preferred for real-time), fall back to youtube_metrics if table doesn't exist
        try:
            metrics_res = supabase.table("youtube_latest_metrics").select("p_id, view_count").in_("p_id", feed_project_ids).execute()
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
    
    # Display feed
    st.markdown("### Your Feed")
    st.caption(f"Recent activity from {len(followed_ids)} creator{'s' if len(followed_ids) != 1 else ''} you follow")
    
    for item in feed_items:
        user = users_map.get(item["u_id"], {})
        user_name = user.get("u_name", "Unknown Creator")
        # Use saved profile image if available, otherwise fall back to generated avatar
        profile_image_url = user.get("profile_image_url")
        if profile_image_url:
            avatar_url = profile_image_url
        else:
            avatar_url = f"https://api.dicebear.com/7.x/identicon/svg?seed={user_name}"
        # Get project-specific view count for this feed item
        project_views = project_metrics_map.get(item.get("p_id"), 0)
        activity_type = "New project" if item["type"] == "new_project" else "Metrics updated"
        timestamp = item.get("timestamp", "")
        
        # Parse and format timestamp
        try:
            if timestamp:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                time_ago = datetime.now(timezone.utc) - dt.replace(tzinfo=timezone.utc)
                if time_ago.days > 0:
                    time_str = f"{time_ago.days} day{'s' if time_ago.days != 1 else ''} ago"
                elif time_ago.seconds > 3600:
                    hours = time_ago.seconds // 3600
                    time_str = f"{hours} hour{'s' if hours != 1 else ''} ago"
                else:
                    mins = time_ago.seconds // 60
                    time_str = f"{mins} minute{'s' if mins != 1 else ''} ago" if mins > 0 else "Just now"
            else:
                time_str = "Recently"
        except:
            time_str = "Recently"
        
        # Feed card
        with st.container():
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            col1, col2 = st.columns([1, 5])
            with col1:
                st.image(avatar_url, width=50)
            with col2:
                st.markdown(f"**{user_name}** · {activity_type} · {time_str}")
                if item.get("p_title"):
                    st.markdown(f"[{item['p_title']}]({item.get('p_link', '#')})")
                if project_views > 0:
                    st.caption(f"Views: {project_views:,}")
            st.markdown("</div>", unsafe_allow_html=True)


def show_notifications_page():
    st.title("Notifications")
    # Basic recent credit events inferred from user_projects
    user_res = supabase.table("users").select("u_id").eq("u_email", normalized_email).execute()
    if not user_res.data:
        st.info("No notifications yet.")
        return
    u_id = user_res.data[0]["u_id"]

    results = supabase.table("user_projects").select("u_role, projects(p_title)").eq("u_id", u_id).order("created_at", desc=True).limit(25).execute()
    items = results.data or []
    if not items:
        st.info("No recent activity.")
        return
    for it in items:
        title = it.get("projects", {}).get("p_title", "Project")
        role = it.get("u_role", "Role")
        st.write(f"✅ Credit accepted: {role} on {title}")

# -------------------------------
# PAGE 2 — YOUTUBE OVERVIEW
# -------------------------------
def show_youtube_overview():
    # Ensure platform context
    st.session_state["selected_platform"] = "youtube"

    # Back to Profile Overview
    back_cols = st.columns([1, 2, 1])
    with back_cols[0]:
        if st.button("← Back to Profile Overview", key="btn_back_profile_youtube"):
            st.session_state["page_override"] = "Profile"
            st.rerun()

    # Get user info
    user_res = supabase.table("users").select("*").eq("u_email", normalized_email).execute()
    if not user_res.data:
        st.info("No profile found yet — one will be created after your first claim.")
        return
    user = user_res.data[0]
    u_id = user["u_id"]

    # Header: profile image
    profile_image_url = user.get("profile_image_url")
    if profile_image_url:
        avatar_url = profile_image_url
    else:
        avatar_url = f"https://api.dicebear.com/7.x/identicon/svg?seed={user['u_name']}"
    st.markdown(f"""
        <div style=\"text-align: center; margin-bottom: 24px;\">
            <img src=\"{avatar_url}\" 
                 style=\"width: 140px; height: 140px; border-radius: 50%; margin: 0 auto 12px auto; display: block; object-fit: cover; object-position: center; border: 3px solid #E6E6E6; box-shadow: 0 2px 8px rgba(0,0,0,0.1); transform: translateX(-12px);\" />
        </div>
    """, unsafe_allow_html=True)

    # Name and Bio
    sanitized_name = sanitize_user_input(user.get('u_name', ''))
    st.markdown(f"<h1 style='text-align: center; margin-bottom: 0px; font-weight: 800;'>{sanitized_name}</h1>", unsafe_allow_html=True)
    if user.get("u_bio"):
        sanitized_bio = sanitize_user_input(user.get('u_bio', ''))
        st.markdown(f"<p style='text-align: center; color: #666; margin-top: 4px; margin-bottom: 0px;'>{sanitized_bio}</p>", unsafe_allow_html=True)

    # Metrics style (match Profile centering)
    st.markdown(f"""
        <style>
        .profile-metrics-container {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 50px;
            margin: 16px 0 20px 0;
            flex-wrap: wrap;
        }}
        .profile-metric-item {{
            text-align: center;
            min-width: 60px;
        }}
        @media (max-width: 768px) {{
            .profile-metrics-container {{ gap: 30px; }}
        }}
        @media (max-width: 480px) {{
            .profile-metrics-container {{ gap: 20px; }}
        }}
        </style>
    """, unsafe_allow_html=True)

    # Live metrics (YouTube only)
    if "live_metrics" not in st.session_state:
        st.session_state.live_metrics = None
    if st.session_state.live_metrics is None:
        with st.spinner("Fetching live metrics..."):
            live_data = fetch_live_metrics_for_user(u_id)
            if live_data:
                st.session_state.live_metrics = live_data

    # Cooldown for refresh
    cooldown_seconds = 300
    ss_key = "user_refresh_cooldown"
    if ss_key not in st.session_state:
        st.session_state[ss_key] = 0
    last_ts = st.session_state[ss_key]
    now_ts = datetime.now(timezone.utc).timestamp()
    remaining = max(0, int(cooldown_seconds - (now_ts - last_ts)))

    # Aggregate YouTube totals
    if st.session_state.live_metrics:
        live_total_views = sum(m["view_count"] for m in st.session_state.live_metrics.values())
        live_total_likes = sum(m["like_count"] for m in st.session_state.live_metrics.values())
        live_total_comments = sum(m["comment_count"] for m in st.session_state.live_metrics.values())
    else:
        live_total_views = 0
        live_total_likes = 0
        live_total_comments = 0

    # Metrics row
    st.markdown(f"""
        <div class="profile-metrics-container">
            <div class="profile-metric-item">
                <div style="font-size: 12px; color: #666; margin-bottom: 4px;">Views</div>
                <div style="font-size: 20px; font-weight: 700;">{live_total_views:,}</div>
            </div>
            <div class="profile-metric-item">
                <div style="font-size: 12px; color: #666; margin-bottom: 4px;">Likes</div>
                <div style="font-size: 20px; font-weight: 700;">{live_total_likes:,}</div>
            </div>
            <div class="profile-metric-item">
                <div style="font-size: 12px; color: #666; margin-bottom: 4px;">Comments</div>
                <div style="font-size: 20px; font-weight: 700;">{live_total_comments:,}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Refresh + View Analytics actions
    actions_col1, actions_col2, actions_col3 = st.columns([1, 2, 1])
    with actions_col2:
        act_cols = st.columns(2)
        with act_cols[0]:
            disabled = remaining > 0
            label = "Refresh" if not disabled else f"{remaining}s"
            if st.button(label, key="yt_live_refresh_btn", disabled=disabled, use_container_width=True):
                with st.spinner("Fetching latest metrics from YouTube..."):
                    live_data = fetch_live_metrics_for_user(u_id)
                if live_data:
                    st.session_state.live_metrics = live_data
                    st.session_state[ss_key] = datetime.now(timezone.utc).timestamp()
                    st.success(f"Fetched latest metrics for {len(live_data)} videos")
                    st.rerun()
                else:
                    st.warning("Could not fetch live metrics right now.")
        with act_cols[1]:
            if st.button("View Analytics", key="btn_view_yt_analytics", use_container_width=True):
                st.session_state["selected_platform"] = "youtube"
                st.session_state["page_override"] = "Analytics"
                st.rerun()

    st.divider()

    # Videos list (Your Credits)
    st.markdown("### Your Videos")
    projects_response = supabase.table("user_projects") \
        .select("projects(p_id, p_title, p_link, p_thumbnail_url), u_role") \
        .eq("u_id", u_id).execute()

    data = projects_response.data
    if not data:
        st.info("You haven't been credited on any projects yet.")
        return

    unique_projects = {}
    for rec in data:
        pid = rec["projects"]["p_id"]
        role = rec["u_role"]
        if pid not in unique_projects:
            unique_projects[pid] = {"project": rec["projects"], "roles": [role]}
        else:
            unique_projects[pid]["roles"].append(role)

    pids = list(unique_projects.keys())
    metrics_map = {}
    if pids:
        try:
            metrics_resp = supabase.table("youtube_latest_metrics").select("p_id, view_count, like_count, comment_count").in_("p_id", pids).execute()
            for m in (metrics_resp.data or []):
                pid = m["p_id"]
                metrics_map[pid] = {
                    "view_count": m.get("view_count", 0) or 0,
                    "like_count": m.get("like_count", 0) or 0,
                    "comment_count": m.get("comment_count", 0) or 0,
                }
        except Exception:
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

    sorted_projects = []
    for pid, rec in unique_projects.items():
        rec_metrics = metrics_map.get(pid, {"view_count": 0, "like_count": 0, "comment_count": 0})
        rec["views"] = rec_metrics["view_count"]
        rec["metrics"] = rec_metrics
        sorted_projects.append(rec)
    sorted_projects = sorted(sorted_projects, key=lambda x: x["views"], reverse=True)

    cols = st.columns(3)
    for i, rec in enumerate(sorted_projects):
        proj = rec["project"]
        roles = ", ".join(rec["roles"])
        with cols[i % 3]:
            st.markdown("<div class='project-card'>", unsafe_allow_html=True)
            if proj.get("p_thumbnail_url"):
                st.image(proj["p_thumbnail_url"], use_container_width=True)
            else:
                st.info("No thumbnail available")
            st.markdown(f"**[{escape(proj['p_title'])}]({proj['p_link']})**")
            m = rec.get("metrics", {"view_count": 0, "like_count": 0, "comment_count": 0})
            st.caption(f"Views: {m['view_count']:,} | Likes: {m['like_count']:,} | Comments: {m['comment_count']:,}")
            st.markdown("</div>", unsafe_allow_html=True)

    # Collaborators
    try:
        st.markdown("### Collaborators")
        channel_map = fetch_channels_for_projects(pids)
        if not channel_map:
            st.info("No collaborators detected yet.")
            return
        channels_sorted = sorted(channel_map.items(), key=lambda x: x[1]["title"].lower())
        cols = st.columns(4)
        for idx, (ch_id, ch) in enumerate(channels_sorted):
            with cols[idx % 4]:
                st.markdown("<div class='card'>", unsafe_allow_html=True)
                st.markdown(f"**[{escape(ch['title'])}]({ch['url']})**")
                st.markdown("</div>", unsafe_allow_html=True)
    except Exception:
        pass

# -------------------------------
# PLATFORM PAGES — INSTAGRAM & TIKTOK (placeholders until data exists)
# -------------------------------
def _show_generic_platform_overview(platform_key: str, platform_label: str):
    st.session_state["selected_platform"] = platform_key

    # Back to Profile Overview
    back_cols = st.columns([1, 2, 1])
    with back_cols[0]:
        if st.button("← Back to Profile Overview", key=f"btn_back_profile_{platform_key}"):
            st.session_state["page_override"] = "Profile"
            st.rerun()

    user_res = supabase.table("users").select("*").eq("u_email", normalized_email).execute()
    if not user_res.data:
        st.info("No profile found yet — one will be created after your first claim.")
        return
    user = user_res.data[0]

    profile_image_url = user.get("profile_image_url")
    avatar_url = profile_image_url if profile_image_url else f"https://api.dicebear.com/7.x/identicon/svg?seed={user['u_name']}"
    st.markdown(f"""
        <div style=\"text-align: center; margin-bottom: 24px;\">
            <img src=\"{avatar_url}\" 
                 style=\"width: 140px; height: 140px; border-radius: 50%; margin: 0 auto 12px auto; display: block; object-fit: cover; object-position: center; border: 3px solid #E6E6E6; box-shadow: 0 2px 8px rgba(0,0,0,0.1); transform: translateX(-12px);\" />
        </div>
    """, unsafe_allow_html=True)

    sanitized_name = sanitize_user_input(user.get('u_name', ''))
    st.markdown(f"<h1 style='text-align: center; margin-bottom: 0px; font-weight: 800;'>{sanitized_name}</h1>", unsafe_allow_html=True)
    if user.get("u_bio"):
        sanitized_bio = sanitize_user_input(user.get('u_bio', ''))
        st.markdown(f"<p style='text-align: center; color: #666; margin-top: 4px; margin-bottom: 0px;'>{sanitized_bio}</p>", unsafe_allow_html=True)

    # Metrics style (match Profile centering)
    st.markdown(f"""
        <style>
        .profile-metrics-container {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 50px;
            margin: 16px 0 20px 0;
            flex-wrap: wrap;
        }}
        .profile-metric-item {{
            text-align: center;
            min-width: 60px;
        }}
        @media (max-width: 768px) {{
            .profile-metrics-container {{ gap: 30px; }}
        }}
        @media (max-width: 480px) {{
            .profile-metrics-container {{ gap: 20px; }}
        }}
        </style>
    """, unsafe_allow_html=True)

    # Placeholder totals until platform integrations land
    views = 0
    likes = 0
    comments = 0

    st.markdown(f"""
        <div class=\"profile-metrics-container\">
            <div class=\"profile-metric-item\">
                <div style=\"font-size: 12px; color: #666; margin-bottom: 4px;\">Views</div>
                <div style=\"font-size: 20px; font-weight: 700;\">{views:,}</div>
            </div>
            <div class=\"profile-metric-item\">
                <div style=\"font-size: 12px; color: #666; margin-bottom: 4px;\">Likes</div>
                <div style=\"font-size: 20px; font-weight: 700;\">{likes:,}</div>
            </div>
            <div class=\"profile-metric-item\">
                <div style=\"font-size: 12px; color: #666; margin-bottom: 4px;\">Comments</div>
                <div style=\"font-size: 20px; font-weight: 700;\">{comments:,}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Actions: View Analytics
    actions_col1, actions_col2, actions_col3 = st.columns([1, 2, 1])
    with actions_col2:
        if st.button("View Analytics", key=f"btn_view_{platform_key}_analytics", use_container_width=True):
            st.session_state["selected_platform"] = platform_key
            st.session_state["page_override"] = "Analytics"
            st.rerun()

    st.divider()
    st.markdown(f"### Your {platform_label} Credits")
    st.info(f"No {platform_label} credits yet.")
    st.markdown(f"### {platform_label} Collaborators")
    st.info(f"No {platform_label} collaborators detected yet.")


def show_instagram_overview():
    st.session_state["selected_platform"] = "instagram"

    # Back to Profile Overview
    back_cols = st.columns([1, 2, 1])
    with back_cols[0]:
        if st.button("← Back to Profile Overview", key="btn_back_profile_instagram"):
            st.session_state["page_override"] = "Profile"
            st.rerun()

    # Get user info
    user_res = supabase.table("users").select("*").eq("u_email", normalized_email).execute()
    if not user_res.data:
        st.info("No profile found yet — one will be created after your first claim.")
        return
    user = user_res.data[0]
    u_id = user["u_id"]

    # Get user's Instagram account (multi-user aware)
    instagram_account = get_user_instagram_account(supabase, u_id)
    
    if not instagram_account:
        st.info("""
        **Connect your Instagram account to view insights**
        
        Go to **Settings → Connections** to connect your Instagram Business account.
        """)
        return
    
    access_token = instagram_account["access_token"]
    account_id = instagram_account["account_id"]

    # Header: profile image
    profile_image_url = user.get("profile_image_url")
    if profile_image_url:
        avatar_url = profile_image_url
    else:
        avatar_url = f"https://api.dicebear.com/7.x/identicon/svg?seed={user['u_name']}"
    st.markdown(f"""
        <div style=\"text-align: center; margin-bottom: 24px;\">
            <img src=\"{avatar_url}\" 
                 style=\"width: 140px; height: 140px; border-radius: 50%; margin: 0 auto 12px auto; display: block; object-fit: cover; object-position: center; border: 3px solid #E6E6E6; box-shadow: 0 2px 8px rgba(0,0,0,0.1); transform: translateX(-12px);\" />
        </div>
    """, unsafe_allow_html=True)

    # Name and Bio
    sanitized_name = sanitize_user_input(user.get('u_name', ''))
    st.markdown(f"<h1 style='text-align: center; margin-bottom: 0px; font-weight: 800;'>{sanitized_name}</h1>", unsafe_allow_html=True)
    if user.get("u_bio"):
        sanitized_bio = sanitize_user_input(user.get('u_bio', ''))
        st.markdown(f"<p style='text-align: center; color: #666; margin-top: 4px; margin-bottom: 0px;'>{sanitized_bio}</p>", unsafe_allow_html=True)

    # Metrics style (match Profile centering)
    st.markdown(f"""
        <style>
        .profile-metrics-container {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 50px;
            margin: 16px 0 20px 0;
            flex-wrap: wrap;
        }}
        .profile-metric-item {{
            text-align: center;
            min-width: 60px;
        }}
        @media (max-width: 768px) {{
            .profile-metrics-container {{ gap: 30px; }}
        }}
        @media (max-width: 480px) {{
            .profile-metrics-container {{ gap: 20px; }}
        }}
        </style>
    """, unsafe_allow_html=True)

    # Fetch latest Instagram metrics
    latest_metrics = get_latest_instagram_metrics(supabase, user_id=u_id)
    
    # Map Instagram metrics to display names
    reach = latest_metrics.get("reach", 0)
    profile_views = latest_metrics.get("profile_views", 0)
    accounts_engaged = latest_metrics.get("accounts_engaged", 0)
    follower_count = latest_metrics.get("follower_count", 0)

    # Metrics row
    st.markdown(f"""
        <div class="profile-metrics-container">
            <div class="profile-metric-item">
                <div style="font-size: 12px; color: #666; margin-bottom: 4px;">Reach</div>
                <div style="font-size: 20px; font-weight: 700;">{reach:,.0f}</div>
            </div>
            <div class="profile-metric-item">
                <div style="font-size: 12px; color: #666; margin-bottom: 4px;">Profile Views</div>
                <div style="font-size: 20px; font-weight: 700;">{profile_views:,.0f}</div>
            </div>
            <div class="profile-metric-item">
                <div style="font-size: 12px; color: #666; margin-bottom: 4px;">Accounts Engaged</div>
                <div style="font-size: 20px; font-weight: 700;">{accounts_engaged:,.0f}</div>
            </div>
            <div class="profile-metric-item">
                <div style="font-size: 12px; color: #666; margin-bottom: 4px;">Followers</div>
                <div style="font-size: 20px; font-weight: 700;">{follower_count:,.0f}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Refresh + View Analytics actions
    actions_col1, actions_col2, actions_col3 = st.columns([1, 2, 1])
    with actions_col2:
        act_cols = st.columns(2)
        with act_cols[0]:
            if st.button("🔄 Refresh Insights", key="ig_refresh_btn", use_container_width=True):
                with st.spinner("Fetching latest Instagram insights..."):
                    try:
                        # Get user's Instagram account (multi-user)
                        account_info = get_user_instagram_account(supabase, u_id)
                        
                        if not account_info:
                            st.error("Instagram account not connected. Go to Settings → Connections to connect your account.")
                            return
                        
                        access_token = account_info["access_token"]
                        account_id = account_info["account_id"]
                        
                        # Check if token is expired
                        expires_at = account_info.get("expires_at")
                        if expires_at and is_token_expired(expires_at):
                            st.warning("Your Instagram token has expired. Please reconnect in Settings → Connections.")
                            return
                        
                        result: FetchResult = fetch_and_store_instagram_insights(
                            supabase=supabase,
                            access_token=access_token,
                            instagram_account_id=account_id,
                            user_id=u_id
                        )
                        
                        if result.success:
                            st.success(f"✅ Fetched and stored {result.total_inserted} metric records")
                            st.rerun()
                        elif result.total_inserted > 0:
                            st.warning(f"⚠️ Inserted {result.total_inserted} records with {result.total_errors} errors")
                            if result.errors:
                                with st.expander("View errors"):
                                    for error in result.errors:
                                        st.error(error)
                        else:
                            st.warning("No new metrics fetched. Data may already be up to date.")
                            if result.errors:
                                st.error(f"Errors: {', '.join(result.errors)}")
                    except Exception as e:
                        st.error(f"Error fetching Instagram insights: {str(e)}")
        with act_cols[1]:
            if st.button("View Analytics", key="btn_view_ig_analytics", use_container_width=True):
                st.session_state["selected_platform"] = "instagram"
                st.session_state["page_override"] = "Analytics"
                st.rerun()

    st.divider()

    # Show recent metrics history
    st.markdown("### Recent Insights")
    try:
        insights_res = supabase.table("instagram_insights") \
            .select("metric, value, end_time") \
            .eq("user_id", u_id) \
            .order("end_time", desc=True) \
            .limit(20) \
            .execute()
        
        if insights_res.data:
            insights_df = pd.DataFrame(insights_res.data)
            insights_df["end_time"] = pd.to_datetime(insights_df["end_time"])
            insights_df = insights_df.sort_values("end_time")
            
            # Create a simple line chart for each metric
            for metric_name in ["reach", "profile_views", "accounts_engaged", "follower_count"]:
                metric_data = insights_df[insights_df["metric"] == metric_name]
                if not metric_data.empty:
                    st.markdown(f"#### {metric_name.replace('_', ' ').title()}")
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=metric_data["end_time"],
                        y=metric_data["value"],
                        mode='lines+markers',
                        name=metric_name,
                        line=dict(color='rgba(66,133,244,1)', width=2),
                        marker=dict(size=4)
                    ))
                    fig.update_layout(
                        height=200,
                        showlegend=False,
                        margin=dict(l=0, r=0, t=0, b=0),
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        xaxis=dict(showgrid=True, gridcolor='rgba(0,0,0,0.1)'),
                        yaxis=dict(showgrid=True, gridcolor='rgba(0,0,0,0.1)')
                    )
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        else:
            st.info("No Instagram insights data yet. Click 'Refresh Insights' to fetch your first metrics.")
    except Exception as e:
        st.warning(f"Could not load insights history: {str(e)}")


def show_tiktok_overview():
    _show_generic_platform_overview("tiktok", "TikTok")

# -------------------------------
# PAGE 4 — SETTINGS
# -------------------------------
def show_analytics_page():
    # Determine view mode: overall dashboard or platform detail
    if "analytics_view" not in st.session_state:
        st.session_state.analytics_view = "overall"
    analytics_view = st.session_state.get("analytics_view", "overall")
    platform = st.session_state.get("selected_platform", "youtube")

    # Header
    if analytics_view == "overall":
        st.title("Analytics")
        st.caption("Combined overview across all connected platforms.")
    else:
        st.title(f"{platform.capitalize()} Analytics")
        # Back to overview
        back_cols = st.columns([1, 2, 1])
        with back_cols[0]:
            if st.button("← Back to Overview", key="btn_back_overview"):
                st.session_state.analytics_view = "overall"
                st.rerun()
        if platform == "youtube":
            st.caption("Daily totals across your YouTube credits (views, likes, comments).")
        elif platform == "instagram":
            st.caption("Daily Instagram Business account metrics (reach, profile views, accounts engaged, followers).")
        else:
            st.info("Platform analytics coming soon.")
            return

    # Identify user id
    user_res = supabase.table("users").select("u_id").eq("u_email", normalized_email).execute()
    if not user_res.data:
        st.info("No user record found. Add a credit to get started.")
        return
    u_id = user_res.data[0]["u_id"]

    # Controls: range only (daily metrics)
    col_a, col_b = st.columns([1, 2])
    with col_a:
        preset = st.radio("Range", ["Last 7 days", "Last 28 days", "Last 12 months"], index=0)
    with col_b:
        today = datetime.now(timezone.utc).date()
        yesterday = today - timedelta(days=1)  # Exclude today since metrics are gathered each morning
        if preset == "Last 7 days":
            start_date = today - timedelta(days=6)
            end_date = yesterday
        elif preset == "Last 28 days":
            start_date = today - timedelta(days=27)
            end_date = yesterday
        elif preset == "Last 12 months":
            start_date = today - timedelta(days=365)  # Full year
            end_date = yesterday

    # Fetch data (used by both overview and platform detail)
    start_iso = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc).isoformat()
    end_iso = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc).isoformat()
    
    # Platform-specific data fetching
    ts_df_youtube = pd.DataFrame()
    ts_df_instagram = {}
    
    if analytics_view == "overall" or platform == "youtube":
        # Debug: Check what projects and data exist
        projects_resp = supabase.table("user_projects").select("p_id").eq("u_id", u_id).execute()
        project_ids = [p["p_id"] for p in (projects_resp.data or [])]
        
        # Check if any metrics exist at all for these projects
        any_metrics_check = supabase.table("youtube_metrics") \
            .select("p_id, fetched_at, view_count") \
            .in_("p_id", project_ids) \
            .order("fetched_at", desc=False) \
            .limit(5) \
            .execute()
        
        with st.spinner("Loading analytics..."):
            ts_df_youtube = fetch_user_daily_timeseries(u_id, start_iso, end_iso)
            if ts_df_youtube.empty:
                end_date_fallback = end_date - timedelta(days=1)
                if end_date_fallback >= start_date:
                    end_iso_fb = datetime.combine(end_date_fallback, datetime.max.time(), tzinfo=timezone.utc).isoformat()
                    ts_df_youtube = fetch_user_daily_timeseries(u_id, start_iso, end_iso_fb)
    
    if analytics_view == "overall" or platform == "instagram":
        # Fetch Instagram metrics
        with st.spinner("Loading Instagram analytics..."):
            instagram_metrics = ["reach", "profile_views", "accounts_engaged", "follower_count"]
            for metric in instagram_metrics:
                ts_df_instagram[metric] = fetch_instagram_daily_timeseries(u_id, start_iso, end_iso, metric)
    
    # Platform-specific data validation and metric setup
    if platform == "youtube":
        # Debug info (temporary)
        projects_resp = supabase.table("user_projects").select("p_id").eq("u_id", u_id).execute()
        project_ids = [p["p_id"] for p in (projects_resp.data or [])]
        any_metrics_check = supabase.table("youtube_metrics") \
            .select("p_id, fetched_at, view_count") \
            .in_("p_id", project_ids) \
            .order("fetched_at", desc=False) \
            .limit(5) \
            .execute()
        
        if ts_df_youtube.empty:
            if not project_ids:
                st.info("No projects linked to your account yet. Add credits to get started.")
                return
            
            # Check if any metrics exist for these projects (without date filter)
            any_metrics = supabase.table("youtube_metrics") \
                .select("p_id, fetched_at") \
                .in_("p_id", project_ids) \
                .order("fetched_at", desc=False) \
                .limit(1) \
                .execute()
            
            if any_metrics.data:
                earliest_date = pd.to_datetime(any_metrics.data[0].get("fetched_at", ""))
                latest_check = supabase.table("youtube_metrics") \
                    .select("p_id, fetched_at") \
                    .in_("p_id", project_ids) \
                    .order("fetched_at", desc=True) \
                    .limit(1) \
                    .execute()
                latest_date = pd.to_datetime(latest_check.data[0].get("fetched_at", "")) if latest_check.data else None
                
                date_range_msg = f"Data exists from {earliest_date.strftime('%Y-%m-%d')}"
                if latest_date:
                    date_range_msg += f" to {latest_date.strftime('%Y-%m-%d')}"
                
                st.warning(
                    f"No metrics found in the selected date range ({start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}). "
                    f"{date_range_msg}."
                )
            else:
                st.info("No metrics yet. Once your AWS job runs, data will appear here.")
            return
        
        # Metric definitions for YouTube
        metric_options = ["Views", "Likes", "Comments"]
        metric_map = {
            "Views": "views",
            "Likes": "likes",
            "Comments": "comments",
        }
        metric_totals = {m: int(ts_df_youtube[metric_map[m]].sum()) for m in metric_options}
        chart_df_base = ts_df_youtube
        
    elif platform == "instagram":
        # Check if Instagram data exists
        has_instagram_data = any(not df.empty for df in ts_df_instagram.values())
        if not has_instagram_data:
            st.info("No Instagram insights data yet. Go to Instagram Overview and click 'Refresh Insights' to fetch your first metrics.")
            return
        
        # Metric definitions for Instagram
        metric_options = ["Reach", "Profile Views", "Accounts Engaged", "Followers"]
        metric_map = {
            "Reach": "reach",
            "Profile Views": "profile_views",
            "Accounts Engaged": "accounts_engaged",
            "Followers": "follower_count",
        }
        metric_totals = {}
        for display_name, metric_key in metric_map.items():
            df = ts_df_instagram.get(metric_key, pd.DataFrame())
            metric_totals[display_name] = int(df["value"].sum()) if not df.empty else 0
        chart_df_base = None  # Will be set per metric
    
    else:
        # Overall view - combine YouTube and Instagram
        metric_options = ["Views", "Likes", "Comments"]
        metric_map = {
            "Views": "views",
            "Likes": "likes",
            "Comments": "comments",
        }
        metric_totals = {m: int(ts_df_youtube[metric_map[m]].sum()) if not ts_df_youtube.empty else 0 for m in metric_options}
        chart_df_base = ts_df_youtube
    
    # Track selected metric in session state
    if "selected_analytics_metric" not in st.session_state:
        st.session_state.selected_analytics_metric = metric_options[0]
    
    # OVERALL VIEW: show combined totals
    if analytics_view == "overall":
        # Buttons to open platform-specific analytics
        st.markdown("### Platform Analytics")
        btn_cols = st.columns(3)
        with btn_cols[0]:
            if st.button("YouTube Analytics", key="btn_open_youtube_analytics", use_container_width=True):
                st.session_state.selected_platform = "youtube"
                st.session_state.analytics_view = "platform"
                st.rerun()
        with btn_cols[1]:
            if st.button("Instagram Analytics", key="btn_open_instagram_analytics", use_container_width=True):
                st.session_state.selected_platform = "instagram"
                st.session_state.analytics_view = "platform"
                st.rerun()
        with btn_cols[2]:
            if st.button("TikTok Analytics", key="btn_open_tiktok_analytics", use_container_width=True):
                st.session_state.selected_platform = "tiktok"
                st.session_state.analytics_view = "platform"
                st.rerun()
    
    # Two-tier layout: buttons (labels) on top, value cards below
    st.markdown("""
        <style>
        .analytics-metrics-wrapper {
            display: flex;
            justify-content: center;
            align-items: flex-start;
            gap: 30px;
            margin-bottom: 24px;
            flex-wrap: wrap;
            width: 100%;
        }
        .analytics-metric-column-wrapper {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 8px;
            min-width: 120px;
        }
        .analytics-metric-button-custom {
            background-color: #FFFFFF;
            color: #111111;
            border: 1px solid #E0E0E0;
            border-radius: 8px;
            padding: 10px 20px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease-in-out;
            width: 100%;
            text-align: center;
            font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
        }
        .analytics-metric-button-custom:hover {
            background-color: #F4F4F4;
            border-color: #E0E0E0;
        }
        .analytics-metric-button-custom.selected {
            background-color: #E0E0E0;
            border: 2px solid #000000;
            font-weight: 700;
        }
        .analytics-metric-card {
            background-color: #FFFFFF;
            border: 1px solid #E0E0E0;
            border-radius: 8px;
            padding: 16px 20px;
            width: 100%;
            text-align: center;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
            min-width: 100px;
        }
        .analytics-metric-value {
            font-size: 24px;
            font-weight: 700;
            color: #111111;
            margin: 0;
            font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
        }
        @media (max-width: 768px) {
            .analytics-metrics-wrapper {
                gap: 20px;
            }
            .analytics-metric-column-wrapper {
                min-width: 100px;
            }
        }
        @media (max-width: 480px) {
            .analytics-metrics-wrapper {
                gap: 15px;
            }
            .analytics-metric-column-wrapper {
                min-width: 80px;
            }
            .analytics-metric-value {
                font-size: 20px;
            }
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Use Streamlit columns for layout with native buttons styled to match
    metric_cols = st.columns(len(metric_options))
    
    for idx, metric in enumerate(metric_options):
        with metric_cols[idx]:
            is_selected = st.session_state.selected_analytics_metric == metric
            total = metric_totals[metric]
            button_key = f"metric_btn_{metric}"
            
            # Use Streamlit button styled to look like our custom design
            if st.button(metric, key=button_key, use_container_width=True):
                st.session_state.selected_analytics_metric = metric
                st.rerun()
            
            # Value card below the button
            st.markdown(f"""
                <div class="analytics-metric-card">
                    <div class="analytics-metric-value">{total:,}</div>
                </div>
            """, unsafe_allow_html=True)
    
    # Style the Streamlit buttons to match our design
    st.markdown("""
        <style>
        /* Style all metric buttons to match custom design */
        button[key^="metric_btn_"] {
            background-color: #FFFFFF !important;
            color: #111111 !important;
            border: 1px solid #E0E0E0 !important;
            border-radius: 8px !important;
            padding: 10px 20px !important;
            font-size: 14px !important;
            font-weight: 600 !important;
            transition: all 0.2s ease-in-out !important;
            width: 100% !important;
            text-align: center !important;
            font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif !important;
            margin-bottom: 8px !important;
        }
        button[key^="metric_btn_"]:hover {
            background-color: #F4F4F4 !important;
            border-color: #E0E0E0 !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Add dynamic styling for selected button
    selected_metric = st.session_state.selected_analytics_metric
    selected_button_key = f"metric_btn_{selected_metric}"
    st.markdown(f"""
        <style>
        button[key="{selected_button_key}"] {{
            background-color: #E0E0E0 !important;
            border: 2px solid #000000 !important;
            font-weight: 700 !important;
        }}
        </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Get selected metric
    selected_metric = st.session_state.selected_analytics_metric
    metric_col = metric_map[selected_metric]
    metric_sum = metric_totals[selected_metric]

    # Chart: Platform-specific data preparation
    if platform == "instagram":
        # Instagram metrics use different structure
        chart_df = ts_df_instagram.get(metric_col, pd.DataFrame())
        if chart_df.empty:
            st.info(f"No data available for {selected_metric} in the selected date range.")
            return
        chart_df = chart_df.set_index("date")[["value"]].rename(columns={"value": selected_metric.lower()})
    else:
        # YouTube or overall view
        if chart_df_base.empty:
            st.info(f"No data available for {selected_metric} in the selected date range.")
            return
        chart_df = chart_df_base.set_index("date")[[metric_col]].rename(columns={metric_col: selected_metric.lower()})
    
    # Apply smooth interpolation using rolling average for Spotify-like curves
    # Use a small window (3 days) to smooth without losing detail
    smoothed_values = chart_df[selected_metric.lower()].rolling(
        window=min(3, len(chart_df)), 
        min_periods=1,
        center=True
    ).mean()
    
    # Create Plotly area chart
    fig = go.Figure()
    
    # Add filled area trace with smoothed data
    fig.add_trace(go.Scatter(
        x=chart_df.index,
        y=smoothed_values,
        mode='lines',
        name=selected_metric,
        fill='tozeroy',
        fillcolor='rgba(66,133,244,0.2)',  # Soft translucent blue
        line=dict(
            color='rgba(66,133,244,1)',  # Solid blue line
            width=2.5
        ),
        hovertemplate='<b>%{fullData.name}</b><br>' +
                      '%{x|%b %d, %Y}<br>' +
                      '%{y:,.0f}<extra></extra>'
    ))
    
    # Update layout for Spotify-style aesthetics
    fig.update_layout(
        height=320,
        showlegend=False,
        margin=dict(l=0, r=0, t=0, b=0),
        hovermode='x unified',
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(
            showgrid=True,
            gridcolor='rgba(0,0,0,0.1)',
            showline=False,
            zeroline=False
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(0,0,0,0.1)',
            showline=False,
            zeroline=False
        ),
        font=dict(
            family='-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif',
            size=12,
            color='#111111'
        )
    )
    
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # Previous period comparison for selected metric
    period_days = (end_date - start_date).days + 1
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=period_days - 1)
    prev_start_iso = datetime.combine(prev_start, datetime.min.time(), tzinfo=timezone.utc).isoformat()
    prev_end_iso = datetime.combine(prev_end, datetime.max.time(), tzinfo=timezone.utc).isoformat()
    
    if platform == "instagram":
        prev_df = fetch_instagram_daily_timeseries(u_id, prev_start_iso, prev_end_iso, metric_col)
        prev_sum = int(prev_df["value"].sum()) if not prev_df.empty else 0
    else:
        prev_df = fetch_user_daily_timeseries(u_id, prev_start_iso, prev_end_iso)
        prev_sum = int(prev_df[metric_col].sum()) if not prev_df.empty else 0
    
    def pct(curr: int, prev: int) -> str:
        if prev == 0:
            return "–"
        return f"{((curr - prev)/prev)*100:.1f}%"
    
    delta = metric_sum - prev_sum
    delta_pct = pct(metric_sum, prev_sum)
    delta_color = "green" if delta >= 0 else "red"
    
    st.caption(
        f"**{selected_metric}** — Δ vs previous {period_days}d: <span style='color: {delta_color}; font-weight: 600;'>{delta:+,} ({delta_pct})</span>",
        unsafe_allow_html=True
    )

    # Peak day for selected metric
    if platform == "instagram":
        if not chart_df.empty and chart_df[selected_metric.lower()].max() > 0:
            peak_row = chart_df.loc[chart_df[selected_metric.lower()].idxmax()]
            peak_date = peak_row.name.date() if hasattr(peak_row.name, 'date') else peak_row.name
            peak_value = int(peak_row[selected_metric.lower()])
            st.caption(f"Peak day: **{peak_date}** with **{peak_value:,} {selected_metric.lower()}**")
    else:
        if not chart_df_base.empty and chart_df_base[metric_col].max() > 0:
            peak_row = chart_df_base.loc[chart_df_base[metric_col].idxmax()]
        peak_date = peak_row["date"].date()
        peak_value = int(peak_row[metric_col])
        st.caption(f"Peak day: **{peak_date}** with **{peak_value:,} {selected_metric.lower()}**")


def handle_instagram_oauth_callback(user_id: str, code: str):
    """Handle Instagram OAuth callback and store tokens.
    
    Args:
        user_id: User ID
        code: OAuth authorization code
    """
    fb_app_id, fb_app_secret = get_facebook_app_credentials()
    redirect_uri = get_instagram_redirect_url()
    
    if not fb_app_id or not fb_app_secret:
        st.error("Facebook App credentials not configured")
        return
    
    with st.spinner("Connecting Instagram account..."):
        try:
            # Exchange code for short-lived token
            # Use base redirect_uri (without query params) for token exchange
            token_data = exchange_code_for_token(
                app_id=fb_app_id,
                app_secret=fb_app_secret,
                code=code,
                redirect_uri=redirect_uri  # Base URL only - must match what's in Facebook App settings
            )
            
            if not token_data or "access_token" not in token_data:
                st.error("Failed to get access token")
                return
            
            short_token = token_data["access_token"]
            
            # Exchange for long-lived token
            long_token_data = get_long_lived_token(
                short_lived_token=short_token,
                app_id=fb_app_id,
                app_secret=fb_app_secret
            )
            
            if not long_token_data:
                st.error("Failed to get long-lived token")
                return
            
            long_token = long_token_data["access_token"]
            expires_in = long_token_data.get("expires_in", 5184000)
            
            # Get Instagram Business Account ID and username
            account_info = get_instagram_business_account_id(
                access_token=long_token
            )
            
            if not account_info or not account_info.get("account_id"):
                st.error("Could not find Instagram Business Account. Make sure your Facebook Page has an Instagram Business account connected.")
                return
            
            account_id = account_info["account_id"]
            account_username = account_info.get("username")
            
            # Store token
            success = store_instagram_token(
                supabase=supabase,
                user_id=user_id,
                access_token=long_token,
                account_id=account_id,
                expires_in=expires_in,
                account_username=account_username
            )
            
            if success:
                st.success("✅ Instagram account connected successfully!")
                # Clear OAuth query params
                st.query_params.clear()
                st.rerun()
            else:
                st.error("Failed to store Instagram token")
                
        except Exception as e:
            st.error(f"Error connecting Instagram: {str(e)}")


def show_settings_page():
    st.title("Settings")
    
    # Create tabs for different settings sections
    # Note: Connections tab added for Instagram OAuth integration
    tabs_list = ["Profile", "Connections", "Preferences"]
    tab1, tab2, tab3 = st.tabs(tabs_list)
    
    # Ensure all tabs are accessible (this helps with Streamlit rendering)
    # Tabs are created above, content is in the with blocks below
    
    with tab1:
        # Get current user info
        user_res = supabase.table("users").select("*").eq("u_email", normalized_email).execute()
        if not user_res.data:
            st.error("User not found")
            # Don't return here - let other tabs render
            st.stop()
        
        user = user_res.data[0]
        
        # Name and Bio Section
        st.markdown("### Name & Bio")
        st.caption("Update your display name and bio")
        
        current_name = user.get("u_name", "")
        current_bio = user.get("u_bio", "")
        
        name_input = st.text_input(
            "Display Name",
            value=current_name,
            placeholder="Enter your name",
            key="profile_name_input"
        )
        
        bio_input = st.text_area(
            "Bio (optional)",
            value=current_bio,
            placeholder="Tell us about yourself...",
            key="profile_bio_input",
            height=100
        )
        
        # Save Name and Bio button
        if st.button("💾 Save Name & Bio", key="save_name_bio"):
            if not name_input or not name_input.strip():
                st.error("Name is required")
            else:
                try:
                    # Sanitize inputs before saving
                    sanitized_name = sanitize_user_input(name_input.strip())
                    sanitized_bio = sanitize_user_input(bio_input.strip()) if bio_input else ""
                    
                    supabase.table("users").update({
                        "u_name": sanitized_name,
                        "u_bio": sanitized_bio
                    }).eq("u_email", normalized_email).execute()
                    st.success("✅ Name and bio saved!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving name and bio: {str(e)}")
        
        st.markdown("---")
        
        # Profile Picture Section
        st.markdown("### Profile Picture")
        st.caption("Paste a public image URL to set your profile picture")
        
        current_image_url = user.get("profile_image_url", "")
        
        # Display current profile picture if exists
        if current_image_url:
            st.markdown("#### Current Profile Picture")
            st.image(current_image_url, width=150, use_container_width=False)
        
        # URL input
        image_url = st.text_input(
            "Profile Picture URL",
            value=current_image_url,
            placeholder="https://example.com/profile.jpg",
            key="profile_image_url_input"
        )
        
        # Live preview
        if image_url and image_url.strip():
            st.markdown("#### Preview")
            try:
                st.image(image_url, width=150, use_container_width=False)
            except Exception as e:
                st.error(f"Could not load image: {str(e)}")
        
        # Save button
        if st.button("💾 Save Profile Picture", key="save_profile_picture"):
            if image_url and image_url.strip():
                if not is_valid_image_url(image_url):
                    st.warning("Please enter a valid public image URL (http/https, image content).")
                else:
                    try:
                        supabase.table("users").update({
                            "profile_image_url": image_url.strip()
                        }).eq("u_email", normalized_email).execute()
                        st.success("✅ Profile picture saved!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error saving profile picture: {str(e)}")
            else:
                st.warning("Please enter a valid URL")
    
    with tab2:
        st.markdown("### Connected Accounts")
        st.caption("Connect your social media accounts to view analytics")
        
        # Get user ID
        user_res = supabase.table("users").select("u_id").eq("u_email", normalized_email).execute()
        if not user_res.data:
            st.error("User not found")
            st.stop()  # Stop rendering this tab, but don't prevent other tabs from showing
        u_id = user_res.data[0]["u_id"]
        
        # Instagram Connection Section
        st.markdown("#### Instagram")
        
        # Check if Instagram is connected
        instagram_account = get_user_instagram_account(supabase, u_id)
        
        # Handle OAuth callback for Instagram
        query_params = st.query_params
        if "code" in query_params and "state" in query_params:
            received_state = query_params.get("state")
            expected_state = st.session_state.get("instagram_oauth_state")

            if expected_state and received_state and secrets.compare_digest(str(received_state), str(expected_state)):
                # State validated; clear it before handling callback to avoid reuse on rerun
                st.session_state.pop("instagram_oauth_state", None)
                handle_instagram_oauth_callback(u_id, query_params.get("code"))
            else:
                st.error("Invalid Instagram OAuth state. Please try connecting again.")
                st.session_state.pop("instagram_oauth_state", None)
                st.query_params.clear()
                st.stop()
        
        if instagram_account:
            account_id = instagram_account.get("account_id", "Unknown")
            username = instagram_account.get("account_username", "Connected")
            expires_at = instagram_account.get("expires_at")
            
            # Check if token is expiring soon
            token_status = "✅ Active"
            if expires_at and is_token_expired(expires_at):
                token_status = "⚠️ Expiring soon"
            
            st.success(f"Connected: **{username}** ({account_id})")
            st.caption(f"Status: {token_status}")
            
            if expires_at:
                try:
                    expiry_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                    if expiry_dt.tzinfo is None:
                        expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
                    else:
                        expiry_dt = expiry_dt.astimezone(timezone.utc)
                    
                    days_until_expiry = (expiry_dt - datetime.now(timezone.utc)).days
                    if days_until_expiry > 0:
                        st.caption(f"Token expires in {days_until_expiry} days")
                    else:
                        st.warning("Token has expired. Please reconnect.")
                except Exception:
                    pass
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 Refresh Token", key="refresh_ig_token", use_container_width=True):
                    st.info("Token refresh coming soon. For now, please disconnect and reconnect.")
            with col2:
                if st.button("🔌 Disconnect", key="disconnect_ig", use_container_width=True):
                    if disconnect_instagram_account(supabase, u_id):
                        st.success("Instagram account disconnected")
                        st.rerun()
                    else:
                        st.error("Failed to disconnect account")
        else:
            st.info("Connect your Instagram Business account to view insights")
            
            # Check if we're in developer mode (for developer-only UI messages)
            developer_mode = st.secrets.get("DEVELOPER_MODE", "false").lower() == "true"
            
            # Get Facebook App credentials (server-side secrets/environment, always present in production)
            fb_app_id, fb_app_secret = get_facebook_app_credentials()
            
            # Show developer setup instructions only if secrets are missing AND in developer mode
            # In production, secrets should always be present, so this message won't show to end users
            if developer_mode and (not fb_app_id or not fb_app_secret):
                st.warning("""
                **Instagram connection requires Facebook App setup:**
                
                1. Create a Facebook App at [developers.facebook.com](https://developers.facebook.com)
                2. Add Instagram Graph API product
                3. Add `FACEBOOK_APP_ID` and `FACEBOOK_APP_SECRET` to `.streamlit/secrets.toml`
                4. Configure OAuth redirect URI in Facebook App settings
                """)
            
            # Always show Connect button - app ID must be present; secret validated on callback
            if fb_app_id:
                redirect_uri = get_instagram_redirect_url()

                # Ensure state exists for OAuth flow
                oauth_state = st.session_state.get("instagram_oauth_state")
                if not oauth_state:
                    oauth_state = secrets.token_urlsafe(16)
                    st.session_state["instagram_oauth_state"] = oauth_state

                # Show redirect URI for debugging (helpful for Facebook App setup) - only in developer mode
                if developer_mode:
                    with st.expander("🔧 OAuth Configuration (for Facebook App setup)", expanded=False):
                        st.caption("**Add this exact URL to Facebook App → Settings → Valid OAuth Redirect URIs:**")
                        st.code(redirect_uri, language=None)
                        st.caption("⚠️ Make sure it matches exactly (no trailing slash, correct protocol)")
                        st.info("""
                        **Steps:**
                        1. Copy the URL above
                        2. Go to [Facebook App Settings](https://developers.facebook.com/apps/)
                        3. Settings → Basic → Valid OAuth Redirect URIs
                        4. Add the URL exactly as shown
                        5. Enable "Client OAuth Login" and "Web OAuth Login"
                        6. Save changes
                        """)
                        if not fb_app_secret:
                            st.warning("Facebook App secret is missing. The OAuth callback will fail until it is configured.")

                oauth_url = get_instagram_oauth_url(
                    app_id=fb_app_id,
                    redirect_uri=redirect_uri,
                    state=oauth_state,
                )

                st.link_button("🔗 Connect Instagram", oauth_url, use_container_width=True)
            else:
                # Secrets missing - this should only happen in development
                # In production, secrets are always present server-side
                if developer_mode:
                    st.error("⚠️ Facebook App credentials not configured. Please add FACEBOOK_APP_ID and FACEBOOK_APP_SECRET to secrets.")
                # Don't show anything to end users if secrets are missing (shouldn't happen in production)
    
    with tab3:
        st.info("Preferences coming soon.")


# -------------------------------
# SEARCH COMPONENTS
# -------------------------------
def render_search_result_item(user: dict, current_u_id: str):
    """Render a single search result item in the dropdown."""
    # Use saved profile image if available, otherwise fall back to generated avatar
    profile_image_url = user.get("profile_image_url")
    if profile_image_url:
        avatar_url = profile_image_url
    else:
        avatar_url = f"https://api.dicebear.com/7.x/identicon/svg?seed={user.get('u_name', 'user')}"
    is_following_user = user.get("is_following", False)
    total_views = user.get("total_views", 0)
    bio = user.get("u_bio", "")
    
    # Determine meta text (bio or views)
    meta_text = bio if bio else f"{total_views:,} views" if total_views > 0 else "No metrics yet"
    if len(meta_text) > 60:
        meta_text = meta_text[:57] + "..."
    
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown(f"""
            <div class='search-result-item'>
                <img src='{avatar_url}' class='search-result-avatar' />
                <div class='search-result-content'>
                    <div class='search-result-name'>{sanitize_user_input(user.get('u_name', 'Unknown'))}</div>
                    <div class='search-result-meta'>{sanitize_user_input(meta_text) if meta_text else meta_text}</div>
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        button_label = "Unfollow" if is_following_user else "Follow"
        button_kind = "secondary" if is_following_user else "primary"
        if st.button(button_label, key=f"search_follow_{user['u_id']}", use_container_width=True):
            try:
                if is_following_user:
                    unfollow_user(supabase, current_u_id, user["u_id"])
                    st.success(f"Unfollowed {user.get('u_name', 'user')}")
                else:
                    follow_user(supabase, current_u_id, user["u_id"])
                    st.success(f"Following {user.get('u_name', 'user')}")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {str(e)}")


def render_search_dropdown(search_query: str, current_u_id: str):
    """Render search dropdown with results."""
    if not search_query or len(search_query.strip()) < 1:
        return
    
    users = search_users(supabase, search_query, current_u_id)
    
    if not users:
        st.markdown("""
            <div class='search-dropdown'>
                <div style='padding:16px;text-align:center;color:#666;'>No users found</div>
            </div>
        """, unsafe_allow_html=True)
        return
    
    # Render dropdown with results
    st.markdown('<div class="search-dropdown">', unsafe_allow_html=True)
    for user in users:
        render_search_result_item(user, current_u_id)
    st.markdown('</div>', unsafe_allow_html=True)


# -------------------------------
# TOP BAR (avatar + notifications + search)
# -------------------------------
def show_topbar():
    """Render top navigation bar with integrated search."""
    current_u_id = get_current_user_id()
    
    # Initialize search query in session state if not present
    if "search_query" not in st.session_state:
        st.session_state.search_query = ""
    
    # Topbar HTML with search integrated
    st.markdown("""
        <div class='topnav'>
          <div class='brand'>Credify</div>
          <div class='actions'>
            <span>💬</span>
            <span>🔔</span>
            <span class='avatar'></span>
          </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Search container positioned below topbar (in fixed wrapper)
    if current_u_id:
        st.markdown('<div class="search-wrapper">', unsafe_allow_html=True)
        st.markdown('<div class="search-container">', unsafe_allow_html=True)
        search_input = st.text_input(
            "Search users",
            value=st.session_state.search_query,
            key="topbar_search",
            placeholder="Search by name or email...",
            label_visibility="collapsed"
        )
        
        # Update session state on input change
        if search_input != st.session_state.search_query:
            st.session_state.search_query = search_input
        
        # Show dropdown if there's a query
        if st.session_state.search_query:
            render_search_dropdown(st.session_state.search_query, current_u_id)
        
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

# -------------------------------
# SIDEBAR NAVIGATION
# -------------------------------
with st.sidebar:
    st.markdown("<div class='sb-brand'>Credify</div>", unsafe_allow_html=True)
    page = st.radio("Navigate to:", ["Home", "Profile", "Analytics", "Notifications", "Settings"], index=1)
    st.divider()
    logout_button()

apply_theme()

# Render top bar with avatar and bell
show_topbar()

# -------------------------------
# PAGE ROUTING
# -------------------------------
override = st.session_state.get("page_override")
if override:
    page = override
    st.session_state["page_override"] = None

if page == "Home":
    show_home_page()
elif page == "Profile":
    show_profile()
elif page == "YouTube":
    show_youtube_overview()
elif page == "Instagram":
    show_instagram_overview()
elif page == "TikTok":
    show_tiktok_overview()
elif page == "Analytics":
    show_analytics_page()
elif page == "Notifications":
    show_notifications_page()
else:
    show_settings_page()
