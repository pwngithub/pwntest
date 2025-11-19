import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import urllib3
import matplotlib.pyplot as plt

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="PRTG — Working Peaks", layout="wide", page_icon="Chart")

# ====================== CREDENTIALS ======================
try:
    USER = st.secrets["prtg_username"]
    PH   = st.secrets["prtg_passhash"]
except:
    st.error("Add prtg_username and prtg_passhash to secrets.toml")
    st.stop()

BASE = "https://prtg.pioneerbroadband.net"

# ====================== PERIOD ======================
period = st.selectbox(
    "Time Period",
    ["Last 48 hours", "Last 7 days", "Last 30 days", "Last 365 days"],
    index=0,
    key="period"
)

graphid = {"Last 48 hours": "1", "Last 7 days": "-7", "Last 30 days": "2", "Last 365 days": "3"}[period]

SENSORS = {
    "Firstlight":          "12435",
    "NNINIX":              "12506",
    "Hurricane Electric":  "12363",
    "Cogent":              "12340",
}

# ====================== WORKING PEAK EXTRACTION (NO graphstyling) ======================
def get_peaks(sensor_id):
    url = f"{BASE}/chart.png"
    params = {
        "id": sensor_id,
        "graphid": graphid,
        "width": 800,
        "height": 400,
        "username": USER,
        "passhash": PH
    }
    try:
        r = requests.get(url, params=params, verify=False, timeout=15)
        img = Image.open(BytesIO(r.content))
        info = img.info

        # These keys are there when width/height > 1
        in_bits  = int(float(info.get("max1", "0").replace(",", "")))
        out_bits = int(float(info.get("max2", "0").replace(",", "")))

        return round(in_bits / 1_000_000), round(out_bits / 1_000_000)
    except:
        return 0, 0

# ====================== DISPLAY ======================
def show_sensor(name, sid):
    in_mbps, out_mbps = get_peaks(sid)

    st.subheader(name)
    c1, c2 = st.columns(2)
    c1.metric("Peak In",  f"{in_mbps:,} Mbps")
    c2.metric("Peak Out", f"{out_mbps:,} Mbps")

    gurl = f"{BASE}/chart.png?id={sid}&graphid={graphid}&width=1800&height=800&bgcolor=1e1e1e&fontcolor=ffffff"
    try:
        img_data = requests.get(gurl, params={"username": USER, "passhash": PH}, verify=False).content
        st.image(img_data, use_container_width=True)
    except:
        st.write("Graph not loaded")

    return in_mbps, out_mbps

# ====================== MAIN ======================
st.title("PRTG Peak Bandwidth — WORKS NOW")
st.caption(f"Period: {period}")

total_in = total_out = 0

for name, sid in SENSORS.items():
    i, o = show_sensor(name, sid)
    total_in  += i
    total_out += o

st.success(f"**TOTAL PEAK IN:  {total_in:,} Mbps**")
st.success(f"**TOTAL PEAK OUT: {total_out:,} Mbps**")

fig, ax = plt.subplots(figsize=(8,5))
ax.bar(["Total In", "Total Out"], [total_in, total_out], color=["#00ff88", "#ff3366"], width=0.6)
ax.set_ylabel("Mbps")
ax.set_title("Combined Peak", fontweight="bold", color="white")
ax.set_facecolor("#1e1e1e")
fig.patch.set_facecolor("#0e1117")
ax.tick_params(colors="white")
for i, v in enumerate([total_in, total_out]):
    ax.text(i, v*1.02, f"{v:,}", ha="center", fontweight="bold", color="white")
st.pyplot(fig)
