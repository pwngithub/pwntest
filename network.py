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
    Auvik API token not found or empty.
    
    Fix:
    1. Go to your app on share.streamlit.io
    2. Click ⋮ → Settings → Secrets tab
    3. Add exactly this line (replace with your token):
    
    auvik_api_token = "your_full_token_here"
    
    4. Click Save
    5. Reboot the app (three dots → Reboot app)
    6. Refresh this page
    """)
    st.stop()

st.success("Auvik API token loaded successfully ✓")

# ────────────────────────────────────────────────
# Your correct Auvik region (from https://pioneerbbhq.us6.my.auvik.com)
# ────────────────────────────────────────────────

BASE_URL = "https://auvikapi.us6.my.auvik.com/api/v1"

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/json"
}

# ────────────────────────────────────────────────
# Helper function
# ────────────────────────────────────────────────

@st.cache_data(ttl=300)
def auvik_get(endpoint, params=None):
    try:
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        r = requests.get(url, headers=HEADERS, params=params, timeout=20)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError as e:
        st.error(f"HTTP Error {r.status_code}: {r.text[:500]}...")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Network/API request failed: {str(e)}\n\nURL: {url}")
        return None

# ────────────────────────────────────────────────
# Main UI
# ────────────────────────────────────────────────

st.title("Auvik API Explorer – Your Network Data")

st.caption(f"Using region: us6.my.auvik.com | Token loaded ✓")

# ── Organizations ────────────────────────────────────────────────────────────
st.header("1. Organizations")

if st.button("Load Organizations", key="load_orgs"):
    orgs = auvik_get("organization")
    if orgs and "data" in orgs:
        st.success(f"Found {len(orgs['data'])} organization(s)")
        for org in orgs["data"]:
            name = org["attributes"].get("name", "Unnamed")
            org_id = org["id"]
            with st.expander(f"{name} (ID: {org_id})"):
                st.json(org)
    elif orgs is None:
        st.warning("Request failed – likely invalid/expired token or permissions issue")
    else:
        st.warning("No organizations returned – check token scope")

# ── Devices ──────────────────────────────────────────────────────────────────
st.header("2. Devices")

if st.button("Load Devices", key="load_devices"):
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
        st.warning("Request failed – likely 401/403 auth issue")
    else:
        st.warning("No devices returned")

# ── Interfaces ───────────────────────────────────────────────────────────────
st.header("3. Interfaces (Ports)")

device_id_filter = st.text_input("Filter by Device ID (optional)", "")

if st.button("Load Interfaces", key="load_interfaces"):
    params = {"perPage": 100}
    if device_id_filter:
        params["deviceId"] = device_id_filter

    interfaces = auvik_get("interface", params)
    if interfaces and "data" in interfaces:
        df = pd.DataFrame([
            {
                "Interface ID": i["id"],
                "Name": i["attributes"].get("interfaceName", "N/A"),
                "Device": i["attributes"].get("deviceName", "N/A"),
                "Speed": i["attributes"].get("speed", "N/A"),
                "Status": i["attributes"].get("status", "N/A"),
                "MAC": i["attributes"].get("macAddress", "N/A")
            } for i in interfaces["data"]
        ])
        st.dataframe(df.head(50))
        st.success(f"Found {len(interfaces['data'])} interfaces")
    elif interfaces is None:
        st.warning("Request failed")
    else:
        st.warning("No interfaces returned")

# ── Traffic Stats Example ────────────────────────────────────────────────────
st.header("4. Example: Recent Traffic on an Interface")

interface_id = st.text_input("Enter Interface ID for 24h stats", "")

if interface_id and st.button("Get 24h Bandwidth Stats"):
    end = datetime.utcnow()
    start = end - timedelta(hours=24)

    params = {
        "from": start.isoformat() + "Z",
        "to": end.isoformat() + "Z",
        "interval": "5m"
    }

    stats = auvik_get(f"interface/statistics/{interface_id}", params)
    if stats and "data" in stats:
        st.success(f"Retrieved {len(stats['data'])} data points")
        st.json(stats["data"][:5])  # first 5 for preview

        # Simple cumulative bytes example (not rate – you need delta for real Mbps)
        max_in_bytes = max(p.get("inOctets", 0) for p in stats["data"])
        max_out_bytes = max(p.get("outOctets", 0) for p in stats["data"])
        st.metric("Max In Bytes (cumulative)", f"{max_in_bytes:,}")
        st.metric("Max Out Bytes (cumulative)", f"{max_out_bytes:,}")
        st.info("Note: These are total bytes counters. To get Mbps peaks, calculate delta bytes / delta time between points.")
    else:
        st.warning("No stats returned – check interface ID or permissions")

st.markdown("---")
st.caption("If you see real data above → we can add full bandwidth peak/min graphs, alerts, topology, etc. Let me know what you'd like next!")
