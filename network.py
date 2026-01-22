import streamlit as st
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta
import pandas as pd

# ────────────────────────────────────────────────
# Load Auvik API creds from Streamlit Secrets
# ────────────────────────────────────────────────
API_USERNAME = st.secrets.get("auvik_api_username")
API_KEY = st.secrets.get("auvik_api_key")

if not API_USERNAME or not API_KEY:
    st.error("""
Auvik API credentials not found.

Add these to Streamlit Secrets:

auvik_api_username = "api-user@yourdomain.com"
auvik_api_key = "your_api_key_here"
""")
    st.stop()

st.success("Auvik API credentials loaded successfully ✓")

# Region host (from your app URL) + v1 base path
BASE_URL = "https://auvikapi.us6.my.auvik.com/v1"  # <-- note /v1

HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
}

AUTH = HTTPBasicAuth(API_USERNAME, API_KEY)

@st.cache_data(ttl=300)
def auvik_get(endpoint, params=None):
    url = f"{BASE_URL}/{endpoint.lstrip('/')}"
    try:
        r = requests.get(
            url,
            headers=HEADERS,
            auth=AUTH,
            params=params,
            timeout=20,
        )
        # Helpful error output for auth failures
        if r.status_code in (401, 403):
            return {"_error": True, "status": r.status_code, "text": r.text, "url": url}
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        return {"_error": True, "status": None, "text": str(e), "url": url}

st.title("Auvik API Explorer – Your Network Data")
st.caption("Using Basic Auth (username + api_key)")

# ────────────────────────────────────────────────
# 0. Verify credentials
# ────────────────────────────────────────────────
st.header("0. Verify Credentials")

if st.button("Verify Auvik API Login"):
    # Some docs call this endpoint without /v1; if this fails, we’ll show you.
    verify = auvik_get("authentication/verify")
    if verify.get("_error"):
        st.error(f"Verify failed ({verify.get('status')}): {verify.get('text')[:500]}")
        st.write("URL tried:", verify.get("url"))
        st.info("If this endpoint 404s, your region may expose verify at a different path, but 401/403 still means creds/permissions.")
    else:
        st.success("Credentials verified ✓")
        st.json(verify)

# ────────────────────────────────────────────────
# 1. Tenants / Organizations (Auvik commonly uses tenants)
# ────────────────────────────────────────────────
st.header("1. Tenants / Organizations")

if st.button("Load Tenants"):
    tenants = auvik_get("tenants")
    if tenants.get("_error"):
        st.error(f"Error ({tenants.get('status')}): {tenants.get('text')[:500]}")
        st.write("URL:", tenants.get("url"))
    else:
        st.json(tenants)

# ────────────────────────────────────────────────
# 2. Devices (example using the new base)
# ────────────────────────────────────────────────
st.header("2. Devices")

if st.button("Load Devices"):
    devices = auvik_get("inventory/device/info")
    if devices.get("_error"):
        st.error(f"Error ({devices.get('status')}): {devices.get('text')[:500]}")
        st.write("URL:", devices.get("url"))
    elif "data" in devices:
        df = pd.DataFrame([{
            "ID": d.get("id"),
            "Name": d.get("attributes", {}).get("deviceName", "N/A"),
            "Type": d.get("attributes", {}).get("deviceType", "N/A"),
            "Model": d.get("attributes", {}).get("model", "N/A"),
            "IP": d.get("attributes", {}).get("ipAddress", "N/A"),
            "Status": d.get("attributes", {}).get("status", "N/A"),
        } for d in devices["data"]])
        st.dataframe(df)
        st.success(f"Found {len(df)} devices")
    else:
        st.warning("Unexpected response format")
        st.json(devices)
