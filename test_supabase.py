from supabase import Client, create_client
import streamlit as st

# Read secrets from .streamlit/secrets.toml
url = st.secrets.get("SUPABASE_URL")
key = st.secrets.get("SUPABASE_ANON_KEY")
if not url or not key:
    st.error("Missing Supabase credentials in .streamlit/secrets.toml")
    raise SystemExit(1)

# Create client
supabase = create_client(url, key)

# Test the connection by listing your tables
try:
    result = supabase.table("videos").select("*").limit(1).execute()
    st.write("✅ Supabase connection successful!")
    st.write("Example data:", result.data)
except Exception as e:
    st.error("❌ Supabase connection failed:")
    st.exception(e)
