import streamlit as st
from supabase import create_client, Client

# Initialize Supabase
SUPABASE_URL = st.secrets["supabase"]["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["supabase"]["SUPABASE_ANON_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

def show_login():
    st.title("🔐 Credify Login")

    # Google Login
    if st.button("Continue with Google"):
        res = supabase.auth.sign_in_with_oauth({"provider": "google"})
        st.markdown(f"[Click here to complete sign-in →]({res.url})")

    st.markdown("---")
    st.subheader("Or use Email / Password")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Sign In"):
            try:
                user = supabase.auth.sign_in_with_password(
                    {"email": email, "password": password}
                )
                st.session_state["user"] = user.user
                st.success(f"Welcome, {user.user.email}!")
                st.rerun()
            except Exception as e:
                st.error(f"Login failed: {e}")
    with col2:
        if st.button("Sign Up"):
            try:
                supabase.auth.sign_up({"email": email, "password": password})
                st.success("Account created! Check your email to confirm.")
            except Exception as e:
                st.error(f"Sign-up failed: {e}")

def logout_button():
    """Logout and clear session."""
    if st.button("Logout"):
        supabase.auth.sign_out()
        st.session_state.clear()
        st.rerun()
