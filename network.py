import streamlit as st
import requests
from requests.auth import HTTPBasicAuth
import pandas as pd  # optional but common

st.set_page_config(page_title="Auvik Dashboard", layout="wide")

# ────────────────────────────────────────────────
# Secrets loader (supports BOTH Streamlit TOML styles)
# ────────────────────────────────────────────────
def load_auvik_creds():
    """
    Supports:
    A) Top-level:
       auvik_api_username = "..."
       auvik_api_key = "..."

    B) Section:
       [auvik]
       api_username = "..."
       api_key = "..."
    """
    username = ""
    api_key = ""

    # A) top-level
    if "auvik_api_username" in st.secrets:
        username = str(st.secrets.get("auvik_api_username", "")).strip()
    if "auvik_api_key" in st.secrets:
        api_key = str(st.secrets.get("auvik_api_key", "")).strip()

    # B) section
    if (not username or not api_key) and "auvik" in st.secrets:
        block = st.secrets.get("auvik", {})
        if isinstance(block, dict):
            username = username or str(block.get("api_username", "")).strip()
            api_key = api_key or str(block.get("api_key", "")).strip()

    return username, api_key


API_USERNAME, API_KEY = load_auvik_creds()

# ────────────────────────────────────────────────
# Sidebar: Safe Secrets Debug (does NOT expose key)
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
        st.write("API key prefix:", (API_KEY[:4] + "…") if len(API_KEY) >= 4 else "…")

# ────────────────────────────────────────────────
# Stop if missing creds
# ────────────────────────────────────────────────
if not API_USERNAME or not API_KEY:
    st.error("Auvik API credentials not found / not loaded by Streamlit Cloud.")
    st.markdown("""
### Streamlit Cloud Secrets (VALID TOML)

**Option A (top-level):**
```toml
auvik_api_username = "api-user@yourdomain.com"
auvik_api_key = "YOUR_AUVIK_API_KEY_HERE"
