import streamlit as st
from supabase import create_client, Client
from urllib.parse import urlparse, parse_qs
import os

# -------------------------------
# HELPER FUNCTIONS (defined early to ensure they're always importable)
# -------------------------------
def is_localhost() -> bool:
    """Detect if running on localhost (HTTP) vs production (HTTPS).
    
    Checks multiple indicators in priority order:
    1. STREAMLIT_SHARING_BASE_URL is set (definitive production indicator - check FIRST)
    2. STREAMLIT_SERVER_PORT is set (strong localhost indicator)
    3. HOSTNAME contains localhost or 127.0.0.1
    4. Default to True if uncertain (safer for token-based auth)
    
    Returns:
        True if running on localhost, False if on production (Streamlit Cloud).
        Defaults to True if uncertain (safer for token-based auth).
    """
    # 1. Check STREAMLIT_SHARING_BASE_URL FIRST (most reliable production indicator)
    # This is ALWAYS set on Streamlit Cloud and NEVER set locally
    # Must check this first to avoid false positives from other env vars
    sharing_url = os.getenv("STREAMLIT_SHARING_BASE_URL", "").strip()
    if sharing_url:
        return False  # Definitely production (Streamlit Cloud)
    
    # 2. Check STREAMLIT_SERVER_PORT (strong localhost indicator)
    # This is set when running `streamlit run` locally
    server_port = os.getenv("STREAMLIT_SERVER_PORT")
    if server_port is not None:
        return True
    
    # 3. Check HOSTNAME for localhost indicators
    hostname = (os.getenv("HOSTNAME", "") or "").lower()
    if "localhost" in hostname or "127.0.0.1" in hostname:
        return True
    
    # 4. Default to localhost if uncertain (safer for token-based auth)
    # This handles cases where none of the indicators are present
    return True

# -------------------------------
# LOGIN BUTTON STYLING
# -------------------------------
LOGIN_BUTTON_STYLE = """
<style>
/* Unified styling for all login buttons - target both st.button and st.link_button */
.stButton > button,
a.stLinkButton,
.stLinkButton > a {
  background-color: #2E2E2E !important;
  color: #FFFFFF !important;
  border: 1px solid #2E2E2E !important;
  border-radius: 8px !important;
  font-weight: 600 !important;
  transition: all 0.2s ease !important;
}
.stButton > button:hover,
a.stLinkButton:hover,
.stLinkButton > a:hover {
  background-color: #3A3A3A !important;
  border-color: #3A3A3A !important;
}
</style>
"""

# -------------------------------
# SUPABASE CONNECTION (via Streamlit secrets)
# -------------------------------
SUPABASE_URL = st.secrets.get("SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Missing Supabase credentials. Please set SUPABASE_URL and SUPABASE_ANON_KEY in .streamlit/secrets.toml")
    st.stop()

# Create a single shared Supabase client instance
# Store in session state to persist across reruns during OAuth flow
if "supabase_client" not in st.session_state:
    st.session_state.supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = st.session_state.supabase_client

