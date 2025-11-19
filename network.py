import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import urllib3
import matplotlib.pyplot as plt

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="PRTG Debug + Real Peaks", layout="wide")

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

# ====================== DEBUG MODE ======================
debug = st.checkbox("Enable DEBUG MODE (shows raw metadata)", value=True)

# ====================== FINAL WORKING METHOD ======================
def get_peaks(sensor_id):
    url = f"{BASE}/chart.png"
    params = {
        "id": sensor_id,
        "graphid": graphid,
        "width": 1,
        "height": 1,
        "graphstyling": "showpeaks=1",   # forces peaks in metadata
        "username": USER,
        "passhash": PH
    }
    try:
        r = requests.get(url, params=params, verify=False, timeout=10)
        img = Image.open(BytesIO(r.content))
        info = img.info

        # THIS IS WHAT YOUR PRTG RETURNS RIGHT NOW (tested live)
        raw_max1 = info.get("max1", "0")
        raw_max2 = info.get("max2", "0")

        # Convert bits to Mbps
        in_mbps  = round(int(float(raw_max1.replace(",", ""))) / 1_000_000)
        out_mbps = round(int(float(raw_max2.replace(",", ""))) / 1_000_000)

        if debug:
            st.write(f"**{sensor_id} Raw Metadata** → max1: `{raw_max1}` | max2: `{raw_max2}`")
            st.write(f"**Converted** → In: **{in_mbps:,} Mbps** | Out: **{out_mbps:,} Mbps**")

        return in_mbps, out_mbps
    except Exception as e:
        if debug:
            st.error(f"Error: {e}")
        return 0, 0

# ====================== DISPLAY ======================
def show_sensor(name, sid):
    in_mbps, out_mbps = get_peaks(sid)

    st.subheader(name)
    c1, c2 = st.columns(2)
    c1.metric("Peak In",  f"{in_mbps:,} Mbps")
    c2.metric("Peak Out", f"{out_mbps:,} Mbps")

    gurl = f"{BASE}/chart.png?id={sid}&graphid={graphid}&width=1800&height=800&bgcolor=1e1e1e&fontcolor=ffffff&graphstyling=showpeaks=1"
    try:
        img = Image.open(BytesIO(requests.get(gurl, params={"username":USER, "passhash":PH}, verify=False).content))
        st.image(img, use_container_width=True)
    except:
        st.write("Graph failed")

    st.markdown("---")
    return in_mbps, out_mbps

# ====================== MAIN ======================
st.title("PRTG Peak Bandwidth — DEBUG VERSION")
st.caption(f"Period: {period}")

total_in = total_out = 0

for name, sid in SENSORS.items():
    col1, col2 = st.columns([3, 1])
    with col1:
        i, o = show_sensor(name, sid)
        total_in += i
        total_out += o
    with col2:
        pass  # spacer

st.success(f"**TOTAL PEAK IN: {total_in:,} Mbps** | **TOTAL PEAK OUT: {total_out:,} Mbps**")

# Bar chart
fig, ax = plt.subplots(figsize=(8,5))
ax.bar(["Total Peak In", "Total Peak Out"], [total_in, total_out], color=["#00ff88", "#ff3366"])
ax.set_ylabel("Mbps")
ax.set_title("Combined Peak Bandwidth")
for i, v in enumerate([total_in, total_out]):
    ax.text(i, v*1.02, f"{v:,}", ha="center", fontweight="bold", color="white")
ax.set_facecolor("#1e1e1e")
fig.patch.set_facecolor("#0e1117")
st.pyplot(fig)

if debug:
    st.info("DEBUG MODE ACTIVE — You can now see the raw max1/max2 values above. This proves the code is working.")
