import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd

# ────────────────────────────────────────────────
# Auvik API Token (from Secrets)
# ────────────────────────────────────────────────

API_TOKEN = st.secrets.get("auvik_api_token")

if not API_TOKEN:
    st.error("""
    Auvik API token not found.
    
    Fix: Go to your app → Settings → Secrets tab
    Add exactly:
    
    auvik_api_token = "your_real_token_here"
    
    Save → Reboot app → refresh page
    """)
    st.stop()

st.success("API token loaded ✓")

# ────────────────────────────────────────────────
# IMPORTANT: Use YOUR correct regional base URL
# Check your Auvik dashboard URL (e.g. us1.my.auvik.com → auvikapi.us1.my.auvik.com)
# ────────────────────────────────────────────────

BASE_URL = "https://auvikapi.us1.my.auvik.com/api/v1"   # Change this to match your region!

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/json"
}

# ────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────

@st.cache_data(ttl=300)
def auvik_get(endpoint, params=None):
    try:
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API request failed: {str(e)}\n\n"
                 f"URL attempted: {url}\n"
                 f"Tip: Double-check BASE_URL matches your Auvik region (see dashboard URL).")
        return None

# ────────────────────────────────────────────────
# UI
# ────────────────────────────────────────────────

st.title("Auvik API Explorer")

st.info(f"Using base URL: {BASE_URL}\n\n"
        "If requests fail with DNS/name resolution → change BASE_URL to your region (e.g. us2, eu1...)")

# Load organizations
if st.button("Load Organizations"):
    orgs = auvik_get("organization")
    if orgs and "data" in orgs:
        st.success(f"Found {len(orgs['data'])} organizations")
        st.json(orgs)
    elif orgs is None:
        st.warning("Request failed – check BASE_URL and token")
    else:
        st.warning("No organizations returned")

# Load devices
if st.button("Load Devices"):
    devices = auvik_get("device")
    if devices and "data" in devices:
        df = pd.DataFrame([
            {
                "ID": d["id"],
                "Name": d["attributes"].get("deviceName", "N/A"),
                "Type": d["attributes"].get("deviceType", "N/A"),
                "Model": d["attributes"].get("model", "N/A"),
                "IP": d["attributes"].get("ipAddress", "N/A")
            } for d in devices["data"]
        ])
        st.dataframe(df)
        st.success(f"Found {len(devices['data'])} devices")
    elif devices is None:
        st.warning("Request failed – likely wrong BASE_URL or token issue")
    else:
        st.warning("No devices returned")

st.markdown("---")
st.caption("Once this works, we can add bandwidth stats, peaks, graphs, etc. Reply with what you see!")
