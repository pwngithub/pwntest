import streamlit as st

st.set_page_config(page_title="Auvik Dashboard", layout="wide")

# This ALWAYS renders — if you don't see this, Streamlit isn't running app.py
st.title("Auvik Dashboard ✅")
st.caption("If you can see this, the app is running. Any errors will appear below.")

import requests
from requests.auth import HTTPBasicAuth

# ────────────────────────────────────────────────
# Secrets loader (supports BOTH TOML styles)
# ────────────────────────────────────────────────
def load_auvik_creds():
    username = ""
    api_key = ""

    # Option A: top-level
    if "auvik_api_username" in st.secrets:
        username = str(st.secrets.get("auvik_api_username", "")).strip()
    if "auvik_api_key" in st.secrets:
        api_key = str(st.secrets.get("auvik_api_key", "")).strip()

    # Option B: section
    if (not username or not api_key) and "auvik" in st.secrets:
        block = st.secrets.get("auvik", {})
        if isinstance(block, dict):
            username = username or str(block.get("api_username", "")).strip()
            api_key = api_key or str(block.get("api_key", "")).strip()

    return username, api_key


API_USERNAME, API_KEY = load_auvik_creds()

# ────────────────────────────────────────────────
# Sidebar Debug (safe)
# ────────────────────────────────────────────────
with st.sidebar:
    st.header("🔧 Debug")
    try:
        keys = list(st.secrets.keys())
    except Exception:
        keys = []
    st.write("Secrets keys found:", keys)
    st.write("Username loaded:", bool(API_USERNAME))
    st.write("API key loaded:", bool(API_KEY))
    if API_KEY:
        st.write("API key length:", len(API_KEY))
        st.write("API key prefix:", API_KEY[:4] + "…" if len(API_KEY) >= 4 else "…")

# ────────────────────────────────────────────────
# Stop if missing creds
# ────────────────────────────────────────────────
if not API_USERNAME or not API_KEY:
    st.error("Auvik API credentials not found / not loaded.")
    st.markdown("""
Paste this into Streamlit Cloud → Settings → Secrets:

```toml
auvik_api_username = "api-user@yourdomain.com"
auvik_api_key = "YOUR_AUVIK_API_KEY_HERE"
