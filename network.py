import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import urllib3
import matplotlib.pyplot as plt

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="PRTG Peak Bandwidth", layout="wide", page_icon="Chart")

# ==================== CREDENTIALS ====================
try:
    user = st.secrets["prtg_username"]
    ph   = st.secrets["prtg_passhash"]
except:
    st.error("Please add prtg_username and prtg_passhash to secrets.toml")
    st.stop()

base = "https://prtg.pioneerbroadband.net"

# ==================== PERIOD ====================
period = st.selectbox(
    "Select Period",
    ["Live (2 hours)", "Last 48 hours", "Last 7 days", "Last 30 days", "Last 365 days"],
    index=1
)

graphid_map = {
    "Live (2 hours)": "0",
    "Last 48 hours":  "1",
    "Last 7 days":    "-7",
    "Last 30 days":   "2",
    "Last 365 days":  "3"
}
graphid = graphid_map[period]

# ==================== SENSORS ====================
SENSORS = {
    "Firstlight":          "12435",
    "NNINIX":              "12506",
    "Hurricane Electric":  "12363",
    "Cogent":              "12340",
}

# ==================== GET REAL PEAK VALUES FROM PNG METADATA ====================
def get_real_peaks(sensor_id: str):
    url = f"{base}/chart.png"
    params = {
        "id": sensor_id,
        "graphid": graphid,
        "width": 100,
        "height": 100,
        "username": user,
        "passhash": ph
    }
    try:
        r = requests.get(url, params=params, verify=False, timeout=15)
        r.raise_for_status()
        img = Image.open(BytesIO(r.content))
        info = img.info

        in_bits  = float(info.get("max1", "0").replace(",", ""))
        out_bits = float(info.get("max2", "0").replace(",", ""))

        in_mbps  = round(in_bits  / 1_000_000, 1)
        out_mbps = round(out_bits / 1_000_000, 1)

        return in_mbps, out_mbps
    except Exception as e:
        st.error(f"Failed to get peaks for {sensor_id}: {e}")
        return 0.0, 0.0

# ==================== DISPLAY ONE SENSOR ====================
def show_sensor(name, sid):
    in_peak, out_peak = get_real_peaks(sid)

    st.subheader(name)
    c1, c2 = st.columns(2)
    c1.metric("Peak In",  f"{in_peak:,.0f} Mbps")
    c2.metric("Peak Out", f"{out_peak:,.0f} Mbps")

    # Full-size graph
    gurl = f"{base}/chart.png"
    gparams = {
        "id": sid,
        "graphid": graphid,
        "width": 1800,
        "height": 800,
        "bgcolor": "1e1e1e",
        "fontcolor": "ffffff",
        "username": user,
        "passhash": ph
    }
    try:
        img_data = requests.get(gurl, params=gparams, verify=False, timeout=20).content
        st.image(img_data, use_container_width=True)
    except:
        st.warning("Graph could not be loaded")

    st.markdown("---")
    return in_peak, out_peak

# ==================== MAIN ====================
st.title("PRTG Real Peak Bandwidth Dashboard")
st.caption(f"Period: **{period}**")

total_in = total_out = 0.0

for i in range(0, len(SENSORS), 2):
    cols = st.columns(2)
    pair = list(SENSORS.items())[i:i+2]
    for col, (name, sid) in zip(cols, pair):
        with col:
            i_p, o_p = show_sensor(name, sid)
            total_in  += i_p
            total_out += o_p

# ==================== SUMMARY ====================
st.markdown("## Combined Across All Circuits")
a, b = st.columns(2)
a.metric("Total Peak In",  f"{total_in:,.0f} Mbps")
b.metric("Total Peak Out", f"{total_out:,.0f} Mbps")

# Bar chart
fig, ax = plt.subplots(figsize=(8, 5))
ax.bar(["Peak In", "Peak Out"], [total_in, total_out],
       color=["#00ff88", "#ff3366"], width=0.6)
ax.set_ylabel("Mbps")
ax.set_title("Total Peak Bandwidth", fontsize=16, fontweight="bold")
for i, v in enumerate([total_in, total_out]):
    ax.text(i, v * 1.02, f"{v:,.0f}", ha="center", fontweight="bold", fontsize=12)
st.pyplot(fig)
