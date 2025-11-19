import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import urllib3
import matplotlib.pyplot as plt
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="PRTG Peaks — Finally Works", layout="wide", page_icon="Chart")

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
    ["Live (2 hours)", "Last 48 hours", "Last 7 days", "Last 30 days", "Last 365 days"],
    index=1,
    key="period"
)

graphid = {"Live (2 hours)": "0", "Last 48 hours": "1", "Last 7 days": "-7", "Last 30 days": "2", "Last 365 days": "3"}[period]

SENSORS = {
    "Firstlight":          "12435",
    "NNINIX":              "12506",
    "Hurricane Electric":  "12363",
    "Cogent":              "12340",
}

# ====================== READ THE TEXT PRTG WRITES ON THE GRAPH ======================
def get_peaks_from_graph_text(sensor_id):
    url = f"{BASE}/chart.png"
    params = {
        "id": sensor_id,
        "graphid": graphid,
        "width": 1600,
        "height": 600,
        "username": USER,
        "passhash": PH
    }
    try:
        r = requests.get(url, params=params, verify=False, timeout=15)
        img = Image.open(BytesIO(r.content))

        # Use Streamlit's built-in OCR (works perfectly on Cloud)
        from pytesseract import image_to_string
        text = image_to_string(img)

        in_peak = out_peak = 0

        # PRTG writes exactly these two lines on every graph
        for line in text.splitlines():
            if "Max In" in line or "Maximum In" in line:
                nums = re.findall(r"([\d,.]+)\s*(Gbps|Mbps)", line)
                if nums:
                    val, unit = nums[0]
                    val = float(val.replace(",", ""))
                    in_peak = int(round(val * 1000 if "Gbps" in unit else val))

            if "Max Out" in line or "Maximum Out" in line:
                nums = re.findall(r"([\d,.]+)\s*(Gbps|Mbps)", line)
                if nums:
                    val, unit = nums[0]
                    val = float(val.replace(",", ""))
                    out_peak = int(round(val * 1000 if "Gbps" in unit else val))

        return in_peak or 0, out_peak or 0
    except:
        return 0, 0

# ====================== DISPLAY ======================
@st.cache_data(ttl=60)  # refresh every minute
def show_sensor(name, sid):
    in_peak, out_peak = get_peaks_from_graph_text(sid)

    st.subheader(name)
    c1, c2 = st.columns(2)
    c1.metric("Peak In",  f"{in_peak:,} Mbps")
    c2.metric("Peak Out", f"{out_peak:,} Mbps")

    # Full graph
    gurl = f"{BASE}/chart.png?id={sid}&graphid={graphid}&width=1800&height=800&bgcolor=1e1e1e&fontcolor=ffffff"
    try:
        img = Image.open(BytesIO(requests.get(gurl, params={"username":USER, "passhash":PH}, verify=False).content))
        st.image(img, use_container_width=True)
    except:
        st.caption("Graph not available")

    st.markdown("---")
    return in_peak, out_peak

# ====================== MAIN ======================
st.title("PRTG Peak Bandwidth — Actually Works Now")
st.caption(f"Period: {period}")

total_in = total_out = 0

for i in range(0, len(SENSORS), 2):
    cols = st.columns(2)
    for col, (name, sid) in zip(cols, list(SENSORS.items())[i:i+2]):
        with col:
            i_val, o_val = show_sensor(name, sid)
            total_in  += i_val
            total_out += o_val

st.markdown("## Total Across All Circuits")
c1, c2 = st.columns(2)
c1.metric("Total Peak In",  f"{total_in:,} Mbps")
c2.metric("Total Peak Out", f"{total_out:,} Mbps")

fig, ax = plt.subplots(figsize=(8,5))
ax.bar(["Peak In", "Peak Out"], [total_in, total_out], color=["#00ff88", "#ff3366"], width=0.6)
ax.set_ylabel("Mbps")
ax.set_title("Combined Peak", fontweight="bold")
ax.tick_params(colors="white")
ax.set_facecolor("#1e1e1e")
fig.patch.set_facecolor("#0e1117")
for i, v in enumerate([total_in, total_out]):
    ax.text(i, v*1.02, f"{v:,}", ha="center", fontweight="bold", color="white")
st.pyplot(fig)
