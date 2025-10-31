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
    # 1. Check if explicitly set in secrets (highest priority)
    custom_redirect = st.secrets.get("OAUTH_REDIRECT_URL")
    if custom_redirect:
        return custom_redirect.rstrip("/")
    
    # 2. Check Streamlit Cloud environment variables
    # Streamlit Cloud may set various env vars - check for cloud hosting
    streamlit_url = os.getenv("STREAMLIT_SHARING_BASE_URL")
    if streamlit_url:
        return streamlit_url.rstrip("/")
    
    # 3. Check if we're on Streamlit Cloud by checking for streamlit.app domain
    # or check HOSTNAME/other cloud indicators
    hostname = os.getenv("HOSTNAME", "")
    if hostname and "streamlit.app" in hostname.lower():
        return f"https://{hostname}".rstrip("/")
    
    # 4. Check for explicit production URL in environment
    prod_url = os.getenv("PRODUCTION_URL") or os.getenv("BASE_URL")
    if prod_url:
        return prod_url.rstrip("/")
    
    # 5. Default: localhost for local development
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
    st.title("🔐 Credify Login")

    # Optional Demo Mode: allow local testing without real auth
    demo_mode_enabled = str(st.secrets.get("DEMO_MODE", "false")).lower() == "true"
    if demo_mode_enabled:
        if st.button("Continue as Demo User"):
            class _DemoUser:
                def __init__(self, email: str):
                    self.email = email

            demo_user = _DemoUser("demo_user@example.com")
            st.session_state["user"] = demo_user
            ensure_user_in_db(demo_user)
            st.success("✅ Running in Demo Mode as demo_user@example.com")
            st.rerun()

    # --- Handle OAuth redirect ---
    query_params = st.query_params
    if "code" in query_params:
        code = query_params["code"]
        try:
            # ✅ FIX: Supabase v2.22+ expects a dict, not a string
            res = supabase.auth.exchange_code_for_session({"auth_code": code})
            if res and hasattr(res, "user") and res.user:
                st.session_state["user"] = res.user
                ensure_user_in_db(res.user)
                st.success(f"✅ Logged in as {res.user.email}")
                st.rerun()
            else:
                st.error("❌ Failed to exchange session code.")
        except Exception as e:
            st.error(f"Error during OAuth session exchange: {e}")
        return

    # --- Google Sign-In Button ---
    if st.button("Continue with Google"):
        try:
            redirect_url = get_redirect_url()
            # Supabase OAuth with dynamic redirect URL
            # Try both snake_case and camelCase formats for compatibility
            try:
                res = supabase.auth.sign_in_with_oauth({
                    "provider": "google",
                    "options": {
                        "redirect_to": redirect_url
                    }
                })
            except (TypeError, KeyError, AttributeError):
                # Fallback: try camelCase format
                res = supabase.auth.sign_in_with_oauth({
                    "provider": "google",
                    "options": {
                        "redirectTo": redirect_url
                    }
                })
            st.markdown(f"[Click here to continue →]({res.url})")
        except Exception as e:
            st.error(f"Google Sign-in failed: {e}")

    st.markdown("---")
    st.subheader("Or use Email / Password")

    # ---- Email/Password ----
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Sign In"):
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

    with col2:
        if st.button("Sign Up"):
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
