from supabase import Client, create_client
import streamlit as st
import os

# Read secrets from .streamlit/secrets.toml
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_ANON_KEY")

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
