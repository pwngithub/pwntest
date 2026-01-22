# =============================================================================
# Auvik API Explorer – See what data you can pull
# Run locally or deploy to Streamlit Cloud
# =============================================================================

import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd

# ────────────────────────────────────────────────
# Configuration
# ────────────────────────────────────────────────

# === Put your Auvik API token here (or better – use Streamlit secrets) ===
# Recommended: go to app settings → Secrets tab and add:
# auvik_api_token = "your_token_here"
API_TOKEN = st.secrets.get("auvik_api_token") or "paste_your_token_here_for_testing"

BASE_URL = "https://auvikapi.com/api/v1"   # US region
# BASE_URL = "https://eu.auvikapi.com/api/v1"   # EU region – uncomment if needed

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/json"
}

# ────────────────────────────────────────────────
# Helper functions
# ────────────────────────────────────────────────

@st.cache_data(ttl=300)
def auvik_get(endpoint, params=None):
    """Generic GET request to Auvik API"""
    try:
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError as e:
        st.error(f"HTTP {r.status_code}: {r.text}")
        return None
    except Exception as e:
        st.error(f"Request failed: {str(e)}")
        return None

def get_organizations():
    """List all organizations you have access to"""
    data = auvik_get("organization")
    if data and "data" in data:
        return data["data"]
    return []

def get_devices(org_id=None):
    """List devices (optionally filter by organization)"""
    params = {"organizationId": org_id} if org_id else None
    data = auvik_get("device", params)
    if data and "data" in data:
        return data["data"]
    return []

def get_interfaces(device_id=None, page=1, per_page=100):
    """List interfaces (optionally for a specific device)"""
    params = {"page": page, "perPage": per_page}
    if device_id:
        params["deviceId"] = device_id
    data = auvik_get("interface", params)
    if data and "data" in data:
        return data["data"]
    return []

def get_interface_stats(interface_id, hours_back=24):
    """Get recent traffic stats for one interface"""
    end = datetime.utcnow()
    start = end - timedelta(hours=hours_back)
    
    params = {
        "from": start.isoformat() + "Z",
        "to": end.isoformat() + "Z",
        "interval": "5m"  # 5-minute buckets
    }
    
    data = auvik_get(f"interface/statistics/{interface_id}", params)
    if data and "data" in data:
        return data["data"]
    return []

# ────────────────────────────────────────────────
# Streamlit UI
# ────────────────────────────────────────────────

st.title("Auvik API Explorer – See What You Can Pull")

if not API_TOKEN or API_TOKEN == "paste_your_token_here_for_testing":
    st.error("Please set your Auvik API token in Streamlit Secrets or replace the placeholder.")
    st.stop()

st.success("API token found ✓")

# ── Organizations ────────────────────────────────────────────────────────────
st.header("1. Your Organizations")

orgs = get_organizations()

if orgs:
    st.write(f"Found {len(orgs)} organization(s)")
    for org in orgs:
        with st.expander(f"{org.get('attributes', {}).get('name', 'Unnamed')} (ID: {org['id']})"):
            st.json(org)
else:
    st.warning("No organizations returned – check token permissions")

# Let user pick one organization
if orgs:
    selected_org = st.selectbox(
        "Select organization to explore",
        options=[(o["id"], o.get("attributes", {}).get("name", "Unnamed")) for o in orgs],
        format_func=lambda x: x[1],
        key="org_selector"
    )
    selected_org_id = selected_org[0] if selected_org else None
else:
    selected_org_id = None

# ── Devices ──────────────────────────────────────────────────────────────────
st.header("2. Devices")

if st.button("Load Devices", key="load_devices"):
    devices = get_devices(selected_org_id)
    if devices:
        df = pd.DataFrame([
            {
                "ID": d["id"],
                "Name": d["attributes"].get("deviceName"),
                "Type": d["attributes"].get("deviceType"),
                "Model": d["attributes"].get("model"),
                "IP": d["attributes"].get("ipAddress"),
                "Status": d["attributes"].get("status")
            } for d in devices
        ])
        st.dataframe(df)
        st.success(f"Found {len(devices)} devices")
    else:
        st.warning("No devices found or API error")

# ── Interfaces ───────────────────────────────────────────────────────────────
st.header("3. Interfaces (with traffic potential)")

device_id = st.text_input("Enter Device ID to filter interfaces (optional)", "")

if st.button("Load Interfaces", key="load_interfaces"):
    interfaces = get_interfaces(device_id)
    if interfaces:
        df = pd.DataFrame([
            {
                "ID": i["id"],
                "Name": i["attributes"].get("interfaceName"),
                "Device": i["attributes"].get("deviceName"),
                "Speed": i["attributes"].get("speed"),
                "Status": i["attributes"].get("status"),
                "MAC": i["attributes"].get("macAddress")
            } for i in interfaces
        ])
        st.dataframe(df.head(50))  # limit display
        st.success(f"Found {len(interfaces)} interfaces")
    else:
        st.warning("No interfaces found")

# ── Traffic Stats Example ────────────────────────────────────────────────────
st.header("4. Recent Traffic Stats (example)")

interface_id = st.text_input("Enter Interface ID to see recent stats", "")

if interface_id and st.button("Get 24h Traffic Stats", key="load_stats"):
    stats = get_interface_stats(interface_id, hours_back=24)
    if stats:
        st.success(f"Got {len(stats)} data points")
        st.json(stats[:3])  # show first few
        st.info("Full data is a list of time buckets with inOctets/outOctets etc.")
    else:
        st.warning("No stats returned")

st.markdown("---")
st.caption("Tip: Use the IDs from above to explore more endpoints like /alert, /topology, /configuration...")
