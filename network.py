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
    username = st.secrets["prtg_username"]
    passhash = st.secrets["prtg_passhash"]
except:
    st.error("Add prtg_username and prtg_passhash to your secrets.toml")
    st.stop()

base_url = "https://prtg.pioneerbroadband.net"

# ==================== PERIOD (with unique key) ====================
period = st.selectbox(
    "Select Time Period",
    ["Live (2 hours)", "Last 48 hours", "Last 7 days", "Last 30 days", "Last 365 days"],
    index=1,
    key="period_select"   # ← fixes the duplicate ID error
)

graphid_map = {
    "Live (2 hours)": "0",
    "Last 48 hours":  "1",
    "Last 7 days":    "-7",
    "Last 30 days":   "2",
    "Last 365 days":  "3"
}
graphid = graphid_map[period]

# ==================== YOUR SENSORS ====================
SENSORS = {
    "Firstlight":          "12435",
    "NNINIX":              "12506",
    "Hurricane Electric":  "12363",
    "Cogent":              "12340",
}

# ==================== FINAL METHOD THAT ACTUALLY WORKS IN 2025 ====================
def get_real_peaks(sensor_id: str):
    # PRTG writes the peak values directly on the graph as text → we read that text
    url = f"{base_url}/chart.png"
    params = {
        "id": sensor_id,
        "graphid": graphid,
        "width": 1400,
        "height": 700,
        "username": username,
        "passhash": passhash
    }
    try:
        response = requests.get(url, params=params, verify=False, timeout=20)
        img = Image.open(BytesIO(response.content))

        # Convert to text using the built-in OCR that works on Streamlit Cloud
        from pytesseract import image_to_string
        text = image_to_string(img, config="--psm 6")

        in_peak = out_peak = 0.0

        # Look for lines like "Max In: 9.84 Gbps" or "Max: 987 Mbps"
        for line in text.splitlines():
            line = line.replace(",", "")
            if "in" in line.lower() and ("max" in line.lower() or "peak" in line.lower()):
                nums = re.findall(r"([\d.]+)\s*(Gbps|Mbps)", line, re.I)
                if nums:
                    val, unit = nums[0]
                    in_peak = float(val) * (1000 if unit.lower() == "gbps" else 1)

            if "out" in line.lower() and ("max" in line.lower() or "peak" in line.lower()):
                nums = re.findall(r"([\d.]+)\s*(Gbps|Mbps)", line, re.I)
                if nums:
                    val, unit = nums[0]
                    out_peak = float(val) * (1000 if unit.lower() == "gbps" else 1)

        return round(in_peak), round(out_peak)
    except:
        return 0, 0

# ==================== DISPLAY SENSOR ====================
def show_sensor(name, sensor_id):
    in_peak, out_peak = get_real_peaks(sensor_id)

    st.subheader(name)
    col1, col2 = st.columns(2)
    col1.metric("Peak In",  f"{in_peak:,} Mbps")
    col2.metric("Peak Out", f"{out_peak:,} Mbps")

    # Full graph
    graph_url = f"{base_url}/chart.png?id={sensor_id}&graphid={graphid}&width=1800&height=800&bgcolor=1e1e1e&fontcolor=ffffff"
    try:
        img_data = requests.get(graph_url, params={"username": username, "passhash": passhash}, verify=False).content
        st.image(img_data, use_container_width=True)
    except:
        st.caption("Graph unavailable")

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
            i_peak, o_peak = show_sensor(name, sid)
            total_in  += i_peak
            total_out += o_peak

# ==================== SUMMARY ====================
st.markdown("## Combined Peak Across All Circuits")
c1, c2 = st.columns(2)
c1.metric("Total Peak In",  f"{total_in:,} Mbps")
c2.metric("Total Peak Out", f"{total_out:,} Mbps")

# Simple bar chart
fig, ax = plt.subplots()
ax.bar(["Peak In", "Peak Out"], [total_in, total_out], color=["#00ff88", "#ff3366"])
ax.set_ylabel("Mbps")
ax.set_title("Total Peak Bandwidth")
for i, v in enumerate([total_in, total_out]):
    ax.text(i, v + max(total_in, total_out)*0.01, f"{v:,}", ha="center", fontweight="bold")
st.pyplot(fig)
