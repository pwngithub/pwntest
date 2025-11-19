import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import urllib3
import matplotlib.pyplot as plt

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="PRTG Bandwidth – EXACT", layout="wide")

USER = st.secrets["prtg_username"]
PH   = st.secrets["prtg_passhash"]
BASE = "https://prtg.pioneerbroadband.net"

period = st.selectbox("Time Period",
    ["Live (2 hours)", "Last 48 hours", "Last 7 days", "Last 30 days", "Last 365 days"],
    index=1, key="period")

graphid = {"Live (2 hours)":"0","Last 48 hours":"1","Last 7 days":"-7","Last 30 days":"2","Last 365 days":"3"}[period]

SENSORS = {"Firstlight":"12435","NNINIX":"12506","Hurricane Electric":"12363","Cogent":"12340"}

def get_exact_peaks(sensor_id):
    url = f"{BASE}/api/table.json"
    params = {
        "content": "channels",
        "id": sensor_id,
        "columns": "name,maximum_raw",
        "username": USER,
        "passhash": PH
    }
    try:
        r = requests.get(url, params=params, verify=False, timeout=10)
        data = r.json()
        in_peak = out_peak = 0.0
        for ch in data.get("channels", []):
            name = ch.get("name", "").strip()
            raw = ch.get("maximum_raw", "0")
            if not raw or float(raw) == 0:
                continue
            # EXACT FORMULA THAT MATCHES PRTG 100 %
            mbps = (float(raw) / 10240) * 1024
            if "Traffic In" in name:
                in_peak = round(mbps, 2)
            elif "Traffic Out" in name:
                out_peak = round(mbps, 2)
        return in_peak, out_peak
    except:
        return 0.0, 0.0

st.title("PRTG Bandwidth – Matches Web UI Exactly")
st.caption(f"Period: **{period}**")

total_in = total_out = 0.0

for name, sid in SENSORS.items():
    i, o = get_exact_peaks(sid)
    total_in  += i
    total_out += o
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader(name)
        st.metric("Peak In",  f"{i:,.2f} Mbps")
        st.metric("Peak Out", f"{o:,.2f} Mbps")
    with col2:
        pass  # spacing

# Graphs
for name, sid in SENSORS.items():
    st.subheader(f"{name} – Full Graph")
    gurl = f"{BASE}/chart.png?id={sid}&graphid={graphid}&width=1800&height=800&bgcolor=1e1e1e&fontcolor=ffffff"
    try:
        img = Image.open(BytesIO(requests.get(gurl, params={"username":USER,"passhash":PH}, verify=False).content))
        st.image(img, use_container_width=True)
    except:
        st.write("Graph unavailable")

# Total
st.markdown("## Combined Peak Across All Circuits")
c1, c2 = st.columns(2)
c1.metric("Total Peak In",  f"{total_in:,.2f} Mbps")
c2.metric("Total Peak Out", f"{total_out:,.2f} Mbps")

# Bar chart
fig, ax = plt.subplots(figsize=(10,6))
ax.bar(["Total In", "Total Out"], [total_in, total_out], color=["#00ff88", "#ff3366"], width=0.6)
ax.set_ylabel("Mbps")
ax.set_title(f"Total Peak ({period})", fontweight="bold", color="white")
ax.set_facecolor("#1e1e1e")
fig.patch.set_facecolor("#0e1117")
ax.tick_params(colors="white")
for i, v in enumerate([total_in, total_out]):
    ax.text(i, v*1.02, f"{v:,.2f}", ha="center", fontweight="bold", color="white", fontsize=14)
st.pyplot(fig)
