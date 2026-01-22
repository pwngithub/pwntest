import streamlit as st
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta
import pandas as pd

st.set_page_config(page_title="Auvik API Explorer", layout="wide")

# ────────────────────────────────────────────────
# Secrets Loader (supports multiple TOML layouts)
# ────────────────────────────────────────────────

def load_auvik_creds():
    """
    Supports:
      Option A (top-level):
        auvik_api_username = "..."
        auvik_api_key = "..."

      Option B (section):
        [auvik]
        api_username = "..."
        api_key = "..."
    """
    username = None
    api_key = None

    # Option A: top-level keys
    if "auvik_api_username" in st.secrets:
        username = st.secrets.get("auvik_api_username")
    if "auvik_api_key" in st.secrets:
        api_key = st.secrets.get("auvik_api_key")

    # Option B: section keys
    if (not username or not api_key) and "auvik" in st.secrets:
        auvik_block = st.secrets.get("auvik", {})
        if isinstance(auvik_block, dict):
            username = username or auvik_block.get("api_username")
            api_key = api_key or auvik_block.get("api_key")

    # Final cleanup
    username = (username or "").strip()
    api_key = (api_key or "").strip()

    return username, api_key


API_USERNAME, API_KEY = load_auvik_creds()

# ────────────────────────────────────────────────
# Debug panel (safe; does not reveal key)
# ────────────────────────────────────────────────

with st.sidebar:
    st.header("🔧 Debug (Secrets)")
    keys = list(st.secrets.keys()) if hasattr(st, "secrets") else []
    st.write("Secrets keys found:", keys)

    st.write("Username loaded:", bool(API_USERNAME))
    st.write("API key loaded:", bool(API_KEY))
    if API_KEY:
        st.write("API key length:", len(API_KEY))
        st.write("API key starts with:", API_KEY[:4] + "…" if len(API_KEY) >= 4 else "…")
    st.caption("If keys list is empty, Streamlit Cloud is NOT loading your Secrets.")

# ────────────────────────────────────────────────
# Hard stop if missing secrets
# ────────────────────────────────────────────────

if not API_USERNAME or not API_KEY:
    st.error("Auvik API credentials not found / not loaded by Streamlit.")
    st.markdown("""
### Fix in Streamlit Cloud
Go to **App → Settings → Secrets** and paste **one** of these valid TOML formats:

**Option A (top-level keys):**
```toml
auvik_api_username = "api-user@yourdomain.com"
auvik_api_key = "YOUR_AUVIK_API_KEY_HERE"
