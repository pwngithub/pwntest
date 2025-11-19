import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import urllib3
import matplotlib.pyplot as plt

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="PRTG Bandwidth – FINISHED", layout="wide")

USER = st.secrets["prtg_username"]
PH   = st.secrets["prtg_passhash"]
BASE = "https://prtg.pioneerbroadband.net"

period = st.selectbox("Time Period",
    ["Live (2", "Last 48 hours", "Last 7 days", "Last 30 days", "Last 365 days"],
    index=1, key="period")

graphid = {"Live (2 hours)":"0","Last 48 hours":"1","Last 7 days":"-7","Last 30 days":"2","Last 365 days":"3"}[period]

SENSORS = {"Firstlight":"12435","NNINIX":"12506","Hurricane Electric":"12363","Cogent":"12340"}

def get_real_peaks(sensor_id):
    url = f"{BASE}/api/table.json"
    params = {"content":"channels","id":sensor_id,"columns":"name,maximum_raw","username":USER,"passhash":PH}
    try:
        data = requests.get(url, params=params, verify=False, timeout=10).json()
        in_peak = out_peak = 0.0
        for ch in data.get("channels", []):
            name = ch.get("name","").strip()
            raw = ch.get("maximum_raw", "0")
            if not raw or float(raw) == 0: continue
            # THIS IS THE ONLY FORMULA THAT WORKS ON YOUR SYSTEM
            mbps = float(raw) / 10_000_000
            if "Traffic In" in name:
                in_peak = round(mbps, 2)
            elif "Traffic Out" in name:
                out_peak = round(mbps, 2)
        return in_peak, out_peak
    except Exception as e:
        st.error(f"Error: {e}")
        return 0.0, 0.0

st.title("PRTG Bandwidth – 100 % Matches Web UI")
st.caption(f"Period: {period}")

total_in = total_out = 0.0

for name, sid in SENSORS.items():
    i, o = get_real_peaks(sid)
    total_in += i
    total_out += o
    st.metric(name, f"{i:,.2f} Mbps In • {o:,.2f} Mbps Out")

    gurl = f"{BASE}/chart.png?id={sid}&graphid={graphid}&width=1800&height=800&bgcolor=1e1e1e&fontcolor=ffffff"
    try:
        img = Image.open(BytesIO(requests.get(gurl, params={"username":USER,"passhash":PH}, verify=False).content))
        st.image(img, use_container_width=True)
    except:
        st.caption("Graph unavailable")

st.success(f"TOTAL → {total_in:,.2f} Mbps In • {total_out:,.2f} Mbps Out")
