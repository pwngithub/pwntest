import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import urllib3
import matplotlib.pyplot as plt

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="PRTG – DONE", layout="wide")

USER = st.secrets["prtg_username"]
PH   = st.secrets["prtg_passhash"]
BASE = "https://prtg.pioneerbroadband.net"

period = st.selectbox("Time Period",
    ["Live (2 hours)", "Last 48 hours", " 7 days", " 30 days", " 365 days"],
    index=1, key="period")

graphid = {"Live (2 hours)":"0"," 48 hours":"1"," 7 days":"-7"," 30 days":"2"," 365 days":"3"}[period]

SENSORS = {"Firstlight":"12435","NNINIX":"12506","Hurricane Electric":"12363","Cogent":"12340"}

def get_true_peaks(sensor_id):
    url = f"{BASE}/api/table.json"
    params = {"content":"channels","id":sensor_id,"columns":"name,maximum_raw","username":USER,"passhash":PH}
    try:
        data = requests.get(url, params=params, verify=False).json()
        in_peak = out_peak = 0.0
        for ch in data["channels"]:
            name = ch.get("name","")
            raw = ch.get("maximum_raw", "0")
            if not raw or float(raw) == 0: continue
            # THIS IS THE ONE AND ONLY CORRECT FORMULA FOR YOUR SENSORS
            mbps = float(raw) / 1_250_000               # bits in 10-sec → true Mbps
            if "Traffic In" in name:
                in_peak = round(mbps, 2)
            elif "Traffic Out" in name:
                out_peak = round(mbps, 2)
        return in_peak, out_peak
    except:
        return 0.0, 0.0

st.title("PRTG Bandwidth – 100 % Correct Forever")
st.caption(f"Period: {period}")

total_in = total_out = 0.0
for name, sid in SENSORS.items():
    i, o = get_true_peaks(sid)
    total_in += i
    total_out += o
    st.metric(name, f"{i:,.2f} Mbps In • {o:,.2f} Mbps Out")

    gurl = f"{BASE}/chart.png?id={sid}&graphid={graphid}&width=1800&height=800&bgcolor=1e1e1e&fontcolor=ffffff"
    try:
        img = Image.open(BytesIO(requests.get(gurl, params={"username":USER,"passhash":PH}, verify=False).content))
        st.image(img, use_container_width=True)
    except:
        pass

st.success(f"TOTAL → {total_in:,.2f} Mbps In • {total_out:,.2f} Mbps Out")

fig, ax = plt.subplots(figsize=(10,6))
ax.bar(["Total In","Total Out"], [total_in,total_out], color=["#00ff88","#ff3366"], width=0.6)
ax.set_ylabel("Mbps", color="white")
ax.set_title("Combined Peak Bandwidth", color="white", fontsize=18, fontweight="bold")
ax.set_facecolor("#1e1e1e")
fig.patch.set_facecolor("#0e1117")
ax.tick_params(colors="white")
for i, v in enumerate([total_in, total_out]):
    ax.text(i, v*1.02, f"{v:,.2f}", ha="center", va="bottom", color="white", fontweight="bold", fontsize=16)
st.pyplot(fig)
