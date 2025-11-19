import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import urllib3
import matplotlib.pyplot as plt
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="PRTG Real Peaks", layout="wide", page_icon="Chart")

# ==================== CREDENTIALS ====================
try:
    USER = st.secrets["prtg_username"]
    PH   = st.secrets["prtg_passhash"]
except:
    st.error("Add prtg_username and prtg_passhash to secrets.toml")
    st.stop()

BASE = "https://prtg.pioneerbroadband.net"

# ==================== PERIOD (unique key - fixes the error you saw) ====================
period = st.selectbox(
    "Select Time Period",
    ["Live (2 hours)", "Last 48 hours", "Last 7 days", "Last 30 days", "Last 365 days"],
    index=1,
    key="main_period_select"
)

graphid = {
    "Live (2 hours)": "0",
    "Last 48 hours":  "1",
    "Last 7 days": "-7",
    "Last 30 days":   "2",
    "Last 365 days":  "3"
}[period]

SENSORS = {
    "Firstlight":         "12435",
    "NNINIX":             "12506",
    "Hurricane Electric": "12363",
    "Cogent":             "12340",
}

# ==================== THE ONLY METHOD THAT WORKS IN 2025 ====================
def get_peaks(sensor_id):
    url = f"{BASE}/api/getstatus.htm"
    params = {
        "id": sensor_id,
        "username": USER,
        "passhash": PH
    }
    try:
        r = requests.get(url, params=params, verify=False, timeout=10)
        text = r.text

        # Look for the exact lines PRTG returns
        in_match  = re.search(r'Last Maximum In.*?>([\d,.]+)\s*(Gbit/s|Mbit/s)', text, re.I)
        out_match = re.search(r'Last Maximum Out.*?>([\d,.]+)\s*(Gbit/s|Mbit/s)', text, re.I)

        in_peak = out_peak = 0
        if in_match:
            val = float(in_match.group(1).replace(",", ""))
            in_peak = val * 1000 if "gbit" in in_match.group(2).lower() else val
        if out_match:
            val = float(out_match.group(1).replace(",", ""))
            out_peak = val * 1000 if "gbit" in out_match.group(2).lower() else val

        return int(round(in_peak)), int(round(out_peak))
    except:
        return 0, 0

# ==================== DISPLAY SENSOR ====================
def show_sensor(name, sid):
    in_peak, out_peak = get_peaks(sid)

    st.subheader(name)
    c1, c2 = st.columns(2)
    c1.metric("Peak In",  f"{in_peak:,} Mbps")
    c2.metric("Peak Out", f"{out_peak:,} Mbps")

    # Full graph
    gurl = f"{BASE}/chart.png?id={sid}&graphid={graphid}&width=1800&height=800&bgcolor=1e1e1e&fontcolor=ffffff"
    try:
        img = Image.open(BytesIO(requests.get(gurl + f"&username={USER}&passhash={PH}", verify=False).content))
        st.image(img, use_container_width=True)
    except:
        st.caption("Graph not loaded")

    st.markdown("---")
    return in_peak, out_peak

# ==================== MAIN ====================
st.title("PRTG Real Peak Bandwidth Dashboard")
st.caption(f"Period: {period}")

total_in = total_out = 0

for i in range(0, len(SENSORS), 2):
    cols = st.columns(2)
    for col, (name, sid) in zip(cols, list(SENSORS.items())[i:i+2]):
        with col:
            ip, op = show_sensor(name, sid)
            total_in  += ip
            total_out += op

st.markdown("## Total Across All Circuits")
a, b = st.columns(2)
a.metric("Total Peak In",  f"{total_in:,} Mbps")
b.metric("Total Peak Out", f"{total_out:,} Mbps")

fig, ax = plt.subplots()
ax.bar(["Peak In", "Peak Out"], [total_in, total_out], color=["#00ff88", "#ff3366"])
ax.set_ylabel("Mbps")
ax.set_title("Combined Peak Bandwidth")
for i, v in enumerate([total_in, total_out]):
    ax.text(i, v*1.02, f"{v:,}", ha="center", fontweight="bold")
st.pyplot(fig)
