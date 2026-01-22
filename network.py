import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd

# ────────────────────────────────────────────────
# Auvik API Token (from Streamlit Secrets)
# ────────────────────────────────────────────────

API_TOKEN = st.secrets.get("auvik_api_token")

if not API_TOKEN:
    st.error("""
    **Auvik API token not found.**
    
    Go to your app → Settings → Secrets tab
    Add exactly:
    
    auvik_api_token = "your_real_token_here"
    
    Save → Reboot app → refresh page
    """)
    st.stop()

st.success("Auvik API token loaded ✓")

# ────────────────────────────────────────────────
# YOUR CORRECT REGIONAL BASE URL (from your dashboard)
# ────────────────────────────────────────────────

BASE_URL = "https://auvikapi.us6.my.auvik.com/api/v1"

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/json"
}

# ────────────────────────────────────────────────
# Helper
# ────────────────────────────────────────────────

@st.cache_data(ttl=300)
def auvik_get(endpoint, params=None):
    try:
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API request failed: {str(e)}\n\nURL: {url}\n\nTip: Check token, region, or network.")
        return None

# ────────────────────────────────────────────────
# UI
# ────────────────────────────────────────────────

st.title("Auvik API Explorer – Your Data")

st.info(f"Using your regional base: {BASE_URL}")

# Organizations
if st.button("Load My Organizations"):
    orgs = auvik_get("organization")
    if orgs and "data" in orgs:
        st.success(f"Found {len(orgs['data'])} organization(s)")
        for org in orgs["data"]:
            with st.expander(f"{org['attributes'].get('name', 'Unnamed')} (ID: {org['id']})"):
                st.json(org)
    elif orgs is None:
        st.warning("Request failed – check token or URL")
    else:
        st.warning("No organizations returned")

# Devices
if st.button("Load Devices"):
    devices = auvik_get("device")
    if devices and "data" in devices:
        df = pd.DataFrame([
            {
                "ID": d["id"],
                "Name": d["attributes"].get("deviceName", "N/A"),
                "Type": d["attributes"].get("deviceType", "N/A"),
                "Model": d["attributes"].get("model", "N/A"),
                "IP": d["attributes"].get("ipAddress", "N/A"),
                "Status": d["attributes"].get("status", "N/A")
            } for d in devices["data"]
        ])
        st.dataframe(df)
        st.success(f"Found {len(devices['data'])} devices")
    elif devices is None:
        st.warning("Request failed")
    else:
        st.warning("No devices returned")

st.caption("Once devices load, we can add bandwidth stats, peaks, graphs, alerts, etc. Reply with what you see!")