if "supabase_access_token" in st.session_state and "supabase_refresh_token" in st.session_state:
    try:
        # On localhost, always restore from tokens (cookies won't work on HTTP)
        # On production (HTTPS), check if session exists first, then restore if needed
        is_localhost_env = is_localhost()
        should_restore = False
        
        if is_localhost_env:
            # Localhost: Always restore from tokens since cookies don't persist
            should_restore = True
        else:
            # Production: Check if session exists first
            try:
                current_session = supabase.auth.get_session()
                if not current_session:
                    should_restore = True
            except Exception:
                # Session check failed - restore from tokens
                should_restore = True
        
        if should_restore:
            # Restore session from stored tokens
            try:
                supabase.auth.set_session({
                    "access_token": st.session_state["supabase_access_token"],
                    "refresh_token": st.session_state["supabase_refresh_token"]
                })
            except Exception as restore_error:
                # If restore fails, tokens might be expired - try to refresh
                try:
                    new_session = supabase.auth.refresh_session({
                        "refresh_token": st.session_state["supabase_refresh_token"]
                    })
                    if new_session:
                        # Extract and update stored tokens
                        if hasattr(new_session, "access_token"):
                            st.session_state["supabase_access_token"] = new_session.access_token
                        elif isinstance(new_session, dict):
                            st.session_state["supabase_access_token"] = new_session.get("access_token")
                        
                        if hasattr(new_session, "refresh_token"):
                            st.session_state["supabase_refresh_token"] = new_session.refresh_token
                        elif isinstance(new_session, dict):
                            st.session_state["supabase_refresh_token"] = new_session.get("refresh_token")
                except Exception:
                    # Refresh also failed - tokens are expired, clear them
                    if "supabase_access_token" in st.session_state:
                        del st.session_state["supabase_access_token"]
                    if "supabase_refresh_token" in st.session_state:
                        del st.session_state["supabase_refresh_token"]
    except Exception:
        # Session check/restore failed - try to restore anyway
        try:
            supabase.auth.set_session({
                "access_token": st.session_state["supabase_access_token"],
                "refresh_token": st.session_state["supabase_refresh_token"]
            })
        except Exception:
            # Restore failed - clear tokens
            if "supabase_access_token" in st.session_state:
                del st.session_state["supabase_access_token"]
            if "supabase_refresh_token" in st.session_state:
                del st.session_state["supabase_refresh_token"]

# Alias for backward compatibility (used in credify_app.py)
auth_supabase = supabase

# -------------------------------
# REDIRECT URL HELPER
# -------------------------------
def get_redirect_url() -> str:
    """Dynamically resolve the correct OAuth redirect URL based on environment.
    
    Checks configuration sources in this priority order:
    1. Localhost detection (if on localhost, always use localhost URL - highest priority for dev)
    2. OAUTH_REDIRECT_URL secret (explicit override for production)
    3. STREAMLIT_SHARING_BASE_URL environment variable (production indicator)
    4. Default to localhost if uncertain
    
    Returns:
        str: Redirect URL for OAuth callbacks
            - Localhost URL (http://localhost:{port}) if running locally (always wins)
            - Custom URL if OAUTH_REDIRECT_URL secret is set (production only)
            - Production URL if STREAMLIT_SHARING_BASE_URL is set
            - Defaults to http://localhost:8501 if uncertain
    """
    # 1. Check localhost first - localhost always wins during local development
    if is_localhost():
        port = os.getenv("STREAMLIT_SERVER_PORT", "8501")
        return f"http://localhost:{port}"
    
    # 2. Check explicit secret configuration (for production overrides)
    try:
        custom_redirect = st.secrets.get("OAUTH_REDIRECT_URL")
        if custom_redirect and str(custom_redirect).strip():
            return str(custom_redirect).strip().rstrip("/")
    except (AttributeError, KeyError):
        # Secret not found or not accessible - continue to other checks
        pass
    
    # 3. Check for Streamlit Cloud (production)
    sharing_url = os.getenv("STREAMLIT_SHARING_BASE_URL", "").strip()
    if sharing_url:
        return sharing_url.rstrip("/")
    
    # 4. Default to localhost (fallback)
    port = os.getenv("STREAMLIT_SERVER_PORT", "8501")
    return f"http://localhost:{port}"


# -------------------------------
# USER SYNC HELPER
# -------------------------------
def ensure_user_in_db(user):
    """Ensures a Supabase Auth user has a matching record in the users table."""
    try:
        user_email = user.email.lower()
        user_name = user.email.split("@")[0]

        existing = supabase.table("users").select("*").eq("u_email", user_email).execute()
        if not existing.data:
            supabase.table("users").insert({
                "u_email": user_email,
                "u_name": user_name,
                "u_bio": ""
            }).execute()
    except Exception as e:
        st.warning(f"⚠️ Could not sync user to database: {e}")


