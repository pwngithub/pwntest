import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd

# ────────────────────────────────────────────────
# Load Auvik API token from Streamlit Secrets
# ────────────────────────────────────────────────

API_TOKEN = st.secrets.get("auvik_api_token")

if not API_TOKEN:
    st.error("""
    **Auvik API token not found.**
    
    Please set it in Streamlit Cloud:
    1. Go to your app on share.streamlit.io
    2. Click ⋮ → Settings → Secrets tab
    3. Paste exactly:
    
    auvik_api_token = "your_real_token_here"
    
    4. Save and reboot the app (or wait 10–30 seconds).
    
    After this, refresh the page — the error should disappear.
    """)
    st.stop()

st.success("Auvik API token loaded successfully ✓")

# ────────────────────────────────────────────────
# Configuration
# ────────────────────────────────────────────────

BASE_URL = "https://auvikapi.com/api/v1"   # US region
# BASE_URL = "https://eu.auvikapi.com/api/v1"   # EU region – change if needed

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
        st.error(f"HTTP {r.status_code}: {r.text[:300]}...")
        return None
    except Exception as e:
        st.error(f"Request failed: {str(e)}")
        return None

def get_organizations():
    data = auvik_get("organization")
    return data.get("data", []) if data else []

def get_devices(org_id=None):
    params = {"organizationId": org_id} if org_id else None
    data = auvik_get("device", params)
    return data.get("data", []) if data else []

def get_interfaces(device_id=None):
    params = {"deviceId": device_id} if device_id else {}
    params["perPage"] = 100
    data = auvik_get("interface", params)
    return data.get("data", []) if data else []

def get_interface_stats(interface_id, hours_back=24):
    end = datetime.utcnow()
    start = end - timedelta(hours=hours_back)
    
    params = {
        "from": start.isoformat() + "Z",
        "to": end.isoformat() + "Z",
        "interval": "5m"
    }
    
    data = auvik_get(f"interface/statistics/{interface_id}", params)
    return data.get("data", []) if data else []

# ────────────────────────────────────────────────
# Streamlit UI
# ────────────────────────────────────────────────

st.title("Auvik API Explorer – What Data Can I Pull?")

# ── Organizations ────────────────────────────────────────────────────────────
st.header("1. Your Organizations")

if st.button("Load Organizations"):
    orgs = get_organizations()
    if orgs:
        st.success(f"Found {len(orgs)} organization(s)")
        for org in orgs:
            with st.expander(f"{org['attributes'].get('name', 'Unnamed')} (ID: {org['id']})"):
                st.json(org)
    else:
        st.warning("No organizations returned – check token or region")

# ── Devices ──────────────────────────────────────────────────────────────────
st.header("2. Devices")

orgs = get_organizations()
org_options = [("", "All Organizations")] + [(o["id"], o["attributes"].get("name", "Unnamed")) for o in orgs]

selected_org = st.selectbox("Filter by Organization", org_options, format_func=lambda x: x[1])
selected_org_id = selected_org[0] if selected_org else None

if st.button("Load Devices"):
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
        st.warning("No devices found")

# ── Interfaces & Traffic ─────────────────────────────────────────────────────
st.header("3. Interfaces & Traffic Stats")

device_id = st.text_input("Device ID (optional – filter interfaces)", "")

if st.button("Load Interfaces"):
    interfaces = get_interfaces(device_id)
    if interfaces:
        df = pd.DataFrame([
            {
                "Interface ID": i["id"],
                "Name": i["attributes"].get("interfaceName"),
                "Device": i["attributes"].get("deviceName"),
                "Speed": i["attributes"].get("speed"),
                "Status": i["attributes"].get("status")
            } for i in interfaces
        ])
        st.dataframe(df)
        st.success(f"Found {len(interfaces)} interfaces")
    else:
        st.warning("No interfaces found")

# Quick traffic stats example
st.subheader("Quick 24h Traffic Stats Example")

interface_id = st.text_input("Enter Interface ID to see recent bandwidth", "")

if interface_id and st.button("Get 24h Stats"):
    stats = get_interface_stats(interface_id, hours_back=24)
    if stats:
        st.success(f"Retrieved {len(stats)} data points (5-min intervals)")
        st.json(stats[:5])  # first 5 points for preview
        
        # Simple peak calculation (example – in reality you'd diff bytes)
        max_in = max(p.get("inOctets", 0) for p in stats)
        max_out = max(p.get("outOctets", 0) for p in stats)
        st.metric("Max In Octets (cumulative)", f"{max_in:,}")
        st.metric("Max Out Octets (cumulative)", f"{max_out:,}")
        st.info("Note: These are cumulative counters. To get real Mbps, calculate delta bytes / delta time.")
    else:
        st.warning("No stats returned – check interface ID")

st.markdown("---")
st.caption("Next steps: bandwidth graphs, peak/min calculations, alerts, topology... let me know what you'd like to add!")
