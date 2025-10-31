import streamlit as st
from supabase import create_client, Client
from urllib.parse import urlparse, parse_qs
import os

# -------------------------------
# SUPABASE CONNECTION (via Streamlit secrets)
# -------------------------------
SUPABASE_URL = st.secrets.get("SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Missing Supabase credentials. Please set SUPABASE_URL and SUPABASE_ANON_KEY in .streamlit/secrets.toml")
    st.stop()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# -------------------------------
# REDIRECT URL HELPER
# -------------------------------
def get_redirect_url() -> str:
    """Dynamically determines the OAuth redirect URL based on the environment.
    
    Returns:
        The redirect URL for OAuth callbacks (production URL or localhost)
    """
    debug_mode = str(st.secrets.get("DEBUG_REDIRECT", "false")).lower() == "true"
    detected_source = None
    
    # 1. Check if explicitly set in secrets (highest priority)
    # Set this in Streamlit Cloud secrets: OAUTH_REDIRECT_URL = "https://credify-belofupq9c9qxcbwlvfqpl.streamlit.app"
    try:
        # Try multiple ways to access the secret (handles different Streamlit versions)
        custom_redirect = None
        try:
            custom_redirect = st.secrets.get("OAUTH_REDIRECT_URL")
        except (AttributeError, KeyError):
            try:
                custom_redirect = st.secrets["OAUTH_REDIRECT_URL"]
            except (KeyError, AttributeError):
                pass
        
        if custom_redirect and str(custom_redirect).strip():
            custom_redirect = str(custom_redirect).strip().rstrip("/")
            if debug_mode:
                st.sidebar.success(f"✅ Redirect URL from secrets: {custom_redirect}")
            return custom_redirect
        elif debug_mode:
            st.sidebar.info("ℹ️ OAUTH_REDIRECT_URL not found in secrets")
    except Exception as e:
        if debug_mode:
            st.sidebar.warning(f"⚠️ Error reading OAUTH_REDIRECT_URL from secrets: {e}")
    
    # 2. Check Streamlit Cloud - try multiple env var patterns
    streamlit_url = (
        os.getenv("STREAMLIT_SHARING_BASE_URL") or 
        os.getenv("STREAMLIT_SERVER_URL") or
        os.getenv("STREAMLIT_SERVER") or
        os.getenv("STREAMLIT_CLOUD_BASE_URL")
    )
    if streamlit_url:
        detected_source = "environment variable"
        if debug_mode:
            st.sidebar.info(f"🔍 Redirect URL from env var: {streamlit_url}")
        return streamlit_url.rstrip("/")
    
    # 3. Check if we're on Streamlit Cloud by checking for streamlit.app domain
    hostname = os.getenv("HOSTNAME", "")
    if hostname and "streamlit.app" in hostname.lower():
        detected_source = "HOSTNAME env var"
        url = f"https://{hostname}".rstrip("/")
        if debug_mode:
            st.sidebar.info(f"🔍 Redirect URL from HOSTNAME: {url}")
        return url
    
    # 4. Check for explicit production URL in environment
    prod_url = os.getenv("PRODUCTION_URL") or os.getenv("BASE_URL")
    if prod_url:
        detected_source = "PRODUCTION_URL env var"
        if debug_mode:
            st.sidebar.info(f"🔍 Redirect URL from PRODUCTION_URL: {prod_url}")
        return prod_url.rstrip("/")
    
    # 5. Debug: Show what we found
    if debug_mode:
        st.sidebar.warning("🔍 Debug Info:")
        st.sidebar.write(f"- OAUTH_REDIRECT_URL in secrets: {custom_redirect}")
        st.sidebar.write(f"- STREAMLIT_SHARING_BASE_URL: {os.getenv('STREAMLIT_SHARING_BASE_URL')}")
        st.sidebar.write(f"- HOSTNAME: {hostname}")
        st.sidebar.write(f"- All env vars with 'STREAMLIT': {[k for k in os.environ.keys() if 'STREAMLIT' in k]}")
        st.sidebar.write(f"- Falling back to: localhost:8501")
    
    # 6. Default: localhost for local development
    return "http://localhost:8501"


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
            if st.button("Continue as Demo User", use_container_width=True):
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
                st.session_state["user"] = user
                # Store session if we have it
                if session:
                    st.session_state["session"] = session
                
                ensure_user_in_db(user)
                st.success(f"✅ Logged in as {user.email}")
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
            st.error(f"Error during OAuth session exchange: {error_msg}")
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
    st.markdown("<div style='display: flex; justify-content: center; margin-bottom: 20px;'>", unsafe_allow_html=True)
    if st.button("Continue with Google", use_container_width=True, key="google_auth"):
        try:
            redirect_url = get_redirect_url()
            debug_mode = st.secrets.get("DEBUG_REDIRECT", "false").lower() == "true"
            
            if debug_mode:
                st.info(f"🔍 Preparing OAuth with redirect URL: {redirect_url}")
                # Show the actual OAuth URL that will be generated
                st.caption(f"Redirect URL that will be sent to Supabase: {redirect_url}")
            
            # Supabase OAuth with dynamic redirect URL
            # Based on supabase-py documentation, redirect_to should be a top-level parameter
            # Try multiple formats to ensure compatibility across versions
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
                if debug_mode:
                    # Parse and show the redirect URL from the OAuth URL
                    from urllib.parse import urlparse, parse_qs
                    parsed = urlparse(oauth_url)
                    params = parse_qs(parsed.query)
                    redirect_param = params.get("redirect_to") or params.get("redirectTo")
                    st.info(f"🔍 OAuth URL contains redirect_to: {redirect_param}")
                    st.text(f"Full OAuth URL (first 200 chars): {oauth_url[:200]}...")
                
                st.markdown(f"[Click here to continue →]({oauth_url})")
            else:
                raise Exception("OAuth response missing URL")
                
        except Exception as e:
            st.error(f"Google Sign-in failed: {e}")
            # Show more details in debug mode
            if st.secrets.get("DEBUG_REDIRECT", "false").lower() == "true":
                import traceback
                st.error(f"Debug details: {str(e)}")
                st.code(traceback.format_exc())
                st.info(f"Attempted redirect URL: {redirect_url}")
                st.info(f"Secrets OAUTH_REDIRECT_URL: {st.secrets.get('OAUTH_REDIRECT_URL', 'NOT SET')}")
    st.markdown("</div>", unsafe_allow_html=True)

    # ---- Email/Password ----
    st.markdown("<br>", unsafe_allow_html=True)
    email_col1, email_col2, email_col3 = st.columns([1, 2, 1])
    with email_col2:
        st.markdown("<p style='text-align: center; color: #666; margin-bottom: 20px;'>Or use Email / Password</p>", unsafe_allow_html=True)
        email = st.text_input("Email", key="email_input")
        password = st.text_input("Password", type="password", key="password_input")
        
        sign_cols = st.columns(2)
        with sign_cols[0]:
            if st.button("Sign In", use_container_width=True, key="sign_in"):
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

        with sign_cols[1]:
            if st.button("Sign Up", use_container_width=True, key="sign_up"):
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
        st.session_state.clear()
        st.rerun()
