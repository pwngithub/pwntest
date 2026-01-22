import streamlit as st
import requests
import json
from PIL import Image
from io import BytesIO
import urllib3
from datetime import datetime, timedelta

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(page_title="PRTG Bandwidth + DEBUG", layout="wide")

USER = st.secrets["prtg_username"]
PH   = st.secrets["prtg_passhash"]
BASE = "https://prtg.pioneerbroadband.net"

DIVISOR = 1000000       # ← change & reload to test different scalings
TOTAL_CAPACITY = 40000  # Mbps

# ────────────────────────────────────────────────
# Session state for period selector
if "period_key" not in st.session_state:
    st.session_state.period_key = f"period_{id(st.session_state)}"  # unique per run

period = st.selectbox(
    "Time Period",
    ["Live (2 hours)", "Last 48 hours", "Last 7 days", "Last 30 days", "Last 365 days"],
    index=1,
    key=st.session_state.period_key
)

graphid_map = {
    "Live (2 hours)": "0",
    "Last 48 hours":  "1",
    "Last 7 days":    "-7",
    "Last 30 days":   "2",
    "Last 365 days":  "3"
}
graphid = graphid_map[period]

# Time range calculation
delta_map = {
    "Live (2 hours)": timedelta(hours=2),
    "Last 48 hours":  timedelta(hours=48),
    "Last 7 days":    timedelta(days=7),
    "Last 30 days":   timedelta(days=30),
    "Last 365 days":  timedelta(days=365)
}
delta = delta_map[period]

now = datetime.now()
edate_str = now.strftime("%Y-%m-%d-%H-%M-%S")
sdate_str = (now - delta).strftime("%Y-%m-%d-%H-%M-%S")

# ────────────────────────────────────────────────
# DEBUG SECTION – show everything we can read from API
# ────────────────────────────────────────────────

with st.expander("🛠 DEBUG – Raw API Responses (click to expand)", expanded=True):

    st.subheader("1. Channels (table.json) – current sensor state")

    debug_sensor = st.selectbox("Pick sensor for detailed debug", list(SENSORS.values()), index=0, format_func=lambda x: [k for k,v in SENSORS.items() if v==x][0])

    if st.button("Fetch & Show Raw Channel Data", type="primary"):
        try:
            url = f"{BASE}/api/table.json"
            params = {
                "content": "channels",
                "id": debug_sensor,
                "columns": "objid,name,minimum_raw,maximum_raw,average_raw,lastvalue_raw",
                "username": USER,
                "passhash": PH
            }
            r = requests.get(url, params=params, verify=False, timeout=15)
            r.raise_for_status()
            data = r.json()

            st.success(f"Status: {r.status_code} – {len(data.get('channels', []))} channels found")

            # Show full JSON
            st.markdown("**Full raw JSON response:**")
            st.json(data)

            # Pretty table of channels
            if "channels" in data:
                st.markdown("**Channel breakdown:**")
                for ch in data["channels"]:
                    with st.container(border=True):
                        st.write(f"**{ch.get('name', '—')}** (objid: {ch.get('objid')})")
                        cols = st.columns(4)
                        cols[0].write("Min raw")
                        cols[0].code(ch.get("minimum_raw", "—"))
                        cols[1].write("Max raw")
                        cols[1].code(ch.get("maximum_raw", "—"))
                        cols[2].write("Avg raw")
                        cols[2].code(ch.get("average_raw", "—"))
                        cols[3].write("Last raw")
                        cols[3].code(ch.get("lastvalue_raw", "—"))

        except Exception as e:
            st.error(f"Channel fetch failed: {str(e)}")

    st.divider()

    st.subheader("2. Historic Data Sample (historicdata.json)")

    if st.button("Fetch & Show Historic Data Sample", type="primary"):
        try:
            params = {
                "id": debug_sensor,
                "sdate": sdate_str,
                "edate": edate_str,
                "avg": 300,  # 5 min – reasonable compromise
                "usecaption": 1,
                "username": USER,
                "passhash": PH
            }
            r = requests.get(f"{BASE}/api/historicdata.json", params=params, verify=False, timeout=30)
            r.raise_for_status()
            data = r.json()

            st.success(f"Status: {r.status_code} – {len(data.get('histdata', []))} intervals returned")

            st.markdown("**Full raw JSON response (truncated if large):**")
            st.json(data)

            if "histdata" in data and data["histdata"]:
                first = data["histdata"][0]
                st.markdown("**Keys in first data point:**")
                st.code(", ".join(sorted(first.keys())))

                st.markdown("**First row sample:**")
                for k, v in first.items():
                    st.write(f"**{k}**: {v}")

        except Exception as e:
            st.error(f"Historic fetch failed: {str(e)}")

# ────────────────────────────────────────────────
# SENSORS list (for reference)
SENSORS = {
    "Firstlight":          "12435",
    "NNINIX":              "12506",
    "Hurricane Electric": "12363",
    "Cogent":              "12340",
}

st.markdown("---")
st.title("PRTG Bandwidth Dashboard")
st.caption(f"{period} • {sdate_str} → {edate_str} • Graph ID: {graphid}")
st.caption(f"Current DIVISOR = {DIVISOR:,} – change at top if Mbps scale is wrong")

# ────────────────────────────────────────────────
# Your normal dashboard code can go below here...
# For now just showing debug – add your metrics when ready
# ────────────────────────────────────────────────

st.info("Use the debug expander above to see exactly what the API returns. "
        "Once we know the raw values and units, we can fix the 0.00 Mbps problem.")

# Example placeholder – replace with your logic after debug
st.subheader("Next steps after debug")
st.write("- Look at Raw max / lastvalue from channel data")
st.write("- Check if historicdata returns actual numbers in _raw fields")
st.write("- Tell me what raw numbers you see (e.g. 1234567890) and what Mbps you expect")
