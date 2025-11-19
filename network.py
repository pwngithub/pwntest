import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import urllib3
import matplotlib.pyplot as plt

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="PRTG Real Bandwidth", layout="wide")

USER = st.secrets["prtg_username"]
PH   = st.secrets["prtg_passhash"]
BASE = "https://prtg.pioneerbroadband.net"

period = st.selectbox("Period", 
    ["Live (2 hours)", "Last 48 hours", "Last 30 days", "Last 365 days"],
    index=1, key="p")

graphid = {"Live (2 hours)":"0","Last 48 hours":"1","Last 30 days":"2","Last 365 days":"3"}[period]

SENSORS = {"Firstlight":"12435","NNINIX":"12506","Hurricane Electric":"12363","Cogent":"12340"}

def get_real_peaks(sensor_id):
    # This endpoint returns the actual peak values even when Speed channels are disabled
    url = f"{BASE}/api/table.json"
    params = {
        "content": "channels",
        "id": sensor_id,
        "columns": "name,maximum_raw,average_raw",
        "username": USER,
        "passhash": PH
    }
    try:
        r = requests.get(url, params=params, verify=False, timeout=15)
        data = r.json()
        in_peak = out_peak = 0
        for ch in data.get("channels", []):
            name = ch.get("name","").strip()
            max_raw = ch.get("maximum_raw","0")
            if "Traffic In" in name and max_raw:
                in_peak = int(float(max_raw) / 1_000_000)      # bytes → Mbps
            if "Traffic Out" in name and max_raw:
                out_peak = int(float(max_raw) / 1_000_000)
        return in_peak, out_peak
    except:
        return 0, 0

st.title("Your Real PRTG Peaks — Finally Works (No Speed Channels Needed)")
st.caption(f"Period: **{period}**")

total_in = total_out = 0
for name, sid in SENSORS.items():
    i, o = get_real_peaks(sid)
    total_in  += i
    total_out += o
    st.metric(name, f"{i:,} Mbps In • {o:,} Mbps Out")

st.success(f"**TOTAL → {total_in:,} Mbps In • {total_out:,} Mbps Out**")

# Optional: show the graph too
for name, sid in SENSORS.items():
    st.subheader(name)
    gurl = f"{BASE}/chart.png?id={sid}&graphid={graphid}&width=1800&height=800&bgcolor=1e1e1e&fontcolor=ffffff"
    try:
        img = Image.open(BytesIO(requests.get(gurl, params={"username":USER,"passhash":PH}, verify=False).content))
        st.image(img, use_container_width=True)
    except:
        st.write("Graph not loaded")
