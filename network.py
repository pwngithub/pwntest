import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="PRTG Peaks – Fixed for Live Mode", layout="wide")

# Credentials
PRTG_USERNAME = st.secrets["prtg_username"]
PRTG_PASSHASH = st.secrets["prtg_passhash"]
PRTG_URL = "https://prtg.pioneerbroadband.net"

# Period selection
graph_period = st.selectbox(
    "Select Graph Period",
    ("Live (2 hours)", "Last 48 hours", "Last 30 days", "Last 365 days"),
    key="period_select"
)

period_to_graphid = {
    "Live (2 hours)": "0",
    "Last 48 hours": "1",
    "Last 30 days": "2",
    "Last 365 days": "3",
}
graphid = period_to_graphid[graph_period]

SENSORS = {
    "Firstlight": "12435",
    "NNINIX": "12506",
    "Hurricane Electric": "12363",
    "Cogent": "12340",
}

# Debug toggle
debug = st.checkbox("Show Debug (Raw API Response)")

def fetch_live_speed(sensor_id):
    """For Live mode: Pull real-time Mbps from channels via API."""
    url = f"{PRTG_URL}/api/table.json?content=channels&columns=name,lastvalue_raw&id={sensor_id}&username={PRTG_USERNAME}&passhash={PRTG_PASSHASH}"
    try:
        r = requests.get(url, verify=False, timeout=10)
        data = r.json()
        in_speed = out_speed = 0.0
        raw_channels = []
        for ch in data.get("channels", []):
            name = ch.get("name", "").strip()
            last_val = ch.get("lastvalue_raw", "0")
            raw_channels.append({"name": name, "lastvalue_raw": last_val})
            if "Traffic In (Speed)" in name:
                in_speed = round(float(last_val) / 1_000_000, 0)
            if "Traffic Out (Speed)" in name:
                out_speed = round(float(last_val) / 1_000_000, 0)
        
        if debug:
            st.write(f"**Debug for {sensor_id} (Live):** Channels: {raw_channels}")
        
        return int(in_speed), int(out_speed)
    except Exception as e:
        if debug:
            st.error(f"Live fetch error: {e}")
        return 0, 0

def fetch_historical_peaks(sensor_id):
    """For historical: Pull peaks from PNG metadata."""
    url = f"{PRTG_URL}/chart.png"
    params = {"id": sensor_id, "graphid": graphid, "width": 1200, "height": 600, "username": PRTG_USERNAME, "passhash": PRTG_PASSHASH}
    try:
        r = requests.get(url, params=params, verify=False, timeout=15)
        img = Image.open(BytesIO(r.content))
        info = img.info
        raw_max1 = info.get("max1", "0")
        raw_max2 = info.get("max2", "0")
        
        if debug:
            st.write(f"**Debug for {sensor_id} (Historical):** max1='{raw_max1}', max2='{raw_max2}'")
        
        i = int(float(raw_max1.replace(",", ""))) // 1_000_000
        o = int(float(raw_max2.replace(",", ""))) // 1_000_000
        return i, o
    except Exception as e:
        if debug:
            st.error(f"Historical fetch error: {e}")
        return 0, 0

st.title("Your Real PRTG Peaks Right Now")
st.caption(f"Period: **{graph_period}**")

total_in = total_out = 0
for name, sid in SENSORS.items():
    if graph_period == "Live (2 hours)":
        i, o = fetch_live_speed(sid)
    else:
        i, o = fetch_historical_peaks(sid)
    
    total_in += i
    total_out += o
    st.metric(name, f"{i:,} Mbps In • {o:,} Mbps Out")

st.success(f"**TOTAL → {total_in:,} Mbps In • {total_out:,} Mbps Out**")

# Summary chart
fig, ax = plt.subplots(figsize=(8, 5))
ax.bar(["Total In", "Total Out"], [total_in, total_out], color=["#00ff88", "#ff3366"], width=0.6)
ax.set_ylabel("Mbps")
ax.set_title(f"Combined Peaks ({graph_period})", fontweight="bold")
for idx, val in enumerate([total_in, total_out]):
    ax.text(idx, val * 1.02, f"{val:,}", ha="center", fontweight="bold", color="white")
st.pyplot(fig)