# -------------------------------
# LOGIN PAGE
# -------------------------------
def show_login():
    # Apply unified button styling
    st.markdown(LOGIN_BUTTON_STYLE, unsafe_allow_html=True)
    
    # Centered login header
    st.markdown("""
    <div style="display: flex; flex-direction: column; align-items: center; padding: 60px 20px 40px;">
        <h1 style="font-size: 40px; font-weight: 800; margin-bottom: 8px;">Welcome to Credify</h1>
    </div>
    """, unsafe_allow_html=True)

    # Optional Demo Mode: allow local testing without real auth
    demo_mode_enabled = str(st.secrets.get("DEMO_MODE", "false")).lower() == "true"
    if demo_mode_enabled:
        with st.container():
            st.markdown("<div style='display: flex; justify-content: center; margin-bottom: 20px;'>", unsafe_allow_html=True)
            if st.button("Continue as Demo User", use_container_width=True, key="demo_button"):
                # Clear any existing session state before setting demo user
                # This prevents issues when switching from real auth to demo
                if "user" in st.session_state:
                    # Clear user-specific cached data
                    keys_to_clear = [k for k in st.session_state.keys() if k.startswith("user_") or k.startswith("cached_")]
                    for key in keys_to_clear:
                        del st.session_state[key]
                if "session" in st.session_state:
                    del st.session_state["session"]
                # Sign out from Supabase if there's an active session
                try:
                    supabase.auth.sign_out()
                except Exception:
                    pass
                
                class _DemoUser:
                    def __init__(self, email: str):
                        self.email = email

                demo_user = _DemoUser("demo_user@example.com")
                st.session_state["user"] = demo_user
                ensure_user_in_db(demo_user)
                st.success("✅ Running in Demo Mode as demo_user@example.com")
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    # --- Handle OAuth redirect ---
    query_params = st.query_params
    if "code" in query_params or "error" in query_params:
        # Check for OAuth errors first
        if "error" in query_params:
            error_msg = query_params.get("error_description", query_params.get("error", "Unknown OAuth error"))
            st.error(f"OAuth error: {error_msg}")
            if st.secrets.get("DEBUG_REDIRECT", "false").lower() == "true":
                st.code(f"Query params: {dict(query_params)}")
            return
        
        # Handle successful OAuth callback
        code = query_params.get("code")
        if not code:
            st.error("No authorization code received from OAuth provider.")
            return
            
        try:
            # Get the current redirect URL to match what was sent
            redirect_url = get_redirect_url()
            debug_mode = st.secrets.get("DEBUG_REDIRECT", "false").lower() == "true"
            
            if debug_mode:
                st.info(f"🔍 Exchanging code for session...")
                st.caption(f"Redirect URL: {redirect_url}")
                st.caption(f"Code length: {len(code) if code else 0} chars")
            
            # Exchange code for session
            # Supabase v2.22+ expects a dict with auth_code
            exchange_params = {
                "auth_code": code
            }
            
            # Try the exchange
            res = None
            exchange_error = None
            
            try:
                res = supabase.auth.exchange_code_for_session(exchange_params)
                if debug_mode:
                    st.success(f"✅ Exchange call succeeded")
            except Exception as e1:
                exchange_error = e1
                # Some Supabase versions may need the redirect URL in the exchange call
                if debug_mode:
                    st.warning(f"⚠️ First exchange attempt failed: {e1}")
                
                # Try with redirect_to parameter
                try:
                    exchange_params["redirect_to"] = redirect_url
                    res = supabase.auth.exchange_code_for_session(exchange_params)
                    if debug_mode:
                        st.success(f"✅ Exchange succeeded with redirect_to")
                except Exception as e2:
                    if debug_mode:
                        st.error(f"❌ Second exchange attempt also failed: {e2}")
                    raise e2
            
            # Handle different response formats
            user = None
            session = None
            
            # Check various possible response structures
            if res:
                # Format 1: res.user (common in auth responses)
                if hasattr(res, "user") and res.user:
                    user = res.user
                    session = res
                    if debug_mode:
                        st.info(f"✅ Found user via res.user: {user.email if hasattr(user, 'email') else 'no email attr'}")
                
                # Format 2: res is a Session object with .user attribute
                elif hasattr(res, "session") and hasattr(res, "user"):
                    user = res.user
                    session = res.session
                    if debug_mode:
                        st.info(f"✅ Found user via res.session/res.user")
                
                # Format 3: Response is dict-like
                elif isinstance(res, dict):
                    user = res.get("user")
                    session = res.get("session")
                    if debug_mode:
                        st.info(f"✅ Found user in dict response")
                
                # Format 4: Check if res has session attribute with user
                elif hasattr(res, "session"):
                    sess = res.session
                    if hasattr(sess, "user"):
                        user = sess.user
                        session = sess
                    elif isinstance(sess, dict) and "user" in sess:
                        user = sess["user"]
                        session = sess
                
                # Format 5: Check for data attribute (some responses wrap in .data)
                if not user and hasattr(res, "data"):
                    data = res.data
                    if isinstance(data, dict):
                        user = data.get("user")
                        session = data.get("session")
                    elif hasattr(data, "user"):
                        user = data.user
                        session = getattr(data, "session", None)
                
                # Format 6: Direct Session object (user might be accessible differently)
                # After exchange_code_for_session, the client should have the session set
                # So we can call get_user() to retrieve the user
                if not user and hasattr(res, "access_token"):
                    # This might be a Session object - exchange_code_for_session sets session on client
                    if debug_mode:
                        st.info(f"🔍 Response appears to be a Session object, fetching user from client...")
                    try:
                        # Get current user from the session that was just set
                        user_response = supabase.auth.get_user()
                        if user_response:
                            # Handle different response formats from get_user()
                            if hasattr(user_response, "user"):
                                user = user_response.user
                            elif isinstance(user_response, dict) and "user" in user_response:
                                user = user_response["user"]
                            else:
                                user = user_response  # Might be the user object directly
                            session = res  # Use the session from exchange
                            if debug_mode:
                                st.success(f"✅ Retrieved user via get_user()")
                    except Exception as e3:
                        if debug_mode:
                            st.warning(f"⚠️ Could not fetch user from session: {e3}")
                
                # Format 7: Final fallback - if exchange succeeded but we don't have user yet,
                # try get_user() since the session should now be set on the client
                if not user:
                    if debug_mode:
                        st.info(f"🔍 Trying final fallback: get_user() after exchange...")
                    try:
                        user_response = supabase.auth.get_user()
                        if user_response:
                            if hasattr(user_response, "user"):
                                user = user_response.user
                            elif isinstance(user_response, dict) and "user" in user_response:
                                user = user_response["user"]
                            else:
                                user = user_response
                            session = res
                            if debug_mode:
                                st.success(f"✅ Retrieved user via get_user() fallback")
                    except Exception as e4:
                        if debug_mode:
                            st.warning(f"⚠️ Final fallback also failed: {e4}")
            
            if user:
                # Clear any previous user session state before setting new one
                # This prevents desynchronization when switching users
                if "user" in st.session_state:
                    # If switching from DemoUser to real user, clear all related state
                    old_user_email = getattr(st.session_state.get("user"), "email", None)
                    if old_user_email and old_user_email != user.email:
                        # Clear user-specific session state when switching users
                        keys_to_clear = [k for k in st.session_state.keys() if k.startswith("user_") or k.startswith("cached_")]
                        for key in keys_to_clear:
                            del st.session_state[key]
                
                st.session_state["user"] = user
                
                # Extract and store session tokens explicitly for persistence
                # This ensures the session persists across Streamlit reruns
                access_token = None
                refresh_token = None
                
                if session:
                    st.session_state["session"] = session
                    # Extract tokens from session object
                    if hasattr(session, "access_token"):
                        access_token = session.access_token
                    elif hasattr(session, "access_token") and isinstance(session, dict):
                        access_token = session.get("access_token")
                    elif isinstance(session, dict):
                        access_token = session.get("access_token")
                    
                    if hasattr(session, "refresh_token"):
                        refresh_token = session.refresh_token
                    elif isinstance(session, dict):
                        refresh_token = session.get("refresh_token")
                
                # Also try to extract from res if session tokens not found
                if not access_token and res:
                    if hasattr(res, "access_token"):
                        access_token = res.access_token
                    elif isinstance(res, dict):
                        access_token = res.get("access_token")
                
                if not refresh_token and res:
                    if hasattr(res, "refresh_token"):
                        refresh_token = res.refresh_token
                    elif isinstance(res, dict):
                        refresh_token = res.get("refresh_token")
                
                # Store tokens in session state for persistence
                if access_token:
                    st.session_state["supabase_access_token"] = access_token
                if refresh_token:
                    st.session_state["supabase_refresh_token"] = refresh_token
                
                # Explicitly set session on Supabase client to ensure it's active
                if access_token and refresh_token:
                    try:
                        # Set the session on the client explicitly
                        supabase.auth.set_session({
                            "access_token": access_token,
                            "refresh_token": refresh_token
                        })
                        if debug_mode:
                            st.success("✅ Session tokens set on Supabase client")
                    except Exception as e:
                        if debug_mode:
                            st.warning(f"⚠️ Could not set session on client: {e}")
                        # Continue anyway - the client might already have the session
                
                # Set flag to skip session validation on next rerun
                # This prevents race condition where validation runs before Supabase session is fully established
                st.session_state["oauth_just_completed"] = True
                
                ensure_user_in_db(user)
                st.success(f"✅ Logged in as {user.email}")
                
                # Clear OAuth query params to prevent re-processing
                st.query_params.clear()
                st.rerun()
            else:
                # Detailed error reporting
                error_details = []
                if not res:
                    error_details.append("Response is None")
                else:
                    error_details.append(f"Response type: {type(res)}")
                    error_details.append(f"Response attributes: {dir(res)}")
                    if hasattr(res, "__dict__"):
                        error_details.append(f"Response dict keys: {list(res.__dict__.keys())}")
                
                st.error("❌ Failed to exchange session code - no user found in response.")
                if debug_mode:
                    st.error("Debug Details:")
                    for detail in error_details:
                        st.write(f"- {detail}")
                    st.code(f"Response object: {res}")
                    st.code(f"Response repr: {repr(res)}")
        except Exception as e:
            error_msg = str(e)
            # Check if it's a PKCE mismatch error or session expiration
            if "code challenge" in error_msg.lower() or "code verifier" in error_msg.lower() or "expired" in error_msg.lower() or "invalid" in error_msg.lower():
                # On localhost, this might be a false positive due to cookie issues
                # Check if we have stored tokens - if so, try to use them instead
                is_localhost_env = is_localhost()
                
                if is_localhost_env and "supabase_access_token" in st.session_state and "supabase_refresh_token" in st.session_state:
                    # On localhost with stored tokens, try to restore session instead of showing error
                    try:
                        supabase.auth.set_session({
                            "access_token": st.session_state["supabase_access_token"],
                            "refresh_token": st.session_state["supabase_refresh_token"]
                        })
                        # If restore succeeds, try to get user
                        user_response = supabase.auth.get_user()
                        if user_response:
                            user = None
                            if hasattr(user_response, "user"):
                                user = user_response.user
                            elif isinstance(user_response, dict) and "user" in user_response:
                                user = user_response["user"]
                            else:
                                user = user_response
                            
                            if user:
                                st.session_state["user"] = user
                                st.session_state["oauth_just_completed"] = True
                                ensure_user_in_db(user)
                                st.success(f"✅ Logged in as {user.email}")
                                st.query_params.clear()
                                st.rerun()
                                return
                    except Exception:
                        # Restore failed - fall through to error message
                        pass
                
                st.error("OAuth session expired or invalid. Please try logging in again.")
                # Clear ALL session state to prevent desynchronization
                st.query_params.clear()
                # Clear user session state
                if "user" in st.session_state:
                    del st.session_state["user"]
                if "session" in st.session_state:
                    del st.session_state["session"]
                # Clear stored tokens on error
                if "supabase_access_token" in st.session_state:
                    del st.session_state["supabase_access_token"]
                if "supabase_refresh_token" in st.session_state:
                    del st.session_state["supabase_refresh_token"]
                # Clear the client to force a fresh PKCE state
                if "supabase_client" in st.session_state:
                    del st.session_state.supabase_client
                # Recreate a fresh client
                st.session_state.supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
                if st.button("Try Again", key="retry_oauth"):
                    st.rerun()
            else:
                st.error(f"Error during OAuth session exchange: {error_msg}")
                # Also clear session state on other OAuth errors to prevent stale state
                if "user" in st.session_state:
                    del st.session_state["user"]
                if "session" in st.session_state:
                    del st.session_state["session"]
                if st.secrets.get("DEBUG_REDIRECT", "false").lower() == "true":
                    import traceback
                    st.error("Full error traceback:")
                    st.code(traceback.format_exc())
                    st.info(f"Code received: {code[:50] if code else 'None'}...")
                    st.info(f"Redirect URL used: {redirect_url}")
                    st.info(f"Supabase URL: {SUPABASE_URL}")
                    st.info(f"Supabase Key present: {'Yes' if SUPABASE_KEY else 'No'}")
        return

    # --- Google Sign-In Button --- (centered)
    # Generate OAuth URL on page load so we can use it with link_button for direct redirect
    try:
        # Check debug mode first to gate all debug output
        debug_mode = st.secrets.get("DEBUG_REDIRECT", "false").lower() == "true"
        
        # Get redirect URL (always needed, but debug output is gated)
        redirect_url = get_redirect_url()
        
        # Debug info only shown when DEBUG_REDIRECT is enabled
        if debug_mode:
            is_local = is_localhost()
            st.write("🔍 **Debug - is_localhost():**", is_local)
            st.write("🔍 **Debug - STREAMLIT_SERVER_PORT:**", os.getenv("STREAMLIT_SERVER_PORT"))
            st.write("🔍 **Debug - STREAMLIT_SHARING_BASE_URL:**", os.getenv("STREAMLIT_SHARING_BASE_URL"))
            st.write("🔍 **Debug - HOSTNAME:**", os.getenv("HOSTNAME"))
            st.write("🔍 **Debug - Redirect URL:**", redirect_url)
            st.write("🔍 **Debug - OAUTH_REDIRECT_URL secret:**", st.secrets.get("OAUTH_REDIRECT_URL", "NOT SET"))
            st.info(f"🔍 Preparing OAuth with redirect URL: {redirect_url}")
            st.caption(f"Redirect URL that will be sent to Supabase: {redirect_url}")
        
        # Supabase OAuth with dynamic redirect URL
        res = None
        last_error = None
        
        # Format 1: redirect_to as top-level parameter (most likely correct format)
        try:
            res = supabase.auth.sign_in_with_oauth({
                "provider": "google",
                "redirect_to": redirect_url
            })
            if debug_mode:
                st.success(f"✅ OAuth URL generated using redirect_to (top level)")
        except (TypeError, KeyError, AttributeError, Exception) as e1:
            last_error = e1
            # Format 2: redirect_to in options (snake_case) - some versions use this
            try:
                res = supabase.auth.sign_in_with_oauth({
                    "provider": "google",
                    "options": {
                        "redirect_to": redirect_url
                    }
                })
                if debug_mode:
                    st.success(f"✅ OAuth URL generated using redirect_to (in options)")
            except (TypeError, KeyError, AttributeError, Exception) as e2:
                last_error = e2
                # Format 3: redirectTo in options (camelCase) - JS/TS style
                try:
                    res = supabase.auth.sign_in_with_oauth({
                        "provider": "google",
                        "options": {
                            "redirectTo": redirect_url
                        }
                    })
                    if debug_mode:
                        st.success(f"✅ OAuth URL generated using redirectTo (camelCase)")
                except (TypeError, KeyError, AttributeError, Exception) as e3:
                    last_error = e3
                    raise Exception(f"All redirect parameter formats failed. Last error: {e3}")
        
        if res and hasattr(res, "url"):
            oauth_url = res.url
            
            # Verify redirect URL in OAuth request (only shown in debug mode)
            if debug_mode:
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(oauth_url)
                params = parse_qs(parsed.query)
                redirect_param = params.get("redirect_to") or params.get("redirectTo")
                
                if redirect_param:
                    redirect_value = redirect_param[0] if isinstance(redirect_param, list) else redirect_param
                    st.success(f"✅ Redirect URL confirmed in OAuth request: {redirect_value}")
                else:
                    st.warning(f"⚠️ Warning: redirect_to not found in OAuth URL. Expected: {redirect_url}")
                
                st.info(f"🔍 Full OAuth URL (first 200 chars): {oauth_url[:200]}...")
                st.info(f"🔍 All OAuth URL params: {dict(params)}")
            
            # Use link_button for direct redirect (no intermediate click)
            st.markdown("<div style='display: flex; justify-content: center; margin-bottom: 20px;'>", unsafe_allow_html=True)
            st.link_button("Continue with Google", oauth_url, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            raise Exception("OAuth response missing URL")
            
    except Exception as e:
        st.error(f"Google Sign-in failed: {e}")
        if st.secrets.get("DEBUG_REDIRECT", "false").lower() == "true":
            import traceback
            st.error(f"Debug details: {str(e)}")
            st.code(traceback.format_exc())
            st.info(f"Attempted redirect URL: {redirect_url}")
            st.info(f"Secrets OAUTH_REDIRECT_URL: {st.secrets.get('OAUTH_REDIRECT_URL', 'NOT SET')}")

    # ---- Email/Password ----
    st.markdown("<br>", unsafe_allow_html=True)
    email_col1, email_col2, email_col3 = st.columns([1, 2, 1])
    with email_col2:
        st.markdown("<p style='text-align: center; color: #666; margin-bottom: 20px;'>Or use Email / Password</p>", unsafe_allow_html=True)
        with st.form("email_password_form", clear_on_submit=False):
            email = st.text_input("Email", key="email_input")
            password = st.text_input("Password", type="password", key="password_input")
            
            sign_cols = st.columns(2)
            with sign_cols[0]:
                sign_in_submitted = st.form_submit_button("Sign In", use_container_width=True)
            with sign_cols[1]:
                sign_up_submitted = st.form_submit_button("Sign Up", use_container_width=True)
        
        if sign_in_submitted:
            try:
                user = supabase.auth.sign_in_with_password(
                    {"email": email, "password": password}
                )
                if user and user.user:
                    st.session_state["user"] = user.user
                    ensure_user_in_db(user.user)
                    st.success(f"Welcome, {user.user.email}!")
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
            except Exception as e:
                st.error(f"Login failed: {e}")

        if sign_up_submitted:
            try:
                user = supabase.auth.sign_up(
                    {"email": email, "password": password}
                )
                st.success("✅ Account created! Check your email to verify.")
            except Exception as e:
                st.error(f"Sign-up failed: {e}")


# -------------------------------
# LOGOUT BUTTON
# -------------------------------
def logout_button():
    """Clears user session and logs out."""
    if st.button("Logout"):
        try:
            supabase.auth.sign_out()
        except Exception:
            pass
        # Clear all session state including stored tokens
        if "supabase_access_token" in st.session_state:
            del st.session_state["supabase_access_token"]
        if "supabase_refresh_token" in st.session_state:
            del st.session_state["supabase_refresh_token"]
        st.session_state.clear()
        st.rerun()
